import axios from 'axios'
import type {
  SelectionRequest,
  SelectionResponse,
  BacktestRequest,
  BacktestResponse,
  Universe,
  ScreeningRequest,
  ScreeningResultResponse,
  ScreeningSummary,
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

// --- 预筛 ---

export const triggerScreening = async (req: ScreeningRequest): Promise<ScreeningResultResponse> => {
  const { data } = await api.post('/screener/run', req)
  return data
}

export const getScreeningResult = async (screeningId?: number): Promise<ScreeningResultResponse> => {
  const params = screeningId === undefined ? {} : { screening_id: screeningId }
  const { data } = await api.get('/screener/result', { params })
  return data
}

export const getScreeningStats = async (): Promise<ScreeningResultResponse['stats']> => {
  const { data } = await api.get('/screener/stats')
  return data
}

export const getScreeningHistory = async (limit = 10): Promise<ScreeningSummary[]> => {
  const { data } = await api.get('/screener/history', { params: { limit } })
  return data
}

// --- WebSocket ---

export const createAgentWebSocket = (taskId: string): WebSocket => {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  return new WebSocket(`${protocol}//${window.location.host}/ws/agent/${taskId}`)
}
