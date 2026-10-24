import React, { useState, useEffect, useRef } from 'react'
import { useLanguage } from '../context/LanguageContext'
import { useAuth } from '../context/AuthContext'
import { marketApi } from '../services/api'
import Background from '../components/Background'
import Navbar from '../components/Navbar'
import GlassCard from '../components/GlassCard'
import GradientButton from '../components/GradientButton'
import FormSelect from '../components/FormSelect'
import { getPlantVillageCropOptions, normalizePlantVillageCrop, translatePlantVillageCrop } from '../constants/crops'
import { localizeMarket } from '../translations/cropMarkets'

const DEFAULT_DISTRICTS = [
  'Pune', 'Nashik', 'Mumbai', 'Nagpur', 'Aurangabad', 'Ahmednagar',
  'Kolhapur', 'Sangli', 'Satara', 'Solapur', 'Ratnagiri', 'Sindhudurg'
]

const Market = () => {
  const { t, language, formatDate, formatNumber } = useLanguage()
  const { user } = useAuth()
  const [loading, setLoading] = useState(false)
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const [availableMarkets, setAvailableMarkets] = useState([])
  const [selectedMarket, setSelectedMarket] = useState('')
  const requestId = useRef(0)

  const userCrop = normalizePlantVillageCrop(user?.farming?.crop || user?.main_crop || user?.mainCrop || '')
  const userDistrict = user?.location?.district || user?.district || ''

  const [crop, setCrop] = useState(userCrop || 'Tomato')
  const [district, setDistrict] = useState(userDistrict || '')
  const [pendingCrop, setPendingCrop] = useState(userCrop || 'Tomato')
  const [pendingDistrict, setPendingDistrict] = useState(userDistrict || '')

  useEffect(() => {
    if (district) loadDistrictMarkets(district)
  }, [])

  useEffect(() => {
    if (!data?.cache?.stale || !selectedMarket) return undefined
    return marketApi.subscribeToMarketPrices(crop, district, selectedMarket, (updated) => {
      setData(updated)
      console.info('Background market price refresh displayed.')
    })
  }, [crop, data?.cache?.stale, district, selectedMarket])

  const loadDistrictMarkets = async (useDistrict) => {
    const currentRequestId = ++requestId.current
    setLoading(true)
    setError('')
    setAvailableMarkets([])
    setSelectedMarket('')
    setData(null)
    try {
      const markets = await marketApi.getMarkets(useDistrict)
      if (currentRequestId === requestId.current) {
        setAvailableMarkets(markets)
      }
    } catch (err) {
      if (currentRequestId === requestId.current) {
        console.error('Market prices error:', err)
        setError(t('common.error') || 'Failed to load market prices')
      }
    } finally {
      if (currentRequestId === requestId.current) setLoading(false)
    }
  }

  const fetchPrices = async (useCrop, useDistrict, useMarket) => {
    const currentRequestId = ++requestId.current
    setLoading(true)
    setError('')
    try {
      const requestStartedAt = performance.now()
      const result = await marketApi.getMarketPrices(useCrop, useDistrict, useMarket)
      if (currentRequestId === requestId.current) {
        setData(result)
        console.info(`Market prices displayed in ${(performance.now() - requestStartedAt).toFixed(1)} ms (${result?.cache?.status || 'network'})`)
      }
    } catch (err) {
      if (currentRequestId === requestId.current) {
        console.error('Market prices error:', err)
        setError(err.response?.data?.detail || t('common.error') || 'Failed to load market prices')
      }
    } finally {
      if (currentRequestId === requestId.current) setLoading(false)
    }
  }

  const handleDistrictChange = (event) => {
    const nextDistrict = event.target.value
    setPendingDistrict(nextDistrict)
    setDistrict(nextDistrict)
    setSelectedMarket('')
    setAvailableMarkets([])
    setData(null)
    setError('')
    requestId.current += 1
    if (nextDistrict) loadDistrictMarkets(nextDistrict)
    else setLoading(false)
  }

  const handleSearch = () => {
    const c = pendingCrop || 'Tomato'
    if (!pendingDistrict || !selectedMarket) {
      setData(null)
      setError(t('market.selectDistrictAndMarket'))
      return
    }
    setCrop(c)
    setDistrict(pendingDistrict)
    fetchPrices(c, pendingDistrict, selectedMarket)
  }

  const cropOptions = getPlantVillageCropOptions(t)
  const districtOptions = [
    ...DEFAULT_DISTRICTS.map((d) => ({ value: d, label: t(`dropdowns.districts.${d}`) }))
  ]

  const cropDisplay = translatePlantVillageCrop(data?.crop || crop, t)

  const prices = (data?.prices || data?.markets || [])
    .filter((p) => (p.market || p.name || '').toLocaleLowerCase() === selectedMarket.toLocaleLowerCase())
    .map((p) => ({
      market: p.market || p.name || 'Unknown Market',
      min_price: Number(p.min_price ?? p.minPrice ?? 0),
      max_price: Number(p.max_price ?? p.maxPrice ?? 0),
      modal_price: Number(p.modal_price ?? p.modalPrice ?? p.average_price ?? 0),
      arrival: Number(p.arrival ?? 0),
      date: p.date || p.reporting_date || ''
    }))

  const isDemoData = Boolean(data?.is_demo) ||
    (typeof data?.data_source === 'string' && (
      data.data_source.toLowerCase().includes('demo') ||
      data.data_source.toLowerCase().includes('estimated') ||
      data.data_source.toLowerCase().includes('offline')
    ))
  const isStaleData = Boolean(data?.cache?.stale)
  const lastUpdated = data?.cache?.last_updated || data?.last_updated

  return (
    <Background>
      <Navbar />
      <div className="page-content animate-fade-in">
        <h1 className="page-title">🏪 {t('market.title')}</h1>
        <p className="page-subtitle">
          🌾 {cropDisplay} · {t('market.perQuintal')} {data?.unit || '₹/Qtl'}
        </p>

        {data && (
          <div
            style={{
              marginBottom: 18,
              padding: '12px 18px',
              borderRadius: 14,
              border: `1px solid ${isDemoData || isStaleData ? 'rgba(239,68,68,0.35)' : 'rgba(16,185,129,0.35)'}`,
              background: isDemoData || isStaleData ? 'rgba(239,68,68,0.08)' : 'rgba(16,185,129,0.07)',
              fontSize: 13.5,
              lineHeight: 1.55,
              color: 'var(--text-primary)',
              fontWeight: 500
            }}
          >
            {isStaleData ? (
              <div>
                <span style={{ color: '#f59e0b', fontWeight: 700 }}>
                ◷ {t(isDemoData ? 'market.cachedReferenceTitle' : 'market.cachedMarketTitle')}
                </span>{' '}
                {t(isDemoData ? 'market.staleReferenceNotice' : 'market.staleMarketNotice')}
                {' '}{t('market.refreshingCached')}
                {lastUpdated && <> {t('market.lastUpdatedAt', { date: formatDate(lastUpdated, { dateStyle: 'medium', timeStyle: 'short' }) })}</>}
              </div>
            ) : isDemoData ? (
              <div>
                <span style={{ color: '#ef4444', fontWeight: 700 }}>{t('market.demoReferenceTitle')}</span>{' '}
                {t('market.demoReferenceNotice')}{' '}
                <a href="https://agmarknet.gov.in" target="_blank" rel="noopener noreferrer" style={{ color: 'var(--accent-green)', textDecoration: 'underline' }}>
                Agmarknet (agmarknet.gov.in)
                </a>{' '}
                {t('market.beforeSale')}
              </div>
            ) : (
              <div>
                <span style={{ color: '#10b981', fontWeight: 700 }}>{t('market.liveFeedTitle')}</span>{' '}
                {String(data.data_source || t('market.defaultSource'))}
              </div>
            )}
          </div>
        )}

        <GlassCard style={{ marginBottom: 24 }}>
          <div className="search-bar">
            <FormSelect
              label={t('farmerMarket.crop')}
              name="search_crop"
              value={pendingCrop}
              onChange={(e) => setPendingCrop(e.target.value)}
              options={cropOptions}
              searchable
              searchPlaceholder={t('market.searchCrops')}
              placeholder={t('farmerMarket.cropPlaceholder')}
            />
            <FormSelect
              label={t('createProfile.district')}
              name="search_district"
              value={pendingDistrict}
              onChange={handleDistrictChange}
              options={districtOptions}
              placeholder={t('market.selectDistrict')}
            />
            <FormSelect
              label={t('market.market')}
              name="search_market"
              value={selectedMarket}
              onChange={(e) => {
                requestId.current += 1
                setSelectedMarket(e.target.value)
                setData(null)
              }}
              options={availableMarkets.map((market) => {
                const value = typeof market === 'object' ? (market.value || market.name) : market
                const label = typeof market === 'object' ? (market.label || market.name || market.value) : market
                return { value, label: localizeMarket(label, language) }
              })}
              placeholder={pendingDistrict ? t('market.selectMarket') : t('market.selectDistrictFirst')}
              disabled={!pendingDistrict || loading || availableMarkets.length === 0}
            />
            <div style={{ display: 'flex', alignItems: 'flex-end', minWidth: 220 }}>
              <GradientButton
                fullWidth
                variant="primary"
                onClick={handleSearch}
                loading={loading}
                disabled={!pendingDistrict || !selectedMarket || loading}
              >
                🔍 {t('buyerMarket.searchBtn')}
              </GradientButton>
            </div>
          </div>
        </GlassCard>

        {loading && !data ? (
          <div style={{ display: 'flex', justifyContent: 'center', padding: 60 }}>
            <div className="loading-spinner" />
          </div>
        ) : error && !data ? (
          <GlassCard>
            <div style={{ textAlign: 'center', padding: 30, color: 'var(--danger-color, #ef4444)' }}>
              ⚠️ {error}
            </div>
          </GlassCard>
        ) : prices.length === 0 ? (
          <GlassCard>
            <p style={{ textAlign: 'center', padding: 30, color: 'var(--text-muted)' }}>
              {t('market.noData') || 'No market data available for your region yet.'}
            </p>
          </GlassCard>
        ) : (
          <GlassCard style={{ padding: 0, overflow: 'hidden' }}>
            <div style={{ overflowX: 'auto' }}>
              <table className="market-table">
                <thead>
                  <tr>
                    <th>{t('market.market')}</th>
                    <th>{t('market.minPrice')}</th>
                    <th>{t('market.maxPrice')}</th>
                    <th>{t('market.modalPrice')}</th>
                    <th>{t('market.arrival')}</th>
                    <th>{t('market.date')}</th>
                  </tr>
                </thead>
                <tbody>
                  {prices.map((p, idx) => (
                    <tr key={idx}>
                      <td data-label={t('market.market')} style={{ fontWeight: 600 }}>
                        📍 {localizeMarket(p.market, language)}
                      </td>
                      <td data-label={t('market.minPrice')}>₹{formatNumber(p.min_price)}</td>
                      <td data-label={t('market.maxPrice')}>₹{formatNumber(p.max_price)}</td>
                      <td data-label={t('market.modalPrice')}>
                        <span className="price-high">₹{formatNumber(p.modal_price)}</span>
                      </td>
                      <td data-label={t('market.arrival')}>{formatNumber(p.arrival)}</td>
                      <td data-label={t('market.date')}>
                        {p.date ? (() => {
                          try { return formatDate(p.date, { day: '2-digit', month: 'short', year: 'numeric' }) } catch { return String(p.date) }
                        })() : '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </GlassCard>
        )}
      </div>
    </Background>
  )
}

export default Market
