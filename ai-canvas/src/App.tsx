import { useMemo, useState } from 'react'
import { LiveblocksProvider, RoomProvider } from '@liveblocks/react'
import 'tldraw/tldraw.css'
import './App.css'
import { Canvas } from './Canvas.tsx'
import { useCanvasSnapshot } from './useCanvasSnapshot.ts'
import { TranscriptPanel } from './components/TranscriptPanel'
import { VoicePanel } from './components/VoicePanel'
import { UsernameModal } from './components/UsernameModal'

const PUBLIC_KEY = import.meta.env.VITE_LIVEBLOCKS_KEY ?? ''
const ROOM_ID = import.meta.env.VITE_ROOM_ID ?? 'hackathon-room'

let getCanvasSnapshotImpl: () => unknown = () => null

export function getCanvasSnapshot() {
  return getCanvasSnapshotImpl()
}

function App() {
  const { registerEditor, getCanvasSnapshot: getCanvasSnapshotFromHook } = useCanvasSnapshot()
  const canUseLiveblocks = useMemo(() => PUBLIC_KEY.startsWith('pk_'), [])

  const [username, setUsername] = useState<string>(
    () => localStorage.getItem('canvas_username') ?? ''
  )
  const showModal = !username

  const handleUsernameSubmit = (name: string) => {
    localStorage.setItem('canvas_username', name)
    setUsername(name)
  }

  getCanvasSnapshotImpl = getCanvasSnapshotFromHook

  if (!canUseLiveblocks) {
    return (
      <div className="missing-key">
        <h1>Liveblocks key missing</h1>
        <p>Set VITE_LIVEBLOCKS_KEY in your env file to enable multiplayer sync.</p>
      </div>
    )
  }

  return (
    <>
      {showModal && <UsernameModal onSubmit={handleUsernameSubmit} />}
      <LiveblocksProvider publicApiKey={PUBLIC_KEY}>
        <RoomProvider id={ROOM_ID}>
          <main className="app-shell">
            <section className="canvas-pane">
              <Canvas registerEditor={registerEditor} username={username} />
            </section>
          </main>
          <TranscriptPanel username={username} />
          <VoicePanel />
        </RoomProvider>
      </LiveblocksProvider>
    </>
  )
}

export default App