import { existsSync, readFileSync } from 'node:fs'
import { getCropImage, CROP_IMAGE_FALLBACK } from '../src/constants/cropImages.js'
import { en } from '../src/translations/en.js'
import { mr } from '../src/translations/mr.js'
import { hi } from '../src/translations/hi.js'
import { ml } from '../src/translations/ml.js'
import { diseaseResultLanguages, localizeDiseaseResult } from '../src/pages/diseaseResultLocalization.js'
import { localizedCropEntries, supportedMarkets, localizeCrop, localizeMarket, localizeVariety } from '../src/translations/cropMarkets.js'
import { brand, localizeDisplayName } from '../src/translations/brand.js'
import { localizeLocation } from '../src/translations/locations.js'
import { localizeUnit, formatQuantity } from '../src/translations/units.js'

const dictionaries = { en, mr, hi, ml }
if (Object.keys(dictionaries).join(',') !== 'en,mr,hi,ml') {
  throw new Error('The application must support exactly English, Marathi, Hindi, and Malayalam.')
}
const flatten = (value, prefix = '') => Object.entries(value).reduce((result, [key, child]) => {
  const path = prefix ? `${prefix}.${key}` : key
  if (child && typeof child === 'object' && !Array.isArray(child)) return { ...result, ...flatten(child, path) }
  result[path] = child
  return result
}, {})

