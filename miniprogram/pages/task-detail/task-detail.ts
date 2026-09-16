// 任务详情：状态机驱动的操作按钮（接单 / 快捷推进 / 验收 / 取消 / 评价 / 仲裁）
import { api, TaskItem } from '../../services/api'

const STATUS_TEXT: Record<string, string> = {
  PENDING: '待接单', ACCEPTED: '已接单', IN_PROGRESS: '进行中',
  ARRIVED_PICKUP: '已到达取件点', PICKED_UP: '已取件', DELIVERING: '配送中',
  PENDING_CONFIRM: '待验收', COMPLETED: '已完成', SETTLED: '已结算',
  CANCELLED: '已取消', ARBITRATING: '仲裁中', CLOSED_BY_ARBITRATION: '仲裁关闭',
}

// 接单者在各状态的下一个快捷操作
const NEXT_ACTION: Record<string, { action: string; label: string }> = {
  ACCEPTED: { action: 'start', label: '🚶 开始执行' },
  IN_PROGRESS: { action: 'arrive_pickup', label: '📍 到达取件点' },
  ARRIVED_PICKUP: { action: 'pickup', label: '📦 已取到物品' },
  PICKED_UP: { action: 'deliver', label: '🚚 前往目的地' },
  DELIVERING: { action: 'finish', label: '✅ 已送达' },
}

Page({
  data: {
    task: null as TaskItem | null,
    statusText: '',
    isPublisher: false,
    isAccepter: false,
    nextAction: null as { action: string; label: string } | null,
    rating: 5,
    showReview: false,
    taskId: 0,
  },

  onLoad(query: Record<string, string>) {
    this.setData({ taskId: Number(query.id) })
  },

  onShow() {
    if (this.data.taskId) this.load()
  },

  async load() {
    const task = await api.taskDetail(this.data.taskId)
    const app = getApp<IAppOption>()
    const isPublisher = task.publisher_id === app.globalData.userId
    const isAccepter = task.accepter_id === app.globalData.userId
    this.setData({
      task,
      statusText: STATUS_TEXT[task.status] || task.status,
      isPublisher,
      isAccepter,
      nextAction: isAccepter ? NEXT_ACTION[task.status] || null : null,
    })
  },

  async accept() {
    await api.acceptTask(this.data.taskId)
    wx.showToast({ title: '接单成功', icon: 'success' })
    this.load()
  },

  async advance() {
    const next = this.data.nextAction
    if (!next) return
    await api.advanceTask(this.data.taskId, next.action)
    this.load()
  },

  async confirm() {
    const res = await wx.showModal({ title: '确认验收', content: '确认对方已完成任务？悬赏将立即结算。' })
    if (!res.confirm) return
    await api.confirmTask(this.data.taskId)
    this.setData({ showReview: true })
    this.load()
  },

  async cancel() {
    const res = await wx.showModal({ title: '取消任务', content: '取消后悬赏将退回。接单者中途取消会影响信用分。' })
    if (!res.confirm) return
    await api.cancelTask(this.data.taskId)
    this.load()
  },

  async arbitrate() {
    const res = await wx.showModal({
      title: '申请仲裁',
      content: '平台将冻结资金并介入审核双方证据。',
      editable: true,
      placeholderText: '请描述争议原因',
    })
    if (!res.confirm || !res.content) return
    await api.arbitrate(this.data.taskId, res.content)
    wx.showToast({ title: '已提交仲裁', icon: 'success' })
    this.load()
  },

  onRate(e: WechatMiniprogram.TouchEvent) {
    this.setData({ rating: Number(e.currentTarget.dataset.value) })
  },

  async submitReview(e: WechatMiniprogram.FormSubmit) {
    await api.reviewTask(this.data.taskId, this.data.rating, e.detail.value.comment || '')
    this.setData({ showReview: false })
    wx.showToast({ title: '评价成功', icon: 'success' })
  },

  goChat() {
    wx.navigateTo({ url: `/pages/chat/chat?id=${this.data.taskId}` })
  },
})
