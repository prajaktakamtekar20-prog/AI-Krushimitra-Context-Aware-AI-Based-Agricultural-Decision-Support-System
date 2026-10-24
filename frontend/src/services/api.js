import axios from 'axios'

export const getApiErrorMessage = (error, fallback = 'Request failed. Please try again.') => {
  const detail = error?.response?.data?.detail ?? error?.response?.data?.message
  if (Array.isArray(detail)) {
    return detail.map((item) => item?.msg).filter(Boolean).join(' ')
  }
  if (typeof detail === 'string') return detail
  if (typeof detail?.message === 'string') return detail.message
  if (error?.code === 'ECONNABORTED' || error?.code === 'ETIMEDOUT') {
    return 'The request timed out while contacting the server. Please try again.'
  }
  if (error?.code === 'ERR_NETWORK' || (!error?.response && error?.request)) {
    const apiAddress = configuredApiBaseUrl || 'the current frontend origin'
    return `Cannot reach the backend at ${apiAddress}. Confirm the API server is running and allows requests from this frontend.`
  }
  return error?.message || fallback
}

const WEATHER_CODE_ICONS = {
  0: { icon: '☀️', desc: 'Clear Sky' },
  1: { icon: '🌤️', desc: 'Mainly Clear' },
  2: { icon: '⛅', desc: 'Partly Cloudy' },
  3: { icon: '☁️', desc: 'Overcast' },
  45: { icon: '🌫️', desc: 'Foggy' },
  48: { icon: '🌫️', desc: 'Depositing Rime Fog' },
  51: { icon: '🌦️', desc: 'Light Drizzle' },
  53: { icon: '🌦️', desc: 'Moderate Drizzle' },
  55: { icon: '🌧️', desc: 'Dense Drizzle' },
  61: { icon: '🌧️', desc: 'Slight Rain' },
  63: { icon: '🌧️', desc: 'Moderate Rain' },
  65: { icon: '🌧️', desc: 'Heavy Rain' },
  71: { icon: '🌨️', desc: 'Slight Snow' },
  73: { icon: '🌨️', desc: 'Moderate Snow' },
  75: { icon: '❄️', desc: 'Heavy Snow' },
  80: { icon: '🌦️', desc: 'Rain Showers' },
  81: { icon: '🌧️', desc: 'Moderate Showers' },
  82: { icon: '⛈️', desc: 'Violent Showers' },
  95: { icon: '⛈️', desc: 'Thunderstorm' },
  96: { icon: '⛈️', desc: 'Thunderstorm w/ Hail' },
  99: { icon: '⛈️', desc: 'Thunderstorm w/ Heavy Hail' },
}

function weatherInfo(code, t) {
  if (code === null || code === undefined || code === '' || !Number.isFinite(Number(code))) {
    return { icon: '🌡️', desc: null, code: null }
  }
  const c = Number(code)
  let normalized = c
  if (!WEATHER_CODE_ICONS[normalized]) {
    if (c <= 3) normalized = 2
    else if (c <= 48) normalized = 45
    else if (c <= 65) normalized = 63
    else if (c <= 75) normalized = 73
    else if (c <= 82) normalized = 80
    else normalized = 95
  }
  const fallback = WEATHER_CODE_ICONS[normalized]
  return {
    ...fallback,
    desc: t?.(`weather.conditions.${normalized}`) || fallback.desc,
    code: normalized
  }
}

const configuredApiBaseUrl = import.meta.env.VITE_API_BASE_URL?.trim().replace(/\/+$/, '')
const DISEASE_DETECTION_TIMEOUT_MS = 30_000
const DISEASE_TRANSLATION_TIMEOUT_MS = 45_000

const api = axios.create({
  baseURL: import.meta.env.DEV
    ? '/api'
    : configuredApiBaseUrl
      ? `${configuredApiBaseUrl}/api`
      : '/api',
  headers: {
    'Content-Type': 'application/json'
  },
  timeout: 60000
})

api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('krushimitra_token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    const lang = localStorage.getItem('krushimitra_language')
    if (lang) {
      config.headers['X-Language'] = lang
    }
    return config
  },
  (error) => Promise.reject(error)
)

api.interceptors.response.use(
  (response) => response.data,
  (error) => {
    if (error.response?.status === 401) {
      const currentPath = typeof window !== 'undefined' ? window.location.pathname : ''
      const authAttemptPaths = ['/auth/login', '/auth/register', '/auth/google', '/auth/logout']
      const requestUrl = error.config?.url || ''
      const isAuthAttempt = authAttemptPaths.some((path) => requestUrl.includes(path))
      const authorization = error.config?.headers?.Authorization
        ?? error.config?.headers?.authorization
        ?? error.config?.headers?.get?.('Authorization')
      const requestToken = typeof authorization === 'string'
        ? authorization.replace(/^Bearer\s+/i, '')
        : ''
      const isCurrentSessionRequest = requestToken
        && requestToken === localStorage.getItem('krushimitra_token')
      if (!isAuthAttempt && isCurrentSessionRequest) {
        localStorage.removeItem('krushimitra_token')
        localStorage.removeItem('krushimitra_user')
        const publicPaths = ['/', '/language-selection', '/login', '/register']
        const isPublic = publicPaths.some(p => currentPath === p || currentPath.startsWith(p + '/'))
        if (typeof window !== 'undefined' && !isPublic) window.location.href = '/login'
      }
    }
    return Promise.reject(error)
  }
)

export const authApi = {
  register: (data) => api.post('/auth/register', data, { timeout: 20000 }),
  login: (data) => api.post('/auth/login', data),
  me: () => api.get('/auth/me'),
  googleLogin: (data) => api.post('/auth/google', data, {
    headers: { 'X-Requested-With': 'XmlHttpRequest' }
  }),
  logout: () => {
    const token = localStorage.getItem('krushimitra_token')
    return api.post('/auth/logout', null, {
      headers: token ? { Authorization: `Bearer ${token}` } : {}
    })
  }
}

export const farmerApi = {
  getProfile: async () => {
    try {
      return await api.get('/farmer/profile')
    } catch (err) {
      if (err.response?.status === 404) return null
      throw err
    }
  },
  createProfile: (data) => api.post('/farmer/profile', data),
  updateProfile: (data) => api.put('/farmer/profile', data)
}