const flattened = Object.fromEntries(Object.entries(dictionaries).map(([language, dictionary]) => [language, flatten(dictionary)]))
const expected = new Set(Object.keys(flattened.en))
const failures = []
const cropCatalogue = JSON.parse(
  readFileSync(new URL('../../shared/crops.json', import.meta.url), 'utf8')
)
const cropEntries = cropCatalogue.flatMap((category) => category.crops)
const permanentCropNames = new Set(cropEntries.map((crop) => crop.value))
const profileSource = readFileSync(new URL('../src/pages/MyProfile.jsx', import.meta.url), 'utf8')
const cropOptionsSource = readFileSync(new URL('../src/constants/crops.js', import.meta.url), 'utf8')
if (
  !profileSource.includes('getPlantVillageCropOptions(t)')
  || !cropOptionsSource.includes('export const getPlantVillageCropOptions = (translate) => getCropOptions(translate)')
) {
  failures.push('crop catalogue: profile dropdown is no longer populated from the permanent crop master')
}
for (const crop of cropEntries) {
  if (!permanentCropNames.has(crop.value)) {
    failures.push(`crop catalogue: ${crop.value} is missing from the permanent profile dropdown`)
  }
  const image = getCropImage(crop.value)
  if (!image) {
    failures.push(`crop image: no image mapping exists for catalogue crop ${crop.value}`)
    continue
  }
  if (image === CROP_IMAGE_FALLBACK) {
    failures.push(`crop image: ${crop.value} uses the generic background as its crop mapping`)
  }
  if (image.startsWith('/assets/') && !existsSync(new URL(`../public${image}`, import.meta.url))) {
    failures.push(`crop image: mapped asset does not exist for ${crop.value}: ${image}`)
  }
}
for (const [crop, image] of Object.entries({
  'Corn (Maize)': '/assets/Maize.jpg',
  Lentils: '/assets/lentils.jpg',
  Rice: '/assets/rice.jpg',
  Apple: '/assets/apple.jpg',
  'Bell Pepper': '/assets/capsicum.jpg'
})) {
  if (getCropImage(crop) !== image) failures.push(`crop image: incorrect ${crop} mapping`)
}
const expectedLocalCropImages = {
  Rice: '/assets/rice.jpg',
  'Corn (Maize)': '/assets/Maize.jpg',
  Jowar: '/assets/jowar.jpg',
  Bajra: '/assets/bajra.jpg',
  Chickpea: '/assets/chickpea%20beans.jpg',
  'Pigeon Pea': '/assets/pigeon%20pea.jpg',
  'Green Gram': '/assets/green%20gram.jpg',
  'Black Gram': '/assets/black%20gram.jpg',
  Lentils: '/assets/lentils.jpg',
  Onion: '/assets/onion.jpg',
  Potato: '/assets/Potato.jpg',
  Brinjal: '/assets/brinjal.jpg',
  Cabbage: '/assets/cabbage.jpg',
  Cauliflower: '/assets/cauliflower.jpg',
  Okra: '/assets/okra.jpg',
  'Green Chilli': '/assets/green%20chilli.jpg',
  'Bell Pepper': '/assets/capsicum.jpg',
  Cucumber: '/assets/cucumber.jpg',
  Spinach: '/assets/spinach.jpg',
  Mango: '/assets/mango.jpg',
  Banana: '/assets/banana.jpg',
  Grape: '/assets/grapes.jpg',
  Pomegranate: '/assets/pomegranate.jpg',
  Orange: '/assets/orange.jpg',
  Papaya: '/assets/papaya.jpg',
  Guava: '/assets/guava.jpg',
  Watermelon: '/assets/watermelon.jpg',
  Sugarcane: '/assets/sugarcane.jpg',
  Cotton: '/assets/cotton.jpg',
  Soybean: '/assets/soyabean.jpg',
  Groundnut: '/assets/groundnut.jpg',
  Sunflower: '/assets/sunflower.jpg',
  Mustard: '/assets/musturd.jpg',
  Turmeric: '/assets/turmeric.jpg',
  Ginger: '/assets/ginger.jpg',
  Garlic: '/assets/garlic.jpg',
  Coriander: '/assets/coriander.jpg',
  Cumin: '/assets/cumin.jpg',
  Apple: '/assets/apple.jpg',
  Blueberry: '/assets/blueberry.jpg',
  Cherry: '/assets/cherry.jpg',
  Peach: '/assets/peach.jpg',
  Raspberry: '/assets/raspberry.jpg',
  Squash: '/assets/squash.jpg',
  Strawberry: '/assets/strawberry.jpg'
}
for (const [crop, image] of Object.entries(expectedLocalCropImages)) {
  if (getCropImage(crop) !== image) failures.push(`crop image: expected ${image} for ${crop}`)
}
for (const crop of ['Corn (Maize)', 'Lentils', 'Potato']) {
  if (!permanentCropNames.has(crop)) {
    failures.push(`crop catalogue: ${crop} disappeared from the master dropdown`)
  }
}
const sharedDiseaseTranslations = JSON.parse(
  readFileSync(new URL('../../shared/disease_result_translations.json', import.meta.url), 'utf8')
)
const modelClasses = JSON.parse(
  readFileSync(new URL('../../backend/models/class_names.json', import.meta.url), 'utf8')
)
if (modelClasses.length !== 38 || !modelClasses.includes('Corn_(maize)___Cercospora_leaf_spot Gray_leaf_spot')) {
  failures.push('disease: classifier source must retain all 38 canonical classes including Gray Leaf Spot')
}
const severityKeys = [
  'Mild (None)', 'Mild', 'Mild to Moderate', 'Moderate', 'Moderate to Severe', 'Severe'
]
for (const language of Object.keys(dictionaries)) {
  const labels = sharedDiseaseTranslations[language].severityLabels
  if (
    !labels
    || Object.keys(labels).length !== severityKeys.length
    || severityKeys.some((severity) => !labels[severity]?.trim())
  ) {
    failures.push(`disease: incomplete ${language} severity translations`)
  }
  const disclaimer = sharedDiseaseTranslations[language].diagnosticDisclaimer
  if (typeof disclaimer !== 'string' || !disclaimer.trim()) {
    failures.push(`disease: missing ${language} complete diagnostic disclaimer`)
  }
}
const diseaseUiKeys = [
  'title', 'subtitle', 'uploadSection', 'dragOrClick', 'supportedFormats',
  'onlyImages', 'selectImageFirst', 'detectBtn', 'analyzing', 'detectionFailed',
  'invalidImageFile', 'imageTooLarge', 'imagePreviewFailed', 'backendUnavailable',
  'modelUnavailable', 'unsupportedCropTitle', 'lowQualityTitle', 'invalidImageTitle',
  'imageProcessingUnavailable', 'detectionUnableTitle', 'retryAnalysis',
  'imagePreviewAlt', 'removeImage', 'supportedCrops', 'unsupportedCropHelp',
  'imageDimensions', 'imageSize', 'tipsTitle', 'tip1', 'tip2', 'tip3', 'tip4',
  'tip5', 'resultPlaceholder', 'resultPlaceholderHint', 'aiThinking',
  'aiThinkingHint', 'detected', 'confidence', 'cropLabel', 'diseaseLabel',
  'confidenceLabel', 'cropConfidenceLabel', 'severityLabel', 'severitySevere',
  'severityModerate', 'severityMildModerate', 'severityModerateSevere', 'severityMild', 'severityNone', 'nonPlantImage',
  'nonPlantExplanation', 'uncertain', 'diagnosticNote', 'preliminaryResult',
  'uncertainExplanation', 'typicalSymptomsNotice', 'symptomsUnavailable',
  'informationUnavailable', 'symptoms', 'causes', 'treatment', 'prevention',
  'safetyWarnings', 'warnings', 'precautions',
  'translationUnavailable', 'retryTranslation', 'translatingDiagnosis',
  'testAnother', 'askAssistant'
]
for (const language of Object.keys(dictionaries)) {
  for (const key of diseaseUiKeys) {
    const value = dictionaries[language].disease?.[key]
    if (typeof value !== 'string' || !value.trim()) {
      failures.push(`${language}: missing or empty disease.${key}`)
    }
  }
}
if (diseaseResultLanguages.join(',') !== 'en,mr,hi,ml') {
  failures.push(`disease result resources must cover exactly en,mr,hi,ml; found ${diseaseResultLanguages.join(',')}`)
}
for (const language of Object.keys(dictionaries)) {
  if (
    !dictionaries[language].disease.translationUnavailable
    || !dictionaries[language].disease.retryTranslation
    || !dictionaries[language].disease.translatingDiagnosis
  ) {
    failures.push(`${language}: missing localized diagnosis translation loading, failure, or retry text`)
  }
}

