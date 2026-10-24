import React from 'react'
import { Link } from 'react-router-dom'
import { useLanguage } from '../context/LanguageContext'

const LegalNotice = () => {
  const { t } = useLanguage()

  return (
    <footer className="auth-legal-notice">
      {t('legal.continueNotice')}{' '}
      <Link to="/terms">{t('legal.termsTitle')}</Link> {t('common.and')}{' '}
      <Link to="/privacy">{t('legal.privacyTitle')}</Link>.
    </footer>
  )
}

export default LegalNotice
