import React, { useEffect, useState } from 'react'
import { useLanguage } from '../context/LanguageContext'
import { localizeDisplayName } from '../translations/brand'
import { localizeLocation } from '../translations/locations'
import { localizeVariety } from '../translations/cropMarkets'
import { useAuth } from '../context/AuthContext'
import { farmerApi } from '../services/api'
import Background from '../components/Background'
import Navbar from '../components/Navbar'
import GlassCard from '../components/GlassCard'
import FormInput from '../components/FormInput'
import FormSelect from '../components/FormSelect'
import GradientButton from '../components/GradientButton'
import {
  getPlantVillageCropOptions,
  normalizePlantVillageCrop,
  translatePlantVillageCrop
} from '../constants/crops'

const profileToForm = (user) => {
  const farming = user?.farming || {}
  const landUnit = farming.land_unit ?? user?.land_unit ?? user?.landUnit ?? 'Acres'

  return {
    fullName: user?.full_name || user?.name || '',
    mobile: user?.mobile || '',
    email: user?.email || '',
    profilePhotoUrl: user?.profile_photo_url || '',
    discoverable: Boolean(user?.discoverable),
    state: user?.location?.state || user?.state || '',
    district: user?.location?.district || user?.district || '',
    taluka: user?.location?.taluka || user?.taluka || '',
    village: user?.location?.village || user?.village || '',
    mainCrop: normalizePlantVillageCrop(farming.crop || user?.main_crop || user?.mainCrop || ''),
    crops: Array.isArray(farming.crops) ? farming.crops : [],
    variety: farming.variety ?? user?.variety ?? '',
    cropStage: farming.stage || user?.crop_stage || user?.cropStage || '',
    landArea: farming.land_area ?? user?.land_area ?? user?.landArea ?? '',
    landUnit: String(landUnit).toLowerCase() === 'hectares' ? 'Hectares' : 'Acres',
    soilType: farming.soil_type || user?.soil_type || user?.soilType || '',
    irrigation: farming.irrigation || user?.irrigation_type || user?.irrigation || ''
  }
}

