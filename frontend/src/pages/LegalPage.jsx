import React from 'react'
import { Link } from 'react-router-dom'
import Background from '../components/Background'
import GlassCard from '../components/GlassCard'
import LanguageSwitcher from '../components/LanguageSwitcher'
import { useLanguage } from '../context/LanguageContext'

const LegalPage = ({ type }) => {
  const isTerms = type === 'terms'
  const { t } = useLanguage()

  return (
    <Background>
      <div className="auth-language-row"><LanguageSwitcher /></div>
      <main className="legal-page">
        <GlassCard glow>
          <h1>{t(isTerms ? 'legal.termsTitle' : 'legal.privacyTitle')}</h1>
          {isTerms ? (
            <>
              <p>{t('legal.termsIntro')}</p>
              <p>{t('legal.termsAccount')}</p>
              <p>{t('legal.termsChanges')}</p>
            </>
          ) : (
            <>
              <p>{t('legal.privacyIntro')}</p>
              <p>{t('legal.privacyProfile')}</p>
              <p>{t('legal.privacySession')}</p>
            </>
          )}
          <div className="auth-footer">
            <Link to="/login">{t('legal.backToLogin')}</Link>
            {' · '}
            <Link to={isTerms ? '/privacy' : '/terms'}>
              {t(isTerms ? 'legal.privacyTitle' : 'legal.termsTitle')}
            </Link>
          </div>
        </GlassCard>
      </main>
    </Background>
  )
}

export default LegalPage
