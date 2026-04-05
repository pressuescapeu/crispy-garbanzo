export type ToolName =
  | 'add_sticky'
  | 'group_stickies'
  | 'add_section'
  | 'add_image'
  | 'draw_arrow'
  | 'suggest'

export interface AddStickyParams {
  x: number
  y: number
  text: string
  color: 'yellow' | 'blue' | 'green' | 'red' | 'purple' | 'orange'
  author: 'claude' | string
}

export interface GroupStickiesParams {
  sticky_ids: string[]
  label: string
  color: 'gray' | 'blue' | 'green' | 'purple' | 'amber'
}

export interface AddSectionParams {
  x: number
  y: number
  width: number
  height: number
  title: string
  color: 'gray' | 'blue' | 'green' | 'purple' | 'amber' | 'red'
}

export interface AddImageParams {
  x: number
  y: number
  prompt: string
  width?: number
  caption?: string
}

export interface DrawArrowParams {
  from_id: string
  to_id: string
  label: string
  style?: 'solid' | 'dashed'
}

export interface SuggestParams {
  action: Exclude<ToolName, 'suggest'>
  action_params: object
  reason: string
}

export type AgentAction =
  | { tool: 'add_sticky'; params: AddStickyParams }
  | { tool: 'group_stickies'; params: GroupStickiesParams }
  | { tool: 'add_section'; params: AddSectionParams }
  | { tool: 'add_image'; params: AddImageParams }
  | { tool: 'draw_arrow'; params: DrawArrowParams }
  | { tool: 'suggest'; params: SuggestParams }

export interface ClaudeThinkingStatusMessage {
  type: 'claude_thinking'
  value: boolean
}

export type WsIncomingMessage = AgentAction | ClaudeThinkingStatusMessage

export interface LogEntry {
  id: number;
  timestamp: string;
  message: string;
  type: "info" | "success" | "error" | "warn";
}

export interface RecorderState {
  isRecording: boolean;
  chunkCount: number;
  currentInterim: string;
  logs: LogEntry[];
  error: string | null;
}