export const marketplaceApi = {
  getBuyerProfile: () => api.get('/marketplace/profile'),
  saveBuyerProfile: (data) => api.put('/marketplace/profile', data),
  getDashboard: () => api.get('/marketplace/dashboard'),
  getProduce: ({ crop = '', location = '', category = '' } = {}) => {
    const params = new URLSearchParams()
    Object.entries({ crop, location, category }).forEach(([key, value]) => {
      if (value !== '' && value !== null && value !== undefined) params.set(key, String(value))
    })
    return api.get(`/marketplace/produce${params.size ? `?${params.toString()}` : ''}`)
  },
  getMyProduce: () => api.get('/marketplace/produce/mine'),
  createProduce: (data) => api.post('/marketplace/produce', data),
  updateProduce: (id, data) => api.put(`/marketplace/produce/${id}`, data),
  removeProduce: (id) => api.delete(`/marketplace/produce/${id}`),
  getFarmers: (filters = {}) => {
    const params = new URLSearchParams()
    Object.entries(filters).forEach(([key, value]) => {
      if (value !== '' && value !== null && value !== undefined) params.set(key, String(value))
    })
    return api.get(`/marketplace/farmers${params.size ? `?${params.toString()}` : ''}`)
  },
  getPublicFarmerProfile: (id) => api.get(`/marketplace/farmers/${id}`),
  createFarmerOrderRequest: (farmerId, data) => api.post(`/marketplace/farmers/${farmerId}/order-requests`, data),
  createListingOrder: (listingId, data) => api.post(`/marketplace/produce/${listingId}/orders`, data),
  decideListingOrder: (orderId, decision) => api.post(`/marketplace/listing-orders/${orderId}/decision?decision=${encodeURIComponent(decision)}`),
  cancelListingOrder: (orderId) => api.post(`/marketplace/listing-orders/${orderId}/cancel`),
  getNotifications: () => api.get('/marketplace/notifications'),
  markNotificationRead: (id) => api.post(`/marketplace/notifications/${id}/read`),
  getConversations: () => api.get('/marketplace/conversations'),
  getOrderMessages: (orderId) => api.get(`/marketplace/orders/${orderId}/messages`),
  sendOrderMessage: (orderId, message, metadata = {}) => api.post(`/marketplace/orders/${orderId}/messages`, { message, ...metadata }),
  deleteOrderMessage: (orderId, messageId, scope) => api.delete(`/marketplace/orders/${orderId}/messages/${messageId}`, { data: { scope } }),
  getRequirements: (filters = {}) => {
    const params = new URLSearchParams()
    Object.entries(filters).forEach(([key, value]) => {
      if (value !== '' && value !== null && value !== undefined) params.set(key, String(value))
    })
    return api.get(`/marketplace/requirements${params.size ? `?${params.toString()}` : ''}`)
  },
  createRequirement: (data) => api.post('/marketplace/requirements', data),
  updateRequirement: (id, data) => api.put(`/marketplace/requirements/${id}`, data),
  cancelRequirement: (id) => api.post(`/marketplace/requirements/${id}/cancel`),
  submitOffer: (id, data) => api.post(`/marketplace/requirements/${id}/offers`, data),
  getRequirementOffers: (id) => api.get(`/marketplace/requirements/${id}/offers`),
  decideOffer: (requirementId, offerId, decision) => api.post(`/marketplace/requirements/${requirementId}/offers/${offerId}/${decision}`),
  getOrders: () => api.get('/marketplace/orders'),
  getOrder: (id) => api.get(`/marketplace/orders/${id}`),
  updateOrderStatus: (id, nextStatus) => api.post(`/marketplace/orders/${id}/status?next_status=${encodeURIComponent(nextStatus)}`)
}

export const weatherApi = {
  getWeather: async (lat, lon, crop, stage, t) => {
    const params = new URLSearchParams()
    params.set('lat', String(lat))
    params.set('lon', String(lon))
    if (crop) params.set('crop', crop)
    if (stage) params.set('stage', stage)
    const res = await api.get(`/weather?${params.toString()}`)
    if (!res?.current) throw new Error('Weather provider returned an incomplete forecast.')
    const wi = weatherInfo(res.current.weather_code, t)
    const current = {
      temp: res.current.temperature,
      humidity: res.current.humidity,
      rainfall: res.current.precipitation,
      wind_speed: res.current.wind_speed,
      wind_direction: res.current.wind_direction,
      wind_gusts: res.current.wind_gusts,
      rain_probability: (res.hourly || []).slice(0, 12)
        .map((hour) => hour.rain_prob)
        .filter(Number.isFinite)
        .reduce((maximum, value) => Math.max(maximum, value), null),
      feels_like: res.current.apparent_temperature,
      pressure: res.current.pressure,
      description: wi.desc,
      weather_code: wi.code,
      icon: wi.icon,
    }
    const forecast = (res.forecast || []).map((day) => {
      const info = weatherInfo(day.weather_code, t)
      return {
        ...day,
        day: day.date
          ? new Intl.DateTimeFormat(undefined, { weekday: 'short' }).format(new Date(`${day.date}T12:00:00`))
          : null,
        temp_max: day.temp_max,
        temp_min: day.temp_min,
        icon: info.icon,
        condition: info.desc,
        weather_code: info.code,
        rain_prob: day.rain_prob_max,
        rainfall: day.precipitation_sum,
      }
    })
    const hourly = (res.hourly || []).map((hour) => {
      const info = weatherInfo(hour.weather_code, t)
      return { ...hour, icon: info.icon, condition: info.desc }
    })
    return { ...res, current, forecast, hourly }
  },
  searchLocations: async (query) => {
    const params = new URLSearchParams({ query })
    const result = await api.get(`/weather/search?${params.toString()}`)
    return result?.results || []
  }
}

export const assistantApi = {
  chat: async (message, context, language, history = []) => {
    const lang = language || localStorage.getItem('krushimitra_language') || 'en'
    try {
      return await api.post(
        '/assistant/chat',
        { message, context: context || null, history },
        { headers: { 'X-Language': lang } }
      )
    } catch (err) {
      console.warn('assistant.chat fallback:', err.message)
      throw err
    }
  },
  streamChat: async (message, context, language, history = [], onEvent) => {
    const lang = language || localStorage.getItem('krushimitra_language') || 'en'
    const token = localStorage.getItem('krushimitra_token')
    const controller = new AbortController()
    const timeoutId = setTimeout(() => controller.abort(), 65000)
    try {
      const response = await fetch(`${api.defaults.baseURL}/assistant/chat/stream`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Language': lang,
          ...(token ? { Authorization: `Bearer ${token}` } : {})
        },
        body: JSON.stringify({ message, context: context || null, history }),
        signal: controller.signal
      })
      if (!response.ok) {
        let detail = ''
        let errorCode
        try {
          const errorBody = await response.json()
          detail = errorBody?.detail || errorBody?.message || ''
          errorCode = errorBody?.code
        } catch {
          // Use the HTTP status when the server does not return JSON.
        }
        const error = new Error(detail || `AI assistant request failed (${response.status}).`)
        error.code = errorCode
        throw error
      }
      if (!response.body) throw new Error('The backend did not provide a streaming response.')

      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      const processEvent = (rawEvent) => {
        const data = rawEvent
          .split(/\r?\n/)
          .filter((line) => line.startsWith('data:'))
          .map((line) => line.slice(5).trim())
          .join('\n')
        if (!data) return
        const event = JSON.parse(data)
        if (event.type === 'error') {
          const error = new Error(event.detail || 'The AI provider could not complete the request.')
          error.code = event.code
          throw error
        }
        onEvent?.(event)
      }

      while (true) {
        const { value, done } = await reader.read()
        buffer += decoder.decode(value || new Uint8Array(), { stream: !done })
        const events = buffer.split(/\r?\n\r?\n/)
        buffer = events.pop() || ''
        events.forEach(processEvent)
        if (done) break
      }
      if (buffer.trim()) processEvent(buffer)
    } catch (error) {
      if (controller.signal.aborted) {
        throw new Error('The AI assistant request timed out. Please try again.')
      }
      throw error
    } finally {
      clearTimeout(timeoutId)
    }
  },
  translateHistory: async (messages, language) => {
    return api.post(
      '/assistant/translate-history',
      { messages },
      { headers: { 'X-Language': language } }
    )
  },
}

