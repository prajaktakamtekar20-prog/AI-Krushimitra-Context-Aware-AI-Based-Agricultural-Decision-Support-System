import React from 'react'
import { useNavigate } from 'react-router-dom'
import { useLanguage } from '../context/LanguageContext'
import Background from '../components/Background'
import GlassCard from '../components/GlassCard'
import GradientButton from '../components/GradientButton'

const Welcome = () => {
  const { t, language, setLanguage } = useLanguage()
  const navigate = useNavigate()

  const languages = [
    { code: 'mr', flag: '🇮🇳', native: 'मराठी', english: 'Marathi' },
    { code: 'hi', flag: '🇮🇳', native: 'हिन्दी', english: 'Hindi' },
    { code: 'en', flag: '🇬🇧', native: 'English', english: 'English' },
    { code: 'ml', flag: '🇮🇳', native: 'മലയാളം', english: 'Malayalam' }
  ]

  const handleGetStarted = () => {
    navigate('/register')
  }

  return (
    <Background heroImage>
      <div className="welcome-screen">
        {/* Top Row: Logo */}
        <div className="welcome-top-bar animate-fade-in">
          <div className="welcome-logo-mini">
            <span className="welcome-logo-icon">🌱</span>
            <div className="welcome-logo-text-wrap">
              <div className="welcome-logo-title">{t('brand.projectName')}</div>
              <div className="welcome-logo-tag">{t('welcome.logoTag')}</div>
            </div>
          </div>
          <div className="top-lang-bar" aria-label={t('languageSelect.title')}>
            <span className="top-lang-bar-label">{t('languageSelect.select')}</span>
            <div className="top-lang-bar-btns">
              {languages.map((lang) => (
                <button
                  key={lang.code}
                  type="button"
                  className={`top-lang-btn ${language === lang.code ? 'top-lang-btn--active' : ''}`}
                  onClick={() => setLanguage(lang.code)}
                  aria-pressed={language === lang.code}
                >
                  <span className="top-lang-btn-flag" aria-hidden="true">{lang.flag}</span>
                  <span className="top-lang-btn-native">{lang.native}</span>
                  <span className="top-lang-btn-english">{lang.english}</span>
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Hero Split Row */}
        <div className="welcome-hero-split">
          {/* LEFT COLUMN */}
          <div className="welcome-left">
            <div className="welcome-pill animate-fade-in" style={{ animationDelay: '0.1s' }}>
              <span className="welcome-pill-icon">🌱</span>
              <span>{t('welcome.futurePill')}</span>
            </div>

            <h1 className="welcome-hero-title animate-fade-in" style={{ animationDelay: '0.2s' }}>
              <span className="welcome-hero-title-w">{t('welcome.titleTop')}</span>
              <br />
              <span className="welcome-hero-title-grad">{t('welcome.titleBot')}</span>
            </h1>

            <p className="welcome-hero-sub animate-fade-in" style={{ animationDelay: '0.3s' }}>
              {t('welcome.subtitle')}
            </p>

            <p className="welcome-hero-desc animate-fade-in" style={{ animationDelay: '0.4s' }}>
              {t('welcome.description')}
            </p>

            <div className="animate-fade-in" style={{ animationDelay: '0.5s' }}>
              <GradientButton size="lg" variant="primary" onClick={handleGetStarted}>
                {t('welcome.getStarted')}
              </GradientButton>
            </div>
          </div>

          {/* RIGHT COLUMN - Hero Image with Floating Badges */}
          <div className="welcome-right animate-fade-in" style={{ animationDelay: '0.25s' }}>
            <div className="welcome-hero-image-wrap">
              <div
                className="welcome-hero-image"
                style={{
                  backgroundImage: `url('https://coresg-normal.trae.ai/api/ide/v1/text_to_image?prompt=close%20up%20young%20vibrant%20green%20corn%20maize%20plant%20seedlings%20growing%20in%20rows%20in%20rich%20dark%20farm%20soil%20at%20golden%20hour%20sunset%20with%20warm%20orange%20sun%20glow%2C%20shallow%20depth%20of%20field%2C%20photorealistic%2C%20premium%20agriculture%20photography%2C%20cinematic&image_size=portrait_4_3')`,
                }}
              />
              {/* Top Floating Badge */}
              <GlassCard className="welcome-badge welcome-badge--top" hover glow>
                <div className="welcome-badge-icon">✨</div>
                <div>
                  <div className="welcome-badge-title">{t('welcome.badge1Title')}</div>
                  <div className="welcome-badge-sub">{t('welcome.badge1Sub')}</div>
                </div>
              </GlassCard>

              {/* Bottom Floating Badge */}
              <GlassCard className="welcome-badge welcome-badge--bot" hover glowGreen>
                <div className="welcome-badge-icon welcome-badge-icon--green">🌾</div>
                <div>
                  <div className="welcome-badge-title">{t('welcome.badge2Title')}</div>
                  <div className="welcome-badge-sub">{t('welcome.badge2Sub')}</div>
                </div>
              </GlassCard>
            </div>
          </div>
        </div>
      </div>
    </Background>
  )
}

export default Welcome
