import React from 'react'

const GradientButton = ({
  children,
  onClick,
  disabled = false,
  variant = 'primary',
  size = 'md',
  fullWidth = false,
  type = 'button',
  className = '',
  loading = false,
  ...props
}) => {
  const classes = [
    'gradient-btn',
    `gradient-btn--${variant}`,
    `gradient-btn--${size}`,
    fullWidth ? 'gradient-btn--full' : '',
    className
  ].filter(Boolean).join(' ')

  return (
    <button
      type={type}
      className={classes}
      onClick={onClick}
      disabled={disabled || loading}
      {...props}
    >
      {loading && <span className="loading-spinner" style={{ width: 18, height: 18 }} />}
      {children}
    </button>
  )
}

export default GradientButton
