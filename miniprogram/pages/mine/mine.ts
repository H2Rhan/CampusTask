// 我的：信用档案 + 钱包入口 + 我的任务 + 日常路线登记
import { api, UserProfile, UserRouteItem, TaskItem } from '../../services/api'

Page({
  data: {
    user: null as UserProfile | null,
    wallet: { balance: 0, frozen: 0 },
    routes: [] as UserRouteItem[],
    myTasks: [] as TaskItem[],
    routeInput: '',
  },

  onShow() {
    this.load()
  },

  async load() {
    const app = getApp<IAppOption>()
    if (!app.globalData.token) {
      wx.redirectTo({ url: '/pages/login/login' })
      return
    }
    const [user, wallet, routes, myTasks] = await Promise.all([
      api.me(), api.wallet(), api.myRoutes(), api.myTasks('all'),
    ])
    this.setData({ user, wallet, routes, myTasks: myTasks.slice(0, 5) })
  },

  onRouteInput(e: WechatMiniprogram.Input) {
    this.setData({ routeInput: e.detail.value })
  },

  async addRoute() {
    // 输入格式：宿舍16斋,学二食堂,图书馆
    const waypoints = this.data.routeInput.split(/[,，、\s]+/).filter(Boolean)
    if (waypoints.length < 2) {
      wx.showToast({ title: '至少两个地点，用逗号分隔', icon: 'none' })
      return
    }
    await api.addRoute('日常路线', waypoints)
    this.setData({ routeInput: '' })
    wx.showToast({ title: '路线已登记', icon: 'success' })
    this.load()
  },

  goWallet() {
    wx.navigateTo({ url: '/pages/wallet/wallet' })
  },

  goDetail(e: WechatMiniprogram.TouchEvent) {
    wx.navigateTo({ url: `/pages/task-detail/task-detail?id=${e.currentTarget.dataset.id}` })
  },

  logout() {
    const app = getApp<IAppOption>()
    app.globalData.token = ''
    wx.removeStorageSync('token')
    wx.removeStorageSync('userId')
    wx.redirectTo({ url: '/pages/login/login' })
  },
})