const marketPriceCache = new Map()
const marketPriceRequests = new Map()
const marketPriceListeners = new Map()
const MARKET_PRICE_CACHE_TTL_MS = 60_000
const MARKET_PRICE_CACHE_MAX_ENTRIES = 64

const marketPriceRequestUrl = (crop, district, market) => {
  const params = new URLSearchParams()
  params.set('crop', crop || 'tomato')
  if (district) params.set('district', district)
  if (market) params.set('market', market)
  return `/market/prices?${params.toString()}`
}

const marketPriceCacheKey = (crop, district, market) => (
  [crop || 'tomato', district || '', market || '']
    .map((value) => value.trim().replace(/\s+/g, ' ').toLocaleLowerCase())
    .join('|')
)

const notifyMarketPriceListeners = (key, data) => {
  marketPriceListeners.get(key)?.forEach((listener) => listener(data))
}

const requestMarketPrices = (url) => api.get(url, { timeout: 12_000 })

const refreshMarketPriceCache = async (key, url, attempt = 0) => {
  try {
    const result = await requestMarketPrices(url)
    if (result?.cache?.stale && attempt < 3) {
      await new Promise((resolve) => window.setTimeout(resolve, 1500))
      return refreshMarketPriceCache(key, url, attempt + 1)
    }
    marketPriceCache.set(key, { data: result, storedAt: Date.now() })
    notifyMarketPriceListeners(key, result)
    while (marketPriceCache.size > MARKET_PRICE_CACHE_MAX_ENTRIES) {
      marketPriceCache.delete(marketPriceCache.keys().next().value)
    }
  } catch (error) {
    console.warn('Market price background refresh failed:', error.message)
  }
}

const startMarketPriceBackgroundRefresh = (key, url) => {
  if (marketPriceRequests.has(key)) return
  const refresh = refreshMarketPriceCache(key, url)
  marketPriceRequests.set(key, refresh)
  refresh.finally(() => {
    if (marketPriceRequests.get(key) === refresh) marketPriceRequests.delete(key)
  })
}

export const marketApi = {
  getMarkets: (district) => api.get(`/market/markets?${new URLSearchParams({ district })}`, { timeout: 5000 }),
  subscribeToMarketPrices: (crop, district, market, listener) => {
    const key = marketPriceCacheKey(crop || 'tomato', district, market)
    const listeners = marketPriceListeners.get(key) || new Set()
    listeners.add(listener)
    marketPriceListeners.set(key, listeners)
    return () => {
      listeners.delete(listener)
      if (!listeners.size) marketPriceListeners.delete(key)
    }
  },
  getMarketPrices: async (crop, district, market) => {
    const key = marketPriceCacheKey(crop || 'tomato', district, market)
    const url = marketPriceRequestUrl(crop, district, market)
    const cached = marketPriceCache.get(key)
    if (cached) {
      if (Date.now() - cached.storedAt >= MARKET_PRICE_CACHE_TTL_MS) {
        startMarketPriceBackgroundRefresh(key, url)
        return {
          ...cached.data,
          cache: {
            status: 'client-stale',
            stale: true,
            last_updated: cached.data?.cache?.last_updated || cached.data?.last_updated || null
          }
        }
      }
      return {
        ...cached.data,
        cache: {
          status: 'client-hit',
          stale: false,
          last_updated: cached.data?.cache?.last_updated || cached.data?.last_updated || null
        }
      }
    }

    const existingRequest = marketPriceRequests.get(key)
    if (existingRequest) return existingRequest

    const request = requestMarketPrices(url).then((result) => {
      marketPriceCache.set(key, { data: result, storedAt: Date.now() })
      notifyMarketPriceListeners(key, result)
      if (result?.cache?.stale) {
        window.setTimeout(() => startMarketPriceBackgroundRefresh(key, url), 1500)
      }
      return result
    }).finally(() => marketPriceRequests.delete(key))
    marketPriceRequests.set(key, request)
    return request
  }
}

export const diseaseApi = {
  detectDisease: async (formData, language) => {
    try {
      const res = await api.post('/disease/detect', formData, {
        headers: {
          'Content-Type': undefined,
          'X-Language': language || localStorage.getItem('krushimitra_language') || 'en'
        },
        timeout: DISEASE_DETECTION_TIMEOUT_MS
      })
      return res
    } catch (err) {
      console.warn('detectDisease API error (backend may not be running):', err.message)
      throw err
    }
  },
  translateResult: (result, language) => api.post(
    '/disease/translate',
    { result },
    {
      headers: { 'X-Language': language || localStorage.getItem('krushimitra_language') || 'en' },
      timeout: DISEASE_TRANSLATION_TIMEOUT_MS
    }
  )
}

