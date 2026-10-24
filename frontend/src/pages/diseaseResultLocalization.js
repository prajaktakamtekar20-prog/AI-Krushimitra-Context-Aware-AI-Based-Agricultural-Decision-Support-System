import diseaseResultTranslations from '../../../shared/disease_result_translations.json' with { type: 'json' }

export const diseaseResultLanguages = Object.keys(diseaseResultTranslations)

export const localizeDiseaseResult = (result, language) => {
  const source = String(
    `${result?.disease_key || ''} ${result?.disease || ''} ${result?.disease_display || ''} ${result?.crop || ''}`
  ).toLowerCase()
  const isCommonRust = source.includes('corn_rust')
    || source.includes('common rust')
    || source.includes('puccinia sorghi')
  const isGrayLeafSpot = source.includes('corn_leaf_spot')
    || source.includes('gray_leaf_spot')
    || source.includes('gray leaf spot')
    || source.includes('cercospora zeae-maydis')
  const localized = diseaseResultTranslations[language]
  if (!localized) return result
  const diagnosticNote = String(result?.diagnostic_note || '').toLowerCase()
  const hasCompleteDiagnosticDisclaimer = [
    'visual analysis agrees with the local classifier',
    'confidence values are model scores',
    'chemical instructions are omitted unless verified',
    'preliminary image-model result, not a confirmed diagnosis',
    'agricultural expert to confirm'
  ].every((marker) => diagnosticNote.includes(marker))
  if (!isCommonRust && !isGrayLeafSpot) {
    if (language === 'en' && !hasCompleteDiagnosticDisclaimer) return result
    const missingFields = []
    const sourceSeverity = result.severity_original || result.severity
    const localizedSeverity = localized.severityLabels[sourceSeverity]
    if (result.crop) missingFields.push('crop_display')
    if (result.disease) missingFields.push('disease_display')
    for (const field of [
      'severity',
      'symptoms',
      'possible_causes',
      'causes',
      'recommended_management',
      'treatment',
      'prevention',
      'safety_warnings',
      'warnings',
      'precautions',
      'diagnostic_note',
      'error'
    ]) {
      if (result[field]) {
        if (field === 'diagnostic_note' && hasCompleteDiagnosticDisclaimer) continue
        if (field === 'severity' && localizedSeverity) continue
        const label = field === 'causes' ? 'possible_causes'
          : field === 'treatment' ? 'recommended_management'
            : field
        if (!missingFields.includes(label)) missingFields.push(label)
      }
    }
    const labels = missingFields.map((field) => localized.fieldLabels[field] || field)
    return {
      ...result,
      ...(hasCompleteDiagnosticDisclaimer
        ? { diagnostic_note: localized.diagnosticDisclaimer }
        : {}),
      crop_display: result.crop_display || result.crop || '',
      disease_display: result.disease_display || result.disease || '',
      ...(localizedSeverity
        ? { severity: localizedSeverity, severity_original: sourceSeverity }
        : {}),
      _untranslated_fields: missingFields,
      translation_complete: missingFields.length === 0,
      ...(missingFields.length
        ? { translation_notice: localized.partialNotice.replace('{fields}', labels.join(', ')) }
        : {})
    }
  }

  const translations = isGrayLeafSpot ? localized.grayLeafSpot : localized
  const translated = {
    ...result,
    ...(hasCompleteDiagnosticDisclaimer
      ? { diagnostic_note: localized.diagnosticDisclaimer }
      : {}),
    crop_display: translations.crop,
    disease_display: translations.disease,
    symptoms: translations.symptoms,
    possible_causes: translations.causes,
    causes: translations.causes,
    recommended_management: translations.treatment,
    treatment: translations.treatment,
    prevention: translations.prevention
  }
  const localizedFields = new Set([
    'crop_display',
    'disease_display',
    'symptoms',
    'possible_causes',
    'recommended_management',
    'prevention'
  ])
  if (hasCompleteDiagnosticDisclaimer) localizedFields.add('diagnostic_note')
  const sourceSeverity = result.severity_original || result.severity
  const localizedSeverity = localized.severityLabels[sourceSeverity]
  if (localizedSeverity) {
    translated.severity = localizedSeverity
    translated.severity_original = sourceSeverity
    localizedFields.add('severity')
  }

  if (isGrayLeafSpot) {
    translated.severity = translations.severity
    localizedFields.add('severity')

    const standardDisclaimer = 'This is a preliminary image-model result, not a confirmed diagnosis. Model scores are not calibrated probabilities; ask an agricultural expert to confirm, especially before taking treatment action.'
    if (
      !result.diagnostic_note
      || result.diagnostic_note.trim() === standardDisclaimer
      || result.translation_complete === true
    ) {
      translated.diagnostic_note = result.diagnostic_note
        && result.diagnostic_note.trim() !== standardDisclaimer
        ? result.diagnostic_note
        : translations.diagnosticNote
      localizedFields.add('diagnostic_note')
    }
    if (
      Array.isArray(result.safety_warnings)
      && result.safety_warnings.length > 0
      && result.safety_warnings.every((warning) => (
        typeof warning === 'string'
        && warning.trim().toLowerCase() === diseaseResultTranslations.en.grayLeafSpot.safetyWarning.toLowerCase()
      ))
    ) {
      translated.safety_warnings = result.safety_warnings.map(() => translations.safetyWarning)
      localizedFields.add('safety_warnings')
    }
  }

  const missingFields = []
  if (result.crop && !localizedFields.has('crop_display')) missingFields.push('crop_display')
  if (result.disease && !localizedFields.has('disease_display')) missingFields.push('disease_display')
  for (const [sourceField, translationField] of [
    ['severity', 'severity'],
    ['symptoms', 'symptoms'],
    ['possible_causes', 'possible_causes'],
    ['causes', 'possible_causes'],
    ['recommended_management', 'recommended_management'],
    ['treatment', 'recommended_management'],
    ['prevention', 'prevention'],
    ['safety_warnings', 'safety_warnings'],
    ['warnings', 'warnings'],
    ['precautions', 'precautions'],
    ['diagnostic_note', 'diagnostic_note'],
    ['error', 'error']
  ]) {
    if (result[sourceField] && !localizedFields.has(translationField) && !missingFields.includes(translationField)) {
      missingFields.push(translationField)
    }
  }

  if (missingFields.length) {
    const labels = missingFields.map((field) => localized.fieldLabels[field] || field)
    translated._untranslated_fields = missingFields
    translated.translation_complete = false
    translated.translation_notice = localized.partialNotice.replace('{fields}', labels.join(', '))
  } else {
    translated._untranslated_fields = []
    translated.translation_complete = true
    delete translated.translation_notice
  }

  return translated
}
