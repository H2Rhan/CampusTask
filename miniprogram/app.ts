// CampusTask · 邻行 —— 校园智能互助任务平台
import { config } from './utils/config'

App({
  globalData: {
    token: '',
    userId: 0,
    baseUrl: config.baseUrl,
  },
  onLaunch() {
    const token = wx.getStorageSync('token')
    if (token) {
      this.globalData.token = token
      this.globalData.userId = wx.getStorageSync('userId') || 0
    }
  },
})
