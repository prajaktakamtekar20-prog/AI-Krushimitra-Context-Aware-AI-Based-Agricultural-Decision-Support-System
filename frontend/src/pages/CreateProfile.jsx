import React, { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useLanguage } from '../context/LanguageContext'
import { useAuth } from '../context/AuthContext'
import { farmerApi } from '../services/api'
import Background from '../components/Background'
import GlassCard from '../components/GlassCard'
import FormInput from '../components/FormInput'
import FormSelect from '../components/FormSelect'
import GradientButton from '../components/GradientButton'
import LanguageSwitcher from '../components/LanguageSwitcher'
import { getPlantVillageCropOptions, normalizePlantVillageCrop } from '../constants/crops'
import { normalizeActivities } from '../utils/schemeActivities'

const DEFAULT_LAT = 18.5204
const DEFAULT_LON = 73.8567
const LEGACY_ACTIVITY_LABELS = {
  plantation: 'Plantation Crops',
  sericulture: 'Sericulture / Silk',
  beekeeping: 'Beekeeping / Honey',
  agroforestry: 'Agroforestry / Farm Forestry'
}
const SCHEME_ACTIVITY_OPTION_KEYS = [
  'field_crops',
  'vegetable_farming',
  'horticulture',
  'dairy',
  'poultry',
  'goat_sheep',
  'fishery',
  'organic',
  'floriculture',
  'other'
]

