interface AgentCursorProps {
  active: boolean
}

export function AgentCursor({ active }: AgentCursorProps) {
  return (
    <div className={`agent-cursor ${active ? 'active' : ''}`} aria-live="polite">
      <span className="agent-dot" aria-hidden="true" />
    </div>
  )
}
