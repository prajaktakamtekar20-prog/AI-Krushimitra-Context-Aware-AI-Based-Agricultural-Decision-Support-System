import React, { useEffect, useRef, useState } from 'react'
import { useLanguage } from '../context/LanguageContext'
import './VoiceControls.css'

const recognitionLocales = {
  en: 'en-IN',
  mr: 'mr-IN',
  hi: 'hi-IN'
}

const speechLocales = {
  en: 'en-IN',
  mr: 'mr-IN',
  hi: 'hi-IN',
  ml: 'ml-IN'
}

let activeSpeech = null

const stopActiveSpeech = () => {
  if (!activeSpeech) return
  const current = activeSpeech
  activeSpeech = null
  current.stop()
}

export const VoiceInputButton = ({ value, onChange, inputRef }) => {
  const { language, t } = useLanguage()
  const [listening, setListening] = useState(false)
  const [status, setStatus] = useState('')
  const recognitionRef = useRef(null)
  const generationRef = useRef(0)
  const valueRef = useRef(value)
  const onChangeRef = useRef(onChange)
  const translateRef = useRef(t)

  valueRef.current = value
  onChangeRef.current = onChange
  translateRef.current = t

  useEffect(() => () => {
    generationRef.current += 1
    const recognition = recognitionRef.current
    recognitionRef.current = null
    if (!recognition) return
    recognition.onresult = null
    recognition.onerror = null
    recognition.onend = null
    try {
      recognition.stop()
    } catch (error) {
      console.warn('Could not stop speech recognition during cleanup:', error)
    }
  }, [])

  const stopListening = () => {
    const recognition = recognitionRef.current
    if (!recognition) return
    generationRef.current += 1
    recognitionRef.current = null
    setListening(false)
    try {
      recognition.stop()
    } catch (error) {
      setStatus(t('voice.recognitionError'))
      console.warn('Could not stop speech recognition:', error)
    }
  }

  useEffect(() => {
    const recognition = recognitionRef.current
    if (!recognition) return
    generationRef.current += 1
    recognitionRef.current = null
    setListening(false)
    try {
      recognition.stop()
    } catch (error) {
      console.warn('Could not stop speech recognition after language change:', error)
    }
    setStatus(recognitionLocales[language] ? '' : translateRef.current('voice.unsupportedLanguage'))
  }, [language])

  const startListening = () => {
    if (!recognitionLocales[language]) {
      setStatus(t('voice.unsupportedLanguage'))
      return
    }

    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition
    if (typeof SpeechRecognition !== 'function') {
      setStatus(t('voice.unsupportedRecognition'))
      return
    }

    setStatus('')
    const generation = ++generationRef.current
    let recognition
    try {
      recognition = new SpeechRecognition()
      recognition.lang = recognitionLocales[language]
      recognition.continuous = false
      recognition.interimResults = false
      recognition.maxAlternatives = 1
      let consumedResultIndex = 0
      recognition.onresult = (event) => {
        if (generation !== generationRef.current) return
        const results = event.results || []
        const firstChanged = Number.isInteger(event.resultIndex) ? event.resultIndex : 0
        const transcriptParts = []
        for (let index = Math.max(firstChanged, consumedResultIndex); index < results.length; index += 1) {
          if (!results[index].isFinal) continue
          transcriptParts.push(results[index][0]?.transcript || '')
          consumedResultIndex = index + 1
        }
        const transcript = transcriptParts
          .join(' ')
          .trim()
        if (!transcript) return
        const current = valueRef.current
        const separator = current && !/\s$/u.test(current) ? ' ' : ''
        const maxLength = inputRef.current?.maxLength
        const available = Number.isInteger(maxLength) && maxLength >= 0
          ? Math.max(0, maxLength - current.length)
          : Infinity
        const addition = `${separator}${transcript}`.slice(0, available)
        if (addition) {
          onChangeRef.current(`${current}${addition}`)
          setStatus(t('voice.speechAdded'))
        }
      }
      recognition.onerror = (event) => {
        if (generation !== generationRef.current) return
        const messageKey = event.error === 'not-allowed' || event.error === 'service-not-allowed'
          ? 'permissionDenied'
          : event.error === 'language-not-supported'
            ? 'unsupportedLanguage'
            : event.error === 'no-speech'
              ? 'noSpeech'
              : 'recognitionError'
        setStatus(t(`voice.${messageKey}`))
        setListening(false)
        recognitionRef.current = null
      }
      recognition.onend = () => {
        if (generation !== generationRef.current) return
        recognitionRef.current = null
        setListening(false)
      }
      recognitionRef.current = recognition
      recognition.start()
      setListening(true)
      inputRef.current?.focus()
    } catch (error) {
      recognitionRef.current = null
      setListening(false)
      setStatus(error?.name === 'NotAllowedError' || error?.name === 'SecurityError'
        ? t('voice.permissionDenied')
        : t('voice.recognitionError'))
      console.warn('Could not start speech recognition:', error)
    }
  }

  const toggleListening = () => {
    if (listening) stopListening()
    else startListening()
  }

  return (
    <div className="voice-input-control">
      <button
        className={`voice-control-button${listening ? ' voice-control-button--active' : ''}`}
        type="button"
        aria-label={t(listening ? 'voice.stopListening' : 'voice.startListening')}
        aria-pressed={listening}
        title={t(listening ? 'voice.stopListening' : 'voice.startListening')}
        onMouseDown={(event) => event.preventDefault()}
        onClick={toggleListening}
      >
        <span aria-hidden="true">{listening ? '■' : '🎙'}</span>
      </button>
      {(status || listening) && (
        <span className="voice-control-status" role="status">
          {status || t('voice.listening')}
        </span>
      )}
    </div>
  )
}

