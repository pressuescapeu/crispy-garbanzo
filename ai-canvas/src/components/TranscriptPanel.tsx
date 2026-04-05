import { useState } from 'react'
import { useSpeechRecorder } from '../hooks/useSpeechRecorder'
import { RecordButton } from './RecordButton'
import { LiveLog } from './LiveLog'

export function TranscriptPanel({ username }: { username: string }) {
  const [collapsed, setCollapsed] = useState(false)
  const { isRecording, chunkCount, interimText, logs, error, startRecording, stopRecording } =
    useSpeechRecorder(username)

  const savedCount = logs.filter((l) => l.type === 'success').length

  return (
    <div
      style={{
        position: 'fixed',
        left: 16,
        bottom: 16,
        width: 320,
        zIndex: 1000,
        borderRadius: 8,
        overflow: 'hidden',
        boxShadow: '0 4px 24px rgba(0,0,0,0.4)',
      }}
    >
      <div
        style={{
          height: 40,
          background: '#1a1a2e',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '0 12px',
          cursor: 'pointer',
          userSelect: 'none',
        }}
        onClick={() => setCollapsed((c) => !c)}
      >
        <span style={{ color: '#e0e0e0', fontSize: 14, fontWeight: 600 }}>
          Transcription
          {collapsed && (
            <span style={{ marginLeft: 8, fontSize: 12, color: '#aaa' }}>
              {savedCount} saved · {isRecording ? 'recording' : 'stopped'}
            </span>
          )}
        </span>
        <button
          type="button"
          style={{
            background: 'none',
            border: 'none',
            color: '#e0e0e0',
            cursor: 'pointer',
            fontSize: 16,
            padding: 0,
            lineHeight: 1,
          }}
          aria-label={collapsed ? 'Expand' : 'Collapse'}
        >
          {collapsed ? '▲' : '▼'}
        </button>
      </div>

      {!collapsed && (
        <div
          style={{
            height: 320,
            background: '#12121f',
            display: 'flex',
            flexDirection: 'column',
            padding: 12,
            gap: 8,
            overflowY: 'hidden',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <RecordButton
              isRecording={isRecording}
              onClick={isRecording ? () => void stopRecording() : startRecording}
            />
            <span style={{ color: '#ccc', fontSize: 13 }}>
              {isRecording ? `Recording… chunk ${chunkCount}` : 'Stopped.'}
            </span>
          </div>

          <div style={{ color: '#888', fontSize: 12 }}>
            Saved: {savedCount} · Attempt #{chunkCount} · Lang: en-US
          </div>

          {error && (
            <div style={{ color: '#ff6b6b', fontSize: 12, wordBreak: 'break-word' }}>{error}</div>
          )}

          <div style={{ flex: 1, overflow: 'auto' }}>
            <LiveLog logs={logs} interimText={interimText} />
          </div>
        </div>
      )}
    </div>
  )
}
