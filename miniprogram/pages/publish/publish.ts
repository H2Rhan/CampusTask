// 发布页：AI 一句话发布 + 手动表单
import { api } from '../../services/api'

const TASK_TYPES = ['取送物品', '快递取送', '带餐', '文件资料', '代购', '校内办事', '物品归还', '其他']

Page({
  data: {
    sentence: '',
    parsing: false,
    parsed: false,
    form: {
      title: '',
      task_type: '取送物品',
      start: '',
      destination: '',
      reward: '',
      deadline: '',
      description: '',
    },
    types: TASK_TYPES,
    typeIndex: 0,
    missing: [] as string[],
    publishing: false,
  },

  onSentenceInput(e: WechatMiniprogram.Input) {
    this.setData({ sentence: e.detail.value })
  },

  // AI 一键解析
  async aiParse() {
    const text = this.data.sentence.trim()
    if (text.length < 2) {
      wx.showToast({ title: '先描述一下你的任务吧', icon: 'none' })
      return
    }
    this.setData({ parsing: true })
    try {
      const r = await api.aiParse(text)
      const typeIndex = Math.max(0, TASK_TYPES.indexOf(r.task_type))
      this.setData({
        parsed: true,
        typeIndex,
        missing: r.missing_fields,
        form: {
          title: r.title || '',
          task_type: r.task_type,
          start: r.start_name || '',
          destination: r.end_name || '',
          reward: r.reward ? String(r.reward) : '',
          deadline: r.deadline ? r.deadline.slice(11, 16) : '',
          description: text,
        },
      })
      if (r.missing_fields.length) {
        wx.showToast({ title: '请补充缺失信息', icon: 'none' })
      }
    } finally {
      this.setData({ parsing: false })
    }
  },

  onInput(e: WechatMiniprogram.Input) {
    const field = e.currentTarget.dataset.field
    this.setData({ [`form.${field}`]: e.detail.value })
  },

  onTypeChange(e: WechatMiniprogram.PickerChange) {
    const i = Number(e.detail.value)
    this.setData({ typeIndex: i, 'form.task_type': TASK_TYPES[i] })
  },

  onTimeChange(e: WechatMiniprogram.PickerChange) {
    this.setData({ 'form.deadline': e.detail.value })
  },

  async publish() {
    const f = this.data.form
    const reward = parseFloat(f.reward)
    if (!f.start || !f.destination || !(reward > 0)) {
      wx.showToast({ title: '起点、终点、悬赏为必填项', icon: 'none' })
      return
    }
    this.setData({ publishing: true })
    try {
      const task = await api.createTask({
        title: f.title,
        description: f.description,
        task_type: f.task_type,
        start: f.start,
        destination: f.destination,
        reward,
        raw_text: this.data.sentence,
      })
      wx.showToast({ title: '发布成功', icon: 'success' })
      setTimeout(() => {
        wx.redirectTo({ url: `/pages/task-detail/task-detail?id=${task.id}` })
      }, 600)
    } catch {
      /* toast 已在 api 层处理 */
    } finally {
      this.setData({ publishing: false })
    }
  },
})
