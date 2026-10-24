import React, { useState } from 'react'
import { useAuth } from '../context/AuthContext'
import { useLanguage } from '../context/LanguageContext'
import { getApiErrorMessage } from '../services/api'
import GoogleSignInButton from './GoogleSignInButton'

const GoogleAccountLink = () => {
  const { linkGoogleAccount } = useAuth()
  const { t } = useLanguage()
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  const handleCredential = async (credential) => {
    setLoading(true)
    setError('')
    setSuccess('')
    try {
      await linkGoogleAccount(credential)
      setSuccess(t('common.googleConnected'))
    } catch (linkError) {
      setError(getApiErrorMessage(linkError, t('common.googleLinkFailed')))
    } finally {
      setLoading(false)
    }
  }

  return (
    <section aria-labelledby="google-account-link-title" style={{ marginTop: 20 }}>
      <h3 id="google-account-link-title" className="section-title">{t('common.connectGoogleTitle')}</h3>
      <p style={{ color: 'var(--text-secondary)', fontSize: 13, margin: '8px 0 14px' }}>
        {t('common.connectGoogleHelp')}
      </p>
      {error && <div role="alert" style={{ color: 'var(--accent-red)', fontSize: 13, marginBottom: 12 }}>{error}</div>}
      {success && <div role="status" style={{ color: 'var(--accent-green)', fontSize: 13, marginBottom: 12 }}>{success}</div>}
      <GoogleSignInButton
        onCredential={handleCredential}
        onError={setError}
        disabled={loading}
      />
    </section>
  )
}

export default GoogleAccountLink
