// 任务聊天室 WebSocket 封装（自动重连）
import { config } from '../utils/config'

export interface WsMessage {
  type: 'text' | 'quick' | 'system' | 'error'
  sender_id?: number
  content: string
  task_status?: string
}

export class TaskChatSocket {
  private taskId: number
  private token: string
  private onMessage: (msg: WsMessage) => void
  private closed = false

  constructor(taskId: number, token: string, onMessage: (msg: WsMessage) => void) {
    this.taskId = taskId
    this.token = token
    this.onMessage = onMessage
  }

  connect() {
    wx.connectSocket({
      url: `${config.wsUrl}/api/v1/ws/chat/${this.taskId}?token=${this.token}`,
      success: () => {
        wx.onSocketMessage((res) => {
          try {
            this.onMessage(JSON.parse(res.data as string) as WsMessage)
          } catch {
            /* ignore malformed frame */
          }
        })
        wx.onSocketClose(() => {
          if (!this.closed) {
            setTimeout(() => this.connect(), 3000) // 简单重连
          }
        })
      },
    })
  }

  sendText(content: string) {
    wx.sendSocketMessage({ data: JSON.stringify({ type: 'text', content }) })
  }

  sendQuick(action: string) {
    wx.sendSocketMessage({ data: JSON.stringify({ type: 'quick', action, content: action }) })
  }

  close() {
    this.closed = true
    wx.closeSocket()
  }
}
