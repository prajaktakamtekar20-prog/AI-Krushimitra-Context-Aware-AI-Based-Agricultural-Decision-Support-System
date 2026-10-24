import React, { useState } from 'react'
import './VirtualKeyboard.css'

const layouts = {
  en: {
    name: 'English',
    languageLabel: 'Keyboard language',
    toggle: 'Open virtual keyboard',
    close: 'Close keyboard',
    backspace: 'Backspace',
    clear: 'Clear text',
    space: 'Space',
    rows: ['1234567890', 'qwertyuiop', 'asdfghjkl', 'zxcvbnm']
  },
  mr: {
    name: 'मराठी',
    languageLabel: 'भाषा निवडा',
    toggle: 'आभासी कीबोर्ड उघडा',
    close: 'कीबोर्ड बंद करा',
    backspace: 'मागील अक्षर मिटवा',
    clear: 'मजकूर पुसून टाका',
    space: 'मोकळी जागा',
    rows: [
      '०१२३४५६७८९',
      'अआइईउऊऋएऐओऔ',
      'कखगघङचछजझञ',
      'टठडढणतथदधन',
      'पफबभमयरलव',
      'शषसहळक्षज्ञ'
    ]
  },
  hi: {
    name: 'हिंदी',
    languageLabel: 'भाषा चुनें',
    toggle: 'वर्चुअल कीबोर्ड खोलें',
    close: 'कीबोर्ड बंद करें',
    backspace: 'पिछला अक्षर मिटाएँ',
    clear: 'टेक्स्ट साफ़ करें',
    space: 'स्पेस',
    rows: [
      '०१२३४५६७८९',
      'अआइईउऊऋएऐओऔ',
      'कखगघङचछजझञ',
      'टठडढणतथदधन',
      'पफबभमयरलव',
      'शषसहक्षज्ञ'
    ]
  }
}

const punctuation = ['।', ',', '.', '?', '!', ':', ';', '-', '(', ')', "'", '"', '@', '#', '/', '&']
const marks = ['ा', 'ि', 'ी', 'ु', 'ू', 'ृ', 'े', 'ै', 'ो', 'ौ', 'ं', 'ः', '्']

const splitKeyboardRow = (row) => (
  typeof Intl.Segmenter === 'function'
    ? [...new Intl.Segmenter(undefined, { granularity: 'grapheme' }).segment(row)].map(({ segment }) => segment)
    : Array.from(row)
)

const previousGraphemeStart = (value, position) => {
  const prefix = value.slice(0, position)
  if (typeof Intl.Segmenter === 'function') {
    const segments = [...new Intl.Segmenter(undefined, { granularity: 'grapheme' }).segment(prefix)]
    return segments.length ? segments[segments.length - 1].index : position
  }
  const lastCodePoint = Array.from(prefix).pop()
  return lastCodePoint ? position - lastCodePoint.length : position
}

const VirtualKeyboard = ({ value, onChange, inputRef }) => {
  const [language, setLanguage] = useState('en')
  const [open, setOpen] = useState(false)
  const layout = layouts[language]

  const updateText = (nextValue, cursor) => {
    onChange(nextValue)
    const input = inputRef.current
    if (!input) return
    input.focus()
    requestAnimationFrame(() => {
      if (inputRef.current === input) input.setSelectionRange(cursor, cursor)
    })
  }

  const insertText = (text) => {
    const input = inputRef.current
    if (!input) return
    const start = input.selectionStart ?? value.length
    const end = input.selectionEnd ?? value.length
    const maxLength = input.maxLength > -1 ? input.maxLength : Infinity
    const available = Math.max(0, maxLength - (value.length - (end - start)))
    const inserted = text.slice(0, available)
    updateText(`${value.slice(0, start)}${inserted}${value.slice(end)}`, start + inserted.length)
  }

  const backspace = () => {
    const input = inputRef.current
    if (!input) return
    const start = input.selectionStart ?? value.length
    const end = input.selectionEnd ?? value.length
    const deleteStart = start === end ? previousGraphemeStart(value, start) : start
    updateText(`${value.slice(0, deleteStart)}${value.slice(end)}`, deleteStart)
  }

  const handleKey = (event, action) => {
    event.preventDefault()
    action()
  }

  return (
    <div className="virtual-keyboard">
      <div className="virtual-keyboard__toolbar">
        <button
          className="virtual-keyboard__toggle"
          type="button"
          aria-expanded={open}
          aria-label={open ? layout.close : layout.toggle}
          title={open ? layout.close : layout.toggle}
          onMouseDown={(event) => event.preventDefault()}
          onClick={() => setOpen((current) => !current)}
        >
          <span aria-hidden="true">⌨</span>
        </button>
        {open && (
          <label className="virtual-keyboard__language">
            <span className="sr-only">{layout.languageLabel}</span>
            <select
              aria-label={layout.languageLabel}
              value={language}
              onChange={(event) => setLanguage(event.target.value)}
            >
              {Object.entries(layouts).map(([code, option]) => (
                <option key={code} value={code}>{option.name}</option>
              ))}
            </select>
          </label>
        )}
        {open && (
          <button
            className="virtual-keyboard__close"
            type="button"
            aria-label={layout.close}
            title={layout.close}
            onClick={() => setOpen(false)}
          >
            ×
          </button>
        )}
      </div>
      {open && (
        <div className="virtual-keyboard__panel" aria-label={`${layout.name} virtual keyboard`}>
          {layout.rows.map((row, index) => (
            <div className="virtual-keyboard__row" key={`${language}-${index}`}>
              {splitKeyboardRow(row).map((character, keyIndex) => (
                <button
                  className="virtual-keyboard__key"
                  key={`${character}-${keyIndex}`}
                  type="button"
                  onMouseDown={(event) => event.preventDefault()}
                  onClick={(event) => handleKey(event, () => insertText(character))}
                >
                  {character}
                </button>
              ))}
            </div>
          ))}
          {language !== 'en' && (
            <div className="virtual-keyboard__row virtual-keyboard__row--marks">
              {marks.map((character, index) => (
                <button
                  className="virtual-keyboard__key"
                  key={`${character}-${index}`}
                  type="button"
                  onMouseDown={(event) => event.preventDefault()}
                  onClick={(event) => handleKey(event, () => insertText(character))}
                >
                  {character}
                </button>
              ))}
            </div>
          )}
          <div className="virtual-keyboard__row virtual-keyboard__row--punctuation">
            {punctuation.map((character) => (
              <button
                className="virtual-keyboard__key"
                key={character}
                type="button"
                onMouseDown={(event) => event.preventDefault()}
                onClick={(event) => handleKey(event, () => insertText(character))}
              >
                {character}
              </button>
            ))}
          </div>
          <div className="virtual-keyboard__row virtual-keyboard__row--actions">
            <button
              className="virtual-keyboard__key virtual-keyboard__key--action"
              type="button"
              onMouseDown={(event) => event.preventDefault()}
              onClick={(event) => handleKey(event, backspace)}
            >
              ⌫ <span>{layout.backspace}</span>
            </button>
            <button
              className="virtual-keyboard__key virtual-keyboard__key--action"
              type="button"
              onMouseDown={(event) => event.preventDefault()}
              onClick={(event) => handleKey(event, () => insertText(' '))}
            >
              {layout.space}
            </button>
            <button
              className="virtual-keyboard__key virtual-keyboard__key--action"
              type="button"
              onMouseDown={(event) => event.preventDefault()}
              onClick={(event) => handleKey(event, () => updateText('', 0))}
            >
              {layout.clear}
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

export default VirtualKeyboard