const CreateProfile = () => {
  const { t } = useLanguage()
  const { user, updateUserProfile, loading: authLoading } = useAuth()
  const navigate = useNavigate()
  const [loading, setLoading] = useState(false)
  const [locating, setLocating] = useState(false)
  const [detectedLoc, setDetectedLoc] = useState(null)
  const [submitError, setSubmitError] = useState('')
  const savedActivities = user?.scheme_profile?.activities ?? user?.activities
  const savedActivityList = normalizeActivities(savedActivities)
  const savedOtherActivities = savedActivityList
    .filter((activity) => typeof activity === 'string' && activity.startsWith('other:'))
    .map((activity) => activity.slice('other:'.length).trim())
    .filter(Boolean)
  const legacyOtherActivities = savedActivityList
    .filter((activity) => typeof activity === 'string' && Object.prototype.hasOwnProperty.call(LEGACY_ACTIVITY_LABELS, activity))
    .map((activity) => LEGACY_ACTIVITY_LABELS[activity])

  const [form, setForm] = useState({
    fullName: user?.name || user?.full_name || '',
    mobile: user?.mobile || '',
    state: '',
    district: '',
    taluka: '',
    village: '',
    latitude: user?.location?.latitude ?? DEFAULT_LAT,
    longitude: user?.location?.longitude ?? DEFAULT_LON,
    mainCrop: '',
    crops: Array.isArray(user?.farming?.crops) ? user.farming.crops : [],
    variety: '',
    cropStage: '',
    landArea: '',
    landUnit: 'Acres',
    soilType: '',
    irrigation: '',
    gender: user?.scheme_profile?.gender || user?.gender || '',
    age: user?.scheme_profile?.age || user?.age || '',
    farmerCategory: user?.scheme_profile?.farmer_category || user?.farmer_category || user?.category || '',
    landTenure: user?.scheme_profile?.land_tenure || user?.scheme_profile?.land_ownership || user?.land_tenure || user?.landOwnership || '',
    activities: savedActivityList.flatMap((activity) => {
      if (typeof activity !== 'string') return []
      return activity.startsWith('other:') || Object.prototype.hasOwnProperty.call(LEGACY_ACTIVITY_LABELS, activity)
        ? ['other']
        : [activity]
    }),
    otherActivity: [...savedOtherActivities, ...legacyOtherActivities].join(', '),
    annualIncomeBand: user?.scheme_profile?.annual_income_band || user?.scheme_profile?.income_band || user?.annual_income_band || user?.incomeBand || '',
    alreadyBeneficiary: user?.scheme_profile?.already_beneficiary != null ? String(user?.scheme_profile?.already_beneficiary) : (user?.already_beneficiary != null ? String(user?.already_beneficiary) : '')
  })
  const [errors, setErrors] = useState({})
  const [cropToAdd, setCropToAdd] = useState('')

  const handleChange = (e) => {
    const target = e.target
    const { name, value, type } = target
    if (type === 'checkbox' && name === 'activities') {
      const val = target.value
      setForm((prev) => {
        const list = Array.isArray(prev.activities) ? [...prev.activities] : []
        const idx = list.indexOf(val)
        if (target.checked) {
          if (idx === -1) list.push(val)
        } else if (idx !== -1) {
          list.splice(idx, 1)
        }
        return { ...prev, activities: list }
      })
    } else {
      setForm((prev) => ({ ...prev, [name]: value }))
    }
    if (errors[name]) setErrors((prev) => ({ ...prev, [name]: '' }))
  }

  const toggleActivity = (val) => {
    setForm((prev) => {
      const list = Array.isArray(prev.activities) ? [...prev.activities] : []
      const idx = list.indexOf(val)
      if (idx === -1) list.push(val)
      else list.splice(idx, 1)
      return { ...prev, activities: list }
    })
  }

  const addCrop = () => {
    const crop = normalizePlantVillageCrop(cropToAdd)
    if (!crop || form.crops.some((savedCrop) => normalizePlantVillageCrop(savedCrop).toLowerCase() === crop.toLowerCase())) return
    setForm((prev) => ({ ...prev, crops: [...prev.crops, crop] }))
    setCropToAdd('')
  }

  const removeCrop = (cropToRemove) => {
    setForm((prev) => ({
      ...prev,
      crops: prev.crops.filter((crop) => crop !== cropToRemove)
    }))
  }

  const useCurrentLocation = () => {
    setLocating(true)
    if (!navigator.geolocation) {
      setLocating(false)
      return
    }
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        const { latitude, longitude } = pos.coords
        setForm((prev) => ({ ...prev, latitude, longitude }))
        setDetectedLoc(`Lat: ${latitude.toFixed(4)}, Lon: ${longitude.toFixed(4)}`)
        setLocating(false)
      },
      (err) => {
        console.error('Geolocation error:', err)
        setForm((prev) => ({ ...prev, latitude: DEFAULT_LAT, longitude: DEFAULT_LON }))
        setDetectedLoc(t('createProfile.locationFallback'))
        setLocating(false)
      },
      { enableHighAccuracy: true, timeout: 10000 }
    )
  }

  const cropOptions = getPlantVillageCropOptions(t)
  const schemeActivityOptions = SCHEME_ACTIVITY_OPTION_KEYS.map((key) => ({
    value: key,
    label: t(`createProfile.schemeActivityOptions.${key}`)
  }))

  const stageOptions = ['seedling', 'vegetative', 'flowering', 'fruiting', 'harvesting'].map(
    (k) => ({ value: k, label: t(`createProfile.stages.${k}`) })
  )
  const soilOptions = ['black', 'red', 'alluvial', 'sandy', 'other'].map(
    (k) => ({ value: k, label: t(`createProfile.soils.${k}`) })
  )
  const irrigationOptions = ['drip', 'sprinkler', 'rainfed', 'canal', 'other'].map(
    (k) => ({ value: k, label: t(`createProfile.irrigations.${k}`) })
  )

  const validate = () => {
    const newErrors = {}
    if (!form.fullName.trim()) newErrors.fullName = t('common.required')
    if (!form.mobile.trim()) newErrors.mobile = t('common.required')
    if (!form.state.trim()) newErrors.state = t('common.required')
    if (!form.district.trim()) newErrors.district = t('common.required')
    if (!form.village.trim()) newErrors.village = t('common.required')
    if (!form.mainCrop) newErrors.mainCrop = t('common.required')
    if (!form.cropStage) newErrors.cropStage = t('common.required')
    if (!form.landArea || Number(form.landArea) <= 0) newErrors.landArea = t('common.required')
    if (!form.soilType) newErrors.soilType = t('common.required')
    if (!form.irrigation) newErrors.irrigation = t('common.required')
    return newErrors
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    setSubmitError('')
    const newErrors = validate()
    if (Object.keys(newErrors).length > 0) {
      setErrors(newErrors)
      return
    }
    setLoading(true)
    try {
      const cleanedMobile = (form.mobile || '').replace(/\D/g, '')
      const locationPayload = {
        state: form.state.trim(),
        district: form.district.trim(),
        taluka: form.taluka.trim() || t('createProfile.talukaFallback') || 'N/A',
        village: form.village.trim(),
        latitude: Number(form.latitude ?? DEFAULT_LAT),
        longitude: Number(form.longitude ?? DEFAULT_LON)
      }
      const farmingPayload = {
        crop: form.mainCrop,
        crops: [...new Set([form.mainCrop, ...form.crops].map(normalizePlantVillageCrop).filter(Boolean))],
        variety: form.variety.trim() || t('createProfile.varietyFallback') || 'Local',
        stage: form.cropStage,
        land_area: Number(form.landArea),
        land_unit: form.landUnit === 'hectares' ? 'Hectares' : (form.landUnit === 'Hectares' ? 'Hectares' : 'Acres'),
        soil_type: form.soilType,
        irrigation: form.irrigation
      }
      const ageNumRaw = form.age ? Number(String(form.age).trim()) : null
      const ageNum = ageNumRaw && Number.isFinite(ageNumRaw) && ageNumRaw >= 18 && ageNumRaw <= 120 ? ageNumRaw : null
      let alreadyBeneficiaryVal = null
      if (form.alreadyBeneficiary === 'true') alreadyBeneficiaryVal = true
      else if (form.alreadyBeneficiary === 'false') alreadyBeneficiaryVal = false
      const schemeProfilePayload = {
        gender: form.gender ? String(form.gender).trim() : undefined,
        age: ageNum ?? undefined,
        farmer_category: form.farmerCategory ? String(form.farmerCategory).trim() : undefined,
        land_tenure: form.landTenure ? String(form.landTenure).trim() : undefined,
        activities: Array.isArray(form.activities) && form.activities.length > 0
          ? form.activities.map((activity) => (
            activity === 'other' && form.otherActivity.trim()
              ? `other: ${form.otherActivity.trim()}`
              : activity
          ))
          : undefined,
        annual_income_band: form.annualIncomeBand ? String(form.annualIncomeBand).trim() : undefined,
        already_beneficiary: typeof alreadyBeneficiaryVal === 'boolean' ? alreadyBeneficiaryVal : undefined,
      }
      const hasAnyScheme = Object.values(schemeProfilePayload).some(v => Array.isArray(v) ? v.length > 0 : (v !== undefined && v !== null && v !== ''))
      const profileData = {
        full_name: form.fullName.trim(),
        mobile: cleanedMobile,
        location: locationPayload,
        farming: farmingPayload,
        scheme_profile: hasAnyScheme ? schemeProfilePayload : undefined
      }

      const saved = await farmerApi.createProfile(profileData)

      const savedScheme = profileData.scheme_profile || {}
      const storedUser = {
        ...(user || {}),
        id: user?.id || saved?.user_id || Date.now(),
        user_id: saved?.user_id || user?.id || Date.now(),
        name: profileData.full_name,
        full_name: profileData.full_name,
        mobile: profileData.mobile,
        email: user?.email || '',
        location: locationPayload,
        farming: farmingPayload,
        scheme_profile: savedScheme,
        schemeProfile: savedScheme,
        eligibility_profile: savedScheme,
        gender: savedScheme.gender || '',
        age: savedScheme.age ?? null,
        farmer_category: savedScheme.farmer_category || '',
        category: savedScheme.farmer_category || '',
        land_tenure: savedScheme.land_tenure || '',
        landOwnership: savedScheme.land_tenure || '',
        activities: savedScheme.activities || [],
        annual_income_band: savedScheme.annual_income_band || '',
        incomeBand: savedScheme.annual_income_band || '',
        already_beneficiary: typeof savedScheme.already_beneficiary === 'boolean' ? savedScheme.already_beneficiary : null,
        state: locationPayload.state,
        district: locationPayload.district,
        taluka: locationPayload.taluka,
        village: locationPayload.village,
        latitude: locationPayload.latitude,
        longitude: locationPayload.longitude,
        main_crop: farmingPayload.crop,
        mainCrop: farmingPayload.crop,
        variety: farmingPayload.variety,
        crop_stage: farmingPayload.stage,
        cropStage: farmingPayload.stage,
        land_area: farmingPayload.land_area,
        landArea: farmingPayload.land_area,
        land_unit: farmingPayload.land_unit,
        landUnit: farmingPayload.land_unit,
        soil_type: farmingPayload.soil_type,
        soilType: farmingPayload.soil_type,
        irrigation_type: farmingPayload.irrigation,
        irrigation: farmingPayload.irrigation,
        hasProfile: true
      }
      updateUserProfile(storedUser)
      navigate('/dashboard', { replace: true })
    } catch (err) {
      console.error('Create profile error:', err)
      setSubmitError(
        err.response?.data?.detail ||
        err.response?.data?.message ||
        err.message ||
        t('common.error')
      )
    } finally {
      setLoading(false)
    }
  }

  return (
    <Background>
      <div className="auth-language-row"><LanguageSwitcher /></div>
      <div className="page-content">
        <div style={{ textAlign: 'center', marginBottom: 32 }}>
          <div style={{ fontSize: 52, marginBottom: 12 }}>📝</div>
          <h1 className="page-title">{t('createProfile.title')}</h1>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 10, flexWrap: 'wrap', marginBottom: 18, color: 'var(--text-secondary)', fontSize: 13 }}>
          <span>{t('createProfile.buyerProfilePrompt')}</span>
          <button type="button" className="edit-profile-btn" onClick={() => navigate('/marketplace?tab=profile')}>{t('createProfile.setupBuyerProfile')}</button>
        </div>

        {submitError && (
          <div role="alert" style={{ padding: '10px 14px', borderRadius: 10, background: 'rgba(239,68,68,0.1)', color: '#fca5a5', fontSize: 13, marginBottom: 16 }}>
            ⚠️ {submitError}
          </div>
        )}

        <form onSubmit={handleSubmit} style={{ display: 'grid', gap: 24 }}>
          <GlassCard>
            <div className="section-header">
              <h2 className="section-title">👤 {t('createProfile.sectionPersonal')}</h2>
            </div>
            <div className="two-col-form">
              <FormInput
                label={t('register.fullName')}
                name="fullName"
                value={form.fullName}
                onChange={handleChange}
                placeholder={t('createProfile.fullNamePlaceholder')}
                required
                icon="👤"
                error={errors.fullName}
              />
              <FormInput
                label={t('register.mobile')}
                name="mobile"
                value={form.mobile}
                onChange={handleChange}
                placeholder={t('createProfile.mobilePlaceholder')}
                required
                icon="📱"
                error={errors.mobile}
              />
            </div>

            <div style={{ marginTop: 8, marginBottom: 20 }}>
              <GradientButton
                variant="outline"
                size="sm"
                type="button"
                onClick={useCurrentLocation}
                disabled={locating}
              >
                {locating ? t('createProfile.detectingLocation') : t('createProfile.useMyLocation')}
              </GradientButton>
              {detectedLoc && (
                <div style={{ marginTop: 10, padding: 10, background: 'var(--glass-bg)', borderRadius: 10, fontSize: 13, color: 'var(--accent-green)' }}>
                  ✓ {t('createProfile.detectedLocation')}: {detectedLoc}
                </div>
              )}
            </div>

            <div className="two-col-form">
              <FormInput
                label={t('createProfile.state')}
                name="state"
                value={form.state}
                onChange={handleChange}
                placeholder={t('createProfile.statePlaceholder')}
                required
                icon="📍"
                error={errors.state}
              />
              <FormInput
                label={t('createProfile.district')}
                name="district"
                value={form.district}
                onChange={handleChange}
                placeholder={t('createProfile.districtPlaceholder')}
                required
                icon="🏙️"
                error={errors.district}
              />
              <FormInput
                label={t('createProfile.taluka')}
                name="taluka"
                value={form.taluka}
                onChange={handleChange}
                placeholder={t('createProfile.talukaPlaceholder')}
                icon="🗺️"
                error={errors.taluka}
              />
              <FormInput
                label={t('createProfile.village')}
                name="village"
                value={form.village}
                onChange={handleChange}
                placeholder={t('createProfile.villagePlaceholder')}
                required
                icon="🏘️"
                error={errors.village}
              />
            </div>
          </GlassCard>

          <GlassCard>
            <div className="section-header">
              <h2 className="section-title">🌾 {t('createProfile.sectionFarming')}</h2>
            </div>
            <div className="two-col-form">
              <FormSelect
                label={t('createProfile.mainCrop')}
                name="mainCrop"
                value={form.mainCrop}
                onChange={handleChange}
                options={cropOptions}
                searchable
                searchPlaceholder="Search crops"
                required
                placeholder={t('common.select')}
                error={errors.mainCrop}
              />
              <div className="farmer-crop-add form-full">
                <FormSelect
                  label={t('myProfile.otherCropLabel')}
                  name="cropToAdd"
                  value={cropToAdd}
                  onChange={(event) => setCropToAdd(event.target.value)}
                  options={cropOptions}
                  searchable
                  searchPlaceholder={t('common.searchCrops')}
                  placeholder={t('createProfile.cropAddPlaceholder')}
                />
                <button className="fb-action-btn fb-action-btn--accept" type="button" onClick={addCrop} disabled={!cropToAdd || new Set([form.mainCrop, ...form.crops].filter(Boolean)).size >= 40}>
                  {t('myProfile.addCrop')}
                </button>
                <div className="farmer-crop-chip-list">
                  {[...new Set([form.mainCrop, ...form.crops].filter(Boolean))].map((crop) => (
                    <span className="farmer-crop-chip" key={crop}>
                      {crop}{crop !== form.mainCrop && <button type="button" aria-label={t('myProfile.removeCrop', { crop })} onClick={() => removeCrop(crop)}>×</button>}
                    </span>
                  ))}
                </div>
              </div>
              <FormInput
                label={t('createProfile.variety')}
                name="variety"
                value={form.variety}
                onChange={handleChange}
                placeholder={t('createProfile.varietyPlaceholder')}
                icon="🌱"
                error={errors.variety}
              />
              <FormSelect
                label={t('createProfile.cropStage')}
                name="cropStage"
                value={form.cropStage}
                onChange={handleChange}
                options={stageOptions}
                required
                placeholder={t('common.select')}
                error={errors.cropStage}
              />
              <FormInput
                label={t('createProfile.landArea')}
                name="landArea"
                type="number"
                min="0"
                step="0.01"
                value={form.landArea}
                onChange={handleChange}
                placeholder={t('createProfile.areaPlaceholder')}
                required
                icon="📐"
                error={errors.landArea}
              />
              <FormSelect
                label={t('createProfile.landUnit')}
                name="landUnit"
                value={form.landUnit}
                onChange={handleChange}
                options={[
                  { value: 'Acres', label: t('createProfile.acres') },
                  { value: 'Hectares', label: t('createProfile.hectares') }
                ]}
                required
                placeholder={t('common.select')}
              />
              <FormSelect
                label={t('createProfile.soilType')}
                name="soilType"
                value={form.soilType}
                onChange={handleChange}
                options={soilOptions}
                required
                placeholder={t('common.select')}
                error={errors.soilType}
              />
              <FormSelect
                label={t('createProfile.irrigation')}
                name="irrigation"
                value={form.irrigation}
                onChange={handleChange}
                options={irrigationOptions}
                required
                placeholder={t('common.select')}
                error={errors.irrigation}
              />
            </div>
          </GlassCard>

          <GlassCard>
            <div className="section-header">
              <h2 className="section-title">🏛️ {t('createProfile.sectionScheme')}</h2>
            </div>
            <p style={{ fontSize: 13, color: 'var(--text-muted)', marginTop: -12, marginBottom: 20, lineHeight: 1.6 }}>
              ℹ️ {t('createProfile.schemeSectionHint')}
            </p>
            <div className="two-col-form">
              <FormSelect
                label={t('createProfile.schemeGender')}
                name="gender"
                value={form.gender}
                onChange={handleChange}
                options={Object.entries((t('createProfile.schemeGenderOptions') || {})).map(([k, v]) => ({ value: k, label: v }))}
                placeholder={t('common.select')}
                icon="👤"
              />
              <FormInput
                label={t('createProfile.schemeAge')}
                name="age"
                type="number"
                min="18"
                max="120"
                step="1"
                value={form.age}
                onChange={handleChange}
                placeholder="e.g., 35"
                icon="🎂"
              />
              <FormSelect
                label={t('createProfile.schemeFarmerCategory')}
                name="farmerCategory"
                value={form.farmerCategory}
                onChange={handleChange}
                options={Object.entries((t('createProfile.schemeCategoryOptions') || {})).map(([k, v]) => ({ value: k, label: v }))}
                placeholder={t('common.select')}
                icon="🧑‍🌾"
              />
              <FormSelect
                label={t('createProfile.schemeLandTenure')}
                name="landTenure"
                value={form.landTenure}
                onChange={handleChange}
                options={Object.entries((t('createProfile.schemeTenureOptions') || {})).map(([k, v]) => ({ value: k, label: v }))}
                placeholder={t('common.select')}
                icon="🏷️"
              />
              <FormSelect
                label={t('createProfile.schemeIncome')}
                name="annualIncomeBand"
                value={form.annualIncomeBand}
                onChange={handleChange}
                options={Object.entries((t('createProfile.schemeIncomeOptions') || {})).map(([k, v]) => ({ value: k, label: v }))}
                placeholder={t('common.select')}
                icon="💰"
              />
              <FormSelect
                label={t('createProfile.schemeBeneficiary')}
                name="alreadyBeneficiary"
                value={form.alreadyBeneficiary}
                onChange={handleChange}
                options={Object.entries((t('createProfile.schemeBeneficiaryOptions') || {})).map(([k, v]) => ({ value: k, label: v }))}
                placeholder={t('common.select')}
                icon="✅"
              />
            </div>

            <div className="form-group" style={{ marginTop: 20 }}>
              <label className="form-label">🌾 {t('createProfile.schemeFarmingActivities')}</label>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 10, marginTop: 10 }}>
                {schemeActivityOptions.map(({ value, label }) => {
                  const isSel = Array.isArray(form.activities) && form.activities.includes(value)
                  return (
                    <label
                      key={value}
                      onClick={() => toggleActivity(value)}
                      style={{
                        display: 'flex', alignItems: 'center', gap: 10, padding: '10px 12px',
                        background: isSel ? 'rgba(34, 197, 94, 0.12)' : 'var(--glass-bg)',
                        border: isSel ? '1px solid var(--accent-green)' : '1px solid var(--border-color, rgba(255,255,255,0.1))',
                        borderRadius: 10, cursor: 'pointer', userSelect: 'none',
                        fontSize: 14, transition: 'all 0.15s ease'
                      }}
                    >
                      <input type="checkbox" readOnly checked={isSel} />
                      <span>{label}</span>
                    </label>
                  )
                })}
              </div>
              {form.activities.includes('other') && (
                <FormInput
                  label={t('createProfile.schemeActivityOther')}
                  name="otherActivity"
                  value={form.otherActivity}
                  onChange={handleChange}
                  placeholder={t('createProfile.schemeActivityOtherPlaceholder')}
                />
              )}
            </div>
          </GlassCard>

          <div style={{ display: 'flex', justifyContent: 'center' }}>
            <GradientButton
              type="submit"
              size="lg"
              loading={loading || authLoading}
              disabled={loading || authLoading}
            >
              {t('createProfile.createProfileBtn')}
            </GradientButton>
          </div>
        </form>
      </div>
    </Background>
  )
}

export default CreateProfile