const expectedUnits = {
  kg: ['kg', 'किलो', 'किलोग्राम', 'കിലോഗ്രാം'],
  quintal: ['quintal', 'क्विंटल', 'क्विंटल', 'ക്വിന്റൽ'],
  tonne: ['tonne', 'टन', 'टन', 'ടൺ']
}
for (const [unit, labels] of Object.entries(expectedUnits)) {
  for (const [index, language] of ['en', 'mr', 'hi', 'ml'].entries()) {
    if (localizeUnit(unit, language) !== labels[index]) failures.push(`unit: incorrect ${unit}/${language}`)
  }
}
if (formatQuantity(10, 'kg', 'mr') !== '10 किलो' || formatQuantity(20, 'kg', 'ml') !== '20 കിലോഗ്രാം') {
  failures.push('unit: quantity display localization failed')
}
if (flattened.hi['marketplace.pricePerKg'] !== 'प्रति किलोग्राम कीमत (₹)') {
  failures.push('unit: Hindi price-per-kg label is incorrect')
}
const requiredOrderKeys = [
  'ordersEyebrow', 'ordersTitle', 'ordersPrivacy', 'orderTotal', 'orderPartner',
  'mobile', 'mobileUnavailable', 'call', 'whatsapp', 'email', 'openChat',
  'markInProgress', 'markCompleted', 'statusPending', 'statusAccepted',
  'statusRejected', 'statusInProgress', 'statusCompleted', 'statusCancelled',
  'noOrders', 'incomingOrdersEmpty', 'outgoingOrdersEmpty'
]
for (const language of ['en', 'mr', 'hi', 'ml']) {
  for (const key of requiredOrderKeys) {
    const value = flattened[language][`marketplace.${key}`]
    if (!value || value === key) failures.push(`orders: missing ${language}.${key}`)
  }
}

