import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  Tldraw,
  createShapeId,
  toRichText,
  type Editor,
  useValue,
  type TLShapeId,
  type TLShapePartial,
} from 'tldraw'
import { useSyncDemo } from '@tldraw/sync'
import { useOthers, useUpdateMyPresence } from '@liveblocks/react'
import { AgentCursor } from './AgentCursor.tsx'
import { useAgentBridge } from './useAgentBridge.ts'
import { sendToBackend, updateCursorPosition, getCursorPosition } from './agentSocket.ts'
import type {
  AddImageParams,
  AddSectionParams,
  AddStickyParams,
  AgentAction,
  DrawArrowParams,
  GroupStickiesParams,
  SuggestParams,
} from './types.ts'

const BACKEND_HTTP = import.meta.env.VITE_BACKEND_URL?.trim() || 'http://localhost:8000'

interface CanvasProps {
  registerEditor: (editor: Editor) => void
  username: string
}

const NOTE_COLOR_MAP = {
  yellow: 'yellow',
  blue: 'light-blue',
  green: 'light-green',
  red: 'red',
  purple: 'violet',
  orange: 'orange',
} as const

const GROUP_COLOR_MAP = {
  gray: 'grey',
  blue: 'blue',
  green: 'green',
  purple: 'violet',
  amber: 'orange',
  red: 'red',
} as const

function tldrawNoteColor(color: keyof typeof NOTE_COLOR_MAP) {
  return NOTE_COLOR_MAP[color] ?? 'yellow'
}

function tldrawGroupColor(color: keyof typeof GROUP_COLOR_MAP) {
  return GROUP_COLOR_MAP[color] ?? 'grey'
}

function execAddSticky(editor: Editor, p: AddStickyParams) {
  const id = createShapeId()
  const mappedColor = tldrawNoteColor(p.color)
  console.log('[execAddSticky] input params:', p)
  console.log('[execAddSticky] tldraw shape:', { id, type: 'geo', x: p.x, y: p.y, props: { geo: 'rectangle', w: 220, h: 140, color: mappedColor, fill: 'solid', richText: toRichText(p.text), align: 'start', verticalAlign: 'start', size: 'm', dash: 'draw' } })
  try {
    editor.createShape({
      id,
      type: 'geo',
      x: p.x,
      y: p.y,
      props: {
        geo: 'rectangle',
        w: 220,
        h: 140,
        color: mappedColor,
        fill: 'solid',
        richText: toRichText(p.text),
        align: 'start',
        verticalAlign: 'start',
        size: 's',
        dash: 'draw',
      },
      meta: { author: 'claude', requestedAuthor: p.author },
    } as TLShapePartial)
  } catch (err) {
    console.error('[execAddSticky] tldraw createShape failed. params:', p, 'error:', err)
  }
  return id
}

function execGroupStickies(editor: Editor, p: GroupStickiesParams) {
  const targetShapes = p.sticky_ids
    .map((id) => editor.getShape(id as TLShapeId))
    .filter((shape): shape is NonNullable<typeof shape> => Boolean(shape))

  if (!targetShapes.length) {
    return null
  }

  const bounds = editor.getShapePageBounds(targetShapes[0])
  if (!bounds) {
    return null
  }

  let minX = bounds.minX
  let minY = bounds.minY
  let maxX = bounds.maxX
  let maxY = bounds.maxY

  for (const shape of targetShapes.slice(1)) {
    const next = editor.getShapePageBounds(shape)
    if (!next) {
      continue
    }
    minX = Math.min(minX, next.minX)
    minY = Math.min(minY, next.minY)
    maxX = Math.max(maxX, next.maxX)
    maxY = Math.max(maxY, next.maxY)
  }

  const id = createShapeId()
  editor.createShape({
    id,
    type: 'geo',
    x: minX - 24,
    y: minY - 48,
    props: {
      geo: 'rectangle',
      w: maxX - minX + 48,
      h: maxY - minY + 72,
      color: tldrawGroupColor(p.color),
      fill: 'semi',
      richText: toRichText(p.label ?? ''),
      align: 'start',
      verticalAlign: 'start',
      size: 's',
      dash: 'dashed',
    },
    meta: { author: 'claude' },
  } as TLShapePartial)

  return id
}

