const crops = {
  Rice: ['Rice', 'भात', 'चावल', 'അരി'], Wheat: ['Wheat', 'गहू', 'गेहूँ', 'ഗോതമ്പ്'],
  'Corn (Maize)': ['Maize', 'मका', 'मक्का', 'ചോളം'], Jowar: ['Jowar', 'ज्वारी', 'ज्वार', 'ചോളം'],
  Bajra: ['Bajra', 'बाजरी', 'बाजरा', 'കമ്പ്'], Chickpea: ['Chickpea', 'हरभरा', 'चना', 'കടല'],
  'Pigeon Pea': ['Pigeon Pea', 'तूर', 'अरहर', 'തുവരപ്പരിപ്പ്'], 'Green Gram': ['Green Gram', 'मूग', 'मूंग', 'ചെറുപയർ'],
  'Black Gram': ['Black Gram', 'उडीद', 'उड़द', 'ഉഴുന്ന്'], Lentils: ['Lentils', 'मसूर', 'मसूर दाल', 'മസൂർപ്പരിപ്പ്'],
  Tomato: ['Tomato', 'टोमॅटो', 'टमाटर', 'തക്കാളി'], Onion: ['Onion', 'कांदा', 'प्याज़', 'സവാള'],
  Potato: ['Potato', 'बटाटा', 'आलू', 'ഉരുളക്കിഴങ്ങ്'], Brinjal: ['Brinjal', 'वांगी', 'बैंगन', 'വഴുതനങ്ങ'],
  Cabbage: ['Cabbage', 'कोबी', 'पत्तागोभी', 'കാബേജ്'], Cauliflower: ['Cauliflower', 'फुलकोबी', 'फूलगोभी', 'കോളിഫ്ലവർ'],
  Okra: ['Okra', 'भेंडी', 'भिंडी', 'വെണ്ടയ്ക്ക'], 'Green Chilli': ['Green Chilli', 'हिरवी मिरची', 'हरी मिर्च', 'പച്ചമുളക്'],
  'Bell Pepper': ['Capsicum', 'ढोबळी मिरची', 'शिमला मिर्च', 'കാപ്സിക്കം'], Cucumber: ['Cucumber', 'काकडी', 'खीरा', 'വെള്ളരിക്ക'],
  Spinach: ['Spinach', 'पालक', 'पालक', 'ചീര'], Mango: ['Mango', 'आंबा', 'आम', 'മാങ്ങ'],
  Banana: ['Banana', 'केळी', 'केला', 'വാഴപ്പഴം'], Grape: ['Grapes', 'द्राक्षे', 'अंगूर', 'മുന്തിരി'],
  Pomegranate: ['Pomegranate', 'डाळिंब', 'अनार', 'മാതളം'], Orange: ['Orange', 'संत्रे', 'संतरा', 'ഓറഞ്ച്'],
  Papaya: ['Papaya', 'पपई', 'पपीता', 'പപ്പായ'], Guava: ['Guava', 'पेरू', 'अमरूद', 'പേരയ്ക്ക'],
  Watermelon: ['Watermelon', 'कलिंगड', 'तरबूज', 'തണ്ണിമത്തൻ'], Sugarcane: ['Sugarcane', 'ऊस', 'गन्ना', 'കരിമ്പ്'],
  Cotton: ['Cotton', 'कापूस', 'कपास', 'പരുത്തി'], Soybean: ['Soybean', 'सोयाबीन', 'सोयाबीन', 'സോയാബീൻ'],
  Groundnut: ['Groundnut', 'भुईमूग', 'मूंगफली', 'നിലക്കടല'], Sunflower: ['Sunflower', 'सूर्यफूल', 'सूरजमुखी', 'സൂര്യകാന്തി'],
  Mustard: ['Mustard', 'मोहरी', 'सरसों', 'കടുക്'], Turmeric: ['Turmeric', 'हळद', 'हल्दी', 'മഞ്ഞൾ'],
  Ginger: ['Ginger', 'आले', 'अदरक', 'ഇഞ്ചി'], Garlic: ['Garlic', 'लसूण', 'लहसुन', 'വെളുത്തുള്ളി'],
  Coriander: ['Coriander', 'कोथिंबीर', 'धनिया', 'മല്ലിയില'], Cumin: ['Cumin', 'जिरे', 'जीरा', 'ജീരകം'],
  Apple: ['Apple', 'सफरचंद', 'सेब', 'ആപ്പിൾ'], Blueberry: ['Blueberry', 'ब्लूबेरी', 'ब्लूबेरी', 'ബ്ലൂബെറി'],
  Cherry: ['Cherry', 'चेरी', 'चेरी', 'ചെറി'], Peach: ['Peach', 'पीच', 'आड़ू', 'പീച്ച്'],
  Raspberry: ['Raspberry', 'रास्पबेरी', 'रास्पबेरी', 'റാസ്ബെറി'], Squash: ['Squash', 'स्क्वॅश', 'स्क्वैश', 'സ്ക്വാഷ്'],
  Strawberry: ['Strawberry', 'स्ट्रॉबेरी', 'स्ट्रॉबेरी', 'സ്ട്രോബെറി']
}