const expectedLocations = {
  Maharashtra: ['Maharashtra', 'महाराष्ट्र', 'महाराष्ट्र', 'മഹാരാഷ്ട്ര'],
  Kolhapur: ['Kolhapur', 'कोल्हापूर', 'कोल्हापुर', 'കോലാപ്പൂർ'],
  'Bawada, Karveer': ['Bawada, Karveer', 'बावडा, करवीर', 'बावड़ा, करवीर', 'ബാവഡ, കർവീർ'],
  'Gangai Lawn': ['Gangai Lawn', 'गंगाई लॉन', 'गंगाई लॉन', 'ഗംഗായി ലോൺ'],
  'Gangai Lawn, Bawda': ['Gangai Lawn, Bawda', 'गंगाई लॉन, बावडा', 'गंगाई लॉन, बावड़ा', 'ഗംഗായി ലോൺ, ബാവഡ']
}
for (const [location, labels] of Object.entries(expectedLocations)) {
  for (const [index, language] of ['en', 'mr', 'hi', 'ml'].entries()) {
    if (localizeLocation(location, language) !== labels[index]) failures.push(`location: incorrect ${location}/${language}`)
  }
}
if (localizeLocation('Kolhapur, Maharashtra', 'mr') !== 'कोल्हापूर, महाराष्ट्र') {
  failures.push('location: composite display localization failed')
}
if (localizeLocation('Bawada', 'mr') !== 'बावडा' || localizeLocation('Karveer', 'ml') !== 'കർവീർ') {
  failures.push('location: structured Bawada/Karveer localization failed')
}
if (localizeLocation('18.5204, 73.8567', 'mr') !== '18.5204, 73.8567') {
  failures.push('location: coordinate preservation failed')
}

const expectedBrand = {
  en: ['AI KrushiMitra', 'Prajakta Kamtekar'],
  mr: ['एआय कृषिमित्र', 'प्राजक्ता कामतेकर'],
  hi: ['एआई कृषिमित्र', 'प्राजक्ता कामतेकर'],
  ml: ['എഐ കൃഷിമിത്ര', 'പ്രാജക്ത കാംതേക്കർ']
}
for (const [language, [projectName, ownerName]] of Object.entries(expectedBrand)) {
  if (brand[language].projectName !== projectName || brand[language].ownerName !== ownerName) {
    failures.push(`brand: incorrect ${language} project or owner name`)
  }
  if (flattened[language]['brand.projectName'] !== projectName || flattened[language]['brand.ownerName'] !== ownerName) {
    failures.push(`brand: dictionary registration failed for ${language}`)
  }
  if (localizeDisplayName('Prajakta Kamtekar', language) !== ownerName) {
    failures.push(`brand: dynamic owner display failed for ${language}`)
  }
  const participantName = {
    en: 'Akanksha Mane',
    mr: 'आकांक्षा माने',
    hi: 'आकांक्षा माने',
    ml: 'അകാംക്ഷ മാനെ'
  }[language]
  if (localizeDisplayName('Akanksha Mane', language) !== participantName) {
    failures.push(`brand: dynamic participant display failed for ${language}`)
  }
}

