import React, { useState } from 'react'
import { useLanguage } from '../context/LanguageContext'

const FormInput = ({
  label,
  type = 'text',
  value,
  onChange,
  placeholder = '',
  required = false,
  icon,
  name,
  error = '',
  className = '',
  inputClassName = '',
  ...props
}) => {
  const { t } = useLanguage()
  const [passwordVisible, setPasswordVisible] = useState(false)
  const isPassword = type === 'password'
  const inputClasses = [
    'form-input',
    error ? 'form-input--error' : '',
    inputClassName
  ].filter(Boolean).join(' ')

  return (
    <div className={`form-group ${className}`}>
      {label && (
        <label className={`form-label ${required ? 'form-label--required' : ''}`}>
          {icon && <span style={{ marginRight: 6 }}>{icon}</span>}
          {label}
        </label>
      )}
      <div style={{ position: 'relative' }}>
        <input
          type={isPassword && passwordVisible ? 'text' : type}
          value={value || ''}
          onChange={onChange}
          placeholder={placeholder}
          name={name}
          className={inputClasses}
          style={isPassword ? { paddingRight: 48 } : undefined}
          {...props}
        />
        {isPassword && (
          <button
            type="button"
            className="password-visibility-toggle"
            onClick={() => setPasswordVisible((visible) => !visible)}
            aria-label={t(passwordVisible ? 'common.hidePassword' : 'common.showPassword')}
            aria-pressed={passwordVisible}
          >
            {passwordVisible ? '🙈' : '👁️'}
          </button>
        )}
      </div>
      {error && (
        <div className="form-error">
          <span>⚠️</span>
          <span>{typeof error === 'boolean' ? t('common.required') : error}</span>
        </div>
      )}
    </div>
  )
}

export default FormInput
