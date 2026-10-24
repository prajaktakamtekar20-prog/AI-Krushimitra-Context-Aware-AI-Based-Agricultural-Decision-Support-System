import { normalizePlantVillageCrop } from '../constants/crops.js'

const normalizeText = (value) => String(value || '')
  .normalize('NFD')
  .replace(/[\u0300-\u036f]/g, '')
  .toLocaleLowerCase()
  .replace(/[^a-z0-9]+/g, ' ')
  .trim()

const getLocationFields = (product) => {
  const structuredLocation = product?.location_obj
  const hasStructuredLocation = structuredLocation && Object.values(structuredLocation).some(Boolean)
  const location = hasStructuredLocation ? structuredLocation : product?.location
  if (typeof location === 'string') {
    const parts = location.split(',').map((part) => part.trim()).filter(Boolean)
    if (parts.length >= 4) {
      const [village, taluka, district, state] = parts
      return { village, taluka, district, state }
    }
    if (parts.length === 3) {
      const [village, district, state] = parts
      return { village, taluka: '', district, state }
    }
    if (parts.length === 2) {
      const [district, state] = parts
      return { village: '', taluka: '', district, state }
    }
    return { village: parts[0] || '', taluka: '', district: '', state: '' }
  }
  if (!location || typeof location !== 'object') return {}
  return Object.fromEntries(['state', 'district', 'taluka', 'village']
    .map((field) => [field, String(location[field] || '').trim()]))
}

export const getProduceLocationOptions = (products, states = [], districts = []) => {
  const options = new Map()
  const addOption = (level, values, label) => {
    if (!values[0]) return
    const value = JSON.stringify({ level, values: values.map(normalizeText) })
    if (!options.has(value)) options.set(value, label)
  }

  states.forEach((state) => addOption('state', [state], state))
  districts.forEach((district) => addOption('district', [district], `${district} (District)`))

  products.forEach((product) => {
    const fields = getLocationFields(product)
    const levels = [
      { level: 'state', fields: ['state'], labelFields: ['state'], suffix: '' },
      { level: 'district', fields: ['district'], labelFields: ['district'], suffix: ' (District)' },
      { level: 'taluka', fields: ['taluka', 'district', 'state'], labelFields: ['taluka', 'district', 'state'], suffix: ' (Taluka)' },
      { level: 'village', fields: ['village', 'taluka', 'district', 'state'], labelFields: ['village', 'taluka', 'district', 'state'], suffix: '' }
    ]

    levels.forEach(({ level, fields: levelFields, labelFields, suffix }) => {
      const values = levelFields.map((field) => fields[field] || '')
      const label = `${labelFields.map((field) => fields[field]).filter(Boolean).join(', ')}${suffix}`
      addOption(level, values, label)
    })
  })
  return [...options].map(([value, label]) => ({ value, label }))
    .sort((a, b) => a.label.localeCompare(b.label))
}

const matchesLocation = (product, selection) => {
  if (!selection) return true
  const { level, values } = JSON.parse(selection)
  const fields = getLocationFields(product)
  const selectedFields = {
    state: ['state'],
    district: ['district'],
    taluka: ['taluka', 'district', 'state'],
    village: ['village', 'taluka', 'district', 'state']
  }[level]
  return selectedFields?.every((field, index) => (
    normalizeText(fields[field]) === values[index]
  )) || false
}

export const filterProduce = (products, { search = '', crop = '', location = '' } = {}) => {
  const normalizedCrop = normalizeText(normalizePlantVillageCrop(crop))
  const normalizedSearch = normalizeText(search)

  return products.filter((product) => {
    const productCrop = normalizeText(normalizePlantVillageCrop(product.crop))
    const productLocation = normalizeText(product.location)
    const farmerName = normalizeText(product.farmerName || product.farmer_name)
    const matchesCrop = !normalizedCrop || productCrop === normalizedCrop
    const matchesSelectedLocation = matchesLocation(product, location)
    const matchesSearch = !normalizedSearch || [productCrop, productLocation, farmerName]
      .some((value) => value.includes(normalizedSearch))

    return matchesCrop && matchesSelectedLocation && matchesSearch
  })
}