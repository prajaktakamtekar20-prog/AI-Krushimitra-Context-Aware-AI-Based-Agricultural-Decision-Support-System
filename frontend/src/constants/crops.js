import cropMaster from '../../../shared/crops.json'
import { localizeCrop, canonicalCrop } from '../translations/cropMarkets'

export const CROP_CATEGORIES = cropMaster

const cropEntries = CROP_CATEGORIES.flatMap(({ category, crops }) => (
  crops.map((crop) => ({ ...crop, category }))
))

const normalizeKey = (value) => String(value || '')
  .trim()
  .toLowerCase()
  .replace(/[()]/g, '')
  .replace(/[_-]+/g, ' ')
  .replace(/\s+/g, ' ')

const cropNamesByKey = new Map()
cropEntries.forEach((crop) => {
  ;[crop.value, crop.label, ...(crop.aliases || [])].forEach((name) => {
    cropNamesByKey.set(normalizeKey(name), crop)
  })
  if (crop.translationKey) cropNamesByKey.set(normalizeKey(crop.translationKey), crop)
})

const plantVillageValues = [
  'Apple', 'Blueberry', 'Cherry', 'Corn (Maize)', 'Grape', 'Orange', 'Peach',
  'Bell Pepper', 'Potato', 'Raspberry', 'Soybean', 'Squash', 'Strawberry', 'Tomato'
]

export const PLANTVILLAGE_CROPS = plantVillageValues.map((value) => {
  const crop = cropNamesByKey.get(normalizeKey(value))
  return { value: crop?.value || value, translationKey: crop?.translationKey || '' }
})

export const normalizePlantVillageCrop = (crop) => {
  const normalized = cropNamesByKey.get(normalizeKey(crop))
  return normalized?.value || canonicalCrop(typeof crop === 'string' ? crop.trim() : '')
}

export const plantVillageCropTranslationKey = (crop) => (
  cropNamesByKey.get(normalizeKey(crop))?.translationKey || ''
)

export const getCropOptions = (translate, cropNames) => {
  const allowedKeys = Array.isArray(cropNames)
    ? new Set(cropNames.map(normalizeKey))
    : null
  const options = CROP_CATEGORIES.flatMap(({ category, crops }) => (
    crops
      .filter((crop) => !allowedKeys || [crop.value, crop.label, ...(crop.aliases || [])]
        .some((name) => allowedKeys.has(normalizeKey(name))))
      .map((crop) => ({
        value: crop.value,
        label: translate
          ? localizeCrop(crop.value, translate.language)
          : crop.label,
        category: translate ? translate(`dropdowns.cropCategories.${category}`) : category
      }))
  ))

  if (!allowedKeys) return options

  const knownKeys = new Set(cropEntries.flatMap((crop) => (
    [crop.value, crop.label, ...(crop.aliases || [])].map(normalizeKey)
  )))
  const customOptions = [...new Map(cropNames
    .filter((name) => typeof name === 'string' && name.trim())
    .filter((name) => !knownKeys.has(normalizeKey(name)))
    .map((name) => [normalizeKey(name), {
      value: name.trim(),
      label: name.trim(),
      category: 'Saved Crops'
    }])).values()]
  return [...options, ...customOptions]
}

export const getPlantVillageCropOptions = (translate) => getCropOptions(translate)

export const getSupportedCropNames = (listedCrops = []) => {
  const uniqueCrops = new Map()
  ;[...cropEntries.map(({ value }) => value), ...listedCrops].forEach((crop) => {
    const value = normalizePlantVillageCrop(crop)
    const key = normalizeKey(value)
    if (key && !uniqueCrops.has(key)) uniqueCrops.set(key, value)
  })
  return [...uniqueCrops.values()].sort((a, b) => a.localeCompare(b))
}

export const translatePlantVillageCrop = (crop, translate) => {
  const language = translate?.language || 'en'
  return localizeCropName(crop, language)
}

export const localizeCropName = (crop, language = 'en') => {
  if (typeof crop !== 'string' || !crop.trim()) return crop || ''
  const normalized = cropNamesByKey.get(normalizeKey(crop))
  const canonical = normalized?.value || canonicalCrop(crop.trim())
  return localizeCrop(canonical, language) || crop
}
