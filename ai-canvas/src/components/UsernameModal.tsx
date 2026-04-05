import { useState } from 'react'

interface UsernameModalProps {
  onSubmit: (name: string) => void
}

export function UsernameModal({ onSubmit }: UsernameModalProps) {
  const [value, setValue] = useState('')

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    const name = value.trim()
    if (!name) return
    onSubmit(name)
  }

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 2000,
        background: 'rgba(0,0,0,0.55)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
      }}
    >
      <form
        onSubmit={handleSubmit}
        style={{
          background: '#1a1a2e',
          borderRadius: 12,
          padding: '32px 28px',
          display: 'flex',
          flexDirection: 'column',
          gap: 16,
          minWidth: 300,
          boxShadow: '0 8px 40px rgba(0,0,0,0.5)',
        }}
      >
        <h2 style={{ color: '#e0e0e0', margin: 0, fontSize: 18, fontWeight: 700 }}>
          What's your name?
        </h2>
        <p style={{ color: '#888', margin: 0, fontSize: 13 }}>
          This will be shown to other collaborators.
        </p>
        <input
          autoFocus
          type="text"
          placeholder="Your name"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          maxLength={32}
          style={{
            padding: '10px 12px',
            borderRadius: 8,
            border: '1px solid #333',
            background: '#0d0d1a',
            color: '#e0e0e0',
            fontSize: 15,
            outline: 'none',
          }}
        />
        <button
          type="submit"
          disabled={!value.trim()}
          style={{
            padding: '10px 0',
            borderRadius: 8,
            border: 'none',
            background: value.trim() ? '#1e40af' : '#333',
            color: '#fff',
            fontSize: 15,
            fontWeight: 600,
            cursor: value.trim() ? 'pointer' : 'not-allowed',
          }}
        >
          Join
        </button>
      </form>
    </div>
  )
}
