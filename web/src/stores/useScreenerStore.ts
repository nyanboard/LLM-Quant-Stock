import { create } from 'zustand'
import type { ScreeningResultResponse, ScreeningSummary, ScreeningStats } from '../types'
import {
  triggerScreening,
  getScreeningResult,
  getScreeningStats,
  getScreeningHistory,
} from '../services/api'

interface ScreenerState {
  loading: boolean
  result: ScreeningResultResponse | null
  stats: ScreeningStats | null
  history: ScreeningSummary[]
  error: string | null

  runScreening: (universe: string) => Promise<void>
  fetchResult: (screeningId?: number) => Promise<void>
  fetchStats: () => Promise<void>
  fetchHistory: (limit?: number) => Promise<void>
  clearError: () => void
}

export const useScreenerStore = create<ScreenerState>((set) => ({
  loading: false,
  result: null,
  stats: null,
  history: [],
  error: null,

  runScreening: async (universe: string) => {
    set({ loading: true, error: null })
    try {
      const res = await triggerScreening({ universe: universe as ScreeningResultResponse['universe'] & 'hs300' })
      set({ result: res })
      // 后台任务启动后轮询结果
      if (res.status === 'running') {
        const pollInterval = setInterval(async () => {
          try {
            const latest = await getScreeningResult()
            if (latest.status === 'completed' || latest.status === 'failed') {
              set({ result: latest, loading: false })
              clearInterval(pollInterval)
            }
          } catch {
            clearInterval(pollInterval)
            set({ loading: false })
          }
        }, 2000)
        // 最多轮询 60 秒
        setTimeout(() => clearInterval(pollInterval), 60000)
      } else {
        set({ loading: false })
      }
    } catch (e: any) {
      set({ error: e.message, loading: false })
    }
  },

  fetchResult: async (screeningId?: number) => {
    set({ loading: true, error: null })
    try {
      const res = await getScreeningResult(screeningId)
      set({ result: res })
    } catch {
      // 404 表示暂无数据，静默处理
      set({ result: null })
    } finally {
      set({ loading: false })
    }
  },

  fetchStats: async () => {
    try {
      const stats = await getScreeningStats()
      set({ stats })
    } catch {
      // 暂无统计数据
    }
  },

  fetchHistory: async (limit = 10) => {
    set({ error: null })
    try {
      const history = await getScreeningHistory(limit)
      set({ history })
    } catch (e: any) {
      set({ error: e.message })
    }
  },

  clearError: () => set({ error: null }),
}))
