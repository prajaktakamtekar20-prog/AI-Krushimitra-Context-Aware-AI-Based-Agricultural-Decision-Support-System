import React from 'react'
import { useNavigate } from 'react-router-dom'
import { useLanguage } from '../context/LanguageContext'
import Background from '../components/Background'
import GlassCard from '../components/GlassCard'
import GradientButton from '../components/GradientButton'
import LanguageSwitcher from '../components/LanguageSwitcher'

const ProfileCreated = () => {
  const { t } = useLanguage()
  const navigate = useNavigate()

  return (
    <Background>
      <div className="auth-language-row"><LanguageSwitcher /></div>
      <div className="centered-page">
        <GlassCard className="auth-card animate-fade-in" glowGreen>
          <div className="success-icon">✓</div>
          <div className="success-message">
            <h1 className="page-title" style={{ marginBottom: 12 }}>
              {t('profileCreated.title')}
            </h1>
            <p className="page-subtitle" style={{ marginBottom: 0 }}>
              {t('profileCreated.message')}
            </p>
          </div>
          <div className="farmer-illustration">
            <span>🌾</span>
            <span>👨‍🌾</span>
            <span>🚜</span>
          </div>
          <div style={{ textAlign: 'center', marginTop: 20 }}>
            <GradientButton
              size="lg"
              variant="secondary"
              onClick={() => navigate('/dashboard')}
            >
              {t('profileCreated.goToDashboard')}
            </GradientButton>
          </div>
        </GlassCard>
      </div>
    </Background>
  )
}

export default ProfileCreated