const markets = [
  'Kapiltirth Market', 'Shahupuri Market', 'Kolhapur APMC', 'Laxmipuri Market',
  'Sangli Market', 'Miraj Market', 'Tasgaon Market', 'Islampur Market', 'Vita Market',
  'Satara Market', 'Karad Market', 'Phaltan Market', 'Wai Market', 'Man Market',
  'Ratnagiri APMC', 'Chiplun APMC', 'Khed APMC', 'Dapoli APMC', 'Rajapur APMC',
  'Sawantwadi APMC', 'Malvan APMC', 'Vengurla APMC', 'Kudal APMC', 'Sindhudurg APMC',
  'Pune APMC (Market Yard)', 'Pimpri-Chinchwad APMC', 'Baramati APMC', 'Junnar APMC', 'Indapur APMC',
  'Navi Mumbai APMC (Vashi)', 'Mumbai Wholesale Market', 'Bhiwandi APMC', 'Thane APMC', 'Kalyan APMC',
  'Nashik APMC', 'Sinnar APMC', 'Malegaon APMC', 'Niphad APMC', 'Nagpur APMC',
  'Aurangabad APMC', 'Paithan APMC', 'Gangapur APMC', 'Vaijapur APMC',
  'Ahmednagar APMC', 'Shrirampur APMC', 'Rahuri APMC', 'Sangamner APMC', 'Pathardi APMC'
]

const normalize = (value) => String(value || '').trim().toLowerCase().replace(/[()]/g, '').replace(/[-_]/g, ' ').replace(/\s+/g, ' ')
const placeNames = {
  Pune: ['Pune', 'पुणे', 'पुणे', 'പൂനെ'], Nashik: ['Nashik', 'नाशिक', 'नासिक', 'നാസിക്'],
  Mumbai: ['Mumbai', 'मुंबई', 'मुंबई', 'മുംബൈ'], Navi: ['Navi', 'नवी', 'नवी', 'നവി'],
  Kolhapur: ['Kolhapur', 'कोल्हापूर', 'कोल्हापुर', 'കോലാപ്പൂർ'], Sangli: ['Sangli', 'सांगली', 'सांगली', 'സാംഗ്ലി'],
  Miraj: ['Miraj', 'मिरज', 'मिरज', 'മിറജ്'], Tasgaon: ['Tasgaon', 'तासगाव', 'तासगांव', 'താസ്ഗാവ്'],
  Islampur: ['Islampur', 'इस्लामपूर', 'इस्लामपुर', 'ഇസ്ലാംപൂർ'], Vita: ['Vita', 'विटा', 'विटा', 'വിറ്റ'],
  Satara: ['Satara', 'सातारा', 'सातारा', 'സത്താറ'], Karad: ['Karad', 'कराड', 'कराड', 'കരാട്'],
  Phaltan: ['Phaltan', 'फलटण', 'फलटण', 'ഫൽട്ടൺ'], Wai: ['Wai', 'वाई', 'वाई', 'വായ്'],
  Man: ['Man', 'माण', 'माण', 'മാൻ'], Ratnagiri: ['Ratnagiri', 'रत्नागिरी', 'रत्नागिरी', 'രത്നഗിരി'],
  Chiplun: ['Chiplun', 'चिपळूण', 'चिपलून', 'ചിപ്ലൂൺ'], Khed: ['Khed', 'खेड', 'खेड़', 'ഖേഡ്'],
  Dapoli: ['Dapoli', 'दापोली', 'दापोली', 'ദാപോളി'], Rajapur: ['Rajapur', 'राजापूर', 'राजापुर', 'രാജാപൂർ'],
  Sawantwadi: ['Sawantwadi', 'सावंतवाडी', 'सावंतवाड़ी', 'സാവന്ത്‌വാടി'], Malvan: ['Malvan', 'मालवण', 'मालवण', 'മാൽവൻ'],
  Vengurla: ['Vengurla', 'वेंगुर्ला', 'वेंगुर्ला', 'വെങ്കുർല'], Kudal: ['Kudal', 'कुडाळ', 'कुडाल', 'കുടാൽ'],
  Sindhudurg: ['Sindhudurg', 'सिंधुदुर्ग', 'सिंधुदुर्ग', 'സിന്ധുദുർഗ്'], Pimpri: ['Pimpri-Chinchwad', 'पिंपरी-चिंचवड', 'पिंपरी-चिंचवड़', 'പിംപ്രി-ചിഞ്ച്‌വഡ്'],
  Baramati: ['Baramati', 'बारामती', 'बारामती', 'ബാരാമതി'], Junnar: ['Junnar', 'जुन्नर', 'जुन्नर', 'ജുന്നർ'],
  Indapur: ['Indapur', 'इंदापूर', 'इंदापुर', 'ഇന്ദാപൂർ'], Nagpur: ['Nagpur', 'नागपूर', 'नागपुर', 'നാഗ്പൂർ'],
  Aurangabad: ['Aurangabad', 'औरंगाबाद', 'औरंगाबाद', 'ഔറംഗാബാദ്'], Paithan: ['Paithan', 'पैठण', 'पैठन', 'പൈഠൺ'],
  Gangapur: ['Gangapur', 'गंगापूर', 'गंगापुर', 'ഗംഗാപൂർ'], Vaijapur: ['Vaijapur', 'वैजापूर', 'वैजापुर', 'വൈജാപൂർ'],
  Ahmednagar: ['Ahmednagar', 'अहमदनगर', 'अहमदनगर', 'അഹമ്മദ്നഗർ'], Shrirampur: ['Shrirampur', 'श्रीरामपूर', 'श्रीरामपुर', 'ശ്രീരാംപൂർ'],
  Rahuri: ['Rahuri', 'राहुरी', 'राहुरी', 'റാഹുരി'], Sangamner: ['Sangamner', 'संगमनेर', 'संगमनेर', 'സംഗംനേർ'],
  Pathardi: ['Pathardi', 'पाथर्डी', 'पाथर्डी', 'പാഥർഡി'], Sinnar: ['Sinnar', 'सिन्नर', 'सिन्नर', 'സിന്നർ'],
  Malegaon: ['Malegaon', 'मालेगाव', 'मालेगांव', 'മാലേഗാവ്'], Niphad: ['Niphad', 'निफाड', 'निफाड', 'നിഫാഡ്'],
  Bhiwandi: ['Bhiwandi', 'भिवंडी', 'भिवंडी', 'ഭിവണ്ടി'], Thane: ['Thane', 'ठाणे', 'ठाणे', 'താനെ'],
  Kalyan: ['Kalyan', 'कल्याण', 'कल्याण', 'കല്യാൺ']
}
const localizedPlace = (name, language) => placeNames[name]?.[{ en: 0, mr: 1, hi: 2, ml: 3 }[language] ?? 0] || name
const cropEntries = Object.entries(crops)
const cropMap = new Map(cropEntries.flatMap(([canonical, labels]) => labels.concat(canonical).map((label) => [normalize(label), { canonical, labels }])))

