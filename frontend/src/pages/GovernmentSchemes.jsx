import React, { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useLanguage } from '../context/LanguageContext'
import { useAuth } from '../context/AuthContext'
import Background from '../components/Background'
import Navbar from '../components/Navbar'
import GlassCard from '../components/GlassCard'
import GradientButton from '../components/GradientButton'
import FormInput from '../components/FormInput'
import FormSelect from '../components/FormSelect'
import { schemeApi } from '../services/api'
import { getPlantVillageCropOptions } from '../constants/crops'
import { dropdowns } from '../translations/dropdowns'
import { localizeApplicationStep, localizeDeadline, localizeDepartment, localizeDocument, localizeDocumentStatus, localizeFieldName, localizeGovernmentLevel, localizeMatchText, localizeSchemeBenefit, localizeSchemeCategory, localizeSchemeCrop, localizeSchemeDescription, localizeSchemeName, localizeSource } from '../translations/schemes'

const CATEGORY_LABELS = {
  farmer_support: 'Farmer Support',
  income_support: 'Income Support',
  crop_insurance: 'Crop Insurance',
  credit: 'Credit / Loans',
  irrigation: 'Irrigation',
  infrastructure: 'Farm Infrastructure',
  subsidy: 'Subsidy Schemes',
  advisory: 'Advisory Services',
  soil_testing: 'Soil Testing',
  solar_energy: 'Solar / Renewable Energy',
  equipment: 'Farm Equipment',
  helpline: 'Helpline / Support',
  search_portal: 'Search Portal',
  information: 'Information',
  organic_farming: 'Organic Farming',
  certification: 'Certification Support',
  capacity_building: 'Capacity Building',
}

const BENEFIT_LABELS = {
  direct_benefit_transfer: 'Direct Benefit (DBT)',
  insurance: 'Crop Insurance',
  credit: 'Credit / Loan',
  capital_subsidy: 'Capital / Equipment Subsidy',
  advisory_service: 'Free Advisory',
  information_portal: 'Portal / Info',
}

const STATE_OPTIONS = [
  { value: '', label: 'All States' },
  { value: 'Maharashtra', label: 'Maharashtra' },
  { value: 'Karnataka', label: 'Karnataka' },
  { value: 'Madhya Pradesh', label: 'Madhya Pradesh' },
  { value: 'Uttar Pradesh', label: 'Uttar Pradesh' },
  { value: 'Gujarat', label: 'Gujarat' },
  { value: 'Rajasthan', label: 'Rajasthan' },
  { value: 'Punjab', label: 'Punjab' },
  { value: 'Haryana', label: 'Haryana' },
  { value: 'Tamil Nadu', label: 'Tamil Nadu' },
  { value: 'Telangana', label: 'Telangana' },
  { value: 'Andhra Pradesh', label: 'Andhra Pradesh' },
  { value: 'Bihar', label: 'Bihar' },
  { value: 'Odisha', label: 'Odisha' },
  { value: 'Kerala', label: 'Kerala' },
  { value: 'Chhattisgarh', label: 'Chhattisgarh' },
]

const matchBadge = (status, t) => {
  switch (status) {
    case 'potentially_eligible':
      return { label: `🟢 ${t('schemes.eligible')}`, cls: 'badge badge--success' }
    case 'more_information_required':
      return { label: `🟡 ${t('schemes.moreInfo')}`, cls: 'badge badge--warning' }
    case 'eligibility_criteria_not_met':
      return { label: `🔴 ${t('schemes.notEligible')}`, cls: 'badge badge--danger' }
    default:
      return { label: `🟡 ${t('schemes.moreInfo')}`, cls: 'badge badge--warning' }
  }
}

const prettyLabel = (raw, map) => {
  if (!raw) return raw
  if (map && map[raw]) return map[raw]
  return String(raw).replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())
}

const localizeDropdownValue = (section, value, language, fallbackMap) => {
  if (!value) return value
  return dropdowns[language]?.[section]?.[value]
    || dropdowns.en?.[section]?.[value]
    || prettyLabel(value, fallbackMap)
}