const DEMO_SCHEMES = [
  { id: 'pm-kisan', official_name: 'Pradhan Mantri Kisan Samman Nidhi (PM-KISAN)', department: 'Ministry of Agriculture & Farmers Welfare', government_level: 'central', states: ['all'], categories: ['farmer_support','income_support'], crops: ['all'], benefit_types: ['direct_benefit_transfer'], benefits_summary: 'Income support of ₹6,000 per year to eligible farmer families in three equal instalments of ₹2,000.', required_documents: [{id:'aadhaar',name:'Aadhaar',status:'typically_mandatory',why:'Identity and DBT authentication on the official portal.'},{id:'land_record',name:'Land ownership record (7/12 extract / Record of Rights)',status:'typically_mandatory',why:'PM-KISAN is linked to cultivable land records.'},{id:'bank_passbook',name:'Bank passbook / cancelled cheque',status:'typically_mandatory',why:'Benefit is transferred via DBT to a linked bank account.'},{id:'photo',name:'Passport-size photograph',status:'conditional',why:'May be requested during CSC or state registration.'}], application_steps: [{step:1,title:'Check eligibility',detail:'Confirm you are a farmer family with cultivable land and not in an exclusion category.',verified:true},{step:2,title:'Gather documents',detail:'Keep Aadhaar, land record, and bank passbook ready. Never share OTP or banking password.',verified:true},{step:3,title:'Open official portal',detail:'Use https://pmkisan.gov.in only. Beware of lookalike websites.',verified:true},{step:4,title:'Register on government site',detail:'Use Farmer Corner. Authentication happens on the government website, not here.',verified:true},{step:5,title:'Locate registration form',detail:'Follow Farmer Corner links. Use portal help if unsure.',verified:false},{step:6,title:'Enter farmer and land details',detail:'Fill name, Aadhaar, bank, and land details exactly as in official records.',verified:true},{step:7,title:'Upload documents if asked',detail:'Upload only on the official site or at an authorised CSC.',verified:true},{step:8,title:'Review and submit',detail:'Check every field before submit. State/district officials verify records.',verified:true},{step:9,title:'Save acknowledgement',detail:'Note the registration/acknowledgement number shown by the portal.',verified:true},{step:10,title:'Check status',detail:'Use Beneficiary Status on pmkisan.gov.in. Follow up with State Nodal Officer if payment is pending.',verified:true}], official_application_url: 'https://pmkisan.gov.in', last_verified: '2026-10-09', verification_status: 'official_url_verified', source_notes: 'Taken from official PM-KISAN portal. Final eligibility decided by the government.' },
  { id: 'pmfby', official_name: 'Pradhan Mantri Fasal Bima Yojana (PMFBY)', department: 'Ministry of Agriculture & Farmers Welfare', government_level: 'central', states: ['all'], categories: ['crop_insurance'], crops: ['notified'], benefit_types: ['insurance'], benefits_summary: 'Crop insurance cover against notified yield losses, prevented sowing, mid-season adversity, and post-harvest losses where notified by the state.', required_documents: [{id:'aadhaar',name:'Aadhaar',status:'typically_mandatory',why:'Farmer identification on National Crop Insurance Portal.'},{id:'land_record',name:'Land record or tenancy proof accepted by the state',status:'typically_mandatory',why:'Enrolment linked to notified survey numbers or tenancy evidence.'},{id:'bank_passbook',name:'Bank account details',status:'typically_mandatory',why:'Claims paid by DBT. Provide only on official portal or bank.'},{id:'sowing_proof',name:'Sowing / crop details',status:'conditional',why:'Required to enrol correct notified crop and area.'}], application_steps: [{step:1,title:'Check notification',detail:'Open pmfby.gov.in and check current season notification for your state, district, crop, and cut-off date.',verified:true},{step:2,title:'Gather documents before cut-off',detail:'Do not miss the seasonal cut-off. Late applications are usually rejected.',verified:true},{step:3,title:'Open NCIP / PMFBY website',detail:'Use https://pmfby.gov.in or the National Crop Insurance Portal linked there.',verified:true},{step:4,title:'Sign in on the government portal',detail:'Never type the portal password or OTP into AI-KrushiMitra.',verified:true},{step:5,title:'Find farmer enrolment',detail:'Use the farmer application / enrolment section for the current season.',verified:false},{step:6,title:'Enter crop, survey, and bank details',detail:'Select notified crop and area exactly as in the notification.',verified:true},{step:7,title:'Upload documents',detail:'Upload land/tenancy and identity documents if the portal asks.',verified:true},{step:8,title:'Pay farmer share of premium',detail:'Pay only through official portal/bank channels. Premium rates are season-specific.',verified:true},{step:9,title:'Save policy / application number',detail:'Download or note the acknowledgement and policy details.',verified:true},{step:10,title:'Track claims',detail:'Use application status / claim status on the portal. Yield-based claims follow crop-cutting experiments.',verified:true}], official_application_url: 'https://pmfby.gov.in', last_verified: '2026-10-09', verification_status: 'official_url_verified', source_notes: 'Official portal pmfby.gov.in. Enrolment is not automatic and not guaranteed by this matcher.' },
  { id: 'kisan-credit-card', official_name: 'Kisan Credit Card (KCC)', department: 'Department of Financial Services / NABARD / Scheduled Banks', government_level: 'central', states: ['all'], categories: ['credit','farmer_support'], crops: ['all'], benefit_types: ['credit'], benefits_summary: 'Short-term credit for cultivation, post-harvest, and farm-related needs through banks, with interest subvention as notified by GoI.', required_documents: [{id:'identity',name:'Aadhaar or other KYC identity proof accepted by the bank',status:'typically_mandatory',why:'Banks must complete KYC.'},{id:'land_record',name:'Land record or tenancy evidence accepted by the bank',status:'typically_mandatory',why:'Used to assess scale of finance.'},{id:'photo',name:'Photographs',status:'typically_mandatory',why:'Bank account / card issuance KYC.'}], application_steps: [{step:1,title:'Confirm you need crop credit',detail:'KCC is a bank product, not an automatic government grant.',verified:true},{step:2,title:'Collect KYC and land/tenancy papers',detail:'Banks publish their own checklist. This app cannot replace the bank form.',verified:true},{step:3,title:'Use official bank channels',detail:'Visit your bank, or use https://www.jansamarth.in if your bank offers KCC there.',verified:true},{step:4,title:'Sign in only on the bank/Jan Samarth site',detail:'Never enter net-banking password or OTP in AI-KrushiMitra.',verified:true},{step:5,title:'Locate KCC application',detail:'Ask the branch agricultural officer or use the bank agri-loan section.',verified:false},{step:6,title:'Fill crop, land, and finance details',detail:'The bank calculates the credit limit.',verified:true},{step:7,title:'Submit KYC documents to the bank',detail:'Upload only on the bank portal or submit physical copies at the branch.',verified:true},{step:8,title:'Review sanction terms',detail:'Read interest, charges, and repayment before accepting.',verified:true},{step:9,title:'Keep sanction letter / account number',detail:'Store bank acknowledgement safely.',verified:true},{step:10,title:'Follow up with the same bank',detail:'Status is with the lending bank, not this app.',verified:true}], official_application_url: 'https://www.jansamarth.in', last_verified: '2026-10-09', verification_status: 'official_url_verified', source_notes: 'NABARD and Jan Samarth are official references. Individual bank circulars govern sanction.' },
  { id: 'pmksy', official_name: 'Pradhan Mantri Krishi Sinchayee Yojana (PMKSY)', department: 'Ministry of Agriculture & Farmers Welfare / Department of Water Resources', government_level: 'central', states: ['all'], categories: ['irrigation','infrastructure','subsidy'], crops: ['all'], benefit_types: ['capital_subsidy'], benefits_summary: 'Per-drop-more-crop support: micro-irrigation (drip/sprinkler), water storage, command area development, and watershed interventions with component-wise subsidy as per State Irrigation Plan.', required_documents: [{id:'aadhaar',name:'Aadhaar',status:'typically_mandatory',why:'Farmer identification and DBT.'},{id:'land_record',name:'Land record (survey number-wise)',status:'typically_mandatory',why:'Works are sanctioned per plot / command area.'},{id:'bank_passbook',name:'Bank passbook',status:'typically_mandatory',why:'Subsidy disbursement via DBT.'},{id:'project_report',name:'Estimate / project report from approved vendor or department',status:'conditional',why:'Required for structural or large drip/sprinkler components.'}], application_steps: [{step:1,title:'Check whether component is open in your district',detail:'PMKSY has multiple components (PDMC, WDC-PMKSY, CADWM, Har Khet Ko Pani). Open state/department portal or meet the Agricultural/DAEO office.',verified:true},{step:2,title:'Understand subsidy percentage and cap',detail:'Subsidy ceilings and categories (SC/ST/small/marginal/general) are notified per component and state.',verified:true},{step:3,title:'Prepare land and bank documents',detail:'Keep plot-wise survey details and bank passbook ready.',verified:true},{step:4,title:'Contact block horticulture / agriculture office',detail:'Many applications are routed through DAEO/ADA or block office with a sanctioned vendor list.',verified:true},{step:5,title:'Locate online application portal',detail:'Some states use https://www.myscheme.gov.in or state-specific portals such as Krishi Maharashtra.',verified:false},{step:6,title:'Fill application with plot and component details',detail:'Specify drip/sprinkler/storage or watershed component as applicable.',verified:true},{step:7,title:'Get estimate from approved vendor or department',detail:'Verify vendor is on the approved list before paying any advance.',verified:true},{step:8,title:'Submit application and documents',detail:'On official portal or at the block office. Retain a dated receipt.',verified:true},{step:9,title:'After sanction: install work and get inspection done',detail:'Subsidy is typically released after physical verification / geo-tagging.',verified:true},{step:10,title:'Track subsidy release',detail:'Confirm subsidy credited to your bank account. Follow up with block or DAEO office if delayed.',verified:true}], official_application_url: 'https://www.myscheme.gov.in', last_verified: '2026-10-09', verification_status: 'indicative', source_notes: 'Application channels vary by state and component. Use MyScheme or state agriculture portal for exact links.' },
  { id: 'soil-health-card', official_name: 'Soil Health Card Scheme', department: 'Department of Agriculture & Farmers Welfare', government_level: 'central', states: ['all'], categories: ['advisory','soil_testing'], crops: ['all'], benefit_types: ['advisory_service'], benefits_summary: 'Soil testing every 2-3 years and a Soil Health Card showing nutrient status and crop-wise fertilizer recommendation for selected crops.', required_documents: [{id:'aadhaar',name:'Aadhaar / farmer identity',status:'typically_mandatory',why:'Farmer registration in soil testing database.'},{id:'land_record',name:'Land record or survey number list',status:'typically_mandatory',why:'Geo-referencing of sample collection points.'}], application_steps: [{step:1,title:'Check if sample collection drive is on in your village',detail:'State AGRI department or Krishi Vigyan Kendra (KVK) announces camps.',verified:true},{step:2,title:'Contact your AEO / KVK',detail:'Register your fields for sample collection. Some states also offer on-demand paid testing.',verified:true},{step:3,title:'Collect soil samples as per method shown',detail:'Typically 8-10 cores per 2.5 ha, mixed, dried, and bagged with proper label.',verified:true},{step:4,title:'Submit sample at soil testing lab or camp',detail:'Follow labeling instructions (plot, crop, survey no.) for useful recommendations.',verified:true},{step:5,title:'Receive sample receipt / application ID',detail:'Retain this ID for status tracking.',verified:true},{step:6,title:'Wait for lab analysis',detail:'Turnaround varies by lab and seasonal load.',verified:false},{step:7,title:'Collect Soil Health Card (digital or printed)',detail:'Cards are also issued on https://www.soilhealth.dac.gov.in farmer login.',verified:true},{step:8,title:'Understand nutrient status and recommendation',detail:'Card shows N-P-K, micro-nutrients, pH, EC, OC, and crop-wise fertilizer dose.',verified:true},{step:9,title:'Apply recommendation this season',detail:'Adjust fertilizers and add organic matter as suggested. Retest after 2-3 years.',verified:true},{step:10,title:'Raise a query with AEO / KVK if results look off',detail:'If card values do not match visible symptoms, request a retest or advisory visit.',verified:true}], official_application_url: 'https://www.soilhealth.dac.gov.in', last_verified: '2026-10-09', verification_status: 'official_url_verified', source_notes: 'Official Soil Health Card portal. Many states also route applications through their own portals.' },
  { id: 'solar-pump-sauri', official_name: 'PM-KUSUM (Solar Agricultural Pumps & Grid-connected Solar)', department: 'Ministry of New and Renewable Energy (MNRE)', government_level: 'central', states: ['all'], categories: ['solar_energy','subsidy','irrigation'], crops: ['all'], benefit_types: ['capital_subsidy'], benefits_summary: 'Component-B: Standalone solar pumps for farmers; Component-C: Grid-connected solar on agricultural land with subsidy as per MNRE / State Nodal Agency notification.', required_documents: [{id:'aadhaar',name:'Aadhaar',status:'typically_mandatory',why:'Farmer identification and subsidy DBT.'},{id:'land_record',name:'Land record (cultivable land / well / pump site)',status:'typically_mandatory',why:'Pump installed on farmer-owned cultivable land only per most state rules.'},{id:'electricity_connection',name:'Electricity connection details (Component-C feeder-level)',status:'conditional',why:'Grid-feeder-level solarisation needs DISCOM data. Standalone may not require grid connection.'},{id:'bank_passbook',name:'Bank passbook',status:'typically_mandatory',why:'Subsidy disbursement via DBT; also for loan portion if opted.'}], application_steps: [{step:1,title:'Read latest MNRE / state KUSUM guidelines',detail:'State Nodal Agency publishes eligible categories, pump sizes, subsidy %, and empanelled vendors.',verified:true},{step:2,title:'Confirm Component (B standalone / C grid or feeder)',detail:'Check which component is open in your DISCOM circle and for your pump size.',verified:true},{step:3,title:'Prepare land, Aadhaar, bank, and connection documents',detail:'Verify names match across all documents.',verified:true},{step:4,title:'Register on official KUSUM or state portal',detail:'Use https://mnre.gov.in or state KUSUM portal. Many states route KUSUM through their agriculture / energy portal.',verified:true},{step:5,title:'Fill application: pump size, component, location',detail:'Specify HP/kW, well/tubewell location and feeder details if Component-C.',verified:true},{step:6,title:'Pick vendor from empanelled list only',detail:'Never pay full amount to a non-empanelled vendor. Pay subsidy portion only through DBT after sanction.',verified:true},{step:7,title:'Submit application and track status',detail:'Keep acknowledgement ID. State Nodal Agency / DISCOM conducts feasibility for Component-C.',verified:true},{step:8,title:'After sanction: install work as per technical norms',detail:'Quality / technical inspection is mandatory before subsidy release.',verified:true},{step:9,title:'Get pump commissioned / net-metering installed',detail:'Component-C: net-metering / feeder-level commissioning by DISCOM. Standalone: performance report.',verified:true},{step:10,title:'Track subsidy credit and maintain invoice copies',detail:'Retain commissioning report, invoices, and payment proofs for future audits.',verified:true}], official_application_url: 'https://mnre.gov.in', last_verified: '2026-10-09', verification_status: 'indicative', source_notes: 'MNRE and State Nodal Agency guidelines. Exact portal varies by state / DISCOM.' },
  { id: 'mahadbt-schemes', official_name: 'Maharashtra Aaple Sarkar DBT Portal (MahaDBT) - Agricultural Schemes', department: 'Maharashtra Government (Planning Department / Agricultural Department)', government_level: 'state', states: ['Maharashtra'], categories: ['farmer_support','subsidy','equipment'], crops: ['all'], benefit_types: ['capital_subsidy','direct_benefit_transfer'], benefits_summary: 'Single Maharashtra state portal applying to notified schemes such as seed subsidy, farm equipment subsidy, drip/sprinkler, organic farming certification support, and Maharashtra farmer welfare schemes - subject to MahaDBT notifications and budget.', required_documents: [{id:'aadhaar',name:'Aadhaar',status:'typically_mandatory',why:'MahaDBT requires Aadhaar-linked registration and e-KYC.'},{id:'7_12_extract',name:'7/12 extract / Satbara Utara (Maharashtra land record)',status:'typically_mandatory',why:'Land-based schemes need plot-wise verified entries on MahaDBT.'},{id:'crops_sown',name:'Crop sown declaration / crop diary if applicable',status:'conditional',why:'For seed subsidy or crop-season specific subsidies.'},{id:'bank_passbook',name:'Bank passbook (Aadhaar-linked preferred)',status:'typically_mandatory',why:'All MahaDBT benefits go through DBT to the Aadhaar-linked bank account.'}], application_steps: [{step:1,title:'Open only https://mahadbt.maharashtra.gov.in',detail:'MahaDBT is the official Maharashtra DBT portal. Do not use lookalike URLs.',verified:true},{step:2,title:'Register / sign in on MahaDBT',detail:'Use your mobile and Aadhaar to complete e-KYC. Never share MahaDBT password or OTP with AI-KrushiMitra.',verified:true},{step:3,title:'View eligible schemes on the portal after login',detail:'Portal suggests schemes based on your profile. Verify each against the government scheme notification.',verified:false},{step:4,title:'Choose a notified scheme and open application form',detail:'Read eligibility, benefit, and deadline carefully before applying.',verified:true},{step:5,title:'Attach required documents in specified format',detail:'Most MahaDBT forms accept PDF/JPEG with stated size limits.',verified:true},{step:6,title:'Fill land, crop, and bank details exactly as in records',detail:'Mismatches with Aadhaar or 7/12 extract cause rejections.',verified:true},{step:7,title:'Preview, save draft, and submit within deadline',detail:'Keep a downloaded copy of the submitted application PDF with submission ID.',verified:true},{step:8,title:'Track application status on MahaDBT',detail:'Applications go through verification stages (block/district/department).',verified:true},{step:9,title:'Respond to queries / re-upload if status asks',detail:'Check messages frequently. Delay leads to auto-closure after the notified window.',verified:true},{step:10,title:'Confirm benefit credited to your bank account',detail:'After sanction and e-Signed order, DBT is released. Follow up with district nodal officer if not received.',verified:true}], official_application_url: 'https://mahadbt.maharashtra.gov.in', last_verified: '2026-10-09', verification_status: 'official_url_verified', source_notes: 'Official MahaDBT portal (Maharashtra state). Schemes listed are subject to annual budget and notification.' },
  { id: 'maha-krushi-sanvad', official_name: 'Maharashtra Krishi Sanvad / 1800-233-0500 Helpline & Portal', department: 'Maharashtra State Agricultural Department', government_level: 'state', states: ['Maharashtra'], categories: ['advisory','helpline'], crops: ['all'], benefit_types: ['advisory_service'], benefits_summary: 'Toll-free agricultural helpline and Maharashtra Krishi portal for query resolution on crops, pests, diseases, seeds, weather, market, and government scheme guidance.', required_documents: [{id:'mobile',name:'Farmer mobile number',status:'typically_mandatory',why:'Registration and OTP-based call-back on the portal / helpline.'}], application_steps: [{step:1,title:'Use helpline or official Maharashtra Krishi site',detail:'Helpline 1800-233-0500 or https://krishi.maharashtra.gov.in for login.',verified:true},{step:2,title:'If using portal: register with mobile and Aadhaar (if asked)',detail:'Use your own mobile. Never register someone else\'s number on your behalf.',verified:true},{step:3,title:'Open Query section or Advisory section',detail:'Labels vary on portal. Use the help option if unsure.',verified:false},{step:4,title:'Describe your query clearly: crop, stage, symptom, location',detail:'Better details → more accurate advice from KVK / subject matter specialist.',verified:true},{step:5,title:'Upload symptom photo if query is pest/disease',detail:'Clear, close-up daylight photo of affected plant/leaf.',verified:true},{step:6,title:'Submit the query / call-back request',detail:'Not all states provide immediate call-back; wait for SMS or portal message.',verified:true},{step:7,title:'Review advice sent by SMS / on portal',detail:'Save reference number for escalation.',verified:true},{step:8,title:'If pest/disease: cross-check with our Disease Detection module',detail:'Use Disease Detection section for an independent visual check. Always cross-verify with a qualified expert for expensive decisions.',verified:true},{step:9,title:'Follow recommended action and re-query if symptoms worsen',detail:'Re-contact helpline or visit AEO/KVK if results are contrary to expectation.',verified:true},{step:10,title:'Share feedback on quality of advice',detail:'Helpline uses feedback for training KVK/AEO teams.',verified:true}], official_application_url: 'https://krishi.maharashtra.gov.in', last_verified: '2026-10-09', verification_status: 'official_url_verified', source_notes: 'Maharashtra Agriculture portal and toll-free helpline 1800-233-0500. Other states have similar portals/helplines.' },
  { id: 'myscheme-india', official_name: 'MyScheme.gov.in - Central + States Unified Scheme Search', department: 'Government of India (DPIIT / multiple departments)', government_level: 'central', states: ['all'], categories: ['search_portal','information'], crops: ['all'], benefit_types: ['information_portal'], benefits_summary: 'Search across 400+ Central and State schemes in one portal. Filter by state, category, beneficiary group, and language. Links to each scheme\'s official application page with eligibility summary.', required_documents: [{id:'none',name:'No documents needed to search',status:'not_applicable',why:'MyScheme is a search and redirect portal; application documents are specific to the scheme you choose.'}], application_steps: [{step:1,title:'Open https://www.myscheme.gov.in in the language of your choice',detail:'Choose English, Hindi, Marathi, or another supported language from the menu.',verified:true},{step:2,title:'Use Filters: State, Beneficiary Category, Department, Sector',detail:'Set Agriculture sector and your state for a focused shortlist.',verified:true},{step:3,title:'Open any scheme card from results',detail:'Each card provides Official Scheme Name, benefits, eligibility, required documents, and the official apply link.',verified:true},{step:4,title:'Click Apply Now → redirected to the scheme\'s official portal',detail:'Verify the redirected URL is a government domain (gov.in or state portal).',verified:true},{step:5,title:'Cross-verify eligibility with the latest government notification',detail:'MyScheme content is curated but may lag behind the latest notification / budget cut-off.',verified:false},{step:6,title:'Register on the official application portal',detail:'Never create logins or upload documents on MyScheme; use actual scheme portal.',verified:true},{step:7,title:'Gather scheme-specific documents from the Required Documents list',detail:'Use our in-app document checklist and tick off items as you prepare them.',verified:true},{step:8,title:'Apply within stated deadline',detail:'Note the cut-off date; many schemes have seasonal or financial year limits.',verified:true},{step:9,title:'Retain application ID and submitted form PDF',detail:'This is your proof for any escalation / Grievance Redressal.',verified:true},{step:10,title:'Track status on the scheme portal and, if needed, raise PGRS grievance',detail:'Use CPGRAMS (pgportal.gov.in) or state PGRS if no response within a reasonable period.',verified:true}], official_application_url: 'https://www.myscheme.gov.in', last_verified: '2026-10-09', verification_status: 'official_url_verified', source_notes: 'Official MyScheme portal (GoI). Best single starting-point for scheme discovery across departments and states.' },
  { id: 'organic-farming-mission', official_name: 'Paramparagat Krishi Vikas Yojana (PKVY) - Organic Farming / Cluster Programme', department: 'Ministry of Agriculture & Farmers Welfare / National Centre of Organic Farming', government_level: 'central', states: ['all'], categories: ['organic_farming','certification','subsidy'], crops: ['all'], benefit_types: ['capital_subsidy','capacity_building'], benefits_summary: 'Cluster-based organic farming support, conversion assistance to PGS/NOP certified organic, help with input packing, labelling, and market linkages via FPOs / organic value chains.', required_documents: [{id:'aadhaar',name:'Aadhaar / farmer identity',status:'typically_mandatory',why:'Farmer registration in PKVY/PGS cluster.'},{id:'land_record',name:'Land record (cluster/plot-wise)',status:'typically_mandatory',why:'Conversion area is fixed and verified by cluster agency.'},{id:'bank_passbook',name:'Bank passbook',status:'typically_mandatory',why:'Assistance released by DBT after milestones.'},{id:'cluster_membership',name:'Cluster / FPO membership proof (if joining cluster)',status:'conditional',why:'PKVY is primarily delivered through FPO / cluster approach per NCOF guidelines.'}], application_steps: [{step:1,title:'Check if PKVY cluster exists nearby or register interest',detail:'Contact State Agricultural Department, NCOF regional centre, or KVK for the nearest PKVY cluster / FPO.',verified:true},{step:2,title:'Understand conversion pathway (PGS India or NPOP 3rd party)',detail:'Most smallholder clusters use PGS-India Participatory Guarantee; for exports choose NPOP certification route.',verified:true},{step:3,title:'List crops and total area you want to convert to organic',detail:'Minimum acreage rules vary by state. Discuss with FPO or NCOF before applying.',verified:true},{step:4,title:'Join cluster / FPO and register members collectively',detail:'PKVY works best as group. Individual applications may be allowed only in specific states/centres.',verified:true},{step:5,title:'Open official state PKVY portal or use https://www.myscheme.gov.in search → PKVY',detail:'Apply with cluster details, crop, and land area. Attach land record and member list.',verified:false},{step:6,title:'Submit application along with land and bank documents',detail:'Make sure names in Aadhaar, bank, and land record match.',verified:true},{step:7,title:'Follow conversion practices: no chemicals, on-farm input preparation, record keeping',detail:'Conversion period (typically 24-36 months) is tracked by Internal Auditor and Peer Reviewer (PGS).',verified:true},{step:8,title:'Undergo inspection and get PGS/Organic certification',detail:'NCOF issues certification upon passing all audits.',verified:true},{step:9,title:'Avail assistance for packing, branding, and organic market linkage',detail:'FPOs organise bulk sales and direct marketing / organic fairs.',verified:true},{step:10,title:'Renew certification annually and keep field records',detail:'Lapses in record keeping or use of banned inputs cause withdrawal of certificate.',verified:true}], official_application_url: 'https://www.myscheme.gov.in', last_verified: '2026-10-09', verification_status: 'indicative', source_notes: 'NCOF PKVY guidelines. Application portal and cluster list may be found on State Agriculture department websites or via MyScheme search.' }
];

