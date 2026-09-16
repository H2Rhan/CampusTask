// 登录 / 注册（学号 + 密码；正式版接微信一键登录 + 校园统一身份认证）
import { api } from '../../services/api'

Page({
  data: {
    mode: 'login' as 'login' | 'register',
    student_no: '',
    password: '',
    name: '',
    college: '',
    loading: false,
  },

  switchMode() {
    this.setData({ mode: this.data.mode === 'login' ? 'register' : 'login' })
  },

  onInput(e: WechatMiniprogram.Input) {
    this.setData({ [e.currentTarget.dataset.field]: e.detail.value })
  },

  async submit() {
    const { mode, student_no, password, name, college } = this.data
    if (!student_no || !password || (mode === 'register' && !name)) {
      wx.showToast({ title: '请填写完整', icon: 'none' })
      return
    }
    this.setData({ loading: true })
    try {
      const res = mode === 'login'
        ? await api.login(student_no, password)
        : await api.register({ student_no, password, name, college })
      const app = getApp<IAppOption>()
      app.globalData.token = res.access_token
      app.globalData.userId = res.user.id
      wx.setStorageSync('token', res.access_token)
      wx.setStorageSync('userId', res.user.id)
      wx.switchTab({ url: '/pages/index/index' })
    } catch {
      /* toast 已在 api 层处理 */
    } finally {
      this.setData({ loading: false })
    }
  },
})
