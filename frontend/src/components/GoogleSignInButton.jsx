import React, { useRef } from 'react'
import { useGoogleOAuth } from '@react-oauth/google'

const GoogleSignInButton = ({ onCredential, onError, disabled = false }) => {
  const callbacksRef = useRef({ onCredential, onError })
  callbacksRef.current = { onCredential, onError }
  const { clientId, scriptLoadedSuccessfully } = useGoogleOAuth()

  const startSignIn = () => {
    if (!clientId) {
      callbacksRef.current.onError?.('Google sign-in needs VITE_GOOGLE_CLIENT_ID in frontend/.env and GOOGLE_CLIENT_ID in backend/.env.')
      return
    }
    if (!scriptLoadedSuccessfully || !window.google?.accounts?.oauth2?.initCodeClient) {
      callbacksRef.current.onError?.('Google sign-in is still loading. Please try again.')
      return
    }

    const state = window.crypto?.randomUUID?.()
    if (!state) {
      callbacksRef.current.onError?.('Secure Google sign-in is unavailable in this browser context.')
      return
    }

    try {
      sessionStorage.setItem('krushimitra_google_oauth_state', state)
      const client = window.google.accounts.oauth2.initCodeClient({
        client_id: clientId,
        scope: 'openid email profile',
        ux_mode: 'popup',
        select_account: true,
        state,
        redirect_uri: window.location.origin,
        callback: (response) => {
          const expectedState = sessionStorage.getItem('krushimitra_google_oauth_state')
          sessionStorage.removeItem('krushimitra_google_oauth_state')
          if (response.error) {
            callbacksRef.current.onError?.(response.error_description || 'Google sign-in was not completed.')
            return
          }
          if (!response.code || response.state !== expectedState || response.state !== state) {
            callbacksRef.current.onError?.('Google sign-in could not be verified. Please try again.')
            return
          }
          callbacksRef.current.onCredential?.({
            code: response.code,
            state,
            redirect_uri: window.location.origin
          })
        },
        error_callback: (error) => {
          sessionStorage.removeItem('krushimitra_google_oauth_state')
          if (error.type === 'popup_closed') {
            callbacksRef.current.onError?.('Google sign-in was cancelled. You can try again or use email and password.')
          } else if (error.type === 'popup_failed_to_open') {
            callbacksRef.current.onError?.('The Google sign-in window was blocked. Allow popups and try again.')
          } else {
            callbacksRef.current.onError?.('Google sign-in could not be started. Please try again.')
          }
        }
      })
      client.requestCode()
    } catch {
      sessionStorage.removeItem('krushimitra_google_oauth_state')
      callbacksRef.current.onError?.('Google sign-in could not be started. Please try again.')
    }
  }

  return (
    <>
      <button
        type="button"
        onClick={startSignIn}
        disabled={disabled}
        aria-label="Continue with Google"
        style={{
          width: '100%',
          minHeight: 44,
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          gap: 10,
          marginBottom: 8,
          border: '1px solid #dadce0',
          borderRadius: 6,
          background: '#fff',
          color: '#3c4043',
          fontWeight: 600,
          cursor: disabled ? 'wait' : 'pointer',
          opacity: disabled ? 0.65 : 1
        }}
      >
        <svg aria-hidden="true" width="18" height="18" viewBox="0 0 48 48">
          <path fill="#4285F4" d="M43.611 20.083H42V20H24v8h11.303C33.654 32.657 29.223 36 24 36c-6.627 0-12-5.373-12-12s5.373-12 12-12c3.059 0 5.842 1.154 7.961 3.039l5.657-5.657C34.047 6.053 29.282 4 24 4 12.955 4 4 12.955 4 24s8.955 20 20 20 20-8.955 20-20c0-1.341-.138-2.65-.389-3.917Z" />
          <path fill="#34A853" d="M6.306 14.691 12.88 19.51C14.66 15.11 18.969 12 24 12c3.059 0 5.842 1.154 7.961 3.039l5.657-5.657C34.047 6.053 29.282 4 24 4 16.318 4 9.656 8.337 6.306 14.691Z" />
          <path fill="#FBBC05" d="M24 44c5.175 0 9.86-1.98 13.409-5.204l-6.19-5.238C29.148 35.09 26.682 36 24 36c-5.201 0-9.619-3.317-11.285-7.946l-6.62 5.1C9.406 39.726 16.15 44 24 44Z" />
          <path fill="#EA4335" d="M43.611 20.083H42V20H24v8h11.303a12.01 12.01 0 0 1-4.09 5.558l6.19 5.238C41.197 35.173 44 29.966 44 24c0-1.341-.138-2.65-.389-3.917Z" />
        </svg>
        Continue with Google
      </button>
      <p style={{ margin: '0 0 16px', color: 'var(--text-muted)', fontSize: 12, textAlign: 'center' }}>
        Closing Google's sign-in window cancels the attempt.
      </p>
    </>
  )
}

export default GoogleSignInButton
