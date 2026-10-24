import React, { useEffect, useMemo, useState } from 'react'
import { useLanguage } from '../context/LanguageContext'
import { useAuth } from '../context/AuthContext'
import { weatherApi } from '../services/api'
import Background from '../components/Background'
import Navbar from '../components/Navbar'
import './Weather.css'
import { localizeLocationParts } from '../translations/locations'
import { localizeVariety } from '../translations/cropMarkets'
import { localizeCropName } from '../constants/crops'

const isWeatherNumber = (value) => value !== null && value !== undefined && value !== '' && Number.isFinite(Number(value))
const numberText = (value, suffix = '') => (
  isWeatherNumber(value) ? `${Math.round(Number(value))}${suffix}` : '—'
)

const locationCoordinatesFromProfile = (user) => {
  const latitude = Number(user?.location?.latitude ?? user?.latitude)
  const longitude = Number(user?.location?.longitude ?? user?.longitude)
  if (!Number.isFinite(latitude) || !Number.isFinite(longitude)) return null
  if (latitude < -90 || latitude > 90 || longitude < -180 || longitude > 180) return null
  return { latitude, longitude }
}

const windDirectionText = (degrees) => {
  if (!Number.isFinite(Number(degrees))) return '—'
  const directions = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW']
  return directions[Math.round(Number(degrees) / 45) % directions.length]
}

const formatDate = (date, options, language) => (
  date ? new Intl.DateTimeFormat(language, options).format(new Date(`${date}T12:00:00`)) : '—'
)

const buildRecommendations = (weather, user, t) => {
  if (!weather?.current) return []
  const { current, hourly = [], forecast = [] } = weather
  const nextHours = hourly.slice(0, 12)
  const nextSixHours = hourly.slice(0, 6)
  const rainProbability = nextHours.map((hour) => Number(hour.rain_prob)).filter(Number.isFinite)
  const maxRainProbability = rainProbability.length ? Math.max(...rainProbability) : null
  const nextSixRain = nextSixHours.map((hour) => Number(hour.rain_prob)).filter(Number.isFinite)
  const maxSixHourRain = nextSixRain.length ? Math.max(...nextSixRain) : null
  const temperature = Number(current.temp)
  const wind = Number(current.wind_speed)
  const gusts = Number(current.wind_gusts)
  const rainfall = Number(current.rainfall)
  const hasTemperature = isWeatherNumber(current.temp)
  const hasWind = isWeatherNumber(current.wind_speed)
  const hasRainfall = isWeatherNumber(current.rainfall)
  const profileCrop = user?.farming?.crop || user?.main_crop || user?.mainCrop || ''
  const cropStage = user?.farming?.stage || user?.crop_stage || user?.cropStage || ''
  const soilType = user?.farming?.soil_type || user?.soil_type || user?.soilType || ''
  const cropContext = [profileCrop, cropStage && `${t('weather.cropStage')}: ${cropStage}`]
    .filter(Boolean)
    .join(' · ')

  const make = (key, icon, priority, explanation, action) => ({
    key,
    icon,
    priority,
    explanation: t(explanation),
    action: t(action),
    cropContext,
    soilType,
  })

  const irrigation = maxRainProbability !== null && maxRainProbability >= 60
    ? make('irrigation', '💧', 'caution', 'weather.advice.irrigationRain', 'weather.advice.irrigationRainAction')
    : hasTemperature && temperature >= 34
      ? make('irrigation', '💧', 'caution', 'weather.advice.irrigationHeat', 'weather.advice.irrigationHeatAction')
      : maxRainProbability !== null && maxRainProbability < 30 && hasRainfall && rainfall < 1
        ? make('irrigation', '💧', 'info', 'weather.advice.irrigationDry', 'weather.advice.irrigationDryAction')
        : make('irrigation', '💧', 'info', 'weather.advice.irrigationLimit', 'weather.advice.irrigationLimitAction')

  const spraying = (hasWind && wind >= 15) || (maxSixHourRain !== null && maxSixHourRain >= 40)
    ? make('spraying', '🧴', 'alert', 'weather.advice.sprayRisk', 'weather.advice.sprayRiskAction')
    : hasWind && maxSixHourRain !== null
      ? make('spraying', '🧴', 'info', 'weather.advice.sprayWindow', 'weather.advice.sprayWindowAction')
      : make('spraying', '🧴', 'caution', 'weather.advice.sprayLimit', 'weather.advice.sprayLimitAction')

  const fertilizer = (maxSixHourRain !== null && maxSixHourRain >= 60) || (hasRainfall && rainfall >= 10)
    ? make('fertilizer', '🌱', 'caution', 'weather.advice.fertilizerRain', 'weather.advice.fertilizerRainAction')
    : maxSixHourRain !== null
      ? make('fertilizer', '🌱', 'info', 'weather.advice.fertilizerWindow', 'weather.advice.fertilizerWindowAction')
      : make('fertilizer', '🌱', 'caution', 'weather.advice.fertilizerLimit', 'weather.advice.fertilizerLimitAction')

  const protection = hasTemperature && temperature >= 38
    ? make('protection', '🛡️', 'alert', 'weather.advice.heatRisk', 'weather.advice.heatRiskAction')
    : (Number.isFinite(gusts) && gusts >= 40) || (maxRainProbability !== null && maxRainProbability >= 75)
      ? make('protection', '🛡️', 'caution', 'weather.advice.stormRisk', 'weather.advice.stormRiskAction')
      : make('protection', '🛡️', 'info', 'weather.advice.protectionMonitor', 'weather.advice.protectionMonitorAction')

  const fieldWork = (hasWind && wind >= 25) || (maxSixHourRain !== null && maxSixHourRain >= 60)
    ? make('fieldWork', '👩‍🌾', 'caution', 'weather.advice.fieldWorkRisk', 'weather.advice.fieldWorkRiskAction')
    : make('fieldWork', '👩‍🌾', 'info', 'weather.advice.fieldWorkWindow', 'weather.advice.fieldWorkWindowAction')

  const cropGuidance = profileCrop
    ? make('cropGuidance', '🌾', 'info', 'weather.advice.cropGuidance', 'weather.advice.cropGuidanceAction')
    : null

  return [irrigation, spraying, fertilizer, protection, fieldWork, cropGuidance].filter(Boolean).map((item) => ({
    ...item,
    hasCrop: Boolean(profileCrop),
  }))
}

