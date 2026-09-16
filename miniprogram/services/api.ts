// REST API 封装：自动携带 token，统一错误提示
import { config } from '../utils/config'

const app = getApp<IAppOption>()

interface RequestOptions {
  method?: 'GET' | 'POST' | 'DELETE'
  data?: Record<string, unknown>
  query?: Record<string, string | number>
}

function buildUrl(path: string, query?: Record<string, string | number>): string {
  let url = `${config.baseUrl}/api/v1${path}`
  if (query) {
    const qs = Object.entries(query)
      .map(([k, v]) => `${k}=${encodeURIComponent(String(v))}`)
      .join('&')
    url += `?${qs}`
  }
  return url
}

export function request<T = unknown>(path: string, options: RequestOptions = {}): Promise<T> {
  return new Promise((resolve, reject) => {
    wx.request({
      url: buildUrl(path, options.query),
      method: options.method || 'GET',
      data: options.data,
      header: {
        'Content-Type': 'application/json',
        Authorization: app.globalData.token ? `Bearer ${app.globalData.token}` : '',
      },
      success(res) {
        if (res.statusCode >= 200 && res.statusCode < 300) {
          resolve(res.data as T)
        } else {
          const detail = (res.data as { detail?: string })?.detail || `请求失败 (${res.statusCode})`
          wx.showToast({ title: detail, icon: 'none' })
          reject(new Error(detail))
        }
      },
      fail(err) {
        wx.showToast({ title: '网络异常，请检查后端服务', icon: 'none' })
        reject(err)
      },
    })
  })
}

// ---- 具体接口 ----
export const api = {
  login: (student_no: string, password: string) =>
    request<{ access_token: string; user: UserProfile }>('/auth/login', { method: 'POST', data: { student_no, password } }),
  register: (data: Record<string, string>) =>
    request<{ access_token: string; user: UserProfile }>('/auth/register', { method: 'POST', data }),
  me: () => request<UserProfile>('/users/me'),
  listTasks: (status = 'PENDING') => request<TaskItem[]>('/tasks', { query: { status } }),
  myTasks: (role: 'all' | 'publisher' | 'accepter' = 'all') => request<TaskItem[]>('/tasks/mine', { query: { role } }),
  taskDetail: (id: number) => request<TaskItem>(`/tasks/${id}`),
  createTask: (data: Record<string, unknown>) => request<TaskItem>('/tasks', { method: 'POST', data }),
  acceptTask: (id: number) => request<TaskItem>(`/tasks/${id}/accept`, { method: 'POST' }),
  advanceTask: (id: number, action: string) => request<TaskItem>(`/tasks/${id}/advance`, { method: 'POST', data: { action } }),
  confirmTask: (id: number) => request<TaskItem>(`/tasks/${id}/confirm`, { method: 'POST' }),
  cancelTask: (id: number) => request<TaskItem>(`/tasks/${id}/cancel`, { method: 'POST' }),
  reviewTask: (id: number, rating: number, comment: string) =>
    request(`/tasks/${id}/review`, { method: 'POST', data: { rating, comment } }),
  arbitrate: (id: number, reason: string) =>
    request(`/tasks/${id}/arbitrate`, { method: 'POST', data: { reason } }),
  aiParse: (text: string) => request<AIParseResult>('/ai/parse', { method: 'POST', data: { text } }),
  recommendForMe: () => request<TaskItem[]>('/match/for-me'),
  myRoutes: () => request<UserRouteItem[]>('/users/me/routes'),
  addRoute: (name: string, waypoints: string[]) =>
    request<UserRouteItem>('/users/me/routes', { method: 'POST', data: { name, waypoints } }),
  wallet: () => request<WalletInfo>('/wallet/me'),
  recharge: (amount: number) => request<WalletInfo>('/wallet/recharge', { method: 'POST', data: { amount } }),
  messages: (taskId: number) => request<ChatMessageItem[]>(`/tasks/${taskId}/messages`),
}

// ---- 类型 ----
export interface UserProfile {
  id: number
  name: string
  college: string
  credit_score: number
  tasks_completed: number
  good_rate: number
  is_verified: boolean
}

export interface TaskItem {
  id: number
  publisher_id: number
  accepter_id: number | null
  title: string
  description: string
  task_type: string
  start_name: string
  end_name: string
  reward: number
  distance: number
  est_minutes: number
  status: string
  deadline: string | null
  match_percent?: number | null
  match_reason?: string | null
}

export interface AIParseResult {
  task_type: string
  title: string
  start_node: string | null
  start_name: string | null
  end_node: string | null
  end_name: string | null
  deadline: string | null
  reward: number | null
  confidence: number
  missing_fields: string[]
}

export interface UserRouteItem {
  id: number
  name: string
  waypoints: string[]
  waypoint_names: string[]
}

export interface WalletInfo {
  balance: number
  frozen: number
}

export interface ChatMessageItem {
  id: number
  sender_id: number | null
  msg_type: string
  content: string
  created_at: string
}