const Chip = ({ children, color = 'default' }) => {
  const colorClass =
    color === 'green' ? 'chip--green'
    : color === 'red' ? 'chip--red'
    : color === 'yellow' ? 'chip--yellow'
    : ''
  return <span className={`chip ${colorClass}`.trim()}>{children}</span>
}

const GovernmentSchemes = () => {
  const { t, language, formatDate } = useLanguage()
  const { user } = useAuth()
  const navigate = useNavigate()

  const [loading, setLoading] = useState(true)
  const [data, setData] = useState(null)
  const [isDemo, setIsDemo] = useState(false)
  const [search, setSearch] = useState('')
  const [category, setCategory] = useState('')
  const [state, setState] = useState('')
  const [crop, setCrop] = useState('')
  const [benefit, setBenefit] = useState('')
  const [expandedId, setExpandedId] = useState(null)
  const [localChecklists, setLocalChecklists] = useState({})

  const userCrop = user?.farming?.crop || user?.main_crop || ''
  const userState = user?.location?.state || ''
  const cropOptions = [
    { value: '', label: t('schemes.allCrops') },
    ...getPlantVillageCropOptions(t),
    { value: 'notified', label: t('dropdowns.notifiedCrops') }
  ]

  useEffect(() => {
    let cancelled = false
    const load = async () => {
      setLoading(true)
      try {
        const result = await schemeApi.listOrMatch({
          q: '',
          match: true,
          crop: userCrop || '',
          state: userState || '',
        })
        if (!cancelled) {
          setData(result)
          setIsDemo(Boolean(result?.demo_fallback))
        }
      } catch (err) {
        console.warn('Initial schemes load failed:', err.message)
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    load()
    return () => { cancelled = true }
  }, [userCrop, userState])

  const applyFilters = () => {
    setLoading(true)
    schemeApi.listOrMatch({
      q: search,
      match: true,
      category,
      state,
      crop,
      benefit_type: benefit,
    }).then(result => {
      setData(result)
      setIsDemo(Boolean(result?.demo_fallback))
      setLoading(false)
    }).catch(err => {
      console.warn('Filter apply failed:', err.message)
      setLoading(false)
    })
  }

  const schemesWithMatch = useMemo(() => {
    if (!data) return []
    const arr = data.schemes_with_match || (Array.isArray(data.schemes) ? data.schemes.map(s => ({ scheme: s, match: { status: 'more_information_required', reasons: [], missing_fields: [], blockers: [], unverified_conditions: [] } })) : [])
    if (!search && !category && !state && !crop && !benefit) return arr
    const s = search.toLowerCase()
    return arr.filter(item => {
      const sc = item.scheme || item
      if (s) {
        const hay = `${sc.official_name || ''} ${sc.department || ''} ${sc.benefits_summary || ''}`.toLowerCase()
        if (!hay.includes(s)) return false
      }
      if (category && !(sc.categories || []).includes(category)) return false
      if (benefit && !(sc.benefit_types || []).includes(benefit)) return false
      if (state) {
        const states = sc.states || []
        if (!states.includes('all') && !states.map(String).map(x => x.toLowerCase()).includes(state.toLowerCase())) return false
      }
      if (crop) {
        const crops = sc.crops || []
        if (!crops.includes('all') && !crops.map(String).map(x => x.toLowerCase()).includes(crop.toLowerCase())) return false
      }
      return true
    })
  }, [data, search, category, state, crop, benefit])

  const grouped = useMemo(() => {
    const groups = { potentially_eligible: [], more_information_required: [], eligibility_criteria_not_met: [] }
    schemesWithMatch.forEach(item => {
      const status = item.match?.status || 'more_information_required'
      if (groups[status]) groups[status].push(item)
      else groups.more_information_required.push(item)
    })
    return groups
  }, [schemesWithMatch])

  const counts = useMemo(() => ({
    potentially_eligible: grouped.potentially_eligible.length,
    more_information_required: grouped.more_information_required.length,
    eligibility_criteria_not_met: grouped.eligibility_criteria_not_met.length,
  }), [grouped])

  const categoryOptions = useMemo(() => {
    const raw = data?.categories || (data?.meta?.categories) || []
    const opts = Array.from(new Set([
      ...raw,
      ...schemesWithMatch.flatMap(x => (x.scheme || x).categories || [])
    ]))
    return [{ value: '', label: t('schemes.allCategories') }, ...opts.map(c => ({
      value: c,
      label: localizeSchemeCategory(c, language)
    }))]
  }, [data, schemesWithMatch, language, t])

  const benefitOptions = useMemo(() => {
    const raw = data?.benefit_types || (data?.meta?.benefit_types) || []
    const opts = Array.from(new Set([
      ...raw,
      ...schemesWithMatch.flatMap(x => (x.scheme || x).benefit_types || [])
    ]))
    return [{ value: '', label: t('schemes.allBenefits') }, ...opts.map(b => ({
      value: b,
      label: localizeSchemeBenefit(b, language)
    }))]
  }, [data, schemesWithMatch, language, t])

  const toggleExpand = (id) => setExpandedId(prev => prev === id ? null : id)

  const toggleDoc = (schemeId, docId) => {
    setLocalChecklists(prev => {
      const current = Array.isArray(prev[schemeId]) ? [...prev[schemeId]] : []
      const idx = current.indexOf(docId)
      if (idx === -1) current.push(docId)
      else current.splice(idx, 1)
      return { ...prev, [schemeId]: current }
    })
  }

  const saveChecklist = async (schemeId) => {
    const checked = Array.isArray(localChecklists[schemeId]) ? localChecklists[schemeId] : []
    const initialChecked = checked
    const res = await schemeApi.saveChecklist(schemeId, checked)
    if (res?.checked_document_ids && !res.demo_fallback) {
      setLocalChecklists(prev => ({ ...prev, [schemeId]: res.checked_document_ids }))
    }
    alert(
      (res?.demo_fallback ? `[${t('schemes.demoFallback')}]\n\n` : '') +
      `${initialChecked.length} ${t('schemes.checkedDocuments')}\n` +
      (res?.note || res?.saved_locally ? res.note || t('common.success') : t('common.success'))
    )
  }

  const getCheckedFor = (schemeId, fromServerDocIds) => {
    if (Array.isArray(localChecklists[schemeId]) && localChecklists[schemeId].length > 0) return localChecklists[schemeId]
    if (Array.isArray(fromServerDocIds) && fromServerDocIds.length > 0) return fromServerDocIds
    return []
  }

  const renderCard = (item) => {
    const sc = item.scheme || item
    const match = item.match || { status: 'more_information_required', reasons: [], missing_fields: [], blockers: [], unverified_conditions: [], match_score: null }
    const isExpanded = expandedId === sc.id
    const badge = matchBadge(match.status, t)

    const displayName = localizeSchemeName(sc, language)

    const docIdsFromServer = item.checklist_progress?.checked_document_ids || data?.checklist_progresses?.[sc.id]
    const checkedDocs = getCheckedFor(sc.id, docIdsFromServer)
    const docs = sc.required_documents || []

    return (
      <GlassCard key={sc.id} className="scheme-card" hover glowGreen={match.status === 'potentially_eligible'}>
        <div className="scheme-card__header">
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center', marginBottom: 8 }}>
              <span className={badge.cls}>{badge.label}</span>
              <span className="chip chip--outline">{localizeGovernmentLevel(sc.government_level, language)}</span>
              {typeof match.match_score === 'number' && (
                <span className="chip">{t('schemes.matchAccuracy')}: {match.match_score}%</span>
              )}
            </div>
            <h3 className="scheme-card__title">{displayName}</h3>
            <p className="scheme-card__dept">{localizeDepartment(sc.department, language)}</p>
          </div>
        </div>

        <p className="scheme-card__benefit">{localizeSchemeDescription(sc, language)}</p>

        <div className="scheme-card__chips">
          {(sc.categories || []).map(c => (
            <Chip key={c} color="green">{localizeSchemeCategory(c, language)}</Chip>
          ))}
          {(sc.benefit_types || []).map(b => (
            <Chip key={b} color="yellow">{localizeSchemeBenefit(b, language)}</Chip>
          ))}
          {((sc.states || []).length === 1 && sc.states[0] === 'all')
            ? <Chip>{t('schemes.allIndia')}</Chip>
            : (sc.states || []).map(st => <Chip key={st} color="green">{localizeDropdownValue('states', st, language, {})}</Chip>)
          }
          {(sc.crops || []).includes('all')
            ? <Chip>{t('schemes.allCrops')}</Chip>
            : (sc.crops || []).map(c => <Chip key={c} color="yellow">{localizeSchemeCrop(c, language)}</Chip>)
          }
        </div>

        <div className="scheme-card__meta">
          <span>🕐 {t('schemes.lastVerified')}: <b>{sc.last_verified ? formatDate(sc.last_verified, { dateStyle: 'medium' }) : '—'}</b></span>
          <span style={{ marginLeft: 16 }}>
            {sc.verification_status === 'official_url_verified' ? `✅ ${t('schemes.verified')}` : `ℹ️ ${t('schemes.unverified')}`}
          </span>
        </div>

        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10, marginTop: 16 }}>
          <GradientButton
            size="sm"
            variant={isExpanded ? 'secondary' : 'primary'}
            onClick={() => toggleExpand(sc.id)}
          >
            {isExpanded ? `🔼 ${t('schemes.collapse')}` : `🔽 ${t('schemes.expand')}`}
          </GradientButton>
          {sc.official_application_url && (
            <a href={sc.official_application_url} target="_blank" rel="noreferrer noopener" style={{ textDecoration: 'none' }}>
              <GradientButton size="sm" variant="green">
                🔗 {t('schemes.applyNow')}
              </GradientButton>
            </a>
          )}
        </div>

        {isExpanded && (
          <div className="scheme-card__expanded">
            <div className="scheme-section">
              <h4>🧾 {t('schemes.disclaimer').split('PRELIMINARY DISCLAIMER: ')[1] ? t('schemes.disclaimer') : t('schemes.disclaimer')}</h4>
            </div>

            <div className="scheme-section">
              <h4>✓ {t('schemes.eligibilityReasons')}</h4>
              {(match.reasons && match.reasons.length > 0) ? (
                <ul>
                  {match.reasons.map((r, i) => <li key={i}>{localizeMatchText(r, language)}</li>)}
                </ul>
              ) : <p style={{ color: '#b7c3cc', fontSize: 14 }}>—</p>}

              {(match.missing_fields && match.missing_fields.length > 0) && (
                <>
                  <h4 style={{ marginTop: 14 }}>ℹ️ {t('schemes.missingFieldsList')}</h4>
                  <ul>
                    {match.missing_fields.map((r, i) => <li key={i}>{localizeFieldName(r, language)}</li>)}
                  </ul>
                </>
              )}

              {(match.unverified_conditions && match.unverified_conditions.length > 0) && (
                <>
                  <h4 style={{ marginTop: 14 }}>⚠️ {t('schemes.unverifiedConditions')}</h4>
                  <ul>
                    {match.unverified_conditions.map((r, i) => <li key={i}>{localizeMatchText(r, language)}</li>)}
                  </ul>
                </>
              )}

              {(match.blockers && match.blockers.length > 0) && (
                <>
                  <h4 style={{ marginTop: 14 }}>⛔ {t('schemes.blockers')}</h4>
                  <ul>
                    {match.blockers.map((r, i) => <li key={i}>{localizeMatchText(r, language)}</li>)}
                  </ul>
                </>
              )}
            </div>

            <div className="scheme-section">
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 10 }}>
                <h4>📋 {t('schemes.documentChecklist')}</h4>
                <GradientButton
                  size="sm"
                  variant="green"
                  onClick={() => saveChecklist(sc.id)}
                >
                  💾 {t('schemes.saveChecklist')} ({checkedDocs.length}/{docs.length})
                </GradientButton>
              </div>
              {docs.length > 0 ? (
                <div style={{ display: 'grid', gap: 8, marginTop: 12 }}>
                  {docs.map(d => {
                    const isChecked = checkedDocs.includes(d.id)
                    const localizedDocument = localizeDocument(sc.id, d, language)
                    return (
                      <label key={d.id} className={`check-item ${isChecked ? 'check-item--checked' : ''}`} style={{ display: 'flex', alignItems: 'flex-start', gap: 10, cursor: 'pointer' }}>
                        <input
                          type="checkbox"
                          checked={isChecked}
                          onChange={() => toggleDoc(sc.id, d.id)}
                          style={{ marginTop: 4 }}
                        />
                        <div style={{ flex: 1 }}>
                          <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
                            <b>{localizedDocument.name}</b>
                            <Chip color={d.status === 'typically_mandatory' ? 'red' : d.status === 'conditional' ? 'yellow' : 'default'}>
                              {localizeDocumentStatus(d.status, language)}
                            </Chip>
                          </div>
                          {d.why && (
                            <div style={{ fontSize: 13, color: '#a9b6be', marginTop: 4 }}>
                              <b>{t('schemes.whyNeeded')}</b> {localizedDocument.why}
                            </div>
                          )}
                        </div>
                      </label>
                    )
                  })}
                </div>
              ) : <p style={{ color: '#b7c3cc', fontSize: 14 }}>—</p>}
            </div>

            <div className="scheme-section">
              <h4>📝 {t('schemes.applicationSteps')}</h4>
              <ol style={{ paddingLeft: 22, display: 'grid', gap: 10 }}>
                {(sc.application_steps || []).map(step => {
                  const localizedStep = localizeApplicationStep(sc.id, step, language)
                  return (
                  <li key={step.step} style={{ color: 'inherit' }}>
                    <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
                      <b>{t('schemes.step')} {step.step}: {localizedStep.title}</b>
                      {typeof step.verified === 'boolean' && (
                        <Chip color={step.verified ? 'green' : 'yellow'}>
                          {step.verified ? t('schemes.verifiedStep') : t('schemes.menuMayVary')}
                        </Chip>
                      )}
                    </div>
                    <div style={{ color: '#cfd9df', marginTop: 4 }}>{localizedStep.detail}</div>
                  </li>
                  )
                })}
              </ol>
            </div>

            <div className="scheme-section" style={{ fontSize: 13, color: '#a9b6be' }}>
              <div>📍 {t('schemes.source')}: {localizeSource(sc, language) || t('schemes.officialNotification')}</div>
              {sc.official_guidelines_url && (
                <div style={{ marginTop: 4 }}>
                  📖 {t('schemes.officialLink')}: <a href={sc.official_guidelines_url} target="_blank" rel="noreferrer noopener">{sc.official_guidelines_url}</a>
                </div>
              )}
              {(sc.deadline_note) && (
                <div style={{ marginTop: 4 }}>⏰ {t('schemes.deadline')}: {localizeDeadline(sc, language)}</div>
              )}
            </div>
          </div>
        )}
      </GlassCard>
    )
  }

  return (
    <Background>
      <Navbar />
      <div className="page-wrapper">
        <div className="page-header">
          <div>
            <h1 className="page-title">🏛️ {t('schemes.title')}</h1>
            <p className="page-subtitle">{t('schemes.subtitle')}</p>
          </div>
        </div>

        <GlassCard className="disclaimer-banner" glow>
          <p style={{ margin: 0, lineHeight: 1.6 }}>{t('schemes.disclaimer')}</p>
        </GlassCard>

        {isDemo && (
          <GlassCard className="info-banner">
            <p style={{ margin: 0 }}>
              📡 <b>{t('schemes.demoFallback')}</b>
            </p>
          </GlassCard>
        )}

        <GlassCard className="filters-card" glow>
          <div style={{ display: 'grid', gap: 14, gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))' }}>
            <FormInput
              label={`🔍 ${t('common.search')}`}
              placeholder={t('schemes.searchPlaceholder')}
              value={search}
              onChange={e => setSearch(e.target.value)}
              icon="🔍"
            />
            <FormSelect
              label={`🗂️ ${t('schemes.filterCategory')}`}
              value={category}
              onChange={e => setCategory(e.target.value)}
              options={categoryOptions}
              placeholder={t('schemes.filterCategory')}
            />
            <FormSelect
              label={`📍 ${t('schemes.filterState')}`}
              value={state}
              onChange={e => setState(e.target.value)}
              options={STATE_OPTIONS.map(o => ({ ...o, label: o.value === '' ? t('schemes.allStates') : t(`dropdowns.states.${o.value}`) }))}
              placeholder={t('schemes.filterState')}
            />
            <FormSelect
              label={`🌾 ${t('schemes.filterCrop')}`}
              value={crop}
              onChange={e => setCrop(e.target.value)}
              options={cropOptions}
              searchable
              searchPlaceholder={t('common.searchCrops')}
              placeholder={t('schemes.filterCrop')}
            />
            <FormSelect
              label={`💰 ${t('schemes.filterBenefit')}`}
              value={benefit}
              onChange={e => setBenefit(e.target.value)}
              options={benefitOptions}
              placeholder={t('schemes.filterBenefit')}
            />
          </div>
          <div style={{ display: 'flex', gap: 10, marginTop: 16, flexWrap: 'wrap' }}>
            <GradientButton onClick={applyFilters} loading={loading} variant="green">
              🔄 {t('schemes.applyFilters')}
            </GradientButton>
            <GradientButton
              variant="secondary"
              onClick={() => {
                setSearch('')
                setCategory('')
                setState('')
                setCrop('')
                setBenefit('')
                setLoading(true)
                schemeApi.listOrMatch({ match: true, crop: userCrop || '', state: userState || '' }).then(result => {
                  setData(result)
                  setIsDemo(Boolean(result?.demo_fallback))
                  setLoading(false)
                }).catch(() => setLoading(false))
              }}
            >
              ↺ {t('schemes.reset')}
            </GradientButton>
          </div>

          <div style={{ display: 'flex', gap: 16, marginTop: 16, flexWrap: 'wrap' }}>
            <div className="match-summary match-summary--green">
              🟢 <b>{t('schemes.eligible')}</b>: {counts.potentially_eligible}
            </div>
            <div className="match-summary match-summary--yellow">
              🟡 <b>{t('schemes.moreInfo')}</b>: {counts.more_information_required}
            </div>
            <div className="match-summary match-summary--red">
              🔴 <b>{t('schemes.notEligible')}</b>: {counts.eligibility_criteria_not_met}
            </div>
          </div>
        </GlassCard>

        {loading ? (
          <div style={{ display: 'flex', justifyContent: 'center', padding: '60px 0' }}>
            <div className="loading-spinner" />
          </div>
        ) : schemesWithMatch.length === 0 ? (
          <GlassCard className="empty-card">
            <p style={{ textAlign: 'center', fontSize: 16 }}>📭 {t('schemes.noSchemesFound')}</p>
            <div style={{ display: 'flex', justifyContent: 'center', marginTop: 16 }}>
              <GradientButton variant="primary" onClick={() => navigate('/ai-assistant')}>
                💬 {t('disease.askAssistant')}
              </GradientButton>
            </div>
          </GlassCard>
        ) : (
          <div className="scheme-groups">
            {grouped.potentially_eligible.length > 0 && (
              <section className="scheme-group">
                <h2 className="scheme-group__title scheme-group__title--green">
                  🟢 {t('schemes.eligible')} ({counts.potentially_eligible})
                </h2>
                <div className="scheme-grid">
                  {grouped.potentially_eligible.map(renderCard)}
                </div>
              </section>
            )}
            {grouped.more_information_required.length > 0 && (
              <section className="scheme-group">
                <h2 className="scheme-group__title scheme-group__title--yellow">
                  🟡 {t('schemes.moreInfo')} ({counts.more_information_required})
                </h2>
                <div className="scheme-grid">
                  {grouped.more_information_required.map(renderCard)}
                </div>
              </section>
            )}
            {grouped.eligibility_criteria_not_met.length > 0 && (
              <section className="scheme-group">
                <h2 className="scheme-group__title scheme-group__title--red">
                  🔴 {t('schemes.notEligible')} ({counts.eligibility_criteria_not_met})
                </h2>
                <div className="scheme-grid">
                  {grouped.eligibility_criteria_not_met.map(renderCard)}
                </div>
              </section>
            )}
          </div>
        )}
      </div>
    </Background>
  )
}

export default GovernmentSchemes
