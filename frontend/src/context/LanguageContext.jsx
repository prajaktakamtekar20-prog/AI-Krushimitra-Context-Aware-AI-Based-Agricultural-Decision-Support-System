import { createContext, useContext, useState, useEffect } from 'react'
import { en } from '../translations/en'
import { mr } from '../translations/mr'
import { hi } from '../translations/hi'
import { ml } from '../translations/ml'

const LanguageContext = createContext()

const translations = { en, mr, hi, ml }
const reportedMissingKeys = new Set()
const localeByLanguage = {
  en: 'en-IN',
  mr: 'mr-IN',
  hi: 'hi-IN',
  ml: 'ml-IN'
}

const interpolate = (text, values) => text.replace(/\{\{\s*(\w+)\s*\}\}/g, (match, key) => (
  Object.prototype.hasOwnProperty.call(values, key) ? String(values[key]) : match
))

export const LanguageProvider = ({ children }) => {
  const [language, setLanguageState] = useState(() => {
    const saved = localStorage.getItem('krushimitra_language')
    return translations[saved] ? saved : 'en'
  })

  const setLanguage = (lang) => {
    if (!translations[lang]) {
      throw new Error(`Unsupported language: ${lang}`)
    }
    setLanguageState(lang)
    localStorage.setItem('krushimitra_language', lang)
  }

  useEffect(() => {
    document.documentElement.lang = language
  }, [language])

  const t = (key, values = {}) => {
    const keys = key.split('.')
    let value = translations[language]
    for (const k of keys) {
      if (value && typeof value === 'object') {
        value = value[k]
      } else {
        break
      }
    }
    if (value === undefined || value === null || value === '') {
      if (import.meta.env.DEV && !reportedMissingKeys.has(`${language}:${key}`)) {
        reportedMissingKeys.add(`${language}:${key}`)
        console.warn(`Missing ${language} translation: ${key}`)
      }
      value = key.split('.').pop().replace(/([A-Z])/g, ' $1').replace(/[_-]/g, ' ').replace(/^\w/, (letter) => letter.toUpperCase())
    }

    if (value && typeof value === 'object') {
      const count = values.count
      if (Number.isFinite(Number(count))) {
        const category = new Intl.PluralRules(localeByLanguage[language]).select(Number(count))
        value = value[category] ?? value.other
      }
    }
    if (typeof value !== 'string' || !value.trim()) return key.split('.').pop().replace(/([A-Z])/g, ' $1').replace(/[_-]/g, ' ').replace(/^\w/, (letter) => letter.toUpperCase())
    return interpolate(value, values)
  }
  t.language = language

  const formatNumber = (value, options) => (
    new Intl.NumberFormat(localeByLanguage[language], options).format(value)
  )
  const formatCurrency = (value, currency = 'INR', options = {}) => (
    new Intl.NumberFormat(localeByLanguage[language], {
      style: 'currency',
      currency,
      ...options
    }).format(value)
  )
  const formatDate = (value, options) => (
    new Intl.DateTimeFormat(localeByLanguage[language], options).format(new Date(value))
  )

  return (
    <LanguageContext.Provider value={{
      language,
      locale: localeByLanguage[language],
      setLanguage,
      t,
      formatNumber,
      formatCurrency,
      formatDate
    }}>
      {children}
    </LanguageContext.Provider>
  )
}

export const useLanguage = () => {
  const context = useContext(LanguageContext)
  if (!context) {
    throw new Error('useLanguage must be used within a LanguageProvider')
  }
  return context
}

export default LanguageContext