for (const [crop, labels] of Object.entries(localizedCropEntries)) {
  if (labels.length !== 4 || labels.some((label) => !label.trim())) failures.push(`crop: incomplete mapping ${crop}`)
}
for (const market of supportedMarkets) {
  for (const language of ['en', 'mr', 'hi', 'ml']) {
    if (!localizeMarket(market, language)?.trim()) failures.push(`market: incomplete mapping ${market}/${language}`)
  }
}
if (localizeCrop('Tomato', 'mr') !== 'टोमॅटो' || localizeCrop('Tomato', 'ml') !== 'തക്കാളി') {
  failures.push('crop: canonical localization failed for Tomato')
}
const expectedVariety = { en: 'Desi', mr: 'देशी', hi: 'देसी', ml: 'നാടൻ' }
for (const [language, label] of Object.entries(expectedVariety)) {
  if (localizeVariety('desi', language) !== label || localizeVariety(label, language) !== label) {
    failures.push(`variety: incorrect desi label ${language}`)
  }
}
if (localizeVariety('Custom Variety', 'ml') !== 'Custom Variety') {
  failures.push('variety: custom value was unexpectedly translated')
}
const expectedListingCrops = {
  Wheat: ['Wheat', 'गहू', 'गेहूँ', 'ഗോതമ്പ്'],
  Onion: ['Onion', 'कांदा', 'प्याज़', 'സവാള'],
  Rice: ['Rice', 'भात', 'चावल', 'അരി'],
  Brinjal: ['Brinjal', 'वांगी', 'बैंगन', 'വഴുതനങ്ങ'],
  Cabbage: ['Cabbage', 'कोबी', 'पत्तागोभी', 'കാബേജ്'],
  Soybean: ['Soybean', 'सोयाबीन', 'सोयाबीन', 'സോയാബീൻ'],
  Apple: ['Apple', 'सफरचंद', 'सेब', 'ആപ്പിൾ'],
  Jowar: ['Jowar', 'ज्वारी', 'ज्वार', 'ചോളം'],
  'Corn (Maize)': ['Maize', 'मका', 'मक्का', 'ചോളം'],
  Wheat: ['Wheat', 'गहू', 'गेहूँ', 'ഗോതമ്പ്'],
  Tomato: ['Tomato', 'टोमॅटो', 'टमाटर', 'തക്കാളി']
}
for (const [crop, labels] of Object.entries(expectedListingCrops)) {
  for (const [index, language] of ['en', 'mr', 'hi', 'ml'].entries()) {
    if (localizeCrop(crop, language) !== labels[index]) failures.push(`crop: incorrect listing label ${crop}/${language}`)
    if (localizeCrop(labels[index], language) !== labels[index]) failures.push(`crop: localized alias failed ${crop}/${language}`)
  }
}
const expectedCategories = {
  Cereals: ['Cereals', 'तृणधान्ये', 'अनाज', 'ധാന്യങ്ങൾ'],
  'Cash Crops': ['Cash Crops', 'नगदी पिके', 'नकदी फसलें', 'നാണ്യവിളകൾ'],
  Pulses: ['Pulses', 'कडधान्ये', 'दलहन', 'പയർവർഗങ്ങൾ'],
  Vegetables: ['Vegetables', 'भाजीपाला', 'सब्ज़ियाँ', 'പച്ചക്കറികൾ'],
  Fruits: ['Fruits', 'फळे', 'फल', 'പഴങ്ങൾ'],
  Spices: ['Spices', 'मसाले', 'मसाले', 'സുഗന്ധവ്യഞ്ജനങ്ങൾ'],
  'Other Local Crops': ['Other Local Crops', 'इतर स्थानिक पिके', 'अन्य स्थानीय फसलें', 'മറ്റ് പ്രാദേശിക വിളകൾ']
}
for (const [category, labels] of Object.entries(expectedCategories)) {
  for (const [index, language] of ['en', 'mr', 'hi', 'ml'].entries()) {
    if (flattened[language][`dropdowns.cropCategories.${category}`] !== labels[index]) {
      failures.push(`category: incorrect ${category}/${language}`)
    }
  }
}
for (const [market, labels] of Object.entries({
  Kapiltirth: ['Kapiltirth', 'कपिलतीर्थ', 'कपिलतीर्थ', 'കപിൽതീർഥ്'],
  Shahupuri: ['Shahupuri', 'शाहूपुरी', 'शाहूपुरी', 'ഷാഹുപുരി'],
  Laxmipuri: ['Laxmipuri', 'लक्ष्मीपुरी', 'लक्ष्मीपुरी', 'ലക്ഷ്മിപുരി']
})) {
  for (const [index, language] of ['en', 'mr', 'hi', 'ml'].entries()) {
    if (localizeMarket(`${market} Market`, language) !== labels[index]) failures.push(`market: incorrect ${market}/${language}`)
  }
}

