import axios from 'axios'
import type {
  SelectionRequest,
  SelectionResponse,
  BacktestRequest,
  BacktestResponse,
  Universe,
  SyncRequest,
  SyncResponse,
  SyncStatus,
  MetricsQueryResponse,
} from '../types'

const api = axios.create({
  baseURL: '/api/v1',
  timeout: 60000,
})

// --- 选股 ---

export const runSelection = async (req: SelectionRequest): Promise<SelectionResponse> => {
  const { data } = await api.post('/selection', req)
  return data
}

export const getSelectionResult = async (taskId: string): Promise<SelectionResponse> => {
  const { data } = await api.get(`/selection/${taskId}`)
  return data
}

export const getStockDetail = async (taskId: string, symbol: string) => {
  const { data } = await api.get(`/selection/${taskId}/detail/${symbol}`)
  return data
}

// --- 回测 ---

export const runBacktest = async (req: BacktestRequest): Promise<BacktestResponse> => {
  const { data } = await api.post('/backtest', req)
  return data
}

export const getBacktestResult = async (taskId: string): Promise<BacktestResponse> => {
  const { data } = await api.get(`/backtest/${taskId}`)
  return data
}

// --- 配置 ---

export const getUniverses = async (): Promise<{ universes: Universe[] }> => {
  const { data } = await api.get('/config/universes')
  return data
}

// --- 数据同步（metrics）---

export const triggerSync = async (req: SyncRequest): Promise<SyncResponse> => {
  const { data } = await api.post('/metrics/sync', req)
  return data
}

export const getSyncStatus = async (): Promise<SyncStatus> => {
  const { data } = await api.get('/metrics/sync/status')
  return data
}

export const queryMetrics = async (params?: {
  page?: number
  page_size?: number
  pe_min?: number
  pe_max?: number
  roe_min?: number
  market_cap_min?: number
  is_st?: number
  is_suspended?: number
}): Promise<MetricsQueryResponse> => {
  const { data } = await api.get('/metrics/query', { params })
  return data
}

// --- WebSocket ---

export const createAgentWebSocket = (taskId: string): WebSocket => {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  return new WebSocket(`${protocol}//${window.location.host}/ws/agent/${taskId}`)
}
