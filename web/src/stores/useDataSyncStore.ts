import { create } from 'zustand'
import type { MetricsItem, SyncStatus } from '../types'
import { triggerSync, getSyncStatus, queryMetrics } from '../services/api'

interface DataSyncState {
  loading: boolean
  syncing: boolean
  metrics: MetricsItem[]
  total: number
  page: number
  pageSize: number
  syncStatus: SyncStatus | null
  error: string | null

  triggerSyncAction: (universe: string) => Promise<void>
  fetchSyncStatus: () => Promise<void>
  fetchMetrics: (page?: number, pageSize?: number) => Promise<void>
  clearError: () => void
}

export const useDataSyncStore = create<DataSyncState>((set, get) => ({
  loading: false,
  syncing: false,
  metrics: [],
  total: 0,
  page: 1,
  pageSize: 20,
  syncStatus: null,
  error: null,

  triggerSyncAction: async (universe: string) => {
    set({ syncing: true, error: null })
    try {
      await triggerSync({ universe: universe as any })
      // 轮询同步状态直到完成
      const poll = setInterval(async () => {
        try {
          const status = await getSyncStatus()
          set({ syncStatus: status })
          if (status.status !== 'running') {
            clearInterval(poll)
            set({ syncing: false })
            // 同步完成后刷新数据
            get().fetchMetrics()
          }
        } catch {
          clearInterval(poll)
          set({ syncing: false })
        }
      }, 3000)
      // 最多轮询 5 分钟
      setTimeout(() => clearInterval(poll), 300000)
    } catch (e: any) {
      set({ error: e.response?.data?.detail || e.message, syncing: false })
    }
  },

  fetchSyncStatus: async () => {
    try {
      const status = await getSyncStatus()
      set({ syncStatus: status })
    } catch {
      // 静默处理
    }
  },

  fetchMetrics: async (page?: number, pageSize?: number) => {
    set({ loading: true, error: null })
    const p = page ?? get().page
    const ps = pageSize ?? get().pageSize
    try {
      const res = await queryMetrics({ page: p, page_size: ps, is_st: 0, is_suspended: 0 })
      set({ metrics: res.items, total: res.total, page: p, pageSize: ps })
    } catch (e: any) {
      set({ error: e.message })
    } finally {
      set({ loading: false })
    }
  },

  clearError: () => set({ error: null }),
}))
