const cropImagePaths = {
  onion: '/assets/onion.jpg',
  rice: '/assets/rice.jpg',
  brinjal: '/assets/brinjal.jpg',
  eggplant: '/assets/brinjal.jpg',
  cabbage: '/assets/cabbage.jpg',
  soybean: '/assets/soyabean.jpg',
  soyabean: '/assets/soyabean.jpg',
  apple: '/assets/apple.jpg',
  jowar: '/assets/jowar.jpg',
  sorghum: '/assets/jowar.jpg',
  tomato: 'https://images.unsplash.com/photo-1546094096-0df4bcaaa337?auto=format&fit=crop&w=900&q=80',
  carrot: 'https://images.unsplash.com/photo-1445282768818-728615cc910a?auto=format&fit=crop&w=900&q=80',
  corn: '/assets/Maize.jpg',
  'corn maize': '/assets/Maize.jpg',
  maize: '/assets/Maize.jpg',
  wheat: 'https://images.unsplash.com/photo-1574323347407-f5e1ad6d020b?auto=format&fit=crop&w=900&q=80',
  grain: 'https://images.unsplash.com/photo-1574323347407-f5e1ad6d020b?auto=format&fit=crop&w=900&q=80',
  bajra: '/assets/bajra.jpg',
  'pearl millet': '/assets/bajra.jpg',
  chickpea: '/assets/chickpea%20beans.jpg',
  gram: '/assets/chickpea%20beans.jpg',
  chana: '/assets/chickpea%20beans.jpg',
  'pigeon pea': '/assets/pigeon%20pea.jpg',
  toor: '/assets/pigeon%20pea.jpg',
  arhar: '/assets/pigeon%20pea.jpg',
  'green gram': '/assets/green%20gram.jpg',
  moong: '/assets/green%20gram.jpg',
  'mung bean': '/assets/green%20gram.jpg',
  'black gram': '/assets/black%20gram.jpg',
  urad: '/assets/black%20gram.jpg',
  lentils: '/assets/lentils.jpg',
  masoor: '/assets/lentils.jpg',
  potato: '/assets/Potato.jpg',
  cauliflower: '/assets/cauliflower.jpg',
  okra: '/assets/okra.jpg',
  'lady finger': '/assets/okra.jpg',
  ladyfinger: '/assets/okra.jpg',
  'green chilli': '/assets/green%20chilli.jpg',
  'green chili': '/assets/green%20chilli.jpg',
  'bell pepper': '/assets/capsicum.jpg',
  capsicum: '/assets/capsicum.jpg',
  cucumber: '/assets/cucumber.jpg',
  spinach: '/assets/spinach.jpg',
  mango: '/assets/mango.jpg',
  banana: '/assets/banana.jpg',
  grape: '/assets/grapes.jpg',
  grapes: '/assets/grapes.jpg',
  pomegranate: '/assets/pomegranate.jpg',
  orange: '/assets/orange.jpg',
  papaya: '/assets/papaya.jpg',
  guava: '/assets/guava.jpg',
  watermelon: '/assets/watermelon.jpg',
  sugarcane: '/assets/sugarcane.jpg',
  cotton: '/assets/cotton.jpg',
  groundnut: '/assets/groundnut.jpg',
  peanut: '/assets/groundnut.jpg',
  sunflower: '/assets/sunflower.jpg',
  mustard: '/assets/musturd.jpg',
  turmeric: '/assets/turmeric.jpg',
  ginger: '/assets/ginger.jpg',
  garlic: '/assets/garlic.jpg',
  coriander: '/assets/coriander.jpg',
  cumin: '/assets/cumin.jpg',
  blueberry: '/assets/blueberry.jpg',
  cherry: '/assets/cherry.jpg',
  peach: '/assets/peach.jpg',
  raspberry: '/assets/raspberry.jpg',
  squash: '/assets/squash.jpg',
  strawberry: '/assets/strawberry.jpg',
}

const cropImagePositions = {
  onion: '48% center',
  brinjal: '28% center',
  soybean: '38% center',
  soyabean: '38% center',
}

export const CROP_IMAGE_FALLBACK = '/assets/farm-background.png'

const cropKey = (crop) => String(crop || '').trim().toLowerCase().replace(/[^a-z0-9]+/g, ' ').trim()

export const getCropImage = (crop) => {
  const key = cropKey(crop)
  return cropImagePaths[key] || null
}

export const getCropImagePosition = (crop) => {
  const key = cropKey(crop)
  return cropImagePositions[key] || 'center'
}
