export const brand = {
  en: { projectName: 'AI KrushiMitra', ownerName: 'Prajakta Kamtekar' },
  mr: { projectName: 'एआय कृषिमित्र', ownerName: 'प्राजक्ता कामतेकर' },
  hi: { projectName: 'एआई कृषिमित्र', ownerName: 'प्राजक्ता कामतेकर' },
  ml: { projectName: 'എഐ കൃഷിമിത്ര', ownerName: 'പ്രാജക്ത കാംതേക്കർ' }
}

export const localizeDisplayName = (value, language = 'en') => {
  if (typeof value !== 'string') return value
  const normalized = value.trim().toLocaleLowerCase()
  if (normalized === 'prajakta kamtekar' || normalized === 'प्राजक्ता कामतेकर' || normalized === 'പ്രാജക്ത കാംതേക്കർ') {
    return brand[language]?.ownerName || value
  }
  if (normalized === 'akanksha mane' || normalized === 'आकांक्षा माने' || normalized === 'അകാംക്ഷ മാനെ') {
    return {
      en: 'Akanksha Mane',
      mr: 'आकांक्षा माने',
      hi: 'आकांक्षा माने',
      ml: 'അകാംക്ഷ മാനെ'
    }[language] || value
  }
  return value
}
