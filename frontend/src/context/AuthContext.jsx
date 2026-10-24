import { createContext, useContext, useState, useEffect, useRef } from 'react'
import { authApi, farmerApi, getApiErrorMessage } from '../services/api'
import { normalizePlantVillageCrop } from '../constants/crops'

const AuthContext = createContext()

const DEFAULT_LAT = 18.5204
const DEFAULT_LON = 73.8567
const TOKEN_KEY = 'krushimitra_token'
const USER_KEY = 'krushimitra_user'

export const getAuthenticatedHomePath = (account) => {
  if (account?.role === 'buyer') return '/marketplace?tab=dashboard'
  return account?.role === 'farmer' && (account?.hasProfile ?? account?.profile_complete)
    ? '/dashboard'
    : '/create-profile'
}

const normalizeProfile = (raw) => {
  if (!raw) return raw
  const p = typeof raw.toJS === 'function' ? raw.toJS() : { ...raw }

  const existingLoc = p.location || {}
  const existingFarm = p.farming || {}
  const existingScheme = p.scheme_profile || p.schemeProfile || p.eligibility_profile || {}

  const state = existingLoc.state ?? p.state ?? ''
  const district = existingLoc.district ?? p.district ?? ''
  const taluka = existingLoc.taluka ?? p.taluka ?? ''
  const village = existingLoc.village ?? p.village ?? ''
  const latitude = Number(existingLoc.latitude ?? p.latitude ?? DEFAULT_LAT)
  const longitude = Number(existingLoc.longitude ?? p.longitude ?? DEFAULT_LON)

  const crop = normalizePlantVillageCrop(existingFarm.crop ?? p.main_crop ?? p.mainCrop ?? '')
  const savedCrops = Array.isArray(existingFarm.crops) ? existingFarm.crops : []
  const crops = [...new Map([...savedCrops, crop]
    .map(normalizePlantVillageCrop)
    .filter(Boolean)
    .map((value) => [value.toLocaleLowerCase(), value])).values()]
  const variety = existingFarm.variety ?? p.variety ?? ''
  const stage = existingFarm.stage ?? p.crop_stage ?? p.cropStage ?? ''
  const land_area = Number(existingFarm.land_area ?? p.land_area ?? p.landArea ?? 0)
  const land_unit = existingFarm.land_unit ?? p.land_unit ?? p.landUnit ?? 'Acres'
  const soil_type = existingFarm.soil_type ?? p.soil_type ?? p.soilType ?? ''
  const irrigation = existingFarm.irrigation ?? p.irrigation_type ?? p.irrigation ?? ''

  const full_name = p.full_name ?? p.name ?? ''
  const mobile = p.mobile ?? ''
  const email = p.email ?? ''

  const scheme_profile = {
    gender: existingScheme.gender ?? p.gender ?? '',
    age: existingScheme.age ?? p.age ?? null,
    farmer_category: existingScheme.farmer_category ?? existingScheme.category ?? p.farmer_category ?? p.category ?? '',
    land_tenure: existingScheme.land_tenure ?? existingScheme.land_ownership ?? p.land_tenure ?? p.landOwnership ?? '',
    activities: Array.isArray(existingScheme.activities) ? existingScheme.activities : Array.isArray(p.activities) ? p.activities : [],
    annual_income_band: existingScheme.annual_income_band ?? existingScheme.income_band ?? p.annual_income_band ?? p.incomeBand ?? '',
    already_beneficiary: typeof existingScheme.already_beneficiary === 'boolean' ? existingScheme.already_beneficiary : typeof p.already_beneficiary === 'boolean' ? p.already_beneficiary : null,
  }

  const normalized = {
    ...p,
    id: p.id || p.user_id,
    user_id: p.user_id || p.id,
    name: p.name ?? full_name,
    full_name,
    mobile,
    email,
    language: p.language || localStorage.getItem('krushimitra_language') || 'en',
    hasProfile: typeof p.hasProfile === 'boolean'
      ? p.hasProfile
      : !!((existingLoc.district && existingFarm.crop) || (state && district && village && crop && stage)),
    location: {
      state,
      district,
      taluka,
      village,
      latitude,
      longitude
    },
    farming: {
      crop,
      crops,
      variety,
      stage,
      land_area,
      land_unit,
      soil_type,
      irrigation
    },
    scheme_profile,
    schemeProfile: scheme_profile,
    eligibility_profile: scheme_profile,
    gender: scheme_profile.gender,
    age: scheme_profile.age,
    farmer_category: scheme_profile.farmer_category,
    category: scheme_profile.farmer_category,
    land_tenure: scheme_profile.land_tenure,
    landOwnership: scheme_profile.land_tenure,
    activities: scheme_profile.activities,
    annual_income_band: scheme_profile.annual_income_band,
    incomeBand: scheme_profile.annual_income_band,
    already_beneficiary: scheme_profile.already_beneficiary,
    state,
    district,
    taluka,
    village,
    latitude,
    longitude,
    main_crop: crop,
    mainCrop: crop,
    variety,
    crop_stage: stage,
    cropStage: stage,
    land_area,
    landArea: land_area,
    land_unit,
    landUnit: land_unit,
    soil_type,
    soilType: soil_type,
    irrigation_type: irrigation,
    irrigation
  }
  return normalized
}

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null)
  const [token, setToken] = useState(() => {
    const storedToken = localStorage.getItem(TOKEN_KEY)
    if (storedToken && (storedToken.startsWith('mock-login-token-') || storedToken.startsWith('mock-register-token-'))) {
      localStorage.removeItem(TOKEN_KEY)
      localStorage.removeItem(USER_KEY)
      return null
    }
    return storedToken
  })
  const [loading, setLoading] = useState(() => Boolean(localStorage.getItem(TOKEN_KEY)))
  const [error, setError] = useState(null)
  const skipSessionRestore = useRef(null)

  const isAuthenticated = !!token

  useEffect(() => {
    if (token) {
      if (skipSessionRestore.current === token) {
        skipSessionRestore.current = null
        return
      }
      skipSessionRestore.current = null
      restoreSession(token)
    }
  }, [token]) // eslint-disable-line react-hooks/exhaustive-deps

  const clearSession = () => {
    setToken(null)
    setUser(null)
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem(USER_KEY)
  }

  const cacheUser = (profile) => {
    const normalized = normalizeProfile(profile)
    setUser(normalized)
    localStorage.setItem(USER_KEY, JSON.stringify(normalized))
    return normalized
  }

  const restoreSession = async (sessionToken) => {
    let currentSessionToken = sessionToken
    const isCurrentSession = () => localStorage.getItem(TOKEN_KEY) === currentSessionToken

    try {
      if (!isCurrentSession()) return
      setLoading(true)
      const account = await authApi.me()
      if (!isCurrentSession()) return
      if (!account?.id) {
        throw new Error('The backend did not return a valid authenticated user.')
      }
      if (account.token && account.token !== currentSessionToken) {
        currentSessionToken = account.token
        localStorage.setItem(TOKEN_KEY, account.token)
        skipSessionRestore.current = account.token
        setToken(account.token)
      }
      let profile = null
      let cachedProfile = null
      if (account.role !== 'buyer') {
        try {
          profile = await farmerApi.getProfile()
        } catch (profileError) {
          if (!isCurrentSession()) return
          console.error('Failed to load farmer profile:', profileError)
          const storedUser = localStorage.getItem(USER_KEY)
          if (storedUser) {
            try {
              cachedProfile = normalizeProfile(JSON.parse(storedUser))
            } catch (cacheError) {
              console.error('Cached user profile is invalid:', cacheError)
            }
          }
        }
      }

      if (!isCurrentSession()) return
      cacheUser({
        ...(cachedProfile || {}),
        ...account,
        ...(profile || {}),
        id: account.id,
        user_id: account.id,
        role: account.role,
        profile_complete: Boolean(account.profile_complete),
        hasProfile: Boolean(account.profile_complete)
      })
    } catch (err) {
      if (isCurrentSession()) {
        if (err.response?.status !== 401) {
          console.error('Failed to verify the current session:', err)
        }
        clearSession()
      }
    } finally {
      if (isCurrentSession()) setLoading(false)
    }
  }

  const storeAuthenticatedSession = (result) => {
    if (!result?.token) {
      throw new Error('The server did not return an authentication token.')
    }
    const account = result.user || result
    if (!['buyer', 'farmer'].includes(account.role)) {
      throw new Error('The server did not return a valid account role.')
    }
      const normalized = normalizeProfile({
        ...account,
        hasProfile: Boolean(account.profile_complete)
      })
    localStorage.setItem(TOKEN_KEY, result.token)
    localStorage.setItem(USER_KEY, JSON.stringify(normalized))
    setToken(result.token)
    setUser(normalized)
    return normalized
  }

  const register = async (data) => {
    if (!['buyer', 'farmer'].includes(data?.role)) {
      throw new Error('Choose whether you are registering as a buyer or farmer.')
    }
    try {
      setLoading(true)
      setError(null)
      const result = await authApi.register(data)
      return result
    } catch (err) {
      const msg = getApiErrorMessage(err, 'Registration failed')
      setError(msg)
      throw err
    } finally {
      setLoading(false)
    }
  }

  const login = async (data) => {
    try {
      setLoading(true)
      setError(null)
      const result = await authApi.login(data)
      if (result && result.token) {
        storeAuthenticatedSession(result)
      }
      return result
    } catch (err) {
      const msg = getApiErrorMessage(err, 'Login failed')
      setError(msg)
      throw err
    } finally {
      setLoading(false)
    }
  }

  const loginWithGoogle = async (googleAuthorization) => {
    try {
      setLoading(true)
      setError(null)
      const result = await authApi.googleLogin(googleAuthorization)
      if (result?.token) {
        storeAuthenticatedSession(result)
      }
      return result
    } catch (err) {
      const msg = getApiErrorMessage(err, 'Google sign-in failed')
      setError(msg)
      throw err
    } finally {
      setLoading(false)
    }
  }

  const linkGoogleAccount = async (credential) => {
    const result = await authApi.googleLogin(credential)
    if (!result?.token || !result?.id) {
      throw new Error('Google account linking did not return a valid account.')
    }
    return result
  }

  const logout = () => {
    const request = authApi.logout().catch((err) => {
      if (err.response?.status !== 401) {
        console.warn('Server logout could not complete:', err.message)
      }
    })
    clearSession()
    return request
  }

  const updateUserProfile = (profileData) => {
    return cacheUser({ ...profileData, hasProfile: true })
  }

  const getUserProfile = async (account = user) => {
    if (account?.role === 'buyer') {
      return normalizeProfile({
        ...account,
        hasProfile: Boolean(account.profile_complete ?? account.hasProfile)
      })
    }
    const profile = await farmerApi.getProfile()
    if (profile) {
      return cacheUser({
        ...(account || {}),
        ...profile,
        id: account?.id || profile.user_id,
        user_id: account?.id || profile.user_id,
        hasProfile: true
      })
    }
    return account ? normalizeProfile({ ...account, hasProfile: false }) : null
  }

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        isAuthenticated,
        loading,
        error,
        register,
        login,
        loginWithGoogle,
        linkGoogleAccount,
        logout,
        getUserProfile,
        updateUserProfile,
        setError
      }}
    >
      {children}
    </AuthContext.Provider>
  )
}

export const useAuth = () => {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}

export default AuthContext