function execAddSection(editor: Editor, p: AddSectionParams) {
  const id = createShapeId()
  editor.createShape({
    id,
    type: 'geo',
    x: p.x,
    y: p.y,
    props: {
      geo: 'rectangle',
      w: p.width,
      h: p.height,
      color: tldrawGroupColor(p.color),
      fill: 'none',
      richText: toRichText(p.title),
      align: 'start',
      verticalAlign: 'start',
      size: 'm',
      dash: 'solid',
    },
    meta: { author: 'claude' },
  } as TLShapePartial)
  return id
}

function execAddImage(editor: Editor, p: AddImageParams) {
  const id = createShapeId()
  const caption = p.caption?.trim() ? `\n${p.caption.trim()}` : ''
  editor.createShape({
    id,
    type: 'geo',
    x: p.x,
    y: p.y,
    props: {
      geo: 'rectangle',
      w: p.width ?? 280,
      h: 160,
      richText: toRichText(`[image] ${p.prompt}${caption}`),
      color: 'light-blue',
      align: 'start',
      verticalAlign: 'start',
      fill: 'solid',
      size: 'm',
      dash: 'solid',
    },
    meta: { author: 'claude', placeholder: true, requestedWidth: p.width },
  } as TLShapePartial)
  return id
}

function execDrawArrow(editor: Editor, p: DrawArrowParams) {
  const fromShape = editor.getShape(p.from_id as TLShapeId)
  const toShape = editor.getShape(p.to_id as TLShapeId)
  if (!fromShape || !toShape) {
    return null
  }

  const fromBounds = editor.getShapePageBounds(fromShape)
  const toBounds = editor.getShapePageBounds(toShape)
  if (!fromBounds || !toBounds) {
    return null
  }

  const id = createShapeId()
  editor.createShape({
    id,
    type: 'arrow',
    x: fromBounds.midX,
    y: fromBounds.midY,
    props: {
      richText: toRichText(p.label ?? ''),
      color: 'black',
      dash: p.style === 'dashed' ? 'dashed' : 'solid',
      start: {
        x: 0,
        y: 0,
      },
      end: {
        x: toBounds.midX - fromBounds.midX,
        y: toBounds.midY - fromBounds.midY,
      },
    },
    meta: { author: 'claude' },
  } as TLShapePartial)

  return id
}

function execSuggest(params: SuggestParams, setSuggestion: (value: SuggestParams | null) => void) {
  setSuggestion(params)
}

function execApprovedSuggestion(editor: Editor, suggestion: SuggestParams) {
  switch (suggestion.action) {
    case 'add_sticky':
      execAddSticky(editor, suggestion.action_params as AddStickyParams)
      break
    case 'group_stickies':
      execGroupStickies(editor, suggestion.action_params as GroupStickiesParams)
      break
    case 'add_section':
      execAddSection(editor, suggestion.action_params as AddSectionParams)
      break
    case 'add_image':
      execAddImage(editor, suggestion.action_params as AddImageParams)
      break
    case 'draw_arrow':
      execDrawArrow(editor, suggestion.action_params as DrawArrowParams)
      break
  }
}

