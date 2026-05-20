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

// ── 预筛相关 ──

// 预筛请求
export interface ScreeningRequest {
  universe?: 'hs300' | 'zz500' | 'zz1000' | 'sza'
}

// 预筛单只股票
export interface ScreeningStock {
  symbol: string
  name?: string
  passed: number
  exclusion_reasons?: string[]
  market_cap?: number
  pe?: number
  pb?: number
  roe?: number
  price?: number
}

// 预筛统计
export interface ScreeningStats {
  total: number
  passed_count: number
  excluded_count: number
  dimension_breakdown: Record<string, number>
}

// 预筛结果响应
export interface ScreeningResultResponse {
  screening_id: number | null
  universe: string
  status: 'running' | 'completed' | 'failed'
  passed: ScreeningStock[]
  excluded: ScreeningStock[]
  stats: ScreeningStats
}

// 预筛历史摘要
export interface ScreeningSummary {
  screening_id: number
  pool_id?: number
  universe: string
  total_count: number
  passed_count: number
  excluded_count: number
  created_at: number
}
