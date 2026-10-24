import React from 'react'
import { useLanguage } from '../context/LanguageContext'

const languages = [
  { code: 'en', label: 'English' },
  { code: 'mr', label: 'मराठी' },
  { code: 'hi', label: 'हिन्दी' },
  { code: 'ml', label: 'മലയാളം' }
]

const LanguageSwitcher = () => {
  const { language, setLanguage, t } = useLanguage()

  return (
    <label className="language-switcher">
      <span>{t('dashboard.currentLanguage')}</span>
      <select
        aria-label={t('dashboard.currentLanguage')}
        value={language}
        onChange={(event) => setLanguage(event.target.value)}
      >
        {languages.map(({ code, label }) => (
          <option key={code} value={code}>{label}</option>
        ))}
      </select>
    </label>
  )
}

export default LanguageSwitcher
