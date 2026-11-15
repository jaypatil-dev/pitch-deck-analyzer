async function request(path, options) {
  const res = await fetch(path, options)
  if (!res.ok) {
    let message = res.statusText
    try {
      const body = await res.json()
      if (typeof body.detail === 'string') message = body.detail
    } catch {
      // the server sent no JSON; keep the status text
    }
    throw new Error(message)
  }
  return res.json()
}

export function uploadDeck(file) {
  const form = new FormData()
  form.append('file', file)
  // No Content-Type header here: the browser adds the right one for file uploads.
  return request('/api/decks', { method: 'POST', body: form })
}

export function startAnalysis(deckId) {
  return request(`/api/decks/${deckId}/analyze`, { method: 'POST' })
}

export function getJob(jobId) {
  return request(`/api/jobs/${jobId}`)
}

export function getRun(runId) {
  return request(`/api/runs/${runId}`)
}


export function getRubric() {
  return request('/api/rubric')
}

export function listRuns() {
  return request('/api/runs')
}


export function getFeedback(runId) {
  return request(`/api/runs/${runId}/feedback`)
}

export function makeFeedback(runId, slide, kind) {
  return request(`/api/runs/${runId}/slides/${slide}/${kind}`, { method: 'POST' })
}


export function listDecks() {
  return request('/api/decks')
}

export function saveHumanScores(deckId, body) {
  return request(`/api/decks/${deckId}/human-scores`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
}

export function getEvaluation() {
  return request('/api/evaluation')
}

function postJson(path, body) {
  return request(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
}

export function getSession() {
  return request('/api/session')
}

export function login(password) {
  return postJson('/api/login', { password })
}

export function listFiles() {
  return request('/api/dataroom/files')
}

export function listLinks(deckId) {
  return request(`/api/decks/${deckId}/links`)
}

export function createLink(deckId, label) {
  return postJson(`/api/decks/${deckId}/links`, { label })
}

export function setLinkActive(token, active) {
  return postJson(`/api/links/${token}/active`, { active })
}

export function listViews(deckId) {
  return request(`/api/decks/${deckId}/views`)
}

export function viewInfo(token) {
  return request(`/api/view/${token}`)
}

export function viewStart(token) {
  return request(`/api/view/${token}/start`, { method: 'POST' })
}

export function viewPing(token, viewId, page, seconds) {
  return request(`/api/view/${token}/ping`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ view_id: viewId, page, seconds }),
    keepalive: true, // lets the request finish even while the tab is closing
  })
}

export function logout() {
  return request('/api/logout', { method: 'POST' })
}