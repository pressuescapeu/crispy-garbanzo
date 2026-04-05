// Module-level WebSocket singleton — importable from anywhere without prop drilling.
// useAgentBridge initialises it; useSpeechRecorder and Canvas both call sendToBackend.

let socket: WebSocket | null = null

// Module-level cursor position in tldraw page coordinates.
// Canvas.tsx writes here on every pointer move; useSpeechRecorder reads here on flush.
let _pageCursor: { x: number; y: number } = { x: 200, y: 200 }

export function updateCursorPosition(pos: { x: number; y: number }): void {
  _pageCursor = pos
}

export function getCursorPosition(): { x: number; y: number } {
  return _pageCursor
}

function getWebSocketUrl(): string {
  const raw = import.meta.env.VITE_WS_URL?.trim()
  const roomId = import.meta.env.VITE_ROOM_ID ?? 'hackathon-room'

  let baseUrl = raw || 'ws://localhost:8000'
  if (!baseUrl.startsWith('ws://') && !baseUrl.startsWith('wss://')) {
    baseUrl = `ws://${baseUrl}`
  }

  // Append /ws/{roomId} to the base URL
  return `${baseUrl}/ws/${roomId}`
}

export function initAgentSocket(): WebSocket {
  if (socket && socket.readyState !== WebSocket.CLOSED) {
    socket.close()
  }
  socket = new WebSocket(getWebSocketUrl())
  return socket
}

export function sendToBackend(data: unknown): void {
  if (socket?.readyState === WebSocket.OPEN) {
    socket.send(JSON.stringify(data))
  }
}
