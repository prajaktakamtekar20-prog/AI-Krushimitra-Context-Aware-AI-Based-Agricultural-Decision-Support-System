export const normalizeActivities = (activities) => {
  if (Array.isArray(activities)) {
    return activities.filter((activity) => typeof activity === 'string')
  }
  if (typeof activities !== 'string' || !activities.trim()) return []

  try {
    const parsedActivities = JSON.parse(activities)
    if (Array.isArray(parsedActivities)) {
      return parsedActivities.filter((activity) => typeof activity === 'string')
    }
  } catch {
    return [activities]
  }

  return [activities]
}
