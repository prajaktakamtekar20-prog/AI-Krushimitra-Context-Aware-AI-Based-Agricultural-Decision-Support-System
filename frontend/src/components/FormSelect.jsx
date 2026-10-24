import React, { useEffect, useId, useLayoutEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { useLanguage } from '../context/LanguageContext'

const FormSelect = ({
  label,
  value,
  onChange,
  options = [],
  required = false,
  name,
  error = '',
  className = '',
  placeholder,
  searchable = false,
  searchPlaceholder,
  onOpen,
  loading = false,
  loadingMessage,
  emptyMessage,
  errorMessage = '',
  retryLabel,
  onRetry,
  ...props
}) => {
  const { t } = useLanguage()
  const localizedSearchPlaceholder = searchPlaceholder || t('common.selectSearchPlaceholder')
  const localizedLoadingMessage = loadingMessage || t('common.loadingOptions')
  const localizedEmptyMessage = emptyMessage || t('common.noOptions')
  const localizedRetryLabel = retryLabel || t('common.retry')
  const generatedId = useId()
  const controlId = props.id || `form-select-${generatedId}`
  const errorId = `${controlId}-error`
  const { disabled = false, id, 'aria-label': ariaLabel, ...buttonProps } = props
  const [open, setOpen] = useState(false)
  const [activeIndex, setActiveIndex] = useState(0)
  const [searchQuery, setSearchQuery] = useState('')
  const [menuStyle, setMenuStyle] = useState({})
  const triggerRef = useRef(null)
  const menuRef = useRef(null)
  const typeaheadRef = useRef('')
  const typeaheadTimerRef = useRef(null)
  const optionsList = options.map((option) => ({
    value: String(typeof option === 'object' ? option.value : option),
    label: String(typeof option === 'object' ? option.label : option),
    category: typeof option === 'object' ? option.category : undefined
  }))
  const filteredOptions = searchable && searchQuery.trim()
    ? optionsList.filter((option) => `${option.label} ${option.value}`.toLocaleLowerCase().includes(searchQuery.trim().toLocaleLowerCase()))
    : optionsList
  const currentValue = value == null ? '' : String(value)
  const selectedOption = optionsList.find((option) => option.value === currentValue)

  const positionMenu = () => {
    const trigger = triggerRef.current
    if (!trigger) return

    const viewportPadding = 8
    const gap = 4
    const desiredHeight = Math.min(
      360,
      Math.max(120, filteredOptions.length * 40 + (searchable ? 56 : 0))
    )
    const rect = trigger.getBoundingClientRect()
    const roomBelow = Math.max(0, window.innerHeight - rect.bottom - viewportPadding - gap)

    const width = Math.min(rect.width, window.innerWidth - viewportPadding * 2)
    const left = Math.max(viewportPadding, Math.min(rect.left, window.innerWidth - width - viewportPadding))
    setMenuStyle({
      position: 'fixed',
      top: rect.bottom + gap,
      left,
      width,
      maxHeight: Math.max(48, Math.min(desiredHeight, roomBelow)),
      zIndex: 10000
    })
  }

  const openMenu = () => {
    if (disabled) return
    const selectedIndex = optionsList.findIndex((option) => option.value === currentValue)
    setActiveIndex(selectedIndex >= 0 ? selectedIndex : 0)
    setSearchQuery('')
    setOpen(true)
    onOpen?.()
  }

  const chooseOption = (option) => {
    onChange?.({ target: { name, value: option.value } })
    setOpen(false)
    setSearchQuery('')
    triggerRef.current?.focus()
  }

  const handleKeyDown = (event) => {
    if (event.key === 'ArrowDown') {
      event.preventDefault()
      if (!open) openMenu()
      else setActiveIndex((index) => Math.min(index + 1, filteredOptions.length - 1))
      return
    }
    if (event.key === 'ArrowUp') {
      event.preventDefault()
      if (!open) openMenu()
      else setActiveIndex((index) => Math.max(index - 1, 0))
      return
    }
    if (event.key === 'Home' && open) {
      event.preventDefault()
      setActiveIndex(0)
      return
    }
    if (event.key === 'End' && open) {
      event.preventDefault()
      setActiveIndex(filteredOptions.length - 1)
      return
    }
    if ((event.key === 'Enter' || event.key === ' ') && open) {
      event.preventDefault()
      if (filteredOptions[activeIndex]) chooseOption(filteredOptions[activeIndex])
      return
    }
    if (event.key === ' ' && !open) {
      event.preventDefault()
      openMenu()
      return
    }
    if (event.key === 'Escape' && open) {
      event.preventDefault()
      setOpen(false)
      return
    }
    if (event.key.length === 1 && !event.ctrlKey && !event.metaKey && !event.altKey) {
      typeaheadRef.current += event.key.toLocaleLowerCase()
      window.clearTimeout(typeaheadTimerRef.current)
      typeaheadTimerRef.current = window.setTimeout(() => { typeaheadRef.current = '' }, 700)
      const startIndex = open ? activeIndex + 1 : 0
      const ordered = [...optionsList.slice(startIndex), ...optionsList.slice(0, startIndex)]
      const match = ordered.find((option) => option.label.toLocaleLowerCase().startsWith(typeaheadRef.current))
      if (match) {
        const matchIndex = optionsList.indexOf(match)
        if (!open) setOpen(true)
        setActiveIndex(matchIndex)
      }
    }
  }

  useLayoutEffect(() => {
    if (!open) return undefined

    const handlePointerDown = (event) => {
      if (!triggerRef.current?.contains(event.target) && !menuRef.current?.contains(event.target)) {
        setOpen(false)
      }
    }
    const updateMenuPosition = () => positionMenu()
    positionMenu()
    document.addEventListener('pointerdown', handlePointerDown)
    window.addEventListener('resize', updateMenuPosition)
    window.addEventListener('scroll', updateMenuPosition, true)
    const observer = typeof ResizeObserver === 'undefined' ? null : new ResizeObserver(positionMenu)
    if (observer && triggerRef.current) observer.observe(triggerRef.current)
    if (searchable) menuRef.current?.querySelector('input')?.focus()

    return () => {
      document.removeEventListener('pointerdown', handlePointerDown)
      window.removeEventListener('resize', updateMenuPosition)
      window.removeEventListener('scroll', updateMenuPosition, true)
      observer?.disconnect()
    }
  }, [open, optionsList.length, filteredOptions.length, searchable])

  useEffect(() => {
    if (!open) return
    const menu = menuRef.current
    const option = menu?.querySelector(`[data-option-index="${activeIndex}"]`)
    if (!menu || !option) return

    const menuBounds = menu.getBoundingClientRect()
    const optionBounds = option.getBoundingClientRect()
    if (optionBounds.top < menuBounds.top) {
      menu.scrollTop -= menuBounds.top - optionBounds.top
    } else if (optionBounds.bottom > menuBounds.bottom) {
      menu.scrollTop += optionBounds.bottom - menuBounds.bottom
    }
  }, [activeIndex, open])

  useEffect(() => () => window.clearTimeout(typeaheadTimerRef.current), [])

  return (
    <div className={`form-group ${className}`}>
      {label && (
        <label id={`${controlId}-label`} htmlFor={controlId} className={`form-label ${required ? 'form-label--required' : ''}`}>
          {label}
        </label>
      )}
      <select
        tabIndex={-1}
        aria-hidden="true"
        value={currentValue}
        onChange={() => {}}
        name={name}
        required={required}
        disabled={disabled}
        className="form-select-native"
        onInvalid={(event) => {
          event.preventDefault()
          triggerRef.current?.focus()
          openMenu()
        }}
      >
        {placeholder && (
          <option value="" disabled hidden>
            {placeholder}
          </option>
        )}
        {optionsList.map((option) => {
          return (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          )
        })}
      </select>
      <button
        {...buttonProps}
        ref={triggerRef}
        id={controlId}
        type="button"
        className={`form-select ${error ? 'form-input--error' : ''}`}
        role="combobox"
        aria-label={ariaLabel}
        aria-labelledby={label ? `${controlId}-label` : undefined}
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-controls={open ? `${controlId}-listbox` : undefined}
        aria-activedescendant={open && filteredOptions[activeIndex] ? `${controlId}-option-${activeIndex}` : undefined}
        aria-required={required || undefined}
        aria-invalid={Boolean(error) || undefined}
        aria-describedby={error ? errorId : buttonProps['aria-describedby']}
        disabled={disabled}
        onClick={() => open ? setOpen(false) : openMenu()}
        onKeyDown={handleKeyDown}
      >
        <span className={`form-select-value ${selectedOption ? '' : 'form-select-value--placeholder'}`}>
          {selectedOption?.label || placeholder || ''}
        </span>
        <span className="form-select-caret" aria-hidden="true" />
      </button>
      {open && createPortal(
        <div ref={menuRef} id={`${controlId}-listbox`} className="form-select-menu" role="listbox" style={menuStyle}>
          {searchable && (
            <div className="form-select-search" role="presentation" onMouseDown={(event) => event.stopPropagation()}>
              <input
                className="form-input form-select-search-input"
                type="search"
                value={searchQuery}
                placeholder={localizedSearchPlaceholder}
                aria-label={searchPlaceholder}
                onChange={(event) => { setSearchQuery(event.target.value); setActiveIndex(0) }}
                onKeyDown={(event) => {
                  event.stopPropagation()
                  if (event.key === 'Enter') {
                    event.preventDefault()
                    if (filteredOptions[0]) chooseOption(filteredOptions[0])
                  } else if (event.key === 'ArrowDown') {
                    event.preventDefault()
                    triggerRef.current?.focus()
                    setActiveIndex(0)
                  }
                }}
              />
            </div>
          )}
          {filteredOptions.length === 0 ? (
            errorMessage ? (
              <div className="form-select-no-options" role="alert">
                <div>{errorMessage}</div>
                {onRetry && (
                  <button className="form-select-retry" type="button" onClick={onRetry}>
                    {localizedRetryLabel}
                  </button>
                )}
              </div>
            ) : loading ? (
              <div className="form-select-no-options" role="status">{localizedLoadingMessage}</div>
            ) : optionsList.length === 0 ? (
              <div className="form-select-no-options">{localizedEmptyMessage}</div>
            ) : (
              <div className="form-select-no-options">{t('common.noMatchingOptions')}</div>
            )
          ) : filteredOptions.map((option, index) => (
            <React.Fragment key={option.value}>
              {option.category && option.category !== filteredOptions[index - 1]?.category && (
                <div className="form-select-group" role="presentation">{option.category}</div>
              )}
              <div
                id={`${controlId}-option-${index}`}
                data-option-index={index}
                role="option"
                aria-selected={option.value === currentValue}
                className={`form-select-option ${index === activeIndex ? 'form-select-option--active' : ''}`}
                onMouseEnter={() => setActiveIndex(index)}
                onMouseDown={(event) => event.preventDefault()}
                onClick={() => chooseOption(option)}
              >
                {option.label}
              </div>
            </React.Fragment>
          ))}
        </div>,
        document.body
      )}
      {error && (
        <div id={errorId} className="form-error">
          <span>⚠️</span>
          <span>{typeof error === 'boolean' ? t('common.required') : error}</span>
        </div>
      )}
    </div>
  )
}

export default FormSelect
