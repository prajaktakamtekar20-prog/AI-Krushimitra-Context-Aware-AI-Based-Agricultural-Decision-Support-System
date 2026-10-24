const unitLabels = {
  kg: { en: 'kg', mr: 'किलो', hi: 'किलोग्राम', ml: 'കിലോഗ്രാം' },
  quintal: { en: 'quintal', mr: 'क्विंटल', hi: 'क्विंटल', ml: 'ക്വിന്റൽ' },
  tonne: { en: 'tonne', mr: 'टन', hi: 'टन', ml: 'ടൺ' }
}

export const localizeUnit = (unit, language = 'en') => (
  unitLabels[String(unit || '').toLowerCase()]?.[language] || unit || ''
)

export const formatQuantity = (value, unit, language = 'en', formatNumber = null) => {
  const number = Number(value)
  const displayNumber = formatNumber
    ? formatNumber(number)
    : Number.isFinite(number) ? number.toLocaleString('en-IN') : value
  return `${displayNumber} ${localizeUnit(unit, language)}`.trim()
}

export const unitTranslations = unitLabels