export function Canvas({ registerEditor, username }: CanvasProps) {
  const rootRef = useRef<HTMLDivElement | null>(null)
  const store = useSyncDemo({ roomId: import.meta.env.VITE_ROOM_ID ?? 'hackathon-room' })
  const others = useOthers()
  const updateMyPresence = useUpdateMyPresence()
  const localUserName = username
  const localUserColor = useMemo(() => {
    let hash = 0
    for (let i = 0; i < username.length; i++) {
      hash = username.charCodeAt(i) + ((hash << 5) - hash)
    }
    return `hsl(${Math.abs(hash) % 360}, 75%, 48%)`
  }, [username])
  const [editor, setEditor] = useState<Editor | null>(null)
  const [isThinking, setIsThinking] = useState(false)
  const shapeUpdateTimers = useRef<Map<string, number>>(new Map())
  const [suggestion, setSuggestion] = useState<SuggestParams | null>(null)
  const [exportSummary, setExportSummary] = useState<string | null>(null)
  const [isExporting, setIsExporting] = useState(false)

  const handleExport = async () => {
    if (!editor) return
    setIsExporting(true)
    try {
      const shapes = editor.getCurrentPageShapes().map((s) => ({
        id: s.id,
        type: s.type,
        x: s.x,
        y: s.y,
        props: s.props,
        meta: s.meta,
      }))
      const res = await fetch(`${BACKEND_HTTP}/export`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ shapes, users: username }),
      })
      const data = await res.json()
      setExportSummary(data.summary ?? 'No summary generated.')
    } catch (e) {
      setExportSummary('Export failed. Is the backend running?')
    } finally {
      setIsExporting(false)
    }
  }

  useEffect(() => {
    updateMyPresence({
      userName: localUserName,
      userColor: localUserColor,
    })
  }, [localUserColor, localUserName, updateMyPresence])

  const executeAction = useCallback(
    (action: AgentAction) => {
      if (!editor) {
        return
      }

      switch (action.tool) {
        case 'add_sticky':
          execAddSticky(editor, action.params)
          break
        case 'group_stickies':
          execGroupStickies(editor, action.params)
          break
        case 'add_section':
          execAddSection(editor, action.params)
          break
        case 'add_image':
          execAddImage(editor, action.params)
          break
        case 'draw_arrow':
          execDrawArrow(editor, action.params)
          break
        case 'suggest':
          execSuggest(action.params, setSuggestion)
          break
      }
    },
    [editor],
  )

  useEffect(() => {
    ; (window as Window & { executeAction?: (action: AgentAction) => void }).executeAction =
      executeAction
    return () => {
      delete (window as Window & { executeAction?: (action: AgentAction) => void }).executeAction
    }
  }, [executeAction])

  useAgentBridge({ executeAction, setIsThinking })

  // Stream shape-creation events to the Python backend with user attribution
  useEffect(() => {
    if (!editor) return
    const cleanup = editor.store.listen(
      (entry) => {
        for (const record of Object.values(entry.changes.added)) {
          if (record.typeName !== 'shape') continue
          const shape = record as unknown as {
            id: string
            type: string
            x: number
            y: number
            props: Record<string, unknown>
            meta: Record<string, unknown>
          }
          // Skip shapes placed by the AI agent
          if (shape.meta?.author === 'claude') continue
          const cursor = getCursorPosition()
          sendToBackend({
            event: 'shape_created',
            shape: { id: shape.id, type: shape.type, x: shape.x, y: shape.y, props: shape.props },
            user: username,
            timestamp: new Date().toISOString(),
            cursorX: cursor.x,
            cursorY: cursor.y,
          })
        }

        for (const [, [, record]] of Object.entries(entry.changes.updated)) {
          if (record.typeName !== 'shape') continue
          const shape = record as unknown as {
            id: string
            type: string
            x: number
            y: number
            props: Record<string, unknown>
            meta: Record<string, unknown>
          }
          if (shape.meta?.author === 'claude') continue
          const existing = shapeUpdateTimers.current.get(shape.id)
          if (existing !== undefined) window.clearTimeout(existing)
          const timer = window.setTimeout(() => {
            shapeUpdateTimers.current.delete(shape.id)
            sendToBackend({
              event: 'shape_updated',
              shape: { id: shape.id, type: shape.type, x: shape.x, y: shape.y, props: shape.props },
              user: username,
              timestamp: new Date().toISOString(),
            })
          }, 800)
          shapeUpdateTimers.current.set(shape.id, timer)
        }
      },
      { source: 'user', scope: 'document' },
    )
    return cleanup
  }, [editor, sendToBackend, username])

  const collaboratorCount = useMemo(() => others.length + 1, [others.length])

  const collaboratorCursors = useMemo(() => {
    return others
      .map((user) => {
        const presence = user.presence as
          | {
            cursor?: { x: number; y: number }
            userName?: string
            userColor?: string
          }
          | null
        if (!presence?.cursor) {
          return null
        }
        return {
          id: user.connectionId,
          x: presence.cursor.x,
          y: presence.cursor.y,
          userName: presence.userName ?? `${user.connectionId}`,
          userColor: presence.userColor ?? '#2a7fff',
        }
      })
      .filter((cursor): cursor is NonNullable<typeof cursor> => Boolean(cursor))
  }, [others])

  const activeUsers = useMemo(() => {
    const remoteUsers = others.map((user) => {
      const presence = user.presence as { userName?: string; userColor?: string } | null
      return {
        id: `remote-${user.connectionId}`,
        userName: presence?.userName ?? `${user.connectionId}`,
        userColor: presence?.userColor ?? '#7f8ca3',
      }
    })

    return [{ id: 'self', userName: localUserName, userColor: localUserColor }, ...remoteUsers]
  }, [localUserColor, localUserName, others])

  const selectedShapeBadges = useValue(
    'selected-shape-badges',
    () => {
      if (!editor) {
        return []
      }

      return editor
        .getSelectedShapeIds()
        .map((shapeId) => {
          const shape = editor.getShape(shapeId)
          if (!shape) {
            return null
          }

          const bounds = editor.getShapePageBounds(shape)
          if (!bounds) {
            return null
          }

          const viewportPoint = editor.pageToViewport({ x: bounds.maxX, y: bounds.maxY })
          return {
            id: shapeId,
            x: viewportPoint.x + 8,
            y: viewportPoint.y + 8,
          }
        })
        .filter((badge): badge is NonNullable<typeof badge> => Boolean(badge))
    },
    [editor],
  )

  return (
    <div
      ref={rootRef}
      className="canvas-root"
      onPointerMove={(event) => {
        const rect = rootRef.current?.getBoundingClientRect()
        if (!rect) {
          return
        }
        const viewportX = event.clientX - rect.left
        const viewportY = event.clientY - rect.top
        updateMyPresence({ cursor: { x: viewportX, y: viewportY } })
        if (editor) {
          const page = editor.screenToPage({ x: viewportX, y: viewportY })
          updateCursorPosition(page)
        }
      }}
      onPointerLeave={() => {
        updateMyPresence({ cursor: null })
      }}
    >
      <div className="canvas-meta">
        <span>{collaboratorCount} collaborators</span>
        {suggestion ? <span className="suggestion-pill">Suggestion ready</span> : null}
        <button type="button" className="export-btn" onClick={handleExport} disabled={isExporting}>
          {isExporting ? 'Exporting…' : 'Export Summary'}
        </button>
      </div>
      <div className="user-list" aria-label="Connected users">
        <h3>Users</h3>
        <ul>
          {activeUsers.map((user) => (
            <li key={user.id}>
              <span className="user-swatch" style={{ background: user.userColor }} aria-hidden="true" />
              <span>{user.userName}</span>
            </li>
          ))}
        </ul>
      </div>
      {collaboratorCursors.map((cursor) => (
        <div
          key={cursor.id}
          className="presence-cursor"
          style={{ transform: `translate(${cursor.x}px, ${cursor.y}px)` }}
        >
          <span className="presence-dot" style={{ background: cursor.userColor }} aria-hidden="true" />
          <span className="presence-label">{cursor.userName}</span>
        </div>
      ))}
      {selectedShapeBadges.map((badge) => (
        <div
          key={badge.id}
          className="shape-owner-tag"
          style={{ transform: `translate(${badge.x}px, ${badge.y}px)` }}
        >
          {localUserName}
        </div>
      ))}
      <AgentCursor active={isThinking} />
      <Tldraw
        store={store}
        onMount={(mountedEditor) => {
          setEditor(mountedEditor)
          registerEditor(mountedEditor)
          mountedEditor.selectAll()
          mountedEditor.deleteShapes(mountedEditor.getSelectedShapeIds())
        }}
      />
      {suggestion ? (
        <div className="suggestion-card" role="status" aria-live="polite">
          <strong>Suggestion</strong>
          <p>{suggestion.reason}</p>
          <div className="suggestion-actions">
            <button
              type="button"
              onClick={() => {
                if (editor) {
                  execApprovedSuggestion(editor, suggestion)
                }
                setSuggestion(null)
              }}
            >
              Approve
            </button>
            <button type="button" onClick={() => setSuggestion(null)}>
              Dismiss
            </button>
          </div>
        </div>
      ) : null}
      {exportSummary ? (
        <div className="export-modal" role="dialog" aria-modal="true" aria-label="Canvas Export Summary">
          <div className="export-modal-inner">
            <div className="export-modal-header">
              <strong>Canvas Summary</strong>
              <button type="button" onClick={() => setExportSummary(null)}>✕</button>
            </div>
            <pre className="export-modal-body">{exportSummary}</pre>
            <div className="export-modal-footer">
              <button
                type="button"
                onClick={() => {
                  const blob = new Blob([exportSummary], { type: 'text/markdown' })
                  const url = URL.createObjectURL(blob)
                  const a = document.createElement('a')
                  a.href = url
                  a.download = 'canvas-summary.md'
                  a.click()
                  URL.revokeObjectURL(url)
                }}
              >
                Download .md
              </button>
              <button type="button" onClick={() => setExportSummary(null)}>Close</button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  )
}
