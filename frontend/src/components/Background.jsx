import React from 'react'

const Background = ({ children, heroImage = false }) => {
  return (
    <div className="page-wrapper">
      <div className="bg-wrapper" aria-hidden="true">
        <div className="bg-dark-overlay" />
      </div>
      <div className="content-wrapper">
        {children}
      </div>
    </div>
  )
}

export default Background
