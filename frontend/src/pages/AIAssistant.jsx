import React, { useState, useRef, useEffect } from 'react'
import { useLanguage } from '../context/LanguageContext'
import { useAuth } from '../context/AuthContext'
import { assistantApi } from '../services/api'
import Background from '../components/Background'
import Navbar from '../components/Navbar'
import GlassCard from '../components/GlassCard'
import GradientButton from '../components/GradientButton'
import VirtualKeyboard from '../components/VirtualKeyboard'
import { SpeechOutputButton, VoiceInputButton } from '../components/VoiceControls'

const AIAssistant = () => {
  const { t, language } = useLanguage()
  const { user } = useAuth()
  const [messages, setMessages] = useState([
    { id: 1, role: 'ai', content: t('aiAssistant.welcomeMsg') }
  ])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const messagesEndRef = useRef(null)
  const inputRef = useRef(null)
  const sendLockRef = useRef(false)

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  useEffect(() => {
    let active = true
    const current = messages
    const aiMessages = current.filter(
      (message) => message.role === 'ai' && message.id !== 1 && message.content.trim()
    )

    if (current.length === 1 && current[0].id === 1) {
      setMessages([{ ...current[0], content: t('aiAssistant.welcomeMsg') }])
      return () => { active = false }
    }
    if (aiMessages.length === 0) return () => { active = false }

    assistantApi.translateHistory(aiMessages.map((message) => message.content), language)
      .then((result) => {
        if (!active || !Array.isArray(result?.messages) || result.messages.length !== aiMessages.length) return
        let translatedIndex = 0
        setMessages((previous) => previous.map((message) => (
          message.role === 'ai' && message.id !== 1
            ? { ...message, content: result.messages[translatedIndex++] }
            : message
        )))
      })
      .catch((error) => {
        console.warn('Assistant history translation unavailable:', error.message)
        if (!active) return
        let translatedIndex = 0
        setMessages((previous) => previous.map((message) => (
          message.role === 'ai' && message.id !== 1
            ? { ...message, content: t('aiAssistant.translationUnavailable') }
            : message
        )))
      })

    return () => { active = false }
  }, [language])

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  const handleSend = async () => {
    const msg = input.trim()
    if (!msg || sendLockRef.current) return

    const userMessageId = Date.now()
    const responseId = userMessageId + 1
    const userMessage = { id: userMessageId, role: 'user', content: msg }
    setMessages((prev) => [...prev, userMessage, { id: responseId, role: 'ai', content: '' }])
    setInput('')
    sendLockRef.current = true
    setLoading(true)
    let responseText = ''
    let quotaNoticeAdded = false

    try {
      const context = {
        crop: user?.main_crop || user?.mainCrop,
        stage: user?.crop_stage || user?.cropStage,
        soilType: user?.soil_type || user?.soilType,
        irrigation: user?.irrigation_type || user?.irrigation,
        location: user?.location || null
      }
      const history = messages.filter((message) => message.id !== 1).slice(-8).map(({ role, content }) => ({
        role: role === 'ai' ? 'assistant' : role,
        content
      }))
      await assistantApi.streamChat(msg, context, language, history, (event) => {
        if (event.type === 'chunk' && typeof event.text === 'string') {
          responseText += event.text
        } else if (event.type === 'done' && ['quota_exceeded', 'openai_quota_exceeded'].includes(event.provider_error) && !quotaNoticeAdded) {
          quotaNoticeAdded = true
          responseText += `\n\n${t('aiAssistant.quotaExceeded')}`
        } else if (event.type === 'done' && ['rate_limit', 'openai_rate_limit'].includes(event.provider_error) && !quotaNoticeAdded) {
          quotaNoticeAdded = true
          responseText += `\n\n${t('aiAssistant.rateLimited')}`
        }
        setMessages((prev) => prev.map((item) => (
          item.id === responseId ? { ...item, content: responseText } : item
        )))
      })
      if (!responseText) {
        setMessages((prev) => prev.map((item) => (
          item.id === responseId ? { ...item, content: t('aiAssistant.unavailable') } : item
        )))
      }
    } catch (err) {
      console.error('Chat error:', err)
      const errorText = ['quota_exceeded', 'openai_quota_exceeded', 'groq_quota_exceeded', 'all_providers_quota_exceeded'].includes(err?.code)
        ? t('aiAssistant.quotaExceeded')
        : ['rate_limit', 'openai_rate_limit', 'groq_rate_limited'].includes(err?.code)
          ? t('aiAssistant.rateLimited')
          : err instanceof TypeError || err?.code === 'ERR_NETWORK'
            ? t('aiAssistant.networkError')
            : err?.message || t('aiAssistant.unavailable')
      setMessages((prev) => prev.map((item) => (
        item.id === responseId
          ? { ...item, content: responseText ? `${responseText}\n\n${errorText}` : errorText }
          : item
      )))
    } finally {
      sendLockRef.current = false
      setLoading(false)
      setTimeout(() => inputRef.current?.focus(), 100)
    }
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  return (
    <Background>
      <Navbar />
      <div style={{ maxWidth: 1400, margin: '0 auto', height: 'calc(100vh - 80px)' }}>
        <div
          style={{
            padding: '10px 18px',
            marginBottom: 8,
            borderRadius: 12,
            border: '1px solid rgba(251,191,36,0.45)',
            background: 'rgba(251,191,36,0.10)',
            fontSize: 13,
            lineHeight: 1.55,
            color: 'var(--text-primary)',
            fontWeight: 500
          }}
        >
          <span style={{ fontWeight: 700, color: '#b45309' }}>{t('aiAssistant.disclaimerTitle')}</span>{' '}
          {t('aiAssistant.disclaimer')}
        </div>
        <GlassCard className="chat-container" style={{ margin: 0, borderRadius: 0, background: 'transparent', backdropFilter: 'none', border: 'none', boxShadow: 'none', padding: 0 }}>
          <div className="chat-messages">
            {messages.map((msg) => (
              <div
                key={msg.id}
                className={`chat-message chat-message--${msg.role}`}
              >
                <div className={`chat-bubble chat-bubble--${msg.role}`}>
                  {msg.content}
                  {msg.role === 'ai' && msg.content.trim() && !loading && (
                    <SpeechOutputButton text={msg.content} />
                  )}
                </div>
              </div>
            ))}
            {loading && (
              <div className="chat-message chat-message--ai">
                <div className="chat-bubble chat-bubble--ai">
                  <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
                    <span className="loading-spinner" style={{ width: 16, height: 16, borderWidth: 2 }} />
                    <span style={{ fontSize: 14 }}>{t('aiAssistant.typing')}</span>
                  </span>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>
          <div className="chat-input-container" style={{ borderRadius: '0 0 20px 20px' }}>
            <VirtualKeyboard value={input} onChange={setInput} inputRef={inputRef} />
            <div className="chat-input-wrapper">
              <textarea
                ref={inputRef}
                className="chat-input"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder={t('aiAssistant.placeholder')}
                rows={1}
              />
              <VoiceInputButton value={input} onChange={setInput} inputRef={inputRef} />
              <GradientButton
                variant="primary"
                onClick={handleSend}
                disabled={!input.trim() || loading}
                className="chat-send-btn"
              >
                {loading ? (
                  <span className="loading-spinner" style={{ width: 18, height: 18 }} />
                ) : (
                  <>➤ {t('aiAssistant.send')}</>
                )}
              </GradientButton>
            </div>
          </div>
        </GlassCard>
      </div>
    </Background>
  )
}

export default AIAssistant
