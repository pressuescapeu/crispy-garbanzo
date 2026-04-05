import { useEffect } from 'react'
import type { AgentAction, WsIncomingMessage } from './types.ts'
import { initAgentSocket } from './agentSocket.ts'

interface AgentBridgeConfig {
  executeAction: (action: AgentAction) => void
  setIsThinking: (value: boolean) => void
}

export function useAgentBridge({ executeAction, setIsThinking }: AgentBridgeConfig) {
  useEffect(() => {
    const ws = initAgentSocket()

    ws.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data) as WsIncomingMessage
        console.log('[AgentBridge] received:', JSON.stringify(message, null, 2))
        if ('type' in message && message.type === 'claude_thinking') {
          setIsThinking(Boolean(message.value))
          return
        }
        if ('tool' in message) {
          executeAction(message)
        }
      } catch (err) {
        console.error('[AgentBridge] failed to parse message:', event.data, err)
      }
    }

    return () => {
      ws.close()
    }
  }, [executeAction, setIsThinking])
}
