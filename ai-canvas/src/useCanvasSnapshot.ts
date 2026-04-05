import { useCallback, useRef } from 'react'
import { getSnapshot, type Editor } from 'tldraw'

// Read-only canvas access for AI context. NOT the sync mechanism.
export function useCanvasSnapshot() {
  const editorRef = useRef<Editor | null>(null)

  const registerEditor = useCallback((editor: Editor) => {
    editorRef.current = editor
  }, [])

  const getCanvasSnapshot = useCallback(() => {
    if (!editorRef.current) {
      return null
    }
    return getSnapshot(editorRef.current.store)
  }, [])

  const getVisibleShapes = useCallback(() => {
    return editorRef.current?.getCurrentPageShapes() ?? []
  }, [])

  return { registerEditor, getCanvasSnapshot, getVisibleShapes }
}
