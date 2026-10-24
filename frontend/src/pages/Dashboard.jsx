import React from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useLanguage } from '../context/LanguageContext'
import { useAuth } from '../context/AuthContext'
import Background from '../components/Background'
import Navbar from '../components/Navbar'
import GlassCard from '../components/GlassCard'
import GradientButton from '../components/GradientButton'
import { normalizePlantVillageCrop, translatePlantVillageCrop } from '../constants/crops'
import { localizeDisplayName } from '../translations/brand'
import { localizeLocationParts } from '../translations/locations'
import { localizeVariety } from '../translations/cropMarkets'

const Dashboard = () => {
  const { t, language } = useLanguage()
  const { user } = useAuth()
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const showProfileSummary = searchParams.get('section') === 'profile'
  const userName = localizeDisplayName(user?.full_name || user?.name || 'Farmer', language)
  const location = user?.location
    ? localizeLocationParts(user.location, language).join(', ')
    : t('common.notSet')

  const stageTranslations = {
    seedling: t('createProfile.stages.seedling'),
    vegetative: t('createProfile.stages.vegetative'),
    flowering: t('createProfile.stages.flowering'),
    fruiting: t('createProfile.stages.fruiting'),
    harvesting: t('createProfile.stages.harvesting')
  }
  const soilTranslations = {
    black: t('createProfile.soils.black'),
    red: t('createProfile.soils.red'),
    alluvial: t('createProfile.soils.alluvial'),
    sandy: t('createProfile.soils.sandy'),
    other: t('createProfile.soils.other')
  }
  const irrigationTranslations = {
    drip: t('createProfile.irrigations.drip'),
    sprinkler: t('createProfile.irrigations.sprinkler'),
    rainfed: t('createProfile.irrigations.rainfed'),
    canal: t('createProfile.irrigations.canal'),
    other: t('createProfile.irrigations.other')
  }

  const mainCrop = normalizePlantVillageCrop(user?.farming?.crop || user?.main_crop || user?.mainCrop)
  const cropDisplay = mainCrop ? translatePlantVillageCrop(mainCrop, t) : '—'
  const varietyValue = user?.farming?.variety || user?.variety
  const variety = varietyValue ? localizeVariety(varietyValue, language) : '—'
  const cropStage = user?.farming?.stage || user?.crop_stage || user?.cropStage
  const stageDisplay = cropStage ? (stageTranslations[cropStage] || t('common.notSet')) : '—'
  const landArea = user?.farming?.land_area ?? user?.land_area ?? user?.landArea
  const landUnit = user?.farming?.land_unit || user?.land_unit || user?.landUnit
  const landDisplay = landArea
    ? `${landArea} ${landUnit === 'hectares' ? t('createProfile.hectares') : t('createProfile.acres')}`
    : '—'
  const soilType = user?.farming?.soil_type || user?.soil_type || user?.soilType
  const soilDisplay = soilType ? (soilTranslations[soilType] || t('common.notSet')) : '—'
  const irrigationType = user?.farming?.irrigation || user?.irrigation_type || user?.irrigation
  const irrigationDisplay = irrigationType ? (irrigationTranslations[irrigationType] || t('common.notSet')) : '—'

  const userInitial = userName?.trim()?.charAt(0)?.toUpperCase() || 'F'

  const languageLabel = () => {
    if (language === 'mr') return '🇮🇳 मराठी'
    if (language === 'hi') return '🇮🇳 हिन्दी'
    if (language === 'ml') return '🇮🇳 മലയാളം'
    return '🇬🇧 English'
  }

  const moduleCards = [
    {
      path: '/disease',
      icon: '🌿',
      iconBg: 'module-icon--green',
      accent: 'module-card--accent-green',
      title: t('dashboard.moduleDiseaseTitle'),
      desc: t('dashboard.moduleDiseaseDesc'),
      btnText: t('dashboard.moduleDiseaseBtn'),
      btnVariant: 'primary'
    },
    {
      path: '/market',
      icon: '💰',
      iconBg: 'module-icon--amber',
      accent: 'module-card--accent-amber',
      title: t('dashboard.moduleMarketTitle'),
      desc: t('dashboard.moduleMarketDesc'),
      btnText: t('dashboard.moduleMarketBtn'),
      btnVariant: 'primary'
    },
    {
      path: '/weather',
      icon: '🌦️',
      iconBg: 'module-icon--blue',
      accent: 'module-card--accent-blue',
      title: t('dashboard.moduleWeatherTitle'),
      desc: t('dashboard.moduleWeatherDesc'),
      btnText: t('dashboard.moduleWeatherBtn'),
      btnVariant: 'primary'
    },
    {
      path: '/schemes',
      icon: '🏛️',
      iconBg: 'module-icon--green',
      accent: 'module-card--accent-green',
      title: t('dashboard.moduleSchemesTitle'),
      desc: t('dashboard.moduleSchemesDesc'),
      btnText: t('dashboard.moduleSchemesBtn'),
      btnVariant: 'primary'
    },
    {
      path: '/marketplace?tab=requirements',
      icon: '🧺',
      iconBg: 'module-icon--green',
      accent: 'module-card--accent-green',
      title: t('dashboard.marketplaceTitle'),
      desc: t('dashboard.marketplaceDesc'),
      btnText: t('dashboard.marketplaceBtn'),
      btnVariant: 'primary'
    }
  ]

  return (
    <Background>
      <Navbar />
      <div className="page-content dashboard-page animate-fade-in">
        <GlassCard className="dashboard-welcome-card" glow>
          <div className="dashboard-welcome-left">
            <div className="dashboard-welcome-avatar">
              {userInitial}
            </div>
            <div className="dashboard-welcome-text-wrap">
              <h1 className="dashboard-welcome-title">
                {t('dashboard.welcome')}, <span>{userName}!</span> 👋
              </h1>
              <div className="dashboard-welcome-sub">
                <span className="dashboard-welcome-badge">
                  📍 {location}
                </span>
                <span className="dashboard-welcome-badge dashboard-welcome-badge--lang">
                  🌐 {languageLabel()}
                </span>
                {cropDisplay !== '—' && (
                  <span className="dashboard-welcome-badge dashboard-welcome-badge--crop">
                    🌾 {cropDisplay}
                  </span>
                )}
              </div>
            </div>
          </div>
          <div className="dashboard-welcome-right">
            <div className="dashboard-stat-chip">
              <span className="dashboard-stat-chip-icon">🌱</span>
              <div>
                <div className="dashboard-stat-chip-label">{t('dashboard.stage')}</div>
                <div className="dashboard-stat-chip-value">{stageDisplay}</div>
              </div>
            </div>
            <div className="dashboard-stat-chip">
              <span className="dashboard-stat-chip-icon">📐</span>
              <div>
                <div className="dashboard-stat-chip-label">{t('dashboard.land')}</div>
                <div className="dashboard-stat-chip-value">{landDisplay}</div>
              </div>
            </div>
          </div>
        </GlassCard>

        {user?.hasProfile && (
          showProfileSummary && (
            <GlassCard className="farm-info-card">
              <div className="section-header">
                <h2 className="section-title">{t('myProfile.title')}</h2>
                <button className="edit-profile-btn" type="button" onClick={() => navigate('/profile')}>{t('myProfile.editProfile')}</button>
              </div>
              <div className="info-grid">
                <div className="info-item"><div className="info-label">{t('myProfile.fullName')}</div><div className="info-value">{userName}</div></div>
                <div className="info-item"><div className="info-label">{t('myProfile.mobile')}</div><div className="info-value">{user?.mobile || t('common.notSet')}</div></div>
                <div className="info-item"><div className="info-label">{t('myProfile.email')}</div><div className="info-value">{user?.email || t('common.notSet')}</div></div>
                <div className="info-item"><div className="info-label">{t('dashboard.location')}</div><div className="info-value">{location}</div></div>
                <div className="info-item"><div className="info-label">{t('myProfile.mainCrop')}</div><div className="info-value">{cropDisplay}</div></div>
              </div>
            </GlassCard>
          )
        )}

        <div className="dashboard-section-head">
          <div>
            <h2 className="dashboard-section-title">⚡ {t('dashboard.modulesTitle')}</h2>
            <p className="dashboard-section-sub">{t('dashboard.modulesSubtitle')}</p>
          </div>
        </div>

        <div className="module-cards-grid">
          {moduleCards.map((card) => (
            <GlassCard
              key={card.path}
              hover
              className={`module-card ${card.accent}`}
              onClick={() => navigate(card.path)}
            >
              <div className={`module-icon ${card.iconBg}`}>
                {card.icon}
              </div>
              <h3 className="module-title">{card.title}</h3>
              <p className="module-desc">{card.desc}</p>
              <button className="module-btn">
                {card.btnText} →
              </button>
            </GlassCard>
          ))}
        </div>

        <GlassCard className="ai-assistant-banner" glowGreen>
          <div className="ai-banner-left">
            <div className="ai-banner-icon-wrap">
              <span className="ai-banner-icon">🤖</span>
              <span className="ai-banner-icon ai-banner-icon--small">✨</span>
            </div>
            <div>
              <h2 className="ai-banner-title">{t('dashboard.assistantSectionTitle')}</h2>
              <p className="ai-banner-desc">{t('dashboard.assistantSectionDesc')}</p>
            </div>
          </div>
          <div className="ai-banner-actions">
            <GradientButton onClick={() => navigate('/ai-assistant')} variant="secondary" size="lg">
              {t('dashboard.assistantSectionBtn')} 💬
            </GradientButton>
          </div>
        </GlassCard>

        <div className="dashboard-info-grid">
          <GlassCard className="farm-info-card">
            <div className="section-header">
              <h2 className="section-title">🌾 {t('dashboard.cropCard')}</h2>
              <button className="edit-profile-btn" onClick={() => navigate('/profile')}>
                ✏️ {t('myProfile.editProfile')}
              </button>
            </div>
            <div className="info-grid">
              <div className="info-item">
                <div className="info-label">{t('dashboard.crop')}</div>
                <div className="info-value">{cropDisplay}</div>
              </div>
              <div className="info-item">
                <div className="info-label">{t('dashboard.variety')}</div>
                <div className="info-value">{variety}</div>
              </div>
              <div className="info-item">
                <div className="info-label">{t('dashboard.stage')}</div>
                <div className="info-value">{stageDisplay}</div>
              </div>
              <div className="info-item">
                <div className="info-label">{t('dashboard.land')}</div>
                <div className="info-value">{landDisplay}</div>
              </div>
              <div className="info-item">
                <div className="info-label">{t('dashboard.soil')}</div>
                <div className="info-value">{soilDisplay}</div>
              </div>
              <div className="info-item">
                <div className="info-label">{t('dashboard.irrigation')}</div>
                <div className="info-value">{irrigationDisplay}</div>
              </div>
            </div>
          </GlassCard>

          <GlassCard className="quick-links-card">
            <div className="section-header">
              <h2 className="section-title">🔗 {t('dashboard.quickActions')}</h2>
            </div>
            <div className="quick-links-grid">
              <button className="quick-link-btn" onClick={() => navigate('/disease')}>
                <span className="quick-link-icon">🌿</span>
                <div>
                  <div className="quick-link-title">{t('nav.diseaseDetection')}</div>
                  <div className="quick-link-sub">{t('dashboard.moduleDiseaseDesc')}</div>
                </div>
                <span className="quick-link-arrow">›</span>
              </button>
              <button className="quick-link-btn" onClick={() => navigate('/weather')}>
                <span className="quick-link-icon">🌤️</span>
                <div>
                  <div className="quick-link-title">{t('nav.weather')}</div>
                  <div className="quick-link-sub">{t('dashboard.moduleWeatherDesc')}</div>
                </div>
                <span className="quick-link-arrow">›</span>
              </button>
              <button className="quick-link-btn" onClick={() => navigate('/market')}>
                <span className="quick-link-icon">🏪</span>
                <div>
                  <div className="quick-link-title">{t('nav.market')}</div>
                  <div className="quick-link-sub">{t('dashboard.moduleMarketDesc')}</div>
                </div>
                <span className="quick-link-arrow">›</span>
              </button>
              <button className="quick-link-btn" onClick={() => navigate('/ai-assistant')}>
                <span className="quick-link-icon">🤖</span>
                <div>
                  <div className="quick-link-title">{t('nav.aiAssistant')}</div>
                  <div className="quick-link-sub">{t('dashboard.aiAssistantDesc')}</div>
                </div>
                <span className="quick-link-arrow">›</span>
              </button>
              <button className="quick-link-btn" onClick={() => navigate('/profile')}>
                <span className="quick-link-icon">👤</span>
                <div>
                  <div className="quick-link-title">{t('nav.myProfile')}</div>
                  <div className="quick-link-sub">{t('myProfile.personalInfo')}, {t('myProfile.farmingInfo')}</div>
                </div>
                <span className="quick-link-arrow">›</span>
              </button>
            </div>
          </GlassCard>
        </div>
      </div>
    </Background>
  )
}

export default Dashboard