for (const [language, dictionary] of Object.entries(flattened)) {
  for (const key of expected) {
    if (!(key in dictionary) || dictionary[key] === undefined || dictionary[key] === null || dictionary[key] === '') {
      failures.push(`${language}: missing or blank ${key}`)
    }
  }
}

const marketplaceKeys = Object.keys(flattened.en).filter((key) => key.startsWith('marketplace.'))
if (marketplaceKeys.length < 50) failures.push(`marketplace: expected at least 50 localized interface keys, found ${marketplaceKeys.length}`)

const maizeRust = { crop: 'Corn (Maize)', disease: 'Common Rust of Maize (Puccinia sorghi)', symptoms: ['English symptom'] }
for (const language of Object.keys(dictionaries)) {
  const localized = localizeDiseaseResult(maizeRust, language)
  if (!localized.disease_display || localized.symptoms?.[0] === 'English symptom') {
    failures.push(`${language}: maize disease result was not localized`)
  }
}

const graySource = sharedDiseaseTranslations.en.grayLeafSpot
const diseasePageRenderSource = readFileSync(
  new URL('../src/pages/Disease.jsx', import.meta.url),
  'utf8'
)
for (const [field, label] of [
  ['safety_warnings', 'disease.safetyWarnings'],
  ['warnings', 'disease.warnings'],
  ['precautions', 'disease.precautions']
]) {
  if (!diseasePageRenderSource.includes(`['${field}', '${label}']`)) {
    failures.push(`disease page: ${field} is not rendered with its localized label`)
  }
}
const grayDiagnosis = {
  crop: graySource.crop,
  disease: graySource.disease,
  disease_key: 'corn_leaf_spot',
  raw_class: 'Corn_(maize)___Cercospora_leaf_spot Gray_leaf_spot',
  severity: graySource.severity,
  symptoms: graySource.symptoms,
  possible_causes: graySource.causes,
  recommended_management: graySource.treatment,
  prevention: graySource.prevention,
  diagnostic_note: graySource.diagnosticNote,
  safety_warnings: [graySource.safetyWarning],
  confidence: 96,
  crop_confidence: 99
}
const completeDisclaimerDiagnosis = {
  ...grayDiagnosis,
  diagnostic_note: "The visual analysis agrees with the local classifier's supported crop/disease class. Confidence values are model scores, not calibrated probabilities. Chemical instructions are omitted unless verified against current local product labels. This is a preliminary image-model result, not a confirmed diagnosis. Model scores are not calibrated probabilities; ask an agricultural expert to confirm, especially before taking treatment action."
}
for (const language of Object.keys(dictionaries)) {
  const localized = localizeDiseaseResult(completeDisclaimerDiagnosis, language)
  const expectedDisclaimer = sharedDiseaseTranslations[language].diagnosticDisclaimer
  if (localized.diagnostic_note !== expectedDisclaimer) {
    failures.push(`disease: complete diagnostic disclaimer was not localized for ${language}`)
  }
  if (localized._untranslated_fields?.includes('diagnostic_note')) {
    failures.push(`disease: diagnostic disclaimer remains marked untranslated for ${language}`)
  }
  if (language !== 'en' && /The visual analysis agrees|Confidence values are model scores|Chemical instructions are omitted|This is a preliminary image-model result/i.test(localized.diagnostic_note)) {
    failures.push(`disease: English disclaimer fallback remains in ${language}`)
  }
}
const grayCounts = { symptoms: 4, causes: 4, treatment: 4, prevention: 5 }
const grayNumberTokens = ['1-4 mm', '12-24+', '22-30°C', '14-21', '1-2', '250 EC']
for (const language of Object.keys(dictionaries)) {
  const localized = localizeDiseaseResult(grayDiagnosis, language)
  const expectedGray = sharedDiseaseTranslations[language].grayLeafSpot
  const bullets = {
    symptoms: localized.symptoms,
    causes: localized.possible_causes,
    treatment: localized.recommended_management,
    prevention: localized.prevention
  }
  for (const [field, count] of Object.entries(grayCounts)) {
    if (!Array.isArray(bullets[field]) || bullets[field].length !== count || bullets[field].some((line) => !line.trim())) {
      failures.push(`gray leaf spot: invalid ${language}.${field} bullet list`)
    }
  }
  for (const [field, value] of Object.entries({
    crop: localized.crop_display,
    disease: localized.disease_display,
    severity: localized.severity,
    symptoms: localized.symptoms,
    causes: localized.possible_causes,
    treatment: localized.recommended_management,
    prevention: localized.prevention,
    diagnosticNote: localized.diagnostic_note,
    safetyWarning: localized.safety_warnings?.[0]
  })) {
    if (JSON.stringify(value) !== JSON.stringify(expectedGray[field])) {
      failures.push(`gray leaf spot: incomplete ${language}.${field}`)
    }
  }
  if (localized.confidence !== 96 || localized.crop_confidence !== 99 || localized.translation_complete !== true) {
    failures.push(`gray leaf spot: confidence or completeness changed for ${language}`)
  }
  if (language !== 'en') {
    const allBullets = Object.values(bullets).flat().join(' ')
    const scriptPattern = language === 'ml' ? /[\u0d00-\u0d7f]/ : /[\u0900-\u097f]/
    if (Object.values(bullets).flat().some((bullet) => !scriptPattern.test(bullet))) {
      failures.push(`gray leaf spot: ${language} includes untranslated or broken-script bullets`)
    }
    if (/\b(?:lesions|tank-mix|tassel(?:ing)?\/silking|GLS-resistant)\b/i.test(allBullets)) {
      failures.push(`gray leaf spot: ${language} includes untranslated English prose`)
    }
    for (const token of grayNumberTokens) {
      if (!allBullets.includes(token)) failures.push(`gray leaf spot: ${language} changed numeric value ${token}`)
    }
    if (!localized.disease_display.includes('Cercospora zeae-maydis')) {
      failures.push(`gray leaf spot: ${language} did not preserve the scientific name`)
    }
  }
}

