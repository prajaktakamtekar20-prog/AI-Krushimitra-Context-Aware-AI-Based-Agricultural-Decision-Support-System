import React, { useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { useLanguage } from '../context/LanguageContext'
import { useAuth } from '../context/AuthContext'
import { localizeDisplayName } from '../translations/brand'

const languageLabels = {
  en: 'English',
  mr: 'मराठी',
  hi: 'हिन्दी',
  ml: 'മലയാളം'
}

const Navbar = () => {
  const { t, language, setLanguage } = useLanguage()
  const { logout, user } = useAuth()
  const location = useLocation()
  const navigate = useNavigate()
  const [mobileOpen, setMobileOpen] = useState(false)
  const [showLangMenu, setShowLangMenu] = useState(false)
  const [showUserMenu, setShowUserMenu] = useState(false)

  const homePath = user?.role === 'buyer' ? '/marketplace?tab=dashboard' : '/dashboard'
  const hideLogoutOnFarmerProfile = user?.role === 'farmer' && location.pathname === '/profile'
  const workspacePath = user?.role === 'buyer'
    ? '/marketplace?tab=produce'
    : '/marketplace?tab=requirements'
  const navLinks = user?.role === 'buyer'
    ? [
        { path: homePath, label: t('nav.dashboard'), icon: '🏠', activeTabs: ['dashboard'] },
        { path: workspacePath, label: t('nav.browseProducts'), icon: '🌾', activeTabs: ['produce', 'marketplace'] },
        { path: '/marketplace?tab=orders', label: t('nav.myOrders'), icon: '🛒', activeTabs: ['orders'] },
        { path: '/profile', label: t('nav.myProfile'), icon: '👤', activeTabs: ['profile'] }
      ]
    : [
        { path: homePath, label: t('nav.dashboard'), icon: '🏠' },
        { path: '/disease', label: t('nav.diseaseDetection'), icon: '🌿' },
        { path: '/weather', label: t('nav.weather'), icon: '🌦️' },
        { path: '/market', label: t('nav.market'), icon: '💰' },
        { path: workspacePath, label: t('nav.marketplace'), icon: '🧺' },
        { path: '/schemes', label: t('nav.schemes'), icon: '🏛️' },
        { path: '/ai-assistant', label: t('nav.aiAssistant'), icon: '🤖' }
      ]

  const isActive = (link) => {
    if (user?.role === 'buyer') {
      const currentTab = location.pathname === '/profile'
        ? 'profile'
        : new URLSearchParams(location.search).get('tab') || 'produce'
      return link.activeTabs.includes(currentTab)
    }
    if (link.path.startsWith('/marketplace')) {
      return location.pathname === '/marketplace'
        && (location.search === link.path.slice('/marketplace'.length)
          || link.path.includes('tab=dashboard') && !location.search)
    }
    return location.pathname === link.path
  }

  const handleLogout = () => {
    logout()
    setMobileOpen(false)
    setShowUserMenu(false)
    navigate('/')
  }

  const userName = localizeDisplayName(user?.full_name || user?.name || 'Farmer', language)
  const userInitial = userName?.trim()?.charAt(0)?.toUpperCase() || 'F'
  const userMobile = user?.mobile || ''

  const languageLabel = (code) => {
    const flag = code === 'en' ? '🇬🇧' : '🇮🇳'
    return `${flag} ${languageLabels[code] || languageLabels.en}`
  }

  const handleLangChange = (code) => {
    setLanguage(code)
    setShowLangMenu(false)
  }

  return (
    <nav className="navbar" aria-label={t('nav.mainNavigation')}>
      <div className="navbar-inner">
        <Link to={homePath} className="navbar-logo" onClick={() => setMobileOpen(false)}>
          <span className="navbar-logo-icon">🌾</span>
          <div className="navbar-logo-text">
            <span className="navbar-logo-title">{t('brand.projectName')}</span>
          </div>
        </Link>

        <div className="navbar-links">
          {navLinks.map((link) => (
            <Link
              key={link.path}
              to={link.path}
              className={`navbar-link ${isActive(link) ? 'navbar-link--active' : ''}`}
              aria-current={isActive(link) ? 'page' : undefined}
            >
              <span>{link.icon}</span>
              <span>{link.label}</span>
            </Link>
          ))}
        </div>

        <div className="navbar-actions">
          <div className="navbar-lang-wrap">
            <button
              className="navbar-lang-btn"
              onClick={() => { setShowLangMenu(!showLangMenu); setShowUserMenu(false) }}
              title={t('dashboard.currentLanguage')}
            >
              {languageLabel(language)}
            </button>
            {showLangMenu && (
              <div className="navbar-popup navbar-popup--lang">
                <button className={`navbar-popup-item ${language === 'en' ? 'navbar-popup-item--on' : ''}`} onClick={() => handleLangChange('en')}>
                  🇬🇧 {languageLabels.en}
                </button>
                <button className={`navbar-popup-item ${language === 'mr' ? 'navbar-popup-item--on' : ''}`} onClick={() => handleLangChange('mr')}>
                  🇮🇳 {languageLabels.mr}
                </button>
                <button className={`navbar-popup-item ${language === 'hi' ? 'navbar-popup-item--on' : ''}`} onClick={() => handleLangChange('hi')}>
                  🇮🇳 {languageLabels.hi}
                </button>
                <button className={`navbar-popup-item ${language === 'ml' ? 'navbar-popup-item--on' : ''}`} onClick={() => handleLangChange('ml')}>
                  🇮🇳 {languageLabels.ml}
                </button>
              </div>
            )}
          </div>

          <div className="navbar-user-wrap">
            <button
              className="navbar-user-btn"
              onClick={() => { setShowUserMenu(!showUserMenu); setShowLangMenu(false) }}
            >
              <div className="navbar-user-avatar">{userInitial}</div>
              <div className="navbar-user-text">
                <div className="navbar-user-name">{userName}</div>
                {userMobile && <div className="navbar-user-mobile">{userMobile}</div>}
              </div>
              <span className="navbar-user-caret">▾</span>
            </button>
            {showUserMenu && (
              <div className="navbar-popup navbar-popup--user">
                {user?.role !== 'buyer' && (
                  <Link to="/profile" className="navbar-popup-item" onClick={() => setShowUserMenu(false)}>
                    👤 {t('nav.myProfile')}
                  </Link>
                )}
                {!hideLogoutOnFarmerProfile && (
                  <>
                    <div className="navbar-popup-divider" />
                    <button className="navbar-popup-item navbar-popup-item--danger" onClick={handleLogout}>
                      🚪 {t('nav.logout')}
                    </button>
                  </>
                )}
              </div>
            )}
          </div>

          <button
            className="navbar-menu-btn"
            onClick={() => setMobileOpen(!mobileOpen)}
            aria-label={t('common.menu')}
          >
            {mobileOpen ? '✕' : '☰'}
          </button>
        </div>
      </div>

      {mobileOpen && (
        <div className="mobile-menu mobile-menu--open">
          {navLinks.map((link) => (
            <Link
              key={link.path}
              to={link.path}
              className={`mobile-menu-link ${isActive(link) ? 'mobile-menu-link--active' : ''}`}
              onClick={() => setMobileOpen(false)}
            >
              <span style={{ fontSize: 18 }}>{link.icon}</span>
              <span>{link.label}</span>
            </Link>
          ))}
          <div className="mobile-menu-lang-row">
            <span className="mobile-menu-lang-label">{t('dashboard.currentLanguage')}:</span>
            <div style={{ display: 'flex', gap: 8 }}>
              <button className={`mobile-lang-chip ${language === 'en' ? 'mobile-lang-chip--on' : ''}`} aria-label={languageLabels.en} onClick={() => setLanguage('en')}>{languageLabels.en}</button>
              <button className={`mobile-lang-chip ${language === 'mr' ? 'mobile-lang-chip--on' : ''}`} aria-label={languageLabels.mr} onClick={() => setLanguage('mr')}>{languageLabels.mr}</button>
              <button className={`mobile-lang-chip ${language === 'hi' ? 'mobile-lang-chip--on' : ''}`} aria-label={languageLabels.hi} onClick={() => setLanguage('hi')}>{languageLabels.hi}</button>
              <button className={`mobile-lang-chip ${language === 'ml' ? 'mobile-lang-chip--on' : ''}`} aria-label={languageLabels.ml} onClick={() => setLanguage('ml')}>{languageLabels.ml}</button>
            </div>
          </div>
          {!hideLogoutOnFarmerProfile && (
            <button
              className="mobile-menu-link"
              onClick={handleLogout}
              style={{ textAlign: 'left' }}
            >
              <span style={{ fontSize: 18 }}>🚪</span>
              <span>{t('nav.logout')}</span>
            </button>
          )}
        </div>
      )}
    </nav>
  )
}

export default Navbar