export const SpeechOutputButton = ({ text, className = '' }) => {
  const { language, t } = useLanguage()
  const [speaking, setSpeaking] = useState(false)
  const [status, setStatus] = useState('')
  const utteranceRef = useRef(null)
  const ownerRef = useRef(null)

  useEffect(() => () => {
    if (ownerRef.current && activeSpeech === ownerRef.current) stopActiveSpeech()
  }, [])

  const stopPlayback = () => {
    if (ownerRef.current && activeSpeech === ownerRef.current) {
      stopActiveSpeech()
    }
    ownerRef.current = null
    utteranceRef.current = null
    setSpeaking(false)
  }

  const play = () => {
    if (!text?.trim()) return
    const speechSynthesis = window.speechSynthesis
    if (typeof speechSynthesis?.speak !== 'function' || typeof window.SpeechSynthesisUtterance !== 'function') {
      setStatus(t('voice.unsupportedPlayback'))
      return
    }

    stopActiveSpeech()
    setStatus('')
    const utterance = new window.SpeechSynthesisUtterance(text)
    utterance.lang = speechLocales[language] || speechLocales.en
    const owner = {
      stop: () => {
        window.speechSynthesis.cancel()
        setSpeaking(false)
        setStatus('')
      }
    }
    ownerRef.current = owner
    utteranceRef.current = utterance
    activeSpeech = owner
    setSpeaking(true)
    utterance.onend = () => {
      if (activeSpeech !== owner) return
      activeSpeech = null
      ownerRef.current = null
      utteranceRef.current = null
      setSpeaking(false)
    }
    utterance.onerror = (event) => {
      if (activeSpeech !== owner) return
      activeSpeech = null
      ownerRef.current = null
      utteranceRef.current = null
      setSpeaking(false)
      setStatus(event.error === 'interrupted' || event.error === 'canceled'
        ? ''
        : t('voice.playbackError'))
    }

    try {
      speechSynthesis.speak(utterance)
    } catch (error) {
      if (activeSpeech === owner) activeSpeech = null
      ownerRef.current = null
      utteranceRef.current = null
      setSpeaking(false)
      setStatus(t('voice.playbackError'))
      console.warn('Could not start speech playback:', error)
    }
  }

  const togglePlayback = () => {
    if (speaking) stopPlayback()
    else play()
  }

  if (!text?.trim()) return null

  return (
    <span className={`voice-output-control ${className}`.trim()}>
      <button
        className="voice-control-button voice-control-button--output"
        type="button"
        aria-label={t(speaking ? 'voice.stopPlayback' : 'voice.listen')}
        title={t(speaking ? 'voice.stopPlayback' : 'voice.listen')}
        aria-pressed={speaking}
        onClick={togglePlayback}
      >
        <span aria-hidden="true">{speaking ? '■' : '🔊'}</span>
      </button>
      {status && <span className="voice-control-status" role="status">{status}</span>}
    </span>
  )
}
