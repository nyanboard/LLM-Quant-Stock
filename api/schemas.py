"""
Pydantic 数据模型 — API 请求/响应格式定义
"""
from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum


# --- 选股相关 ---

class Universe(str, Enum):
    hs300 = "hs300"
    zz500 = "zz500"
    zz1000 = "zz1000"
    sza = "sza"


class SelectionRequest(BaseModel):
    universe: Universe = Field(default=Universe.hs300, description="股票池")
    date: Optional[str] = Field(default=None, description="分析日期，默认今天")


class AgentSignal(BaseModel):
    agent: str = Field(description="Agent 名称")
    score: float = Field(ge=1, le=10, description="评分 1-10")
    signal: str = Field(description="bullish/bearish/neutral")
    confidence: float = Field(ge=0, le=1, description="信心度 0-1")
    reasoning: str = Field(description="分析理由")


class QuantMetrics(BaseModel):
    rsi_14: Optional[float] = None
    macd_signal: Optional[str] = None
    volume_ratio: Optional[float] = None
    patterns: list[str] = Field(default_factory=list)
    money_flow_net: Optional[float] = None


class StockPick(BaseModel):
    symbol: str = Field(description="股票代码")
    name: str = Field(description="股票名称")
    total_score: float = Field(description="综合评分")
    llm_score: float = Field(description="LLM 评分")
    quant_score: float = Field(description="量化评分")
    recommendation: str = Field(description="推荐理由")
    agent_signals: list[AgentSignal] = Field(default_factory=list)
    quant_metrics: Optional[QuantMetrics] = None


class SelectionResponse(BaseModel):
    task_id: str
    status: str = Field(description="running/completed/failed")
    universe: str
    picks: list[StockPick]


# --- 回测相关 ---

class BacktestRequest(BaseModel):
    strategy: str = Field(default="llm_quant", description="策略名称")
    start_date: str = Field(description="开始日期")
    end_date: str = Field(description="结束日期")
    universe: Universe = Field(default=Universe.hs300)
    initial_cash: float = Field(default=1_000_000, description="初始资金")


class EquityPoint(BaseModel):
    date: str
    value: float
    benchmark: float


class BacktestMetrics(BaseModel):
    total_return: Optional[float] = None
    annual_return: Optional[float] = None
    max_drawdown: Optional[float] = None
    sharpe_ratio: Optional[float] = None
    win_rate: Optional[float] = None
    avg_hold_days: Optional[float] = None
    excess_return: Optional[float] = None


class BacktestResponse(BaseModel):
    task_id: str
    status: str
    metrics: BacktestMetrics
    equity_curve: list[EquityPoint]


# --- 预筛相关 ---

class ScreenRequest(BaseModel):
    """预筛请求：指定股票池触发预筛"""
    universe: Universe = Field(default=Universe.hs300, description="股票池标识")


class ScreeningStockItem(BaseModel):
    """预筛结果中的单只股票信息"""
    symbol: str = Field(description="股票代码（纯数字格式）")
    name: Optional[str] = Field(default=None, description="股票名称")
    passed: int = Field(description="是否通过预筛（1=通过，0=被过滤）")
    exclusion_reasons: Optional[list[str]] = Field(default=None, description="被过滤的原因列表")
    market_cap: Optional[float] = Field(default=None, description="总市值（亿元）")
    pe: Optional[float] = Field(default=None, description="市盈率")
    pb: Optional[float] = Field(default=None, description="市净率")
    roe: Optional[float] = Field(default=None, description="净资产收益率（%）")
    price: Optional[float] = Field(default=None, description="当前价格（元）")


class ScreenStatsResponse(BaseModel):
    """预筛统计摘要"""
    total: int = Field(description="参与筛选的股票总数")
    passed_count: int = Field(description="通过预筛的股票数量")
    excluded_count: int = Field(description="被过滤的股票数量")
    dimension_breakdown: dict[str, int] = Field(
        default_factory=dict,
        description="各维度淘汰统计，如 {'ST': 15, '市值': 30}",
    )


class ScreenResultResponse(BaseModel):
    """预筛结果完整响应"""
    screening_id: Optional[int] = Field(description="预筛记录 ID")
    universe: str = Field(description="股票池标识")
    status: str = Field(description="状态: running/completed/failed")
    passed: list[ScreeningStockItem] = Field(default_factory=list, description="通过预筛的股票")
    excluded: list[ScreeningStockItem] = Field(default_factory=list, description="被过滤的股票")
    stats: ScreenStatsResponse = Field(description="统计摘要")


class ScreeningSummary(BaseModel):
    """预筛历史摘要（不含股票明细）"""
    screening_id: int
    pool_id: Optional[int] = None
    universe: str
    total_count: int
    passed_count: int
    excluded_count: int
    created_at: float = Field(description="创建时间（Unix timestamp）")
