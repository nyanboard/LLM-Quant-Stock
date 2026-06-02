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

// ── 数据同步（metrics）相关 ──

// 同步请求
export interface SyncRequest {
  universe?: 'hs300' | 'zz500' | 'zz1000' | 'sza'
}

// 同步触发响应
export interface SyncResponse {
  sync_id: string
  status: 'running' | 'completed' | 'failed'
  universe: string
}

// 同步状态
export interface SyncStatus {
  status: 'idle' | 'running' | 'no_data'
  total_count: number
  last_synced_at: number | null
  last_synced_at_str: string | null
}

// 单只股票指标（stock_metrics 宽表一行）
export interface MetricsItem {
  symbol: string
  name?: string
  industry?: string
  market_cap?: number
  pe?: number
  pb?: number
  roe?: number
  debt_ratio?: number
  revenue?: number
  operating_cashflow?: number
  is_st?: number
  is_suspended?: number
  is_limit_up?: number
  is_limit_down?: number
  price?: number
  turnover_rate?: number
  avg_amount?: number
  synced_at?: number
}

// 指标查询响应
export interface MetricsQueryResponse {
  total: number
  items: MetricsItem[]
}