const MyProfile = () => {
  const { t, language } = useLanguage()
  const { user, updateUserProfile } = useAuth()
  const [editing, setEditing] = useState(false)
  const [saving, setSaving] = useState(false)
  const [successMsg, setSuccessMsg] = useState('')
  const [saveError, setSaveError] = useState('')
  const [cropToAdd, setCropToAdd] = useState('')

  const [form, setForm] = useState(() => profileToForm(user))

  useEffect(() => {
    if (!editing && user) setForm(profileToForm(user))
  }, [editing, user])

  const handleChange = (e) => {
    const { name, value } = e.target
    setForm((prev) => ({ ...prev, [name]: value }))
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

  const cropOptions = getPlantVillageCropOptions(t)
  const stageOptions = ['seedling', 'vegetative', 'flowering', 'fruiting', 'harvesting'].map(
    (k) => ({ value: k, label: t(`createProfile.stages.${k}`) })
  )
  const soilOptions = ['black', 'red', 'alluvial', 'sandy', 'other'].map(
    (k) => ({ value: k, label: t(`createProfile.soils.${k}`) })
  )
  const irrigationOptions = ['drip', 'sprinkler', 'rainfed', 'canal', 'other'].map(
    (k) => ({ value: k, label: t(`createProfile.irrigations.${k}`) })
  )

  const translate = (val, translations) => val ? (translations[val] || val) : '—'

  const handleSave = async () => {
    setSaving(true)
    setSaveError('')
    try {
      const profileData = {
        full_name: form.fullName.trim(),
        mobile: form.mobile.trim(),
        profile_photo_url: form.profilePhotoUrl.trim() || null,
        discoverable: form.discoverable,
        location: {
          state: form.state.trim(),
          district: form.district.trim(),
          taluka: form.taluka.trim(),
          village: form.village.trim(),
          latitude: Number(user?.location?.latitude ?? user?.latitude),
          longitude: Number(user?.location?.longitude ?? user?.longitude)
        },
        farming: {
          crop: form.mainCrop,
          crops: [...new Set([form.mainCrop, ...form.crops].map(normalizePlantVillageCrop).filter(Boolean))],
          variety: form.variety.trim(),
          stage: form.cropStage,
          land_area: Number(form.landArea),
          land_unit: form.landUnit,
          soil_type: form.soilType,
          irrigation: form.irrigation
        },
      }
      const savedProfile = await farmerApi.updateProfile(profileData)
      updateUserProfile({ ...savedProfile, email: form.email })
      setEditing(false)
      setSuccessMsg(t('common.success'))
      setTimeout(() => setSuccessMsg(''), 3000)
    } catch (err) {
      console.error('Save profile error:', err)
      setSaveError(typeof err.response?.data?.detail === 'string' ? err.response.data.detail : t('common.error'))
    } finally {
      setSaving(false)
    }
  }

  const cropTrans = (value) => translatePlantVillageCrop(normalizePlantVillageCrop(value) || '—', t)
  const stageTrans = (v) => translate(v, {
    seedling: t('createProfile.stages.seedling'),
    vegetative: t('createProfile.stages.vegetative'),
    flowering: t('createProfile.stages.flowering'),
    fruiting: t('createProfile.stages.fruiting'),
    harvesting: t('createProfile.stages.harvesting')
  })
  const soilTrans = (v) => translate(v, {
    black: t('createProfile.soils.black'),
    red: t('createProfile.soils.red'),
    alluvial: t('createProfile.soils.alluvial'),
    sandy: t('createProfile.soils.sandy'),
    other: t('createProfile.soils.other')
  })
  const irrigTrans = (v) => translate(v, {
    drip: t('createProfile.irrigations.drip'),
    sprinkler: t('createProfile.irrigations.sprinkler'),
    rainfed: t('createProfile.irrigations.rainfed'),
    canal: t('createProfile.irrigations.canal'),
    other: t('createProfile.irrigations.other')
  })

  const landUnitLabel = form.landUnit === 'Hectares' ? t('createProfile.hectares') : t('createProfile.acres')
  const landDisplay = form.landArea ? `${form.landArea} ${landUnitLabel}` : '—'
  return (
    <Background>
      <Navbar />
      <div className="page-content animate-fade-in">
        <div className="section-header" style={{ marginBottom: 24 }}>
          <div>
            <h1 className="page-title">👤 {t('myProfile.title')}</h1>
            {successMsg && (
              <div style={{ color: 'var(--accent-green)', marginTop: 8, fontSize: 14 }}>✓ {successMsg}</div>
            )}
            {saveError && (
              <div role="alert" style={{ color: 'var(--accent-red)', marginTop: 8, fontSize: 14 }}>{saveError}</div>
            )}
          </div>
          {!editing ? (
            <GradientButton variant="primary" size="md" onClick={() => setEditing(true)}>
              ✏️ {t('myProfile.editProfile')}
            </GradientButton>
          ) : (
            <div style={{ display: 'flex', gap: 10 }}>
              <GradientButton variant="outline" size="md" onClick={() => setEditing(false)}>
                {t('myProfile.cancelEdit')}
              </GradientButton>
              <GradientButton variant="secondary" size="md" onClick={handleSave} loading={saving} disabled={saving}>
                {t('myProfile.saveChanges')}
              </GradientButton>
            </div>
          )}
        </div>

        <div className="dashboard-grid">
          <GlassCard className="profile-section">
            <h2 className="section-title">👤 {t('myProfile.personalInfo')}</h2>
            {!editing ? (
              <div className="profile-info-grid">
                <div className="info-item">
                  <div className="info-label">{t('myProfile.fullName')}</div>
                  <div className="info-value">{localizeDisplayName(form.fullName, language) || '—'}</div>
                </div>
                <div className="info-item">
                  <div className="info-label">{t('myProfile.mobile')}</div>
                  <div className="info-value">{form.mobile || '—'}</div>
                </div>
                <div className="info-item">
                  <div className="info-label">{t('myProfile.email')}</div>
                  <div className="info-value">{form.email || '—'}</div>
                </div>
              </div>
            ) : (
              <div className="two-col-form">
                <FormInput label={t('myProfile.fullName')} name="fullName" value={form.fullName} onChange={handleChange} icon="👤" />
                <FormInput label={t('myProfile.mobile')} name="mobile" value={form.mobile} onChange={handleChange} icon="📱" />
                <FormInput label={t('myProfile.email')} name="email" type="email" value={form.email} onChange={handleChange} icon="📧" />
                <FormInput label={`${t('common.photoUrl')} (${t('common.optional')})`} name="profilePhotoUrl" type="url" value={form.profilePhotoUrl} onChange={handleChange} icon="🖼️" />
                <label className="form-full" style={{ display: 'flex', alignItems: 'center', gap: 10, color: 'var(--text-primary)' }}>
                  <input
                    type="checkbox"
                    checked={form.discoverable}
                    onChange={(event) => setForm((prev) => ({ ...prev, discoverable: event.target.checked }))}
                  />
                  Let buyers find my public farmer profile in the marketplace
                </label>
              </div>
            )}
          </GlassCard>

          <GlassCard className="profile-section">
            <h2 className="section-title">📍 {t('myProfile.locationInfo')}</h2>
            {!editing ? (
              <div className="profile-info-grid">
                <div className="info-item">
                  <div className="info-label">{t('myProfile.state')}</div>
                  <div className="info-value">{localizeLocation(form.state, language) || '—'}</div>
                </div>
                <div className="info-item">
                  <div className="info-label">{t('myProfile.district')}</div>
                  <div className="info-value">{localizeLocation(form.district, language) || '—'}</div>
                </div>
                <div className="info-item">
                  <div className="info-label">{t('myProfile.taluka')}</div>
                  <div className="info-value">{localizeLocation(form.taluka, language) || '—'}</div>
                </div>
                <div className="info-item">
                  <div className="info-label">{t('myProfile.village')}</div>
                  <div className="info-value">{localizeLocation(form.village, language) || '—'}</div>
                </div>
              </div>
            ) : (
              <div className="two-col-form">
                <FormInput label={t('myProfile.state')} name="state" value={form.state} onChange={handleChange} icon="📍" />
                <FormInput label={t('myProfile.district')} name="district" value={form.district} onChange={handleChange} icon="🏙️" />
                <FormInput label={t('myProfile.taluka')} name="taluka" value={form.taluka} onChange={handleChange} icon="🗺️" />
                <FormInput label={t('myProfile.village')} name="village" value={form.village} onChange={handleChange} icon="🏘️" />
              </div>
            )}
          </GlassCard>

          <GlassCard className="profile-section">
            <h2 className="section-title">🌾 {t('myProfile.farmingInfo')}</h2>
            {!editing ? (
              <div className="profile-info-grid">
                <div className="info-item">
                  <div className="info-label">{t('myProfile.mainCrop')}</div>
                  <div className="info-value">{cropTrans(form.mainCrop)}</div>
                </div>
                <div className="info-item">
                  <div className="info-label">{t('myProfile.otherCrops')}</div>
                  <div className="info-value">{form.crops.filter((crop) => crop !== form.mainCrop).map(cropTrans).join(', ') || '—'}</div>
                </div>
                <div className="info-item">
                  <div className="info-label">{t('myProfile.variety')}</div>
                  <div className="info-value">{form.variety ? localizeVariety(form.variety, language) : '—'}</div>
                </div>
                <div className="info-item">
                  <div className="info-label">{t('myProfile.cropStage')}</div>
                  <div className="info-value">{stageTrans(form.cropStage)}</div>
                </div>
                <div className="info-item">
                  <div className="info-label">{t('myProfile.landArea')}</div>
                  <div className="info-value">{landDisplay}</div>
                </div>
                <div className="info-item">
                  <div className="info-label">{t('myProfile.soilType')}</div>
                  <div className="info-value">{soilTrans(form.soilType)}</div>
                </div>
                <div className="info-item">
                  <div className="info-label">{t('myProfile.irrigation')}</div>
                  <div className="info-value">{irrigTrans(form.irrigation)}</div>
                </div>
              </div>
            ) : (
              <div className="two-col-form">
                <FormSelect label={t('myProfile.mainCrop')} name="mainCrop" value={form.mainCrop} onChange={handleChange} options={cropOptions} placeholder={t('common.select')} searchable searchPlaceholder={t('common.searchCrops')} />
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
                        {cropTrans(crop)}{crop !== form.mainCrop && <button type="button" aria-label={t('myProfile.removeCrop', { crop: cropTrans(crop) })} onClick={() => removeCrop(crop)}>×</button>}
                      </span>
                    ))}
                  </div>
                </div>
                <FormInput label={t('myProfile.variety')} name="variety" value={form.variety} onChange={handleChange} icon="🌱" />
                <FormSelect label={t('myProfile.cropStage')} name="cropStage" value={form.cropStage} onChange={handleChange} options={stageOptions} placeholder={t('common.select')} />
                <FormInput label={t('myProfile.landArea')} name="landArea" type="number" value={form.landArea} onChange={handleChange} icon="📐" />
                <FormSelect
                  label={t('createProfile.landUnit')}
                  name="landUnit"
                  value={form.landUnit}
                  onChange={handleChange}
                  options={[
                    { value: 'Acres', label: t('createProfile.acres') },
                    { value: 'Hectares', label: t('createProfile.hectares') }
                  ]}
                />
                <FormSelect label={t('myProfile.soilType')} name="soilType" value={form.soilType} onChange={handleChange} options={soilOptions} placeholder={t('common.select')} />
                <FormSelect label={t('myProfile.irrigation')} name="irrigation" value={form.irrigation} onChange={handleChange} options={irrigationOptions} placeholder={t('common.select')} />
              </div>
            )}
          </GlassCard>
        </div>
      </div>
    </Background>
  )
}

export default MyProfile
