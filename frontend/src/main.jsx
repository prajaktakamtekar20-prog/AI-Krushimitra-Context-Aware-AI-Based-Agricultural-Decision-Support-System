import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { GoogleOAuthProvider } from '@react-oauth/google'
import App from './App.jsx'
import { LanguageProvider, useLanguage } from './context/LanguageContext'
import { AuthProvider } from './context/AuthContext'
import './index.css'

const googleClientId = import.meta.env.VITE_GOOGLE_CLIENT_ID?.trim()

const LocalizedGoogleOAuthProvider = ({ children }) => {
  const { language } = useLanguage()
  return (
    <GoogleOAuthProvider clientId={googleClientId || ''} locale={language}>
      {children}
    </GoogleOAuthProvider>
  )
}

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <BrowserRouter>
      <LanguageProvider>
        <LocalizedGoogleOAuthProvider>
          <AuthProvider>
            <App />
          </AuthProvider>
        </LocalizedGoogleOAuthProvider>
      </LanguageProvider>
    </BrowserRouter>
  </React.StrictMode>
)
