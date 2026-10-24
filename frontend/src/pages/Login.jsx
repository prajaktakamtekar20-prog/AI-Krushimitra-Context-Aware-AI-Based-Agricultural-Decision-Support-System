import React, { useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { useLanguage } from '../context/LanguageContext'
import { getAuthenticatedHomePath, useAuth } from '../context/AuthContext'
import { getApiErrorMessage } from '../services/api'
import Background from '../components/Background'
import GlassCard from '../components/GlassCard'
import FormInput from '../components/FormInput'
import GradientButton from '../components/GradientButton'
import GoogleSignInButton from '../components/GoogleSignInButton'
import LegalNotice from '../components/LegalNotice'
import LanguageSwitcher from '../components/LanguageSwitcher'

const Login = () => {
  const { t } = useLanguage()
  const { login, loginWithGoogle, loading, getUserProfile } = useAuth()
  const location = useLocation()
  const navigate = useNavigate()

  const [form, setForm] = useState({
    mobileOrEmail: location.state?.mobileOrEmail || '',
    password: ''
  })
  const [errors, setErrors] = useState({})
  const [submitError, setSubmitError] = useState(null)

  const handleGoogleCredential = async (googleAuthorization) => {
    try {
      setSubmitError(null)
      const result = await loginWithGoogle(googleAuthorization)
      if (!result?.token) throw new Error('Google sign-in failed.')
      const profile = await getUserProfile(result)
      navigate(getAuthenticatedHomePath(profile || result), { replace: true })
    } catch (err) {
      setSubmitError(getApiErrorMessage(err, 'Google sign-in failed.'))
    }
  }

  const handleChange = (e) => {
    const { name, value } = e.target
    setForm((prev) => ({ ...prev, [name]: value }))
    if (errors[name]) {
      setErrors((prev) => ({ ...prev, [name]: '' }))
    }
    if (submitError) setSubmitError(null)
  }

  const validate = () => {
    const newErrors = {}
    if (!form.mobileOrEmail.trim()) newErrors.mobileOrEmail = t('common.required')
    if (!form.password) newErrors.password = t('common.required')
    return newErrors
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    const newErrors = validate()
    if (Object.keys(newErrors).length > 0) {
      setErrors(newErrors)
      return
    }
    setSubmitError(null)
    try {
      const result = await login({
        mobile_or_email: form.mobileOrEmail,
        password: form.password
      })
      if (result && result.token) {
        const profile = await getUserProfile(result)
        navigate(getAuthenticatedHomePath(profile || result), { replace: true })
      } else {
        throw new Error('Invalid credentials')
      }
    } catch (err) {
      setSubmitError(getApiErrorMessage(err, 'Login failed. Please check your credentials and try again.'))
    }
  }

  return (
    <Background>
      <div className="auth-page-layout">
      <div className="auth-language-row"><LanguageSwitcher /></div>
      <main className="auth-container auth-page-main">
        <GlassCard className="auth-card animate-fade-in" glow>
          <div className="auth-header">
            <div style={{ fontSize: 48, marginBottom: 12 }}>👨‍🌾</div>
            <h2 className="auth-title">{t('login.title')}</h2>
          </div>

          {(location.state?.registered || location.state?.message) && (
            <div style={{ padding: '10px 14px', borderRadius: 10, background: location.state?.message ? 'rgba(245,158,11,0.12)' : 'rgba(16,185,129,0.1)', color: location.state?.message ? '#fcd34d' : '#6ee7b7', fontSize: 13, marginBottom: 16 }}>
              {location.state?.message || t('register.registeredSuccess')}
            </div>
          )}

          {submitError && (
            <div style={{ padding: '10px 14px', borderRadius: 10, background: 'rgba(239,68,68,0.1)', color: '#fca5a5', fontSize: 13, marginBottom: 16 }}>
              ⚠️ {submitError}
            </div>
          )}

          <form onSubmit={handleSubmit}>
            <FormInput
              label={t('login.mobileOrEmail')}
              name="mobileOrEmail"
              value={form.mobileOrEmail}
              onChange={handleChange}
              placeholder={t('login.mobilePlaceholder')}
              required
              icon="👤"
              error={errors.mobileOrEmail}
            />
            <div style={{ display: 'flex', alignItems: 'center', gap: 12, margin: '8px 0 16px' }}>
              <span style={{ flex: 1, height: 1, background: 'var(--glass-border)' }} />
              <span style={{ color: 'var(--text-muted)', fontSize: 12 }}>{t('login.orContinueWith')}</span>
              <span style={{ flex: 1, height: 1, background: 'var(--glass-border)' }} />
            </div>
            <GoogleSignInButton
              onCredential={handleGoogleCredential}
              onError={setSubmitError}
              disabled={loading}
            />
            <FormInput
              label={t('login.password')}
              name="password"
              type="password"
              value={form.password}
              onChange={handleChange}
              placeholder={t('login.passwordPlaceholder')}
              required
              icon="🔒"
              error={errors.password}
            />

            <div style={{ textAlign: 'right', marginBottom: 20 }}>
              <Link to="/forgot-password" style={{ color: 'var(--accent-purple)', fontSize: 14, fontWeight: 500 }}>
                {t('login.forgotPassword')}
              </Link>
            </div>

            <GradientButton
              type="submit"
              fullWidth
              size="lg"
              loading={loading}
              disabled={loading}
            >
              {t('login.loginBtn')}
            </GradientButton>
          </form>

          <div className="auth-footer">
            {t('login.noAccount')}
            <Link to="/register">{t('login.register')}</Link>
          </div>
        </GlassCard>
      </main>
      <LegalNotice />
      </div>
    </Background>
  )
}

export default Login