const marketMap = new Map(markets.map((market) => {
  const base = market.replace(/\s+(APMC|Market)$/i, '').replace(/\s+\(Market Yard\)$/i, '')
  const city = base.split(' ')[0]
  const localized = {
    mr: `${localizedPlace(city, 'mr')} बाजार`, hi: `${localizedPlace(city, 'hi')} मंडी`, ml: `${localizedPlace(city, 'ml')} ചന്ത`
  }
  return [normalize(market), { canonical: market, labels: { en: market, ...localized } }]
}))
const requestedMarketLabels = {
  'Kapiltirth Market': { en: 'Kapiltirth', mr: 'कपिलतीर्थ', hi: 'कपिलतीर्थ', ml: 'കപിൽതീർഥ്' },
  'Shahupuri Market': { en: 'Shahupuri', mr: 'शाहूपुरी', hi: 'शाहूपुरी', ml: 'ഷാഹുപുരി' },
  'Laxmipuri Market': { en: 'Laxmipuri', mr: 'लक्ष्मीपुरी', hi: 'लक्ष्मीपुरी', ml: 'ലക്ഷ്മിപുരി' }
}
Object.entries(requestedMarketLabels).forEach(([market, labels]) => {
  const entry = marketMap.get(normalize(market))
  if (entry) {
    marketMap.set(normalize(market), { ...entry, labels })
    marketMap.set(normalize(market.replace(/\s+Market$/i, '')), { ...entry, labels })
  }
})

export const localizeCrop = (value, language = 'en') => {
  const entry = cropMap.get(normalize(value))
  return entry ? entry.labels[{ en: 0, mr: 1, hi: 2, ml: 3 }[language] ?? 0] : value
}

const varietyLabels = {
  desi: { en: 'Desi', mr: 'देशी', hi: 'देसी', ml: 'നാടൻ' }
}
export const localizeVariety = (value, language = 'en') => {
  if (!value || typeof value !== 'string') return value || ''
  const entry = varietyLabels[normalize(value)]
  return entry?.[language] || value
}

export const canonicalCrop = (value) => cropMap.get(normalize(value))?.canonical || value
export const localizeMarket = (value, language = 'en') => marketMap.get(normalize(value))?.labels[language] || value
export const canonicalMarket = (value) => marketMap.get(normalize(value))?.canonical || value
export const localizedCropEntries = crops
export const supportedMarkets = markets
