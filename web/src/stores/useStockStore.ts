import { create } from 'zustand'
import type { StockPick, SelectionResponse } from '../types'
import { runSelection, getSelectionResult } from '../services/api'

interface StockState {
  loading: boolean
  taskId: string | null
  response: SelectionResponse | null
  picks: StockPick[]
  error: string | null

  startSelection: (universe: string) => Promise<void>
  fetchResult: (taskId: string) => Promise<void>
  clearError: () => void
}

export const useStockStore = create<StockState>((set) => ({
  loading: false,
  taskId: null,
  response: null,
  picks: [],
  error: null,

  startSelection: async (universe: string) => {
    set({ loading: true, error: null })
    try {
      const res = await runSelection({ universe: universe as any })
      set({ taskId: res.task_id, response: res, picks: res.picks })
    } catch (e: any) {
      set({ error: e.message })
    } finally {
      set({ loading: false })
    }
  },

  fetchResult: async (taskId: string) => {
    set({ loading: true, error: null })
    try {
      const res = await getSelectionResult(taskId)
      set({ taskId, response: res, picks: res.picks })
    } catch (e: any) {
      set({ error: e.message })
    } finally {
      set({ loading: false })
    }
  },

  clearError: () => set({ error: null }),
}))
