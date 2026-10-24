import React, { useState, useRef, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useLanguage } from '../context/LanguageContext'
import { useAuth } from '../context/AuthContext'
import { diseaseApi, getApiErrorMessage } from '../services/api'
import Background from '../components/Background'
import Navbar from '../components/Navbar'
import GlassCard from '../components/GlassCard'
import GradientButton from '../components/GradientButton'
import LanguageSwitcher from '../components/LanguageSwitcher'
import { SpeechOutputButton } from '../components/VoiceControls'
import { localizeDiseaseResult } from './diseaseResultLocalization'
import { localizeCrop } from '../translations/cropMarkets'

const MAX_IMAGE_SIZE_BYTES = 10 * 1024 * 1024
const IMAGE_TYPES_BY_EXTENSION = {
  jpg: 'image/jpeg',
  jpeg: 'image/jpeg',
  png: 'image/png',
  webp: 'image/webp'
}

const Disease = () => {
  const { t, language } = useLanguage()
  const { user } = useAuth()
  const navigate = useNavigate()
  const fileInputRef = useRef(null)
  const detectInFlightRef = useRef(false)

  const [selectedImage, setSelectedImage] = useState(null)
  const [imagePreview, setImagePreview] = useState(null)
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [resultLanguage, setResultLanguage] = useState(null)
  const [localizedResult, setLocalizedResult] = useState(null)
  const [localizedResultLanguage, setLocalizedResultLanguage] = useState(null)
  const [translationLoading, setTranslationLoading] = useState(false)
  const [translationError, setTranslationError] = useState('')
  const [translationAttempt, setTranslationAttempt] = useState(0)
  const translatedResultCacheRef = useRef(new WeakMap())
  const [storedError, setStoredError] = useState('')
  const [errorLanguage, setErrorLanguage] = useState(language)
  const [detectErrorType, setDetectErrorType] = useState('')
  const [detectErrorContext, setDetectErrorContext] = useState(null)
  const setError = (message) => {
    setStoredError(message)
    setErrorLanguage(language)
  }
  const localizedDetectionError = () => {
    const messageKeyByType = {
      backend_unavailable: 'backendUnavailable',
      file_too_large: 'imageTooLarge',
      image_invalid: 'invalidImageFile',
      invalid_image: 'invalidImageFile',
      missing_image: 'selectImageFirst',
      low_crop_conf: 'uncertainExplanation',
      low_disease_conf: 'uncertainExplanation',
      low_quality: 'lowQualityTitle',
      disease_model_unavailable: 'modelUnavailable',
      model_error: 'modelUnavailable',
      model_unavailable: 'modelUnavailable',
      non_plant: 'nonPlantExplanation',
      service_error: 'imageProcessingUnavailable',
      service_failure: 'imageProcessingUnavailable',
      service_unavailable: 'backendUnavailable',
      server_error: 'backendUnavailable',
      unsupported_crop: 'unsupportedCropTitle',
      uncertain: 'uncertainExplanation'
    }
    return t(`disease.${messageKeyByType[detectErrorType] || 'detectionFailed'}`)
  }
  const error = storedError && errorLanguage !== language
    ? localizedDetectionError()
    : storedError

  useEffect(() => {
    if (!result) {
      setLocalizedResult(null)
      setLocalizedResultLanguage(null)
      setTranslationLoading(false)
      setTranslationError('')
      return undefined
    }
    if (language === resultLanguage) {
      setLocalizedResult(result)
      setLocalizedResultLanguage(language)
      setTranslationLoading(false)
      setTranslationError('')
      return undefined
    }

    const cachedTranslations = translatedResultCacheRef.current.get(result)
    if (cachedTranslations?.has(language)) {
      setLocalizedResult(cachedTranslations.get(language))
      setLocalizedResultLanguage(language)
      setTranslationLoading(false)
      setTranslationError('')
      return undefined
    }

    let active = true
    setLocalizedResult(null)
    setLocalizedResultLanguage(null)
    setTranslationLoading(true)
    setTranslationError('')
    diseaseApi.translateResult(result, language)
      .then((response) => {
        if (!active) return
        if (!response?.success || !response?.result) {
          throw new Error(t('disease.translationUnavailable'))
        }
        const translatedResult = localizeDiseaseResult(
          { ...result, ...response.result },
          language
        )
        const translations = translatedResultCacheRef.current.get(result) || new Map()
        translations.set(language, translatedResult)
        translatedResultCacheRef.current.set(result, translations)
        setLocalizedResult(translatedResult)
        setLocalizedResultLanguage(language)
      })
      .catch(() => {
        if (!active) return
        const localResult = localizeDiseaseResult(result, language)
        const translations = translatedResultCacheRef.current.get(result) || new Map()
        translations.set(language, localResult)
        translatedResultCacheRef.current.set(result, translations)
        setLocalizedResult(localResult)
        setLocalizedResultLanguage(language)
      })
      .finally(() => {
        if (active) setTranslationLoading(false)
      })

    return () => { active = false }
  }, [language, result, resultLanguage, t, translationAttempt])

  const selectImage = (file) => {
    if (!file) return
    const extension = file.name.split('.').pop()?.toLowerCase()
    const inferredType = IMAGE_TYPES_BY_EXTENSION[extension]
    const contentType = file.type.toLowerCase() || inferredType
    if (!['image/jpeg', 'image/png', 'image/webp'].includes(contentType)) {
      setSelectedImage(null)
      setImagePreview(null)
      setResult(null)
      setResultLanguage(null)
      setLocalizedResult(null)
      setLocalizedResultLanguage(null)
      setDetectErrorType('invalid_image')
      setError(t('disease.invalidImageFile'))
      return
    }
    if (file.size > MAX_IMAGE_SIZE_BYTES) {
      setSelectedImage(null)
      setImagePreview(null)
      setResult(null)
      setResultLanguage(null)
      setLocalizedResult(null)
      setLocalizedResultLanguage(null)
      setDetectErrorType('file_too_large')
      setError(t('disease.imageTooLarge'))
      return
    }
    const uploadFile = file.type ? file : new File([file], file.name, { type: contentType })
    setError('')
    setDetectErrorType('')
    setDetectErrorContext(null)
    setResult(null)
    setResultLanguage(null)
    setLocalizedResult(null)
    setLocalizedResultLanguage(null)
    setTranslationError('')
    setTranslationLoading(false)
    setSelectedImage(uploadFile)
    const reader = new FileReader()
    reader.onload = () => setImagePreview(reader.result)
    reader.onerror = () => setError(t('disease.imagePreviewFailed'))
    reader.readAsDataURL(uploadFile)
  }

  const handleImageSelect = (e) => {
    selectImage(e.target.files?.[0])
  }

  const handleDrop = (e) => {
    e.preventDefault()
    selectImage(e.dataTransfer.files?.[0])
  }

  const handleDragOver = (e) => {
    e.preventDefault()
  }

  const clearImage = () => {
    setSelectedImage(null)
    setImagePreview(null)
    setResult(null)
    setResultLanguage(null)
    setLocalizedResult(null)
    setLocalizedResultLanguage(null)
    setTranslationError('')
    setTranslationLoading(false)
    setError('')
    setDetectErrorType('')
    setDetectErrorType('')
    setDetectErrorContext(null)
    if (fileInputRef.current) fileInputRef.current.value = ''
  }

  const handleDetect = async (event) => {
    event?.preventDefault()
    event?.stopPropagation()
    if (detectInFlightRef.current) return
    if (!selectedImage) {
      setDetectErrorType('missing_image')
      setError(t('disease.selectImageFirst'))
      return
    }
    detectInFlightRef.current = true
    setLoading(true)
    setError('')
    setResult(null)
    setResultLanguage(null)
    setLocalizedResult(null)
    setLocalizedResultLanguage(null)
    setTranslationError('')
    setTranslationLoading(false)
    setDetectErrorType('')
    setDetectErrorContext(null)
    try {
      const requestStarted = performance.now()
      const formData = new FormData()
      formData.append('image', selectedImage)
      if (user?.farming?.crop) {
        formData.append('crop', user.farming.crop)
      }
      const res = await diseaseApi.detectDisease(formData, language)
      console.info(
        'Disease detection frontend latency ms:',
        Math.round(performance.now() - requestStarted),
        'backend timing:',
        res?.data?.performance || res?.performance
      )
      if (res?.success === false) {
        const errType = res?.error_type || ''
        const errCtx = res?.image_info || null
        setDetectErrorType(errType)
        setDetectErrorContext(errCtx)
        setError(res?.error || t('disease.detectionFailed'))
      } else if (res?.result) {
        const r = res.result
        const rErrType = r?.error_type || ''
        if (r?.ok === false && rErrType) {
          setDetectErrorType(rErrType)
          setDetectErrorContext({ supported: r?.supported_crops, raw_class: r?.raw_class })
          setError(r?.error || r?.diagnostic_note || t('disease.detectionFailed'))
        } else {
          setResult(r)
          setResultLanguage(
            r?._analysis_source?.startsWith('plantvillage_mobilenetv2') ? 'en' : language
          )
        }
      } else if (!res) {
        setError(t('disease.detectionFailed'))
      } else if (res.disease) {
        setResult(res)
        setResultLanguage(
          res?._analysis_source?.startsWith('plantvillage_mobilenetv2') ? 'en' : language
        )
      } else {
        setError(t('disease.detectionFailed'))
      }
    } catch (err) {
      console.error('Disease detection error:', err)
      const response = err?.response?.data
      setDetectErrorType(
        response?.error_type
          || (err?.response?.status === 413
            ? 'file_too_large'
            : err?.response?.status === 415
              ? 'invalid_image'
              : 'backend_unavailable')
      )
      setDetectErrorContext(response?.image_info || null)
      setError(
        response?.error
          || response?.detail
          || getApiErrorMessage(err, t('disease.backendUnavailable'))
      )
    } finally {
      detectInFlightRef.current = false
      setLoading(false)
    }
  }

  const renderSeverityBadge = (severity) => {
    const sev = (severity || '').toLowerCase()
    if (sev.includes('mild') && sev.includes('moderate')) {
      return <span className="severity-badge severity-badge--moderate">🟡 {t('disease.severityMildModerate')}</span>
    }
    if (sev.includes('moderate') && sev.includes('severe')) {
      return <span className="severity-badge severity-badge--severe">🟠 {t('disease.severityModerateSevere')}</span>
    }
    if (sev.includes('none')) {
      return <span className="severity-badge severity-badge--mild">🟢 {t('disease.severityNone')}</span>
    }
    if (sev.includes('severe')) {
      return <span className="severity-badge severity-badge--severe">🔴 {t('disease.severitySevere')}</span>
    }
    if (sev.includes('mod')) {
      return <span className="severity-badge severity-badge--moderate">🟡 {t('disease.severityModerate')}</span>
    }
    return <span className="severity-badge severity-badge--mild">🟢 {t('disease.severityMild')}</span>
  }

  const displayResult = localizedResultLanguage === language
    ? localizeDiseaseResult(localizedResult, language)
    : null
  const diagnosisSpeechText = (() => {
    if (!displayResult) return ''
    const untranslated = new Set(displayResult._untranslated_fields || [])
    const sections = []
    const diseaseName = untranslated.has('disease_display')
      ? ''
      : displayResult.disease_display || displayResult.disease || ''
    if (diseaseName) sections.push(`${t('disease.diseaseLabel')}: ${diseaseName}`)

    const diagnosticNote = untranslated.has('diagnostic_note') ? '' : displayResult.diagnostic_note
    if (diagnosticNote) {
      sections.push(`${t('disease.diagnosticNote')}: ${diagnosticNote}`)
    }

    const symptoms = untranslated.has('symptoms') || !Array.isArray(displayResult.symptoms)
      ? []
      : displayResult.symptoms.filter((item) => typeof item === 'string' && item.trim())
    if (symptoms.length) {
      const basis = displayResult.symptoms_basis === 'typical_reference'
        ? `${t('disease.typicalSymptomsNotice')} `
        : ''
      sections.push(`${t('disease.symptoms')}: ${basis}${symptoms.join('. ')}`)
    }

    const treatment = untranslated.has('recommended_management')
      ? []
      : displayResult.recommended_management?.length
        ? displayResult.recommended_management
        : displayResult.treatment || []
    if (treatment.length) {
      sections.push(`${t('disease.treatment')}: ${treatment.filter((item) => typeof item === 'string' && item.trim()).join('. ')}`)
    }

    const prevention = untranslated.has('prevention') || !Array.isArray(displayResult.prevention)
      ? []
      : displayResult.prevention.filter((item) => typeof item === 'string' && item.trim())
    if (prevention.length) {
      sections.push(`${t('disease.prevention')}: ${prevention.join('. ')}`)
    }

    const warnings = untranslated.has('safety_warnings') || !Array.isArray(displayResult.safety_warnings)
      ? []
      : displayResult.safety_warnings.filter((item) => typeof item === 'string' && item.trim())
    if (warnings.length) {
      sections.push(`${t('disease.safetyWarnings')}: ${warnings.join('. ')}`)
    }
    return sections.join('. ')
  })()

  return (
    <Background>
      <Navbar />
      <div className="page-content animate-fade-in">
        <div className="section-header disease-page-header">
          <div>
            <h1 className="page-title">🌿 {t('disease.title')}</h1>
            <p className="page-subtitle">{t('disease.subtitle')}</p>
          </div>
          <LanguageSwitcher />
        </div>

        <div className="disease-layout">
          <div className="disease-upload-col">
            <GlassCard className="disease-upload-card">
              <div className="section-header" style={{ marginTop: 0 }}>
                <h2 className="section-title">📷 {t('disease.uploadSection')}</h2>
              </div>

              {!imagePreview ? (
                <div
                  className="upload-area"
                  role="button"
                  tabIndex={0}
                  aria-label={t('disease.dragOrClick')}
                  onClick={() => fileInputRef.current?.click()}
                  onKeyDown={(event) => {
                    if (event.key === 'Enter' || event.key === ' ') {
                      event.preventDefault()
                      fileInputRef.current?.click()
                    }
                  }}
                  onDrop={handleDrop}
                  onDragOver={handleDragOver}
                >
                  <div className="upload-area-icon">🖼️</div>
                  <div className="upload-area-title">{t('disease.dragOrClick')}</div>
                  <div className="upload-area-hint">{t('disease.supportedFormats')}</div>
                </div>
              ) : (
                <div className="preview-wrapper">
                  <img src={imagePreview} alt={t('disease.imagePreviewAlt')} className="image-preview" />
                  <button
                    type="button"
                    className="clear-image-btn"
                    onClick={clearImage}
                    title={t('disease.removeImage')}
                    aria-label={t('disease.removeImage')}
                  >
                    ✕
                  </button>
                </div>
              )}

              <input
                ref={fileInputRef}
                type="file"
                accept=".jpg,.jpeg,.png,.webp,image/jpeg,image/png,image/webp"
                onChange={handleImageSelect}
                style={{ display: 'none' }}
              />

              {error && <div className="form-error-text" style={{ marginTop: 16 }}>⚠️ {error}</div>}

              <div style={{ marginTop: 22, display: 'flex', gap: 12 }}>
                <GradientButton
                  type="button"
                  onClick={handleDetect}
                  disabled={loading}
                  variant="primary"
                  fullWidth
                >
                  {loading
                    ? t('disease.analyzing')
                    : t('disease.detectBtn')}
                </GradientButton>
              </div>
            </GlassCard>

            <GlassCard className="disease-tips-card">
              <div className="section-header" style={{ marginTop: 0 }}>
                <h2 className="section-title">💡 {t('disease.tipsTitle')}</h2>
              </div>
              <ul className="disease-tips-list">
                <li>{t('disease.tip1')}</li>
                <li>{t('disease.tip2')}</li>
                <li>{t('disease.tip3')}</li>
                <li>{t('disease.tip4')}</li>
                <li>{t('disease.tip5')}</li>
              </ul>
            </GlassCard>
          </div>

          <div className="disease-result-col">
            {!result && !loading && detectErrorType && (
              <div className="disease-result-wrapper animate-fade-in">
                <GlassCard className="disease-result-header-card">
                  {(['unsupported_crop'].includes(detectErrorType.toLowerCase())) ? (
                    <div style={{ display: 'flex', alignItems: 'flex-start', gap: 12 }}>
                      <div className="disease-result-icon" style={{ fontSize: 44 }}>🚫</div>
                      <div style={{ width: '100%' }}>
                        <div className="disease-result-detected">{t('disease.detected')}</div>
                        <h2 className="disease-result-name" style={{ margin: '8px 0 6px 0', fontSize: '1.15rem' }}>
                          {t('disease.unsupportedCropTitle')}
                        </h2>
                        <div style={{ opacity: 0.92, marginTop: 6, lineHeight: 1.6 }}>
                          {error}
                        </div>
                        {detectErrorContext?.supported && Array.isArray(detectErrorContext.supported) && detectErrorContext.supported.length > 0 && (
                          <div style={{ marginTop: 18 }}>
                            <div style={{ fontWeight: 600, marginBottom: 8, fontSize: '0.95rem' }}>
                              ✅ {t('disease.supportedCrops')}
                            </div>
                            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                              {detectErrorContext.supported.map((c, i) => (
                                <span key={i}
                                  style={{
                                    padding: '6px 12px',
                                    borderRadius: 999,
                                    background: 'rgba(16, 185, 129, 0.14)',
                                    border: '1px solid rgba(16, 185, 129, 0.35)',
                                    color: 'var(--accent-green-light)',
                                    fontSize: 13,
                                    fontWeight: 500
                                  }}
                                >
                                  {localizeCrop(c, language)}
                                </span>
                              ))}
                            </div>
                            <div style={{ fontSize: 13, opacity: 0.75, marginTop: 10, lineHeight: 1.55 }}>
                              {t('disease.unsupportedCropHelp')}
                            </div>
                          </div>
                        )}
                      </div>
                    </div>
                  ) : (['low_quality', 'invalid_image', 'service_failure'].includes(detectErrorType.toLowerCase()) ? (
                    <div style={{ display: 'flex', alignItems: 'flex-start', gap: 12 }}>
                      <div className="disease-result-icon" style={{ fontSize: 44 }}>
                        {detectErrorType.toLowerCase() === 'invalid_image' ? '🖼️' : '📷'}
                      </div>
                      <div style={{ width: '100%' }}>
                        <div className="disease-result-detected">
                          {t('disease.detected')}
                        </div>
                        <h2 className="disease-result-name" style={{ margin: '8px 0 6px 0', fontSize: '1.15rem' }}>
                          {detectErrorType.toLowerCase() === 'low_quality'
                            ? t('disease.lowQualityTitle')
                            : detectErrorType.toLowerCase() === 'invalid_image'
                              ? t('disease.invalidImageTitle')
                              : t('disease.imageProcessingUnavailable')}
                        </h2>
                        <div style={{ opacity: 0.92, marginTop: 6, lineHeight: 1.6 }}>{error}</div>
                        {detectErrorContext?.width && (
                          <div style={{ marginTop: 12, fontSize: 13, opacity: 0.8 }}>
                            {t('disease.imageDimensions')}: <strong>{detectErrorContext.width} × {detectErrorContext.height} px</strong>
                            {detectErrorContext?.size_kb ? ` · ${t('disease.imageSize')}: ${Math.round(detectErrorContext.size_kb)} KB` : ''}
                          </div>
                        )}
                      </div>
                    </div>
                  ) : (
                    <div style={{ display: 'flex', alignItems: 'flex-start', gap: 12 }}>
                      <div className="disease-result-icon" style={{ fontSize: 44 }}>⚠️</div>
                      <div style={{ width: '100%' }}>
                        <div className="disease-result-detected">{t('disease.detected')}</div>
                        <h2 className="disease-result-name" style={{ margin: '8px 0 6px 0', fontSize: '1.15rem' }}>
                          {t('disease.detectionUnableTitle')}
                        </h2>
                        <div style={{ opacity: 0.92, marginTop: 6, lineHeight: 1.6, whiteSpace: 'pre-wrap' }}>
                          {error}
                        </div>
                      </div>
                    </div>
                  ))}
                  <div style={{ display: 'flex', gap: 12, marginTop: 20, flexWrap: 'wrap' }}>
                    <GradientButton onClick={clearImage} variant="outline">
                      🔄 {t('disease.testAnother')}
                    </GradientButton>
                    <GradientButton onClick={handleDetect} disabled={loading || !selectedImage}>
                      ↻ {t('disease.retryAnalysis')}
                    </GradientButton>
                    <GradientButton onClick={() => navigate('/ai-assistant')} variant="secondary">
                      🤖 {t('disease.askAssistant')}
                    </GradientButton>
                  </div>
                </GlassCard>
              </div>
            )}

            {!result && !loading && !detectErrorType && (
              <GlassCard className="disease-placeholder-card">
                <div className="disease-placeholder-icon">🔬</div>
                <div className="disease-placeholder-title">{t('disease.resultPlaceholder')}</div>
                <div className="disease-placeholder-hint">{t('disease.resultPlaceholderHint')}</div>
              </GlassCard>
            )}

            {loading && (
              <GlassCard className="disease-placeholder-card">
                <div className="loading-spinner" style={{ width: 48, height: 48, borderWidth: 4 }} />
                <div className="disease-placeholder-title" style={{ marginTop: 18 }}>
                  {t('disease.aiThinking')}
                </div>
                <div className="disease-placeholder-hint">{t('disease.aiThinkingHint')}</div>
              </GlassCard>
            )}

            {result && translationLoading && (
              <GlassCard className="disease-placeholder-card">
                <div className="loading-spinner" style={{ width: 40, height: 40, borderWidth: 4 }} />
                <div className="disease-placeholder-title" style={{ marginTop: 18 }}>
                  {t('disease.translatingDiagnosis')}
                </div>
              </GlassCard>
            )}

            {result && translationError && !translationLoading && (
              <GlassCard className="disease-result-header-card">
                <div style={{ color: 'var(--text-primary)', lineHeight: 1.6 }}>
                  ⚠️ {translationError || t('disease.translationUnavailable')}
                </div>
                <div style={{ marginTop: 14 }}>
                  <GradientButton
                    type="button"
                    onClick={() => setTranslationAttempt((attempt) => attempt + 1)}
                    variant="outline"
                  >
                    ↻ {t('disease.retryTranslation')}
                  </GradientButton>
                </div>
              </GlassCard>
            )}

            {displayResult && (
              <div className="disease-result-wrapper animate-fade-in">
                {displayResult.translation_notice && (
                  <GlassCard className="disease-section-card" role="status">
                    <div style={{ color: 'var(--text-primary)', lineHeight: 1.6 }}>
                      ⚠️ {displayResult.translation_notice}
                    </div>
                  </GlassCard>
                )}
                {displayResult.is_valid_plant_image === false ? (
                  <GlassCard className="disease-result-header-card">
                    <div style={{ display: 'flex', alignItems: 'flex-start', gap: 12 }}>
                      <div className="disease-result-icon" style={{ fontSize: 44 }}>🚫</div>
                      <div style={{ width: '100%' }}>
                        <div className="disease-result-detected">{t('disease.detected')}</div>
                        <h2 className="disease-result-name" style={{ margin: '8px 0 6px 0', fontSize: '1.15rem' }}>
                          {t('disease.nonPlantImage')}
                        </h2>
                        <div style={{ opacity: 0.9, marginTop: 4 }}>
                          {displayResult.diagnostic_note || displayResult.error ||
                            t('disease.nonPlantExplanation')}
                        </div>
                      </div>
                    </div>
                    <div style={{ display: 'flex', gap: 12, marginTop: 16 }}>
                      <GradientButton onClick={clearImage} variant="outline">
                        🔄 {t('disease.testAnother')}
                      </GradientButton>
                      <GradientButton onClick={() => navigate('/ai-assistant')} variant="secondary">
                        🤖 {t('disease.askAssistant')}
                      </GradientButton>
                    </div>
                  </GlassCard>
                ) : (
                <>
                {(displayResult.uncertain || displayResult.diagnostic_note) && (
                  <GlassCard className="disease-section-card" style={{ borderLeft: '4px solid #d4a017' }}>
                    <strong>{displayResult.uncertain ? t('disease.uncertain') : t('disease.diagnosticNote')}</strong>
                    <div style={{ marginTop: 6, lineHeight: 1.5 }}>
                      {displayResult.diagnostic_note || t('disease.uncertainExplanation')}
                    </div>
                  </GlassCard>
                )}
                {[
                  ['safety_warnings', 'disease.safetyWarnings'],
                  ['warnings', 'disease.warnings'],
                  ['precautions', 'disease.precautions']
                ].map(([field, labelKey]) => {
                  const value = displayResult[field]
                  const warnings = Array.isArray(value)
                    ? value
                    : typeof value === 'string' && value.trim()
                      ? [value]
                      : []
                  if (warnings.length === 0) return null
                  return (
                    <GlassCard key={field} className="disease-section-card" role="alert">
                      <h2 className="section-title">⚠️ {t(labelKey)}</h2>
                      <ul className="disease-list">
                        {warnings.map((warning, index) => (
                          <li key={`${field}-${index}`}>{warning}</li>
                        ))}
                      </ul>
                    </GlassCard>
                  )
                })}
                <GlassCard className="disease-result-header-card glowGreen">
                  <div className="disease-result-header-main">
                    <div className="disease-result-icon">🌱</div>
                    <div style={{ width: '100%' }}>
                      <div className="disease-result-detected" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        {t('disease.detected')}
                        <SpeechOutputButton text={diagnosisSpeechText} />
                      </div>
                      <div className="disease-result-info-grid" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 8, marginTop: 10 }}>
                        {displayResult.crop && (
                          <div className="result-info-item crop-badge" style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                            <strong style={{ opacity: 0.85 }}>🌾 {t('disease.cropLabel')}:</strong>
                            <span style={{ fontWeight: 600 }}>{displayResult.crop_display || displayResult.crop}</span>
                          </div>
                        )}
                        <div className="result-info-item disease-name-item" style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                          <strong style={{ opacity: 0.85 }}>🦠 {t('disease.diseaseLabel')}:</strong>
                          <h2 className="disease-result-name" style={{ display: 'inline', margin: 0, fontSize: '1.05rem' }}>{displayResult.disease_display || displayResult.disease}</h2>
                        </div>
                        {(typeof displayResult.disease_confidence === 'number' || typeof displayResult.confidence === 'number') && (
                          <div className="result-info-item confidence-badge" style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                            <strong style={{ opacity: 0.85 }}>🎯 {t('disease.confidenceLabel')}:</strong>
                            <span style={{ fontWeight: 700 }}>
                              {Math.round(typeof displayResult.disease_confidence === 'number' ? displayResult.disease_confidence : displayResult.confidence)}%
                              <span style={{ opacity: 0.7, fontWeight: 400, fontSize: '0.85em' }}> ({t('disease.confidence')})</span>
                            </span>
                          </div>
                        )}
                        {typeof displayResult.crop_confidence === 'number' && (
                          <div className="result-info-item crop-confidence-badge" style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                            <strong style={{ opacity: 0.85 }}>🌾 {t('disease.cropConfidenceLabel')}:</strong>
                            <span style={{ fontWeight: 600 }}>{Math.round(displayResult.crop_confidence)}%</span>
                          </div>
                        )}
                        {displayResult.severity && (
                          <div className="result-info-item" style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                            <strong style={{ opacity: 0.85 }}>⚠️ {t('disease.severityLabel')}:</strong>
                            {renderSeverityBadge(displayResult.severity_original || displayResult.severity)}
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                </GlassCard>

                <GlassCard className="disease-section-card">
                  <div className="section-header" style={{ marginTop: 0 }}>
                    <h2 className="section-title">🔎 {t('disease.symptoms')}</h2>
                  </div>
                  {displayResult.symptoms_basis === 'typical_reference' && (
                    <p style={{ opacity: 0.8, marginTop: 0 }}>
                      {t('disease.typicalSymptomsNotice')}
                    </p>
                  )}
                  {displayResult.symptoms_basis === 'unavailable' && (
                    <p style={{ opacity: 0.8, marginTop: 0 }}>
                      {t('disease.symptomsUnavailable')}
                    </p>
                  )}
                  <ul className="disease-list">
                    {displayResult.symptoms?.length
                      ? displayResult.symptoms.map((s, i) => (
                      <li key={i}>{s}</li>
                      ))
                      : <li>{t('disease.informationUnavailable')}</li>}
                  </ul>
                </GlassCard>

                <GlassCard className="disease-section-card">
                  <div className="section-header" style={{ marginTop: 0 }}>
                    <h2 className="section-title">🧪 {t('disease.causes')}</h2>
                  </div>
                  <ul className="disease-list">
                    {(displayResult.possible_causes?.length ? displayResult.possible_causes : displayResult.causes)?.length
                      ? (displayResult.possible_causes?.length ? displayResult.possible_causes : displayResult.causes).map((c, i) => (
                      <li key={i}>{c}</li>
                      ))
                      : <li>{t('disease.informationUnavailable')}</li>}
                  </ul>
                </GlassCard>

                <GlassCard className="disease-section-card">
                  <div className="section-header" style={{ marginTop: 0 }}>
                    <h2 className="section-title">💊 {t('disease.treatment')}</h2>
                  </div>
                  <ul className="disease-list disease-list--primary">
                    {(displayResult.recommended_management?.length ? displayResult.recommended_management : displayResult.treatment)?.length
                      ? (displayResult.recommended_management?.length ? displayResult.recommended_management : displayResult.treatment).map((tr, i) => (
                      <li key={i}>{tr}</li>
                      ))
                      : <li>{t('disease.informationUnavailable')}</li>}
                  </ul>
                </GlassCard>

                <GlassCard className="disease-section-card">
                  <div className="section-header" style={{ marginTop: 0 }}>
                    <h2 className="section-title">🛡️ {t('disease.prevention')}</h2>
                  </div>
                  <ul className="disease-list disease-list--success">
                    {displayResult.prevention?.length
                      ? displayResult.prevention.map((p, i) => (
                      <li key={i}>{p}</li>
                      ))
                      : <li>{t('disease.informationUnavailable')}</li>}
                  </ul>
                </GlassCard>

                <div style={{ display: 'flex', gap: 12, marginTop: 4 }}>
                  <GradientButton onClick={clearImage} variant="outline">
                    🔄 {t('disease.testAnother')}
                  </GradientButton>
                  <GradientButton onClick={() => navigate('/ai-assistant')} variant="secondary">
                    🤖 {t('disease.askAssistant')}
                  </GradientButton>
                </div>
                </>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </Background>
  )
}

export default Disease
