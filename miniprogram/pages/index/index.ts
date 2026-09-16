// 首页：附近任务 + 为我推荐（顺路匹配）
import { api, TaskItem } from '../../services/api'

Page({
  data: {
    tasks: [] as TaskItem[],
    recommended: [] as TaskItem[],
    tab: 'nearby' as 'nearby' | 'foryou',
    loading: true,
  },

  onShow() {
    this.loadTasks()
  },

  async loadTasks() {
    this.setData({ loading: true })
    try {
      const tasks = await api.listTasks('PENDING')
      this.setData({ tasks })
      try {
        const recommended = await api.recommendForMe()
        this.setData({ recommended })
      } catch {
        this.setData({ recommended: [] }) // 未登记日常路线时静默降级
      }
    } finally {
      this.setData({ loading: false })
    }
  },

  switchTab(e: WechatMiniprogram.TouchEvent) {
    this.setData({ tab: e.currentTarget.dataset.tab })
  },

  goDetail(e: WechatMiniprogram.TouchEvent) {
    const id = e.currentTarget.dataset.id
    wx.navigateTo({ url: `/pages/task-detail/task-detail?id=${id}` })
  },

  matchClass(percent?: number | null): string {
    if (!percent && percent !== 0) return ''
    if (percent >= 85) return 'match-high'
    if (percent >= 60) return 'match-mid'
    return 'match-low'
  },
})
