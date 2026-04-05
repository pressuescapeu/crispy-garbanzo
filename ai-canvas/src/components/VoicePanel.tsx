import { useState } from 'react'

export function VoicePanel() {
  const [isExpanded, setIsExpanded] = useState(true)

  return (
    <div
      style={{
        position: 'fixed',
        bottom: 16,
        right: 16,
        width: 300,
        height: isExpanded ? 480 : 48,
        zIndex: 1000,
        background: '#111827',
        borderRadius: 12,
        boxShadow: '0 4px 24px rgba(0,0,0,0.4)',
        overflow: 'hidden',
        display: 'flex',
        flexDirection: 'column',
      }}
    >
      <div
        style={{
          height: 48,
          flexShrink: 0,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '0 12px',
        }}
      >
        <span style={{ color: '#fff', fontSize: 14 }}>Voice Chat</span>
        <button
          type="button"
          onClick={() => setIsExpanded((v) => !v)}
          style={{
            background: 'none',
            border: 'none',
            color: '#fff',
            cursor: 'pointer',
            fontSize: 14,
            padding: 0,
            lineHeight: 1,
          }}
        >
          {isExpanded ? '▲' : '▼'}
        </button>
      </div>

      <div style={{ height: isExpanded ? '432px' : '0', overflow: 'hidden' }}>
        <iframe
          src="https://whereby.com/higgsnotfield?embed&skipMediaPermissionPrompt"
          allow="camera; microphone; fullscreen; speaker; display-capture"
          width="100%"
          height="100%"
          style={{ border: 'none' }}
          title="Voice Chat"
        />
      </div>
    </div>
  )
}
