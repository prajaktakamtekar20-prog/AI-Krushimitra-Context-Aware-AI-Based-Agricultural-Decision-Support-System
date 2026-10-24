const labels = {
  Maharashtra: ['Maharashtra', 'महाराष्ट्र', 'महाराष्ट्र', 'മഹാരാഷ്ട്ര'],
  Karnataka: ['Karnataka', 'कर्नाटक', 'कर्नाटक', 'കർണാടക'],
  'Madhya Pradesh': ['Madhya Pradesh', 'मध्य प्रदेश', 'मध्य प्रदेश', 'മധ്യപ്രദേശ്'],
  'Uttar Pradesh': ['Uttar Pradesh', 'उत्तर प्रदेश', 'उत्तर प्रदेश', 'ഉത്തർപ്രദേശ്'],
  Gujarat: ['Gujarat', 'गुजरात', 'गुजरात', 'ഗുജറാത്ത്'],
  Rajasthan: ['Rajasthan', 'राजस्थान', 'राजस्थान', 'രാജസ്ഥാൻ'],
  Punjab: ['Punjab', 'पंजाब', 'पंजाब', 'പഞ്ചാബ്'],
  Haryana: ['Haryana', 'हरियाणा', 'हरियाणा', 'ഹരിയാന'],
  'Tamil Nadu': ['Tamil Nadu', 'तामिळनाडू', 'तमिलनाडु', 'തമിഴ്നാട്'],
  Telangana: ['Telangana', 'तेलंगणा', 'तेलंगाना', 'തെലങ്കാന'],
  'Andhra Pradesh': ['Andhra Pradesh', 'आंध्र प्रदेश', 'आंध्र प्रदेश', 'ആന്ധ്രാപ്രദേശ്'],
  Bihar: ['Bihar', 'बिहार', 'बिहार', 'ബിഹാർ'],
  Odisha: ['Odisha', 'ओडिशा', 'ओडिशा', 'ഒഡീഷ'],
  Kerala: ['Kerala', 'केरळ', 'केरल', 'കേരളം'],
  Chhattisgarh: ['Chhattisgarh', 'छत्तीसगड', 'छत्तीसगढ़', 'ഛത്തീസ്ഗഢ്'],
  Pune: ['Pune', 'पुणे', 'पुणे', 'പൂനെ'],
  Nashik: ['Nashik', 'नाशिक', 'नासिक', 'നാസിക്'],
  Mumbai: ['Mumbai', 'मुंबई', 'मुंबई', 'മുംബൈ'],
  Nagpur: ['Nagpur', 'नागपूर', 'नागपुर', 'നാഗ്പൂർ'],
  Aurangabad: ['Aurangabad', 'औरंगाबाद', 'औरंगाबाद', 'ഔറംഗാബാദ്'],
  Ahmednagar: ['Ahmednagar', 'अहमदनगर', 'अहमदनगर', 'അഹമ്മദ്നഗർ'],
  Kolhapur: ['Kolhapur', 'कोल्हापूर', 'कोल्हापुर', 'കോലാപ്പൂർ'],
  Bawada: ['Bawada', 'बावडा', 'बावड़ा', 'ബാവഡ'],
  Karveer: ['Karveer', 'करवीर', 'करवीर', 'കർവീർ'],
  'Bawada, Karveer': ['Bawada, Karveer', 'बावडा, करवीर', 'बावड़ा, करवीर', 'ബാവഡ, കർവീർ'],
  'Gangai Lawn': ['Gangai Lawn', 'गंगाई लॉन', 'गंगाई लॉन', 'ഗംഗായി ലോൺ'],
  'Gangai Lawn, Bawda': ['Gangai Lawn, Bawda', 'गंगाई लॉन, बावडा', 'गंगाई लॉन, बावड़ा', 'ഗംഗായി ലോൺ, ബാവഡ'],
  Sangli: ['Sangli', 'सांगली', 'सांगली', 'സാംഗ്ലി'],
  Satara: ['Satara', 'सातारा', 'सातारा', 'സത്താറ'],
  Solapur: ['Solapur', 'सोलापूर', 'सोलापुर', 'സോലാപൂർ'],
  Ratnagiri: ['Ratnagiri', 'रत्नागिरी', 'रत्नागिरी', 'രത്നഗിരി'],
  Sindhudurg: ['Sindhudurg', 'सिंधुदुर्ग', 'सिंधुदुर्ग', 'സിന്ധുദുർഗ്'],
  Kapiltirth: ['Kapiltirth', 'कपिलतीर्थ', 'कपिलतीर्थ', 'കപിൽതീർഥ്'],
  Shahupuri: ['Shahupuri', 'शाहूपुरी', 'शाहूपुरी', 'ഷാഹുപുരി'],
  Laxmipuri: ['Laxmipuri', 'लक्ष्मीपुरी', 'लक्ष्मीपुरी', 'ലക്ഷ്മിപുരി'],
  India: ['India', 'भारत', 'भारत', 'ഇന്ത്യ']
}

const languageIndexes = { en: 0, mr: 1, hi: 2, ml: 3 }

const normalize = (value) => String(value || '').trim().toLowerCase().replace(/\s+/g, ' ')

const aliases = Object.keys(labels).reduce((result, key) => {
  labels[key].forEach((label) => { result[normalize(label)] = key })
  return result
}, {})

export const localizeLocation = (value, language = 'en') => {
  if (!value || typeof value !== 'string') return value || ''
  const canonical = aliases[normalize(value)]
  if (canonical) return labels[canonical][languageIndexes[language] ?? 0]
  const parts = value.split(',').map((part) => part.trim())
  if (parts.length > 1) return parts.map((part) => localizeLocation(part, language)).join(', ')
  return value
}

export const localizeLocationParts = (location, language = 'en') => (
  [location?.village, location?.taluka, location?.district, location?.state, location?.country]
    .filter(Boolean)
    .map((part) => localizeLocation(part, language))
)
