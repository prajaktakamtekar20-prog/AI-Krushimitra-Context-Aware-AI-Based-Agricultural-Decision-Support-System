import asyncio
import unittest
from unittest.mock import AsyncMock, patch

from routes import market


class MarketPriceCacheTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        market._price_cache.clear()
        for task in market._refresh_tasks.values():
            task.cancel()
        market._refresh_tasks.clear()

    async def asyncTearDown(self):
        tasks = list(market._refresh_tasks.values())
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        market._refresh_tasks.clear()
        market._price_cache.clear()

    @staticmethod
    def live_prices(modal_price=2500):
        return {
            "crop": "Tomato",
            "location": "Pune",
            "markets": [{
                "name": "Pune APMC (Market Yard)",
                "min_price": modal_price - 100,
                "max_price": modal_price + 100,
                "modal_price": modal_price,
                "arrival": 50,
                "date": "2026-10-21",
            }],
            "unit": "₹/Quintal",
            "data_source": "Live APMC data from data.gov.in / Agmarknet",
            "is_demo": False,
        }

    async def test_first_request_fetches_and_repeated_request_is_cached(self):
        with patch.object(
            market,
            "fetch_external_market_prices",
            new=AsyncMock(return_value=self.live_prices()),
        ) as fetch:
            first = await market.get_market_prices(
                crop="Tomato", district="Pune", market="Pune APMC (Market Yard)"
            )
            second = await market.get_market_prices(
                crop="tomato", district="pune", market="pune apmc (market yard)"
            )

        self.assertEqual(first["cache"]["status"], "miss")
        self.assertEqual(second["cache"]["status"], "hit")
        self.assertEqual(second["prices"][0]["modal_price"], 2500)
        self.assertEqual(fetch.await_count, 1)
        self.assertIn("last_updated", second["cache"])

    async def test_stale_request_returns_immediately_and_refreshes_in_background(self):
        refresh_started = asyncio.Event()
        allow_refresh = asyncio.Event()

        async def delayed_refresh(*_args):
            refresh_started.set()
            await allow_refresh.wait()
            return self.live_prices(2800)

        with patch.object(
            market,
            "fetch_external_market_prices",
            new=AsyncMock(return_value=self.live_prices()),
        ):
            await market.get_market_prices(
                crop="Tomato", district="Pune", market="Pune APMC (Market Yard)"
            )

        key = market._cache_key("Tomato", "Pune", "Pune APMC (Market Yard)")
        market._price_cache[key]["stored_at"] -= market._CACHE_TTL_SECONDS + 1
        with patch.object(market, "fetch_external_market_prices", new=delayed_refresh):
            stale = await asyncio.wait_for(
                market.get_market_prices(
                    crop="Tomato", district="Pune", market="Pune APMC (Market Yard)"
                ),
                timeout=0.1,
            )
            await asyncio.wait_for(refresh_started.wait(), timeout=0.1)
            self.assertTrue(stale["cache"]["stale"])
            self.assertEqual(stale["prices"][0]["modal_price"], 2500)
            allow_refresh.set()
            await asyncio.gather(*market._refresh_tasks.values())
            refreshed = await market.get_market_prices(
                crop="Tomato", district="Pune", market="Pune APMC (Market Yard)"
            )

        self.assertFalse(refreshed["cache"]["stale"])
        self.assertEqual(refreshed["prices"][0]["modal_price"], 2800)

    async def test_concurrent_identical_requests_share_one_external_call(self):
        release = asyncio.Event()
        calls = 0

        async def delayed_fetch(*_args):
            nonlocal calls
            calls += 1
            await release.wait()
            return self.live_prices()

        with patch.object(market, "fetch_external_market_prices", new=delayed_fetch):
            requests = [
                asyncio.create_task(market.get_market_prices(
                    crop="Tomato", district="Pune", market="Pune APMC (Market Yard)"
                ))
                for _ in range(2)
            ]
            await asyncio.sleep(0)
            release.set()
            responses = await asyncio.gather(*requests)

        self.assertEqual(calls, 1)
        self.assertEqual(responses[0]["prices"], responses[1]["prices"])

    async def test_slow_external_source_falls_back_after_total_timeout(self):
        async def slow_fetch(*_args):
            await asyncio.Event().wait()

        with (
            patch.object(market, "_EXTERNAL_FETCH_TIMEOUT_SECONDS", 0.01),
            patch.object(market, "fetch_external_market_prices", new=slow_fetch),
        ):
            result = await asyncio.wait_for(
                market.get_market_prices(crop="Tomato", district="Pune", market=None),
                timeout=0.2,
            )

        self.assertEqual(result["cache"]["status"], "miss")
        self.assertTrue(result["is_demo"])

    async def test_external_failure_keeps_last_live_cache(self):
        with patch.object(
            market,
            "fetch_external_market_prices",
            new=AsyncMock(return_value=self.live_prices()),
        ):
            first = await market.get_market_prices(
                crop="Tomato", district="Pune", market="Pune APMC (Market Yard)"
            )

        key = market._cache_key("Tomato", "Pune", "Pune APMC (Market Yard)")
        market._price_cache[key]["stored_at"] -= market._CACHE_TTL_SECONDS + 1
        with patch.object(
            market,
            "fetch_external_market_prices",
            new=AsyncMock(return_value=None),
        ):
            stale = await market.get_market_prices(
                crop="Tomato", district="Pune", market="Pune APMC (Market Yard)"
            )
            await asyncio.gather(*market._refresh_tasks.values())
            retained = await market.get_market_prices(
                crop="Tomato", district="Pune", market="Pune APMC (Market Yard)"
            )

        self.assertTrue(stale["cache"]["stale"])
        self.assertTrue(retained["cache"]["stale"])
        self.assertEqual(retained["prices"], first["prices"])
        self.assertFalse(retained["is_demo"])

    async def test_market_list_does_not_fetch_external_prices(self):
        with patch.object(market, "fetch_external_market_prices", new=AsyncMock()) as fetch:
            result = await market.get_markets(district="Pune")
        self.assertIn("Pune APMC (Market Yard)", result)
        fetch.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
