import React, { useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useLanguage } from '../context/LanguageContext'
import { useAuth } from '../context/AuthContext'
import { getApiErrorMessage } from '../services/api'
import Background from '../components/Background'
import GlassCard from '../components/GlassCard'
import FormInput from '../components/FormInput'
import GradientButton from '../components/GradientButton'
import LegalNotice from '../components/LegalNotice'
import LanguageSwitcher from '../components/LanguageSwitcher'

const normalizeMobile = (value) => {
  let digits = value.replace(/\D/g, '')
  if (digits.length === 12 && digits.startsWith('91')) digits = digits.slice(2)
  else if (digits.length === 11 && digits.startsWith('0')) digits = digits.slice(1)
  return digits
}

const Register = () => {
  const { t, language } = useLanguage()
  const { register } = useAuth()
  const navigate = useNavigate()
  const submittingRef = useRef(false)

  const [form, setForm] = useState({
    fullName: '',
    mobile: '',
    email: '',
    role: 'farmer',
    password: '',
    confirmPassword: ''
  })
  const [errors, setErrors] = useState({})
  const [submitError, setSubmitError] = useState(null)
  const [submitting, setSubmitting] = useState(false)

  const handleChange = (e) => {
    const { name, value } = e.target
    setForm((prev) => ({
      ...prev,
      [name]: value
    }))
    if (errors[name]) {
      setErrors((prev) => ({ ...prev, [name]: '' }))
    }
    if (submitError) setSubmitError(null)
  }

  const validate = () => {
    const newErrors = {}
    if (!form.fullName.trim()) newErrors.fullName = t('common.required')
    if (!form.mobile.trim()) {
      newErrors.mobile = t('common.required')
    } else if (!/^[6-9]\d{9}$/.test(normalizeMobile(form.mobile))) {
      newErrors.mobile = t('common.invalidMobile')
    }
    if (form.email.trim() && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email.trim())) {
      newErrors.email = t('common.invalidEmail')
    }
    if (!form.password) {
      newErrors.password = t('common.required')
    } else if (form.password.length < 8) {
      newErrors.password = t('register.passwordMinLength', { count: 8 })
    }
    if (form.password !== form.confirmPassword) {
      newErrors.confirmPassword = t('common.passwordMismatch')
    }
    return newErrors
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (submittingRef.current) return

    const newErrors = validate()
    if (Object.keys(newErrors).length > 0) {
      setErrors(newErrors)
      return
    }
    submittingRef.current = true
    setSubmitting(true)
    setSubmitError(null)
    try {
      const cleanedMobile = normalizeMobile(form.mobile)
      const registrationData = {
        full_name: form.fullName,
        mobile: cleanedMobile,
        password: form.password,
        role: form.role,
        language: language
      }
      const email = form.email.trim()
      if (email) registrationData.email = email

      const result = await register(registrationData)
      if (!result?.id || result.role !== form.role) {
        throw new Error('The server did not confirm that this account was created. Please try again.')
      }
      navigate('/login', {
        replace: true,
        state: {
          registered: true,
          mobileOrEmail: form.email.trim() || cleanedMobile
        }
      })
    } catch (err) {
      if (err.response?.status === 409) {
        setSubmitError(getApiErrorMessage(err, 'This account is already registered. Please log in.'))
        return
      }
      setSubmitError(getApiErrorMessage(err, 'Registration failed. Please try again.'))
    } finally {
      submittingRef.current = false
      setSubmitting(false)
    }
  }

  return (
    <Background>
      <div className="auth-page-layout">
      <div className="auth-language-row"><LanguageSwitcher /></div>
      <div className="auth-two-col auth-page-main">
        <div className="auth-two-col-inner animate-fade-in">
          {/* LEFT COLUMN: Logo + Branding (NO language picker - spec #15) */}
          <div className="auth-side-col">
            <GlassCard className="auth-side-logo-card" glow>
              <div className="auth-side-logo">
                <span className="auth-side-logo-icon">🌱</span>
                <div className="auth-side-logo-text">
                  <div className="auth-side-logo-title">{t('brand.projectName')}</div>
                  <div className="auth-side-logo-tag">{t('welcome.logoTag')}</div>
                </div>
              </div>

              <div className="auth-side-greeting">
                {t('welcome.greetingWelcome')}
              </div>

              <p className="auth-side-sub">
                {t('welcome.subtitle')}
              </p>

              <div style={{ marginTop: 20, display: 'flex', flexDirection: 'column', gap: 12 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10, color: 'var(--text-secondary)', fontSize: 13 }}>
                  <span style={{ color: 'var(--accent-green)', fontSize: 16 }}>🌾</span>
                  {t('welcome.badge1Title')}
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10, color: 'var(--text-secondary)', fontSize: 13 }}>
                  <span style={{ color: 'var(--accent-purple)', fontSize: 16 }}>🤖</span>
                  {t('dashboard.aiAssistant')}
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10, color: 'var(--text-secondary)', fontSize: 13 }}>
                  <span style={{ color: 'var(--accent-blue)', fontSize: 16 }}>🌤️</span>
                  {t('dashboard.weatherDesc')}
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10, color: 'var(--text-secondary)', fontSize: 13 }}>
                  <span style={{ color: 'var(--accent-gold)', fontSize: 16 }}>🏪</span>
                  {t('dashboard.marketDesc')}
                </div>
              </div>
            </GlassCard>
          </div>

          {/* RIGHT COLUMN: Registration Form */}
          <div className="auth-form-col">
            <GlassCard className="auth-form-card-wide" glow>
              <div className="auth-logo">
                <span className="auth-logo-icon">🌱</span>
                <span className="auth-logo-text">{t('brand.projectName')}</span>
              </div>
              <h2 className="auth-title">{t('register.title')}</h2>
              <p className="auth-subtitle">{t('register.authSub') || 'Create your account'}</p>

              {submitError && (
                <div role="alert" style={{ padding: '10px 14px', borderRadius: 10, background: 'rgba(239,68,68,0.1)', color: '#fca5a5', fontSize: 13, marginBottom: 16 }}>
                  ⚠️ {submitError}
                </div>
              )}

              <form onSubmit={handleSubmit} className="auth-form">
                <div>
                  <div className="form-label-wrap">
                    <span className="form-label-icon">👤</span>
                    <span className="form-label-text">{t('register.fullName')}</span>
                  </div>
                  <FormInput
                    name="fullName"
                    value={form.fullName}
                    onChange={handleChange}
                    placeholder={t('register.namePlaceholder')}
                    required
                    error={errors.fullName}
                  />
                </div>

                <div>
                  <div className="form-label-wrap">
                    <span className="form-label-icon">📱</span>
                    <span className="form-label-text">{t('register.mobile')}</span>
                    <span className="form-required-star">*</span>
                  </div>
                  <FormInput
                    name="mobile"
                    value={form.mobile}
                    onChange={handleChange}
                    placeholder={t('register.mobilePlaceholder')}
                    maxLength={15}
                    required
                    error={errors.mobile}
                  />
                </div>

                <div>
                  <div className="form-label-wrap">
                    <span className="form-label-icon">📧</span>
                    <span className="form-label-text">{t('register.email')}</span>
                  </div>
                  <FormInput
                    name="email"
                    type="email"
                    value={form.email}
                    onChange={handleChange}
                    placeholder={t('register.emailPlaceholder')}
                    error={errors.email}
                  />
                </div>

                <div>
                  <div className="form-label-wrap">
                    <span className="form-label-icon">🌾</span>
                    <span className="form-label-text">{t('register.roleLabel')}</span>
                    <span className="form-required-star">*</span>
                  </div>
                  <select
                    className="register-role-select"
                    name="role"
                    value={form.role}
                    onChange={handleChange}
                    required
                    aria-label={t('register.roleLabel')}
                  >
                    <option value="farmer">{t('register.farmerRole')}</option>
                    <option value="buyer">{t('register.buyerRole')}</option>
                  </select>
                </div>

                <div className="auth-form-row">
                  <div>
                    <div className="form-label-wrap">
                      <span className="form-label-icon">🔒</span>
                      <span className="form-label-text">{t('register.password')}</span>
                      <span className="form-required-star">*</span>
                    </div>
                    <FormInput
                      name="password"
                      type="password"
                      value={form.password}
                      onChange={handleChange}
                      placeholder={t('register.passwordPlaceholder')}
                      required
                      error={errors.password}
                    />
                  </div>
                  <div>
                    <div className="form-label-wrap">
                      <span className="form-label-icon">🔐</span>
                      <span className="form-label-text">{t('register.confirmPassword')}</span>
                      <span className="form-required-star">*</span>
                    </div>
                    <FormInput
                      name="confirmPassword"
                      type="password"
                      value={form.confirmPassword}
                      onChange={handleChange}
                      placeholder={t('register.confirmPlaceholder')}
                      required
                      error={errors.confirmPassword}
                    />
                  </div>
                </div>

                <GradientButton
                  type="submit"
                  fullWidth
                  size="lg"
                  loading={submitting}
                  disabled={submitting}
                >
                  {t('register.registerBtn')}
                </GradientButton>
              </form>

              <div className="auth-footer">
                {t('register.haveAccount')}
                <Link to="/login">{t('register.login')}</Link>
              </div>
            </GlassCard>
          </div>
        </div>
      </div>
      <LegalNotice />
      </div>
    </Background>
  )
}

export default Register