const PRELIMINARY_DISCLAIMER = "⚠️ PRELIMINARY DISCLAIMER: The eligibility matching shown here is based on your profile information and is for informational guidance only. Final eligibility and benefit decisions are taken by the concerned government department. Always verify details on the official scheme website before applying.";

const DEMO_MATCH_STATUS = [
  { id: 'pm-kisan', status: 'potentially_eligible', reasons: ['Landholding farmer registered in profile'], missingFields: ['Exact land tenure and tax status'], blockers: [], unverified_conditions: ['Exclusion criteria (income tax / government service status) require verification'] },
  { id: 'pmfby', status: 'more_information_required', reasons: ['Farmer with cultivable land'], missingFields: ['Whether notified crop/village for current season'], blockers: [], unverified_conditions: ['Seasonal cut-off dates and premium payment window'] },
  { id: 'kisan-credit-card', status: 'potentially_eligible', reasons: ['Farming profile and land details present'], missingFields: ['Credit bureau / bank-specific KYC details'], blockers: [], unverified_conditions: ['Bank due diligence and scale of finance per crop'] },
  { id: 'pmksy', status: 'more_information_required', reasons: ['Irrigation info captured in profile'], missingFields: ['Exact PMKSY component (drip/storage/watershed)', 'District/component-wise budget opening'], blockers: [], unverified_conditions: ['Subsidy percentage varies by state and category'] },
  { id: 'soil-health-card', status: 'potentially_eligible', reasons: ['Applicable to all farmers free of cost in most drives'], missingFields: [], blockers: [], unverified_conditions: ['Sample drive timelines vary by district'] },
  { id: 'solar-pump-sauri', status: 'more_information_required', reasons: ['Agricultural pump usage is common'], missingFields: ['Grid/feeder ID for Component-C', 'Land ownership / pump site details'], blockers: [], unverified_conditions: ['State-wise pump size caps, empanelled vendor list, and DISCOM feasibility'] },
  { id: 'mahadbt-schemes', status: 'more_information_required', reasons: ['If farmer is based in Maharashtra, several Aaple Sarkar DBT schemes are applicable'], missingFields: ['State (Maharashtra required for MahaDBT)'], blockers: ['Not located in Maharashtra (applies only if state=Maharashtra)'], unverified_conditions: ['Annual notifications and budget per scheme'] },
  { id: 'maha-krushi-sanvad', status: 'potentially_eligible', reasons: ['Free advisory service open to all Maharashtra farmers'], missingFields: ['State (Maharashtra preferred)'], blockers: [], unverified_conditions: ['Helpline call-back timings and regional language availability'] },
  { id: 'myscheme-india', status: 'potentially_eligible', reasons: ['Open to all Indian citizens and farmers for scheme search'], missingFields: [], blockers: [], unverified_conditions: ['Per-scheme application portals outside MyScheme'] },
  { id: 'organic-farming-mission', status: 'more_information_required', reasons: ['Eligible if willing to convert to organic via FPO/cluster'], missingFields: ['Cluster/FPO membership', 'Crops/area planned for organic conversion'], blockers: [], unverified_conditions: ['Cluster openings, PGS vs NPOP pathway choice'] }
];

