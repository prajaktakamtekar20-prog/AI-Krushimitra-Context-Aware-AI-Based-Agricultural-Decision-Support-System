import React from 'react'
import { Routes, Route, Navigate, useLocation } from 'react-router-dom'
import { getAuthenticatedHomePath, useAuth } from './context/AuthContext'
import Welcome from './pages/Welcome'
import LanguageSelection from './pages/LanguageSelection'
import Register from './pages/Register'
import Login from './pages/Login'
import LegalPage from './pages/LegalPage'
import CreateProfile from './pages/CreateProfile'
import ProfileCreated from './pages/ProfileCreated'
import Dashboard from './pages/Dashboard'
import MyProfile from './pages/MyProfile'
import Weather from './pages/Weather'
import AIAssistant from './pages/AIAssistant'
import Market from './pages/Market'
import Disease from './pages/Disease'
import GovernmentSchemes from './pages/GovernmentSchemes'
import Marketplace from './pages/Marketplace'

const AuthLoading = () => (
  <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '100vh', background: 'var(--bg-primary)' }}>
    <div className="loading-spinner" />
  </div>
)

const PublicAuthRoute = ({ children, allowAuthenticated = false }) => {
  const { isAuthenticated, user, loading } = useAuth()

  if (isAuthenticated && !allowAuthenticated && (loading || user === null)) return <AuthLoading />
  if (isAuthenticated && !allowAuthenticated) {
    return <Navigate to={getAuthenticatedHomePath(user)} replace />
  }
  return children
}

const ProtectedRoute = ({ children, requireProfile = false, requireFarmerProfile = false, role }) => {
  const { isAuthenticated, user, loading } = useAuth()
  const location = useLocation()

  if (loading || (isAuthenticated && user === null)) {
    return <AuthLoading />
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />
  }

  if (role && user?.role !== role) {
    return <Navigate to={getAuthenticatedHomePath(user)} replace />
  }

  if (user?.role === 'buyer' && ['/create-profile', '/profile-created'].includes(location.pathname)) {
    return <Navigate to="/marketplace?tab=profile" replace />
  }

  if (requireProfile && user && !user.hasProfile) {
    const allowedPaths = ['/create-profile', '/profile-created']
    if (!allowedPaths.includes(location.pathname)) {
      return <Navigate to="/create-profile" replace />
    }
  }

  if (requireFarmerProfile && user?.role === 'farmer' && !user.hasProfile) {
    return <Navigate to="/create-profile" replace />
  }

  if (!requireProfile && user?.hasProfile && ['/create-profile', '/profile-created'].includes(location.pathname)) {
    return <Navigate to="/dashboard" replace />
  }

  return children
}

const App = () => {
  const location = useLocation()

  return (
    <Routes>
      <Route path="/" element={<Welcome />} />
      <Route path="/language-selection" element={<LanguageSelection />} />
      <Route path="/register" element={<PublicAuthRoute allowAuthenticated><Register /></PublicAuthRoute>} />
      <Route
        path="/login"
        element={
          <PublicAuthRoute allowAuthenticated={Boolean(location.state?.registered)}>
            <Login />
          </PublicAuthRoute>
        }
      />
      <Route path="/terms" element={<LegalPage type="terms" />} />
      <Route path="/privacy" element={<LegalPage type="privacy" />} />

      <Route
        path="/create-profile"
        element={
          <ProtectedRoute role="farmer">
            <CreateProfile />
          </ProtectedRoute>
        }
      />
      <Route
        path="/profile-created"
        element={
          <ProtectedRoute requireProfile role="farmer">
            <ProfileCreated />
          </ProtectedRoute>
        }
      />

      <Route
        path="/dashboard"
        element={
          <ProtectedRoute requireProfile role="farmer">
            <Dashboard />
          </ProtectedRoute>
        }
      />
      <Route
        path="/disease"
        element={
          <ProtectedRoute requireProfile role="farmer">
            <Disease />
          </ProtectedRoute>
        }
      />
      <Route
        path="/schemes"
        element={
          <ProtectedRoute requireProfile role="farmer">
            <GovernmentSchemes />
          </ProtectedRoute>
        }
      />
      <Route
        path="/profile"
        element={
          <ProtectedRoute>
            <ProfileRoute />
          </ProtectedRoute>
        }
      />
      <Route
        path="/weather"
        element={
          <ProtectedRoute requireProfile role="farmer">
            <Weather />
          </ProtectedRoute>
        }
      />
      <Route
        path="/ai-assistant"
        element={
          <ProtectedRoute requireProfile role="farmer">
            <AIAssistant />
          </ProtectedRoute>
        }
      />
      <Route
        path="/market"
        element={
          <ProtectedRoute requireProfile role="farmer">
            <Market />
          </ProtectedRoute>
        }
      />
      <Route
        path="/marketplace"
        element={
          <ProtectedRoute requireFarmerProfile>
            <Marketplace />
          </ProtectedRoute>
        }
      />

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

const ProfileRoute = () => {
  const { user } = useAuth()
  if (user?.role === 'buyer') return <Marketplace />
  return user?.hasProfile ? <MyProfile /> : <Navigate to="/create-profile" replace />
}

export default App