const Weather = () => {
  const { t, language } = useLanguage()
  const { user } = useAuth()
  const [coordinates, setCoordinates] = useState(null)
  const [location, setLocation] = useState('')
  const [weather, setWeather] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [searchText, setSearchText] = useState('')
  const [searchResults, setSearchResults] = useState([])
  const [searching, setSearching] = useState(false)
  const [selectedDay, setSelectedDay] = useState(0)
  const [refreshKey, setRefreshKey] = useState(0)

  useEffect(() => {
    let active = true
    const profileCoordinates = locationCoordinatesFromProfile(user)
    const profileLocation = localizeLocationParts(user?.location, language).slice(0, 3).join(', ')
    setLocation(profileLocation || t('weather.savedLocation'))

    if (!navigator.geolocation) {
      if (active && profileCoordinates) setCoordinates(profileCoordinates)
      else if (active) {
        setError(t('weather.locationUnavailable'))
        setLoading(false)
      }
      return () => { active = false }
    }

    navigator.geolocation.getCurrentPosition(
      ({ coords: position }) => {
        if (!active) return
        setCoordinates({ latitude: position.latitude, longitude: position.longitude })
        setLocation(t('weather.deviceLocation'))
      },
      () => {
        if (!active) return
        if (profileCoordinates) {
          setCoordinates(profileCoordinates)
        } else {
          setError(t('weather.locationUnavailable'))
          setLoading(false)
        }
      },
      { enableHighAccuracy: false, timeout: 7000, maximumAge: 300000 }
    )
    return () => { active = false }
  }, [user, t, language])

  useEffect(() => {
    if (!coordinates) return
    let active = true
    const load = async () => {
      setLoading(true)
      setError('')
      try {
        const crop = user?.farming?.crop || user?.main_crop || user?.mainCrop || ''
        const stage = user?.farming?.stage || user?.crop_stage || user?.cropStage || ''
        const response = await weatherApi.getWeather(
          coordinates.latitude, coordinates.longitude, crop, stage, t
        )
        if (active) {
          setWeather(response)
          setSelectedDay(0)
        }
      } catch (requestError) {
        if (!active) return
        const status = requestError.response?.status
        setError(
          status === 503
            ? t('weather.providerUnavailable')
            : requestError.response?.data?.detail || t('weather.loadError')
        )
      } finally {
        if (active) setLoading(false)
      }
    }
    load()
    return () => { active = false }
  }, [coordinates, language, refreshKey, user, t])

  const recommendations = useMemo(
    () => buildRecommendations(weather, user, t),
    [weather, user, t]
  )
  const current = weather?.current
  const selectedForecast = weather?.forecast?.[selectedDay]
  const airQuality = weather?.air_quality
  const hourly = weather?.hourly?.slice(0, 12) || []

  const searchLocations = async (event) => {
    event.preventDefault()
    const query = searchText.trim()
    if (query.length < 2) {
      setError(t('weather.searchTooShort'))
      return
    }
    setSearching(true)
    setError('')
    setSearchResults([])
    try {
      const results = await weatherApi.searchLocations(query)
      setSearchResults(results)
      if (!results.length) setError(t('weather.noLocationResults'))
    } catch {
      setError(t('weather.locationSearchError'))
    } finally {
      setSearching(false)
    }
  }

  const chooseLocation = (result) => {
    setLocation([result.name, result.admin1, result.country].filter(Boolean).join(', '))
    setCoordinates({ latitude: result.latitude, longitude: result.longitude })
    setSearchResults([])
    setSearchText('')
  }

  const useDeviceLocation = () => {
    if (!navigator.geolocation) {
      setError(t('weather.locationUnavailable'))
      return
    }
    setLoading(true)
    navigator.geolocation.getCurrentPosition(
      ({ coords: position }) => {
        setLocation(t('weather.deviceLocation'))
        setCoordinates({ latitude: position.latitude, longitude: position.longitude })
        setRefreshKey((value) => value + 1)
        setError('')
      },
      () => {
        setLoading(false)
        setError(t('weather.locationDenied'))
      },
      { enableHighAccuracy: false, timeout: 10000, maximumAge: 300000 }
    )
  }

  const retry = () => {
    if (coordinates) setRefreshKey((value) => value + 1)
  }

  const formatHour = (value) => {
    if (!value) return '—'
    return new Intl.DateTimeFormat(language, { hour: 'numeric' }).format(new Date(value))
  }

  return (
    <Background>
      <Navbar />
      <main className="page-content weather-page animate-fade-in">
        <header className="weather-page-heading">
          <div>
            <h1 className="page-title">🌤️ {t('weather.pageTitle')}</h1>
            <p className="page-subtitle">{t('weather.pageSubtitle')}</p>
          </div>
          <button className="weather-refresh-btn" type="button" onClick={retry} disabled={loading || !coordinates}>
            <span aria-hidden="true">↻</span> {loading ? t('weather.refreshing') : t('weather.refresh')}
          </button>
        </header>

        <div className="weather-location-toolbar">
          <div className="weather-location-label">
            <span aria-hidden="true">📍</span>
            <div>
              <small>{t('weather.currentLocation')}</small>
              <strong>{location || t('weather.chooseLocation')}</strong>
            </div>
          </div>
          <button className="weather-device-btn" type="button" onClick={useDeviceLocation}>
            ⌖ {t('weather.useDeviceLocation')}
          </button>
          <form className="weather-search-form" onSubmit={searchLocations}>
            <input
              aria-label={t('weather.searchPlaceholder')}
              placeholder={t('weather.searchPlaceholder')}
              value={searchText}
              onChange={(event) => setSearchText(event.target.value)}
              maxLength={120}
            />
            <button type="submit" disabled={searching}>{searching ? '…' : t('common.search')}</button>
          </form>
          {searchResults.length > 0 && (
            <div className="weather-search-results" role="listbox" aria-label={t('weather.locationResults')}>
              {searchResults.map((result) => (
                <button
                  key={`${result.id}-${result.latitude}-${result.longitude}`}
                  type="button"
                  role="option"
                  aria-selected="false"
                  onClick={() => chooseLocation(result)}
                >
                  <strong>{result.name}</strong>
                  <span>{[result.admin1, result.country].filter(Boolean).join(', ')}</span>
                </button>
              ))}
            </div>
          )}
        </div>

        {error && (
          <div className="weather-error" role="alert">
            <span>{error}</span>
            {coordinates && <button type="button" onClick={retry}>{t('weather.retry')}</button>}
          </div>
        )}

        {loading && !weather ? (
          <section className="weather-skeleton" aria-label={t('common.loading')}>
            <div className="weather-skeleton-main"><i /><i /><i /></div>
            <div className="weather-skeleton-row">{[1, 2, 3, 4, 5].map((item) => <i key={item} />)}</div>
          </section>
        ) : weather && current ? (
          <>
            <section className="weather-hero-card" aria-label={t('weather.currentConditions')}>
              <div className="weather-hero-topline">
                <div>
                  <span className="weather-eyebrow">{t('weather.currentConditions')}</span>
                  <h2>{location || t('weather.savedLocation')}</h2>
                </div>
                <span className="weather-live-badge"><i /> {t('weather.liveForecast')}</span>
              </div>
              <div className="weather-current-layout">
                <div className="weather-current-summary">
                  <span className="weather-current-icon" aria-hidden="true">{current.icon}</span>
                  <div>
                    <div className="weather-current-temperature">
                      {numberText(current.temp)}<span>°C</span>
                    </div>
                    <div className="weather-current-condition">{current.description || t('weather.conditionUnavailable')}</div>
                    <div className="weather-feels-like">
                      {t('weather.feelsLike')} {numberText(current.feels_like, '°')}
                    </div>
                  </div>
                </div>
                <div className="weather-hero-metrics">
                  <div><span>💧 {t('weather.humidity')}</span><strong>{numberText(current.humidity, '%')}</strong></div>
                  <div><span>💨 {t('weather.wind')}</span><strong>{numberText(current.wind_speed, ' km/h')}</strong></div>
                  <div><span>🌧️ {t('weather.rainProbability')}</span><strong>{numberText(current.rain_probability, '%')}</strong></div>
                </div>
              </div>
              <div className="weather-hourly">
                <h3>{t('weather.hourlyForecast')}</h3>
                {hourly.length ? (
                  <div className="weather-hourly-scroll">
                    {hourly.map((hour, index) => (
                      <div className="weather-hour-item" key={`${hour.time}-${index}`}>
                        <span>{index === 0 ? t('weather.now') : formatHour(hour.time)}</span>
                        <span className="weather-hour-icon" aria-hidden="true">{hour.icon}</span>
                        <strong>{numberText(hour.temp, '°')}</strong>
                        {Number.isFinite(Number(hour.rain_prob)) && (
                          <small>💧 {numberText(hour.rain_prob, '%')}</small>
                        )}
                      </div>
                    ))}
                  </div>
                ) : <p className="weather-muted">{t('weather.hourlyUnavailable')}</p>}
              </div>
              <div className="weather-updated">
                {t('weather.lastUpdated')}: {weather.fetched_at
                  ? new Intl.DateTimeFormat(language, { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(weather.fetched_at))
                  : '—'}
                {loading && <span> · {t('weather.refreshing')}</span>}
              </div>
            </section>

            <section className="weather-section">
              <div className="weather-section-heading">
                <div><span>📅</span><h2>{t('weather.fiveDayForecast')}</h2></div>
                <span>{t('weather.tapDay')}</span>
              </div>
              <div className="weather-daily-scroll">
                {(weather.forecast || []).slice(0, 5).map((day, index) => (
                  <button
                    className={`weather-day-card ${selectedDay === index ? 'is-selected' : ''}`}
                    type="button"
                    key={day.date || index}
                    onClick={() => setSelectedDay(index)}
                    aria-pressed={selectedDay === index}
                  >
                    <span className="weather-day-name">{index === 0 ? t('weather.today') : day.day || '—'}</span>
                    <small>{formatDate(day.date, { month: 'short', day: 'numeric' }, language)}</small>
                    <span className="weather-day-icon" aria-hidden="true">{day.icon}</span>
                    <strong>{numberText(day.temp_max, '°')} <span>{numberText(day.temp_min, '°')}</span></strong>
                    {Number.isFinite(Number(day.rain_prob_max)) && (
                      <small className="weather-rain-prob">💧 {numberText(day.rain_prob_max, '%')}</small>
                    )}
                  </button>
                ))}
              </div>
              {!weather.forecast?.length && <p className="weather-muted">{t('weather.dailyUnavailable')}</p>}
              {selectedForecast && (
                <div className="weather-selected-day">
                  <span className="weather-selected-day-icon" aria-hidden="true">{selectedForecast.icon}</span>
                  <div>
                    <strong>{selectedForecast.day || t('weather.today')} · {selectedForecast.condition || t('weather.conditionUnavailable')}</strong>
                    <p>
                      {t('weather.highLow')}: {numberText(selectedForecast.temp_max, '°')} / {numberText(selectedForecast.temp_min, '°')}
                      {selectedForecast.rain_prob_max != null && ` · ${t('weather.rainProbability')}: ${numberText(selectedForecast.rain_prob_max, '%')}`}
                      {selectedForecast.precipitation_sum != null && ` · ${t('weather.expectedRain')}: ${numberText(selectedForecast.precipitation_sum, ' mm')}`}
                    </p>
                  </div>
                </div>
              )}
            </section>

            <section className="weather-section">
              <div className="weather-section-heading">
                <div><span>🌦️</span><h2>{t('weather.weatherDetails')}</h2></div>
                <span>{t('weather.expandDetails')}</span>
              </div>
              <div className="weather-detail-grid">
                <details className="weather-detail-card" open>
                  <summary><span>🌧️</span><strong>{t('weather.precipitation')}</strong><span className="weather-summary-value">{numberText(current.rain_probability, '%')}</span></summary>
                  <div className="weather-detail-body">
                    <p>{t('weather.rainProbability')}: <strong>{numberText(current.rain_probability, '%')}</strong></p>
                    <p>{t('weather.expectedRain')}: <strong>{numberText(selectedForecast?.precipitation_sum, ' mm')}</strong></p>
                  </div>
                </details>
                <details className="weather-detail-card">
                  <summary><span>💨</span><strong>{t('weather.wind')}</strong><span className="weather-summary-value">{numberText(current.wind_speed, ' km/h')}</span></summary>
                  <div className="weather-detail-body">
                    <p>{t('weather.windSpeed')}: <strong>{numberText(current.wind_speed, ' km/h')}</strong></p>
                    <p>{t('weather.direction')}: <strong>{windDirectionText(current.wind_direction)}</strong></p>
                    <p>{t('weather.gusts')}: <strong>{numberText(current.wind_gusts, ' km/h')}</strong></p>
                  </div>
                </details>
                <details className="weather-detail-card">
                  <summary><span>💧</span><strong>{t('weather.humidity')}</strong><span className="weather-summary-value">{numberText(current.humidity, '%')}</span></summary>
                  <div className="weather-detail-body">
                    <p>{t('weather.currentHumidity')}: <strong>{numberText(current.humidity, '%')}</strong></p>
                  </div>
                </details>
                <details className="weather-detail-card">
                  <summary><span>🌫️</span><strong>{t('weather.airQuality')}</strong><span className="weather-summary-value">{airQuality ? airQuality.value : t('weather.unavailable')}</span></summary>
                  <div className="weather-detail-body">
                    {airQuality ? (
                      <>
                        <p>{t('weather.aqi')}: <strong>{airQuality.value} · {airQuality.category}</strong></p>
                        <p>{t('weather.source')}: <strong>{airQuality.source}</strong></p>
                        <p>{t('weather.observedAt')}: <strong>{airQuality.timestamp || t('weather.unavailable')}</strong></p>
                        {(airQuality.pm2_5 != null || airQuality.pm10 != null) && (
                          <p>PM2.5: <strong>{numberText(airQuality.pm2_5, ' μg/m³')}</strong> · PM10: <strong>{numberText(airQuality.pm10, ' μg/m³')}</strong></p>
                        )}
                      </>
                    ) : <p>{t('weather.airQualityUnavailable')}</p>}
                  </div>
                </details>
              </div>
            </section>

            <section className="weather-section weather-recommendations">
              <div className="weather-section-heading">
                <div><span>🌾</span><h2>{t('weather.agriculturalRecommendations')}</h2></div>
              </div>
              <p className="weather-recommendation-intro">
                {t('weather.recommendationIntro')}
                {user?.farming?.crop && (
                  <span> {t('weather.cropContext')}: <strong>{localizeCropName(user.farming.crop, language)}</strong>
                    {user.farming.variety && ` · ${t('weather.variety')}: ${localizeVariety(user.farming.variety, language)}`}
                    {user.farming.stage && ` · ${t('weather.cropStage')}: ${user.farming.stage}`}
                    {user.farming.soil_type && ` · ${t('weather.soilType')}: ${user.farming.soil_type}`}
                  </span>
                )}
              </p>
              {!user?.farming?.crop && (
                <div className="weather-profile-note">ℹ️ {t('weather.cropProfileMissing')}</div>
              )}
              <div className="weather-recommendation-grid">
                {recommendations.map((item) => (
                  <article className={`weather-recommendation-card priority-${item.priority}`} key={item.key}>
                    <div className="weather-recommendation-top">
                      <span className="weather-recommendation-icon" aria-hidden="true">{item.icon}</span>
                      <div><h3>{t(`weather.advice.${item.key}`)}</h3><span className={`weather-priority priority-${item.priority}`}>{t(`weather.priority.${item.priority}`)}</span></div>
                    </div>
                    <p>{item.explanation}</p>
                    {item.soilType && item.key === 'irrigation' && (
                      <p className="weather-soil-context">{t('weather.soilContext')}: {item.soilType}</p>
                    )}
                    <div className="weather-action"><strong>{t('weather.action')}:</strong> {item.action}</div>
                  </article>
                ))}
              </div>
              <p className="weather-disclaimer">{t('weather.recommendationDisclaimer')}</p>
            </section>

            <footer className="weather-data-source">
              {t('weather.dataSource')}: {weather.data_source || 'Open-Meteo'}
            </footer>
          </>
        ) : (
          !error && <div className="weather-empty">{t('weather.noWeather')}</div>
        )}
      </main>
    </Background>
  )
}

export default Weather