for (const language of ['mr', 'hi', 'ml']) {
  const localized = localizeDiseaseResult({
    crop: 'Corn (Maize)',
    disease: 'Common Rust of Maize (Puccinia sorghi)',
    disease_key: 'corn_rust'
  }, language)
  const prose = [
    ...(localized.treatment || []),
    ...(localized.prevention || [])
  ].join(' ')
  if (/\b(?:tassel(?:ing)?\/silking|tassel stage)\b/i.test(prose)) {
    failures.push(`common rust: ${language} includes untranslated crop-stage prose`)
  }
}

const missingGrayNote = localizeDiseaseResult({
  ...grayDiagnosis,
  diagnostic_note: 'Visible evidence not in the verified translation source.'
}, 'hi')
if (
  missingGrayNote.diagnostic_note !== 'Visible evidence not in the verified translation source.'
  || !missingGrayNote.translation_notice?.includes('निदान टिप्पणी')
  || !missingGrayNote._untranslated_fields.includes('diagnostic_note')
) {
  failures.push('gray leaf spot: unverified diagnosis-note text was not preserved and marked')
}

const diseasePageSource = readFileSync(new URL('../src/pages/Disease.jsx', import.meta.url), 'utf8')
const languageSwitcherSource = readFileSync(new URL('../src/components/LanguageSwitcher.jsx', import.meta.url), 'utf8')
if (
  !diseasePageSource.includes('[language, result, resultLanguage, t, translationAttempt]')
  || !diseasePageSource.includes('diseaseApi.translateResult(result, language)')
  || !diseasePageSource.includes('setLocalizedResult(localResult)')
  || !languageSwitcherSource.includes('value={language}')
  || !languageSwitcherSource.includes('setLanguage(event.target.value)')
) {
  failures.push('disease: language selector no longer relocalizes a displayed diagnosis and falls back locally')
}

if (failures.length) {
  console.error(failures.join('\n'))
  process.exit(1)
}

console.log(`Translation validation passed: ${Object.keys(dictionaries).length} languages, ${expected.size} UI keys, ${marketplaceKeys.length} marketplace keys, and all Gray Leaf Spot fields.`)
