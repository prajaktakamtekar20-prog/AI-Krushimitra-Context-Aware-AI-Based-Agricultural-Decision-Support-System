import React, { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useLanguage } from '../context/LanguageContext'
import Background from '../components/Background'
import GlassCard from '../components/GlassCard'
import GradientButton from '../components/GradientButton'

const LanguageSelection = () => {
  const { t, setLanguage, language } = useLanguage()
  const navigate = useNavigate()
  const [selected, setSelected] = useState(language || '')

  const languages = [
    {
      code: 'mr',
      flag: '🇮🇳',
      native: 'मराठी',
      english: 'Marathi'
    },
    {
      code: 'hi',
      flag: '🇮🇳',
      native: 'हिन्दी',
      english: 'Hindi'
    },
    {
      code: 'en',
      flag: '🇬🇧',
      native: 'English',
      english: 'English'
    },
    {
      code: 'ml',
      flag: '🇮🇳',
      native: 'മലയാളം',
      english: 'Malayalam'
    }
  ]

  const handleSelect = (code) => {
    setSelected(code)
  }

  const handleContinue = () => {
    if (selected) {
      setLanguage(selected)
      navigate('/register')
    }
  }

  return (
    <Background>
      <div className="auth-container">
        <div style={{ width: '100%', maxWidth: 900, textAlign: 'center' }}>
          <div style={{ fontSize: 56, marginBottom: 16 }}>🌍</div>
          <h1 className="page-title" style={{ textAlign: 'center' }}>
            {t('languageSelect.title')}
          </h1>
          <p className="page-subtitle" style={{ textAlign: 'center' }}>
            {t('languageSelect.select')}
          </p>

          <div className="language-grid" style={{ margin: '40px auto' }}>
            {languages.map((lang) => (
              <GlassCard
                key={lang.code}
                hover
                glow={selected === lang.code}
                className={`language-card ${selected === lang.code ? 'language-card--selected' : ''}`}
                onClick={() => handleSelect(lang.code)}
              >
                <span className="language-flag">{lang.flag}</span>
                <div className="language-name-native">{lang.native}</div>
                <div className="language-name-english">{lang.english}</div>
              </GlassCard>
            ))}
          </div>

          <div style={{ marginTop: 20 }}>
            <GradientButton
              size="lg"
              onClick={handleContinue}
              disabled={!selected}
            >
              {t('welcome.getStarted')}
            </GradientButton>
          </div>

          <div style={{ marginTop: 28, fontSize: 14, color: 'var(--text-muted)' }}>
            {t('register.haveAccount')}{' '}
            <Link to="/login" style={{ color: 'var(--accent-purple)', fontWeight: 600, textDecoration: 'none' }}>
              {t('register.login')}
            </Link>
          </div>
        </div>
      </div>
    </Background>
  )
}

export default LanguageSelection
