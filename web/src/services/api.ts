import axios from 'axios'
import type {
  SelectionRequest,
  SelectionResponse,
  BacktestRequest,
  BacktestResponse,
  Universe,
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

// --- WebSocket ---

export const createAgentWebSocket = (taskId: string): WebSocket => {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  return new WebSocket(`${protocol}//${window.location.host}/ws/agent/${taskId}`)
}
