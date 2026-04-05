import type { AgentAction } from './types.ts'

function getApiUrl() {
  const raw = import.meta.env.VITE_API_URL?.trim()
  if (!raw) {
    return 'http://localhost:3001'
  }
  if (raw.startsWith('http://') || raw.startsWith('https://')) {
    return raw
  }
  return `http://${raw}`
}

const API_URL = getApiUrl()

export async function postAgentAction(roomId: string, action: AgentAction) {
  const response = await fetch(`${API_URL}/agent-action`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ roomId, action }),
  })

  if (!response.ok) {
    throw new Error('Unable to post agent action')
  }

  return response.json()
}
