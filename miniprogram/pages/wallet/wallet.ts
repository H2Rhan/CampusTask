// 钱包：余额 / 冻结 / 充值（Demo 虚拟充值）
import { api } from '../../services/api'

Page({
  data: {
    wallet: { balance: 0, frozen: 0 },
    amount: '',
  },

  onShow() {
    this.load()
  },

  async load() {
    const wallet = await api.wallet()
    this.setData({ wallet })
  },

  onAmount(e: WechatMiniprogram.Input) {
    this.setData({ amount: e.detail.value })
  },

  quickAmount(e: WechatMiniprogram.TouchEvent) {
    this.setData({ amount: e.currentTarget.dataset.value })
  },

  async recharge() {
    const amount = parseFloat(this.data.amount)
    if (!(amount > 0)) {
      wx.showToast({ title: '请输入充值金额', icon: 'none' })
      return
    }
    await api.recharge(amount)
    wx.showToast({ title: '充值成功', icon: 'success' })
    this.setData({ amount: '' })
    this.load()
  },
})
