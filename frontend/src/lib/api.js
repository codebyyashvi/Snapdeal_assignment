const BASE = import.meta.env.VITE_API_URL || ''

async function request(path, options = {}) {
  const res = await fetch(`${BASE}/api${path}`, options)
  if (!res.ok) throw new Error(`${res.status}: ${await res.text()}`)
  return res.json()
}

export const api = {
  health: () => request('/health'),
  seller: () => request('/seller'),
  history: () => request('/history'),
  clearHistory: () => request('/history', { method: 'DELETE' }),
  startSession: () => request('/session', { method: 'POST' }),
  endSession: (id) => request(`/session/${id}/end`, { method: 'POST' }),
  sendAudio: (id, wav) => {
    const form = new FormData()
    form.append('audio', wav, 'speech.wav')
    return request(`/session/${id}/turn`, { method: 'POST', body: form })
  },
  sendText: (id, text) => {
    const form = new FormData()
    form.append('text', text)
    return request(`/session/${id}/turn`, { method: 'POST', body: form })
  },
}
