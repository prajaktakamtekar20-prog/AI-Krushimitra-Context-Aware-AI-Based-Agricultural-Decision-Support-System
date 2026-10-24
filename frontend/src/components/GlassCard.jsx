import React from 'react'

const GlassCard = ({ children, className = '', onClick, hover = false, glow = false, glowGreen = false, ...props }) => {
  const classes = [
    'glass-card',
    hover ? 'glass-card--hover' : '',
    glow ? 'glass-card--glow' : '',
    glowGreen ? 'glass-card--glow-green' : '',
    className
  ].filter(Boolean).join(' ')

  return (
    <div className={classes} onClick={onClick} {...props}>
      {children}
    </div>
  )
}

export default GlassCard
