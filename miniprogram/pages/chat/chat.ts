// 任务聊天室：WebSocket 实时收发 + 快捷操作按钮
import { api, ChatMessageItem } from '../../services/api'
import { TaskChatSocket, WsMessage } from '../../services/ws'

const QUICK_ACTIONS = [
  { action: 'arrive_pickup', label: '📍 到达取件点' },
  { action: 'pickup', label: '📦 已取到物品' },
  { action: 'deliver', label: '🚚 前往目的地' },
  { action: 'finish', label: '✅ 已送达' },
]

Page({
  data: {
    taskId: 0,
    messages: [] as Array<ChatMessageItem & { mine: boolean }>,
    input: '',
    quickActions: QUICK_ACTIONS,
    scrollId: '',
  },

  socket: null as TaskChatSocket | null,

  async onLoad(query: Record<string, string>) {
    const taskId = Number(query.id)
    this.setData({ taskId })
    const app = getApp<IAppOption>()
    const myId = app.globalData.userId

    const history = await api.messages(taskId)
    this.setData({
      messages: history.map((m) => ({ ...m, mine: m.sender_id === myId })),
      scrollId: `msg-${history.length ? history[history.length - 1].id : 0}`,
    })

    this.socket = new TaskChatSocket(taskId, app.globalData.token, (msg: WsMessage) => {
      if (msg.type === 'error') {
        wx.showToast({ title: msg.content, icon: 'none' })
        return
      }
      const list = this.data.messages
      const item = {
        id: Date.now(),
        sender_id: msg.sender_id ?? null,
        msg_type: msg.type,
        content: msg.content,
        created_at: '',
        mine: msg.sender_id === myId,
      }
      list.push(item)
      this.setData({ messages: list, scrollId: `msg-${item.id}` })
    })
    this.socket.connect()
  },

  onUnload() {
    this.socket?.close()
  },

  onInput(e: WechatMiniprogram.Input) {
    this.setData({ input: e.detail.value })
  },

  send() {
    const content = this.data.input.trim()
    if (!content) return
    this.socket?.sendText(content)
    this.setData({ input: '' })
  },

  sendQuick(e: WechatMiniprogram.TouchEvent) {
    this.socket?.sendQuick(e.currentTarget.dataset.action)
  },
})