export const schemeApi = {
  listOrMatch: async (params) => {
    try {
      const usp = new URLSearchParams();
      usp.set('match', String(params?.match !== false));
      if (params?.q) usp.set('q', params.q);
      if (params?.state) usp.set('state', params.state);
      if (params?.category) usp.set('category', params.category);
      if (params?.crop) usp.set('crop', params.crop);
      if (params?.benefit_type) usp.set('benefit_type', params.benefit_type);
      if (params?.eligibility_status) usp.set('eligibility_status', params.eligibility_status);
      const qs = usp.toString();
      return await api.get(`/schemes${qs ? '?' + qs : ''}`);
    } catch (err) {
      console.warn('schemeApi.listOrMatch fallback (server unavailable):', err.message);
      const q = (params?.q || '').toLowerCase();
      const state = (params?.state || '').toLowerCase();
      const category = (params?.category || '').toLowerCase();
      const crop = (params?.crop || '').toLowerCase();
      const benefitType = (params?.benefit_type || '').toLowerCase();
      const statusFilter = (params?.eligibility_status || '').toLowerCase();
      const filtered = DEMO_SCHEMES.filter(s => {
        if (q && !(s.official_name.toLowerCase().includes(q) || s.department.toLowerCase().includes(q) || s.benefits_summary.toLowerCase().includes(q))) return false;
        if (state && !s.states.some(st => st === 'all' || st.toLowerCase() === state)) return false;
        if (category && !s.categories.some(c => c.toLowerCase() === category)) return false;
        if (crop && !s.crops.some(c => c === 'all' || c === 'notified' || c.toLowerCase() === crop)) return false;
        if (benefitType && !s.benefit_types.some(b => b.toLowerCase() === benefitType)) return false;
        return true;
      });
      const schemes_with_match = filtered.map(scheme => {
        const m = DEMO_MATCH_STATUS.find(x => x.id === scheme.id) || { status: 'more_information_required', reasons: [], missingFields: [], blockers: [], unverified_conditions: [] };
        return { scheme, match: { status: m.status, match_score: m.status === 'potentially_eligible' ? 82 : m.status === 'more_information_required' ? 55 : 28, reasons: m.reasons, missing_fields: m.missingFields, blockers: m.blockers, unverified_conditions: m.unverified_conditions, accuracy_badge: m.status === 'potentially_eligible' ? 'Verified against official criteria' : 'Indicative — needs full review' } };
      });
      let finalList = schemes_with_match;
      if (statusFilter) {
        const map = { potentially_eligible: 'potentially_eligible', more_info: 'more_information_required', more_information_required: 'more_information_required', not_eligible: 'eligibility_criteria_not_met', eligibility_criteria_not_met: 'eligibility_criteria_not_met' };
        const target = map[statusFilter];
        if (target) finalList = schemes_with_match.filter(x => x.match.status === target);
      }
      const counts = { potentially_eligible: 0, more_information_required: 0, eligibility_criteria_not_met: 0 };
      finalList.forEach(x => { if (counts[x.match.status] !== undefined) counts[x.match.status] += 1; });
      return {
        disclaimer: PRELIMINARY_DISCLAIMER,
        demo_fallback: true,
        is_demo: true,
        data_source: 'Static Demo Scheme List (Backend Offline / API Unavailable) - NOT connected to backend curated database. Verify on official scheme portals before applying.',
        profile_info: { extracted_from: 'fallback_profile', note: 'Backend is not connected. Matching shown is static demo data from the curated schemes list.' },
        match_summary: counts,
        schemes_with_match: finalList,
        schemes: finalList.map(x => x.scheme),
      };
    }
  },
  getMeta: async () => {
    try {
      return await api.get('/schemes/meta');
    } catch (err) {
      console.warn('schemeApi.getMeta fallback:', err.message);
      const cats = new Set(), benefits = new Set(), states = new Set();
      DEMO_SCHEMES.forEach(s => {
        (s.categories || []).forEach(c => cats.add(c));
        (s.benefit_types || []).forEach(b => benefits.add(b));
        (s.states || []).forEach(st => { if (String(st).toLowerCase() !== 'all') states.add(st); });
      });
      return {
        disclaimer: PRELIMINARY_DISCLAIMER,
        demo_fallback: true,
        is_demo: true,
        data_source: 'Static Demo Scheme Meta (Backend Offline / API Unavailable) - NOT connected to backend curated database.',
        categories: Array.from(cats).sort(),
        benefit_types: Array.from(benefits).sort(),
        states: Array.from(states).sort(),
        eligibility_statuses: ['potentially_eligible', 'more_information_required', 'eligibility_criteria_not_met'],
      };
    }
  },
  getDetail: async (schemeId) => {
    try {
      return await api.get(`/schemes/${encodeURIComponent(schemeId)}`);
    } catch (err) {
      console.warn(`schemeApi.getDetail fallback (${schemeId}):`, err.message);
      const scheme = DEMO_SCHEMES.find(s => s.id === schemeId);
      if (!scheme) return { disclaimer: PRELIMINARY_DISCLAIMER, demo_fallback: true, error: 'Scheme not found in demo list.' };
      const m = DEMO_MATCH_STATUS.find(x => x.id === schemeId) || { status: 'more_information_required', reasons: [], missingFields: [], blockers: [], unverified_conditions: [] };
      return {
        disclaimer: PRELIMINARY_DISCLAIMER,
        demo_fallback: true,
        scheme,
        match: { status: m.status, match_score: m.status === 'potentially_eligible' ? 82 : m.status === 'more_information_required' ? 55 : 28, reasons: m.reasons, missing_fields: m.missingFields, blockers: m.blockers, unverified_conditions: m.unverified_conditions, accuracy_badge: m.status === 'potentially_eligible' ? 'Verified against official criteria' : 'Indicative — needs full review' },
        checklist_progress: { checked_document_ids: [], note: 'Checklist not saved. Backend not connected; demo mode only.' },
      };
    }
  },
  saveChecklist: async (schemeId, checkedDocumentIds) => {
    try {
      return await api.put(`/schemes/${encodeURIComponent(schemeId)}/checklist`, { checked_document_ids: Array.isArray(checkedDocumentIds) ? checkedDocumentIds : [] });
    } catch (err) {
      console.warn(`schemeApi.saveChecklist fallback (${schemeId}):`, err.message);
      return { demo_fallback: true, scheme_id: schemeId, checked_document_ids: Array.isArray(checkedDocumentIds) ? checkedDocumentIds : [], saved_locally: true, note: 'Backend not connected. Checklist stored only in this device session memory. Will be lost on reload.' };
    }
  },
}

export default api
