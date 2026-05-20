/**
 * API 类型定义
 */

// Agent 信号
export interface AgentSignal {
  agent: string
  score: number
  signal: 'bullish' | 'bearish' | 'neutral'
  confidence: number
  reasoning: string
}

// 量化指标
export interface QuantMetrics {
  rsi_14?: number
  macd_signal?: string
  volume_ratio?: number
  patterns?: string[]
  money_flow_net?: number
}

// 选出的股票
export interface StockPick {
  symbol: string
  name: string
  total_score: number
  llm_score: number
  quant_score: number
  recommendation: string
  agent_signals: AgentSignal[]
  quant_metrics?: QuantMetrics
}

// 选股响应
export interface SelectionResponse {
  task_id: string
  status: 'running' | 'completed' | 'failed'
  universe: string
  picks: StockPick[]
}

// 选股请求
export interface SelectionRequest {
  universe?: 'hs300' | 'zz500' | 'zz1000' | 'sza'
  date?: string
}

// 净值曲线点
export interface EquityPoint {
  date: string
  value: number
  benchmark: number
}

// 回测指标
export interface BacktestMetrics {
  total_return?: number
  annual_return?: number
  max_drawdown?: number
  sharpe_ratio?: number
  win_rate?: number
  avg_hold_days?: number
  excess_return?: number
}

// 回测响应
export interface BacktestResponse {
  task_id: string
  status: string
  metrics: BacktestMetrics
  equity_curve: EquityPoint[]
}

// 回测请求
export interface BacktestRequest {
  strategy?: string
  start_date: string
  end_date: string
  universe?: string
  initial_cash?: number
}

// 股票池
export interface Universe {
  id: string
  name: string
}
