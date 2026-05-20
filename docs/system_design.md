# LLM-Quant-Stock 系统设计方案

> 面向 A 股的 LLM 多Agent选股 + 量化二次筛选系统

---

## 一、系统定位

将 LLM 的定性分析能力（读财报、理解新闻、评估商业逻辑）与量化指标的精确筛选能力结合，构建三层层叠式选股系统：

```
股票池（如沪深300成分股）
        │
        ▼
┌──────────────────────────┐
│  预筛层：基础量化粗筛       │  ← 确定性规则快速排除，300只→50~100只
│  ST/市值/流动性/财务健康   │     减少 LLM 调用量 60~80%
└──────────────────────────┘
        │ 粗筛后候选池
        ▼
┌──────────────────────────┐
│  第一层：LLM 多Agent选股   │  ← 定性分析，从数十只缩减到个位数
│  （Fund Manager 输出名单）  │
└──────────────────────────┘
        │ 初选名单 + 评分
        ▼
┌──────────────────────────┐
│  第二层：量化指标二次筛选   │  ← 精确过滤，从数十只缩减到个位数
│  （技术指标 + 形态识别）     │
└──────────────────────────┘
        │ 最终标的
        ▼
   回测验证 → 输出报告
```

---

## 二、整体架构

```
llm_quant_stock/
├── config/                     # 配置中心
│   ├── settings.py             # 全局配置（LLM、数据源、策略参数）
│   ├── quant_rules.yaml        # 量化筛选规则（YAML可配置）
│   ├── secrets/                # API Key（受保护，不入库）
│   ├── api_keys/               # 数据源密钥（受保护，不入库）
│   └── prompts/                # Agent 提示词模板
│       ├── fundamental.md
│       ├── sentiment.md
│       ├── technical.md
│       ├── news.md
│       └── fund_manager.md
│
├── data/                       # 数据层
│   ├── datasource.py           # 统一数据接口（抽象层）
│   ├── akshare_source.py       # akshare 实现（实时行情、资金流、龙虎榜）
│   ├── baostock_source.py      # baostock 实现（历史K线、财报）
│   ├── cache.py                # 数据缓存（SQLite + TTL）+ stock_metrics 预筛指标表
│   └── sync.py                 # 预筛指标每日同步（批量拉取慢数据写入 SQLite）
│
├── agents/                     # LLM Agent 层
│   ├── base.py                 # BaseAgent 基类
│   ├── fundamental.py          # 基本面分析师（财报、估值）
│   ├── sentiment.py            # 情绪分析师（新闻、公告、社交媒体）
│   ├── technical.py            # 技术分析师（指标计算 + LLM解读）
│   ├── news.py                 # 新闻分析师（政策、行业动态）
│   ├── researcher.py           # 多空研究员（辩论机制）
│   └── fund_manager.py         # 基金经理（综合决策，输出初选名单）
│
├── quant/                      # 量化筛选层
│   ├── screener.py             # 预筛模块（基础量化粗筛，Agent之前）
│   ├── indicators.py           # 技术指标计算（TA-Lib封装）
│   ├── patterns.py             # K线形态识别
│   ├── filters.py              # 筛选规则引擎（Agent之后的技术筛选）
│   └── scorer.py               # 综合评分模型
│
├── backtest/                   # 回测层
│   ├── engine.py               # 回测引擎
│   ├── strategy.py             # 策略封装
│   └── report.py               # 回测报告生成
│
├── workflow/                   # 工作流编排
│   └── pipeline.py             # 主流程编排（串联两层）
│
├── output/                     # 输出层
│   ├── reporter.py             # 报告生成（Markdown/HTML）
│   └── notifier.py             # 通知（可选：企业微信、钉钉）
│
├── api/                        # FastAPI 后端
│   ├── main.py                 # FastAPI 应用入口
│   ├── routers/                # API 路由
│   │   ├── stock.py            # 选股结果 API
│   │   ├── backtest.py         # 回测 API
│   │   ├── agent.py            # Agent 分析过程 API
│   │   └── config.py           # 配置管理 API
│   ├── schemas.py              # Pydantic 数据模型
│   ├── dependencies.py         # 依赖注入
│   └── websocket.py            # WebSocket（实时推送 Agent 分析进度）
│
├── web/                        # React 前端
│   ├── package.json
│   ├── vite.config.ts
│   ├── tsconfig.json
│   ├── src/
│   │   ├── App.tsx             # 应用入口
│   │   ├── main.tsx            # 渲染入口
│   │   ├── pages/              # 页面
│   │   │   ├── Dashboard/      # 首页看板
│   │   │   ├── StockResult/    # 选股结果页
│   │   │   ├── Backtest/       # 回测分析页
│   │   │   ├── AgentView/      # Agent 分析详情页
│   │   │   └── Settings/       # 系统配置页
│   │   ├── components/         # 通用组件
│   │   │   ├── KlineChart/     # K线图组件（ECharts）
│   │   │   ├── RadarChart/     # Agent评分雷达图
│   │   │   ├── PerformanceChart/ # 回测净值曲线
│   │   │   ├── StockTable/     # 选股结果表格
│   │   │   └── AgentTimeline/  # Agent 分析时间线
│   │   ├── services/           # API 调用层
│   │   │   └── api.ts          # Axios 封装
│   │   ├── stores/             # 状态管理（Zustand）
│   │   │   ├── useStockStore.ts
│   │   │   ├── useBacktestStore.ts
│   │   │   └── useAgentStore.ts
│   │   ├── types/              # TypeScript 类型定义
│   │   │   └── index.ts
│   │   └── utils/              # 工具函数
│   │       ├── echarts.ts      # ECharts 主题配置
│   │       └── format.ts       # 数据格式化
│   └── public/
│
├── tests/                      # 测试
│   ├── test_data/
│   ├── test_agents/
│   ├── test_quant/
│   ├── test_workflow/
│   └── test_api/
│
├── run.py                      # CLI 入口
├── requirements.txt
└── README.md
```

### 项目根目录 Harness 文件（来自 Harness 架构）

```
LLM-Quant-Stock/
├── AGENTS.md                   # 通用项目规则
├── CLAUDE.md                   # Claude 系统提示词
├── REVIEW.md                   # 只读评审代理提示词
│
├── docs/                       # 项目知识库
│   ├── system_design.md        # 本文件：系统设计方案
│   ├── settings_reference.md   # Claude settings 参考配置
│   ├── architecture/
│   │   ├── index.md            # 架构总览（分层、依赖方向）
│   │   └── implicit-contracts.md  # 隐性业务约定（股票代码格式、复权、停牌等）
│   └── standards/
│       ├── testing.md          # 测试规范
│       ├── quant_rules.md      # 量化策略与数据规范
│       └── agent_rules.md      # Agent 开发规范
│
├── openspec/                   # OpenSpec 执行目录
│   ├── config.yaml             # OpenSpec 配置（隐性约定上下文）
│   ├── specs/                  # 系统当前工作方式描述
│   └── changes/                # 变更目录
│       ├── README.md
│       └── archive/            # 归档
│
├── .claude/                    # Claude 项目级配置
│   ├── settings.json           # ⚠️ 需手动从 docs/settings_reference.md 复制
│   ├── settings.local.json.example
│   ├── skills/                 # 专用 Skills
│   │   ├── prepare-review/     # 变更摘要审计
│   │   ├── quant-architecture-review/  # 系统分层检查
│   │   └── data-pipeline-review/       # 数据管道风险检查
│   ├── agents/                 # 子代理
│   │   └── reviewer.md         # 只读评审代理
│   └── hooks/                  # Hook 脚本
│       ├── guard_write.py      # 文件写入保护
│       ├── ensure_change_context.py  # OpenSpec 上下文校验
│       └── run_checks.sh       # 代码变更后自动检查
```

---

## 三、核心模块详细设计

### 3.1 数据层

**设计原则**：统一接口，可切换数据源，本地缓存 + 实时补查混合策略

```python
# data/datasource.py 抽象接口
class DataSource(ABC):
    def get_stock_list(self, index: str) -> List[str]        # 获取指数成分股
    def get_daily_quotes(self, symbol: str, ...) -> DataFrame # 日K线
    def get_financial_report(self, symbol: str, ...) -> dict  # 财报数据
    def get_news(self, symbol: str, ...) -> List[dict]        # 新闻资讯
    def get_money_flow(self, symbol: str, ...) -> DataFrame   # 资金流向
    def get_realtime_quotes(self, symbols: List[str]) -> DataFrame  # 实时行情
    def get_stock_metrics(self, symbols: List[str]) -> DataFrame   # 批量获取预筛指标
```

**数据源选择策略**：

| 数据类型 | 主数据源 | 备用 | 说明 |
|---------|---------|------|------|
| 历史日K线 | baostock | akshare | baostock 稳定、复权准确 |
| 实时行情 | akshare | efinance | akshare 覆盖广 |
| 财报数据 | baostock | akshare | 利润表、资产负债表、现金流 |
| 新闻/公告 | akshare | 东方财富API | 个股新闻、公告 |
| 资金流向 | akshare | efinance | 主力资金、龙虎榜 |
| 行业分类 | akshare | - | 申万行业分类 |

**预筛数据同步策略**：

预筛需要的数据分为两类，采用混合策略避免全量实时查询：

| 数据类型 | 变化频率 | 策略 | TTL |
|---------|---------|------|-----|
| 市值、PE/PB、ROE、负债率、现金流、上市日期、行业 | 日更/季更 | 每日同步到 SQLite（stock_metrics 表） | 1天 |
| ST状态、停牌、涨跌停、实时价格、换手率、成交额 | 实时 | 实时查询 + 内存短缓存 | 5分钟 |

```
每日同步流程（选股前自动触发）：

run.py --universe hs300
    │
    ├─ 1. 检查 stock_metrics 缓存是否过期（TTL=1天）
    │     过期 → 批量拉取300只的慢数据写入 SQLite
    │     未过期 → 跳过，直接查 SQLite
    │
    ├─ 2. 预筛主体：查 SQLite 做市值/估值/财务过滤（毫秒级，零API调用）
    │
    └─ 3. 实时补查：仅对粗筛后的50~100只查 ST/停牌/涨跌停/价格
          API调用量从300只降到50~100只，不会被限流
```

```python
# data/cache.py 扩展：stock_metrics 同步表
class DataCache:
    # ... 原有通用缓存逻辑 ...

    def init_metrics_table(self):
        """初始化预筛指标专用表"""
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS stock_metrics (
                symbol TEXT PRIMARY KEY,
                name TEXT,
                industry TEXT,
                list_date TEXT,
                market_cap REAL,
                pe REAL,
                pb REAL,
                roe REAL,
                debt_ratio REAL,
                revenue REAL,
                operating_cashflow REAL,
                synced_at REAL NOT NULL
            )
        """)

    def get_metrics(self, symbols: List[str], ttl: int = 86400) -> pd.DataFrame | None:
        """批量获取预筛指标，过期返回 None 触发重新同步"""
        placeholders = ",".join("?" * len(symbols))
        rows = self._conn.execute(
            f"SELECT * FROM stock_metrics WHERE symbol IN ({placeholders})", symbols
        ).fetchall()
        if not rows:
            return None
        # 检查是否过期
        if (time.time() - rows[0][-1]) > ttl:
            return None
        return pd.DataFrame(rows, columns=[...])

    def upsert_metrics(self, df: pd.DataFrame):
        """批量写入/更新预筛指标"""
        ...
```

```python
# data/sync.py 新增：每日同步逻辑
class MetricsSyncer:
    """预筛指标同步器：批量拉取慢数据写入 SQLite"""

    def __init__(self, datasource: DataSource, cache: DataCache):
        self.datasource = datasource
        self.cache = cache

    def sync_if_stale(self, symbols: List[str]) -> pd.DataFrame:
        """检查缓存是否过期，过期则重新同步"""
        metrics = self.cache.get_metrics(symbols)
        if metrics is not None:
            return metrics

        # 批量拉取
        metrics = self.datasource.get_stock_metrics(symbols)
        self.cache.upsert_metrics(metrics)
        return metrics
```

### 3.2 预筛层（新增）

**设计目标**：在进入 LLM 分析之前，用确定性规则快速排除不合格标的，将 LLM 调用量减少 60-80%

**预筛流程**：

```
股票池（300~500只）
        │
        ▼
  ┌──────────────┐
  │ 上市状态过滤  │  排除 ST/*ST、退市风险、停牌、次新股(<1年)
  └──────┬───────┘
         ▼
  ┌──────────────┐
  │ 基本面过滤    │  市值、PE/PB、ROE、资产负债率、现金流
  └──────┬───────┘
         ▼
  ┌──────────────┐
  │ 流动性过滤    │  日均成交额、换手率、涨跌停状态
  └──────┬───────┘
         ▼
  ┌──────────────┐
  │ 价格过滤     │  股价 > 2元
  └──────┬───────┘
         ▼
  粗筛后候选池（50~100只）→ 进入 LLM Agent 层
```

**预筛规则配置**（config/quant_rules.yaml 的 pre_screen 段落）：

```yaml
# config/quant_rules.yaml
pre_screen:
  # 上市状态
  exclude_st: true              # 排除 ST/*ST
  exclude_suspended: true       # 排除停牌
  min_list_days: 250            # 上市至少250个交易日（约1年）

  # 市值（亿元）
  market_cap:
    min: 50
    max: 5000

  # 流动性
  liquidity:
    min_avg_amount: 3000        # 日均成交额 > 3000万
    min_turnover_rate: 0.5      # 换手率 > 0.5%

  # 估值
  valuation:
    pe_min: 0                   # PE > 0（排除亏损）
    pe_max: 100                 # PE < 100（排除泡沫）
    pb_min: 0                   # PB > 0
    pb_max: 20                  # PB < 20

  # 盈利能力
  profitability:
    min_roe: 3                  # 最近一期 ROE > 3%
    revenue_positive: true      # 营收为正

  # 财务健康
  financial_health:
    max_debt_ratio: 80          # 资产负债率 < 80%
    operating_cashflow_positive: true  # 经营现金流为正

  # 价格
  price:
    min: 2                      # 股价 > 2元

  # 涨跌停
  exclude_limit_up: true        # 排除涨停（避免追涨）
  exclude_limit_down: true      # 排除跌停
```

**代码位置**：`quant/screener.py`，数据同步见 `data/sync.py`（详见 3.1 数据层）

```python
# quant/screener.py
class StockScreener:
    """预筛模块：基础量化粗筛，减少 LLM 调用量"""

    def __init__(self, datasource: DataSource, rules_path: str = "config/quant_rules.yaml"):
        self.datasource = datasource
        self.rules = self._load_rules(rules_path)

    def screen(self, stock_list: List[str], date=None) -> List[str]:
        """对股票池执行预筛，返回通过筛选的股票列表"""
        # 1. 批量获取基础数据（市值、PE/PB、ROE、成交额等）
        stock_metrics = self._batch_fetch_metrics(stock_list, date)

        # 2. 逐条应用预筛规则
        passed = []
        for symbol, metrics in stock_metrics.items():
            if self._apply_rules(metrics):
                passed.append(symbol)

        return passed

    def _apply_rules(self, metrics: dict) -> bool:
        """应用预筛规则，全部通过才返回 True"""
        rules = self.rules.get("pre_screen", {})
        # 上市状态、市值、流动性、估值、盈利、财务健康、价格、涨跌停
        # 任何一项不满足即排除
        ...
```

**与 Pipeline 的集成**：

```python
# workflow/pipeline.py 中的调用顺序
def run(self, universe="hs300", date=None):
    stock_list = self.datasource.get_stock_list(universe)

    # 新增：预筛，减少 LLM 调用量
    candidates = self.screener.screen(stock_list, date)
    # 300只 → 50~100只

    # 后续不变：LLM Agent 分析 + 量化二次筛选
    ...
```

### 3.3 LLM Agent 层（第一层）

**架构参考**：融合 TradingAgents 的辩论机制 + AI Hedge Fund 的并行分析

**Agent 协作流程**：

```
                    股票池输入
                       │
          ┌────────────┼────────────┐
          ▼            ▼            ▼
   ┌──────────┐ ┌──────────┐ ┌──────────┐
   │ 基本面    │ │ 情绪     │ │ 新闻     │   ← 并行执行
   │ Analyst  │ │ Analyst  │ │ Analyst  │
   └────┬─────┘ └────┬─────┘ └────┬─────┘
        │            │            │
        └────────────┼────────────┘
                     ▼
              ┌──────────────┐
              │  多空辩论     │    ← Bull vs Bear 辩论（2-3轮）
              │  Researcher  │
              └──────┬───────┘
                     ▼
              ┌──────────────┐
              │ 基金经理      │    ← 综合所有分析，输出初选名单
              │ Fund Manager │       附带评分 + 推荐理由
              └──────┬───────┘
                     ▼
              初选股票名单 + 评分
```

**各 Agent 职责**：

| Agent | 输入 | 输出 | LLM 用途 |
|-------|------|------|----------|
| **基本面分析师** | 财报数据（营收、利润、ROE、负债率） | 财务健康评分(1-10) + 看多/看空理由 | 分析财务趋势，判断增长性 |
| **情绪分析师** | 新闻标题、股吧热帖、龙虎榜 | 情绪评分(1-10) + 情绪标签 | 理解文本情绪，识别市场恐慌/狂热 |
| **新闻分析师** | 公司公告、行业政策、宏观数据 | 政策影响评分(1-10) + 关键事件列表 | 理解政策影响，评估行业前景 |
| **多空研究员** | 三个分析师的报告 | 多空辩论记录 + 共识点/分歧点 | 构建多空论据，互相质疑 |
| **基金经理** | 辩论结果 + 分析师评分 | 初选名单(5-20只) + 评分 + 买入理由 | 综合决策，类似真实基金经理 |

**LLM 模型选择策略**：

| 角色 | 推荐模型 | 理由 |
|------|---------|------|
| 分析师（并行） | DeepSeek-V3 / Qwen-Plus | 成本低，速度快，中文能力强 |
| 多空研究员 | DeepSeek-V3 / Qwen-Plus | 需要逻辑推理但不需要极深思考 |
| 基金经理 | DeepSeek-R1 / Claude Sonnet | 需要综合判断，用强模型 |

**Agent 输出格式**（统一结构）：

```python
@dataclass
class AgentSignal:
    agent: str              # agent名称
    symbol: str             # 股票代码
    score: float            # 评分 1-10
    signal: str             # "bullish" / "bearish" / "neutral"
    confidence: float       # 信心度 0-1
    reasoning: str          # 分析理由（中文）
    key_metrics: dict       # 关键数据指标
```

### 3.4 量化筛选层（第二层）

**核心思路**：LLM 输出的初选名单进入量化管道，用确定性指标做二次验证

**筛选流程**：

```
LLM 初选名单（5-20只）
         │
         ▼
  ┌──────────────┐
  │ 技术指标计算   │   ← TA-Lib
  │ RSI, MACD,    │
  │ BOLL, KDJ,    │
  │ MA(5/10/20/60)│
  └──────┬───────┘
         │
         ▼
  ┌──────────────┐
  │ K线形态识别   │   ← TA-Lib candlestick patterns
  │ 锤子线、吞没、 │
  │ 晨星、十字星等 │
  └──────┬───────┘
         │
         ▼
  ┌──────────────┐
  │ 筛选规则引擎   │   ← 可配置的过滤条件
  │ 例：RSI<30    │
  │ 且 MACD金叉   │
  │ 且放量上涨    │
  └──────┬───────┘
         │
         ▼
  ┌──────────────┐
  │ 综合评分      │
  │ LLM评分(40%)  │
  │ 技术指标(30%) │
  │ 形态信号(20%) │
  │ 资金流(10%)   │
  └──────┬───────┘
         │
         ▼
  最终标的（3-5只）+ 评分 + 买入建议
```

**量化筛选规则示例**（可配置）：

```yaml
# config/quant_rules.yaml
filters:
  # 必要条件（AND）
  required:
    - rsi_14 < 70                    # 未超买
    - volume_ratio > 0.8             # 成交量不低于均量80%
    - ma5 > ma20 or cross_up(ma5, ma20)  # 均线多头或刚金叉

  # 加分条件
  bonus:
    - pattern: hammer                # 锤子线 +2分
      score: +2
    - pattern: bullish_engulfing     # 看涨吞没 +2分
      score: +2
    - macd_golden_cross: true        # MACD金叉 +3分
      score: +3
    - rsi_14 < 30                    # 超卖区 +1分
      score: +1
    - money_flow_net > 0             # 主力净流入 +2分
      score: +2

  # 一票否决
  veto:
    - rsi_14 > 85                    # 极度超买
    - limit_down: true               # 跌停
```

### 3.5 回测层

**设计目标**：验证"LLM选股+量化过滤"组合策略 vs 纯LLM vs 纯量化 的效果差异

```python
# 回测策略接口
class LLMQuantStrategy:
    def on_bar(self, date, universe):
        # 1. 每周/每月触发一次LLM选股
        # 2. 对选出的股票执行量化过滤
        # 3. 输出交易信号（买入/卖出/持有）
        # 4. 仓位管理
        pass
```

**回测指标输出**：

| 指标 | 说明 |
|------|------|
| 累计收益率 | 总收益 |
| 年化收益率 | 标准化年化 |
| 最大回撤 | 风险核心指标 |
| 夏普比率 | 风险调整后收益 |
| 胜率 | 盈利交易占比 |
| 平均持仓天数 | 换手率参考 |
| vs 沪深300 | 超额收益 |

### 3.6 FastAPI 后端层

**设计原则**：薄 API 层，只做数据转发和格式转换，不包含业务逻辑

```python
# api/routers/stock.py
@router.post("/api/v1/selection")
async def run_selection(req: SelectionRequest) -> SelectionResponse:
    """触发选股流程，返回最终标的"""

@router.get("/api/v1/selection/{task_id}")
async def get_selection_result(task_id: str) -> SelectionResponse:
    """获取选股结果"""

# api/routers/agent.py
@router.websocket("/ws/agent/{task_id}")
async def agent_progress(websocket: WebSocket, task_id: str):
    """WebSocket 实时推送 Agent 分析进度"""

# api/routers/backtest.py
@router.post("/api/v1/backtest")
async def run_backtest(req: BacktestRequest) -> BacktestResponse:
    """触发回测，返回绩效指标"""
```

**API 分层**：

| 层 | 职责 | 说明 |
|----|------|------|
| `api/routers/` | 路由定义 | 接收请求、参数校验、返回响应 |
| `api/schemas.py` | 数据模型 | Pydantic 模型，定义请求/响应格式 |
| `api/dependencies.py` | 依赖注入 | 数据源、Pipeline 实例的注入 |
| `api/websocket.py` | WebSocket | Agent 分析进度的实时推送 |
| `workflow/pipeline.py` | 业务逻辑 | 实际的选股/回测逻辑 |

### 3.7 React 前端

**技术栈**：React 18 + TypeScript + Vite + Ant Design 5 + ECharts 5 + Zustand

**页面设计**：

```
┌──────────────────────────────────────────────────────────────────┐
│  顶部导航栏：Logo | 选股看板 | 回测分析 | Agent详情 | 系统配置    │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  首页 Dashboard                                                  │
│  ┌──────────────────┐  ┌──────────────────┐                     │
│  │ 本期选股摘要       │  │ 最近回测绩效      │                     │
│  │ 选中 N 只         │  │ 累计收益 XX%     │                     │
│  │ 平均评分 7.2      │  │ 夏普比率 X.XX    │                     │
│  └──────────────────┘  └──────────────────┘                     │
│  ┌────────────────────────────────────────────┐                 │
│  │ 选股结果表格（Ant Design Table）             │                 │
│  │ 股票代码 | 名称 | 综合评分 | LLM评分 | 量化评分 |             │
│  │ 600519  | 贵州茅台 | 8.5  | 8.0   | 9.0   |             │
│  │ 000858  | 五粮液   | 7.8  | 7.5   | 8.2   |             │
│  └────────────────────────────────────────────┘                 │
│                                                                  │
│  选股结果详情页                                                   │
│  ┌──────────────────┐  ┌──────────────────┐                     │
│  │ K线图 + 技术指标   │  │ Agent评分雷达图   │                     │
│  │ (ECharts Kline)  │  │ (ECharts Radar)  │                     │
│  └──────────────────┘  └──────────────────┘                     │
│  ┌────────────────────────────────────────────┐                 │
│  │ Agent 分析时间线                             │                 │
│  │ 基本面(8.0) → 情绪(7.5) → 新闻(8.2)        │                 │
│  │ → 多空辩论 → 基金经理决策 → 量化筛选(9.0)    │                 │
│  └────────────────────────────────────────────┘                 │
│                                                                  │
│  回测分析页                                                       │
│  ┌────────────────────────────────────────────┐                 │
│  │ 净值曲线（策略 vs 沪深300基准）              │                 │
│  │ (ECharts Line)                              │                 │
│  └────────────────────────────────────────────┘                 │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐          │
│  │ 累计收益  │ │ 最大回撤  │ │ 夏普比率  │ │ 胜率     │          │
│  │ XX.XX%  │ │ -XX.XX% │ │ X.XX    │ │ XX%     │          │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘          │
└──────────────────────────────────────────────────────────────────┘
```

**核心组件**：

| 组件 | 图表库 | 功能 |
|------|-------|------|
| KlineChart | ECharts Kline | 日K线 + MA/RSI/MACD/BOLL 叠加 |
| PerformanceChart | ECharts Line | 回测净值曲线 + 基准对比 + 回撤区域 |
| RadarChart | ECharts Radar | 多Agent评分雷达图 |
| AgentTimeline | Ant Design Steps | Agent 分析过程时间线 |
| StockTable | Ant Design Table | 选股结果排序、筛选、分页 |

**前后端交互**：

```
React 前端                      FastAPI 后端
    │                               │
    │── POST /api/v1/selection ───→ │  触发选股
    │←─ task_id ────────────────── │
    │                               │
    │── WS /ws/agent/{task_id} ──→ │  订阅进度
    │←─ {agent, status, result} ── │  实时推送 Agent 分析进度
    │                               │
    │── GET /api/v1/selection/id ─→ │  获取结果
    │←─ {stocks, scores, charts} ─ │
    │                               │
    │── POST /api/v1/backtest ───→ │  触发回测
    │←─ {metrics, equity_curve} ── │
```

---

## 四、工作流编排

主流程串联两层：

```python
# workflow/pipeline.py 伪代码
class StockSelectionPipeline:
    def run(self, universe="hs300", date=None):
        # Phase 1: 获取股票池
        stock_list = self.datasource.get_stock_list(universe)

        # Phase 1.5: 预筛（新增）
        candidates = self.screener.screen(stock_list, date)
        # 300只 → 50~100只，大幅减少 LLM 调用量

        # Phase 2: LLM Agent 并行分析
        # 2a. 先批量获取数据（避免重复请求）
        stock_data = self.batch_fetch_data(candidates)

        # 2b. 并行启动 3 个分析师
        fundamental_signals = self.agents["fundamental"].analyze(stock_data)
        sentiment_signals = self.agents["sentiment"].analyze(stock_data)
        news_signals = self.agents["news"].analyze(stock_data)

        # 2c. 多空辩论
        debate_result = self.agents["researcher"].debate(
            fundamental_signals, sentiment_signals, news_signals
        )

        # 2d. 基金经理决策
        shortlist = self.agents["fund_manager"].decide(
            signals=[fundamental_signals, sentiment_signals, news_signals],
            debate=debate_result
        )
        # shortlist: List[{symbol, score, reasoning}]

        # Phase 3: 量化二次筛选
        for stock in shortlist:
            stock["quant_score"] = self.quant.analyze(stock["symbol"])
            stock["patterns"] = self.quant.detect_patterns(stock["symbol"])

        # Phase 4: 综合评分 + 过滤
        final_picks = self.quant.filter_and_rank(shortlist)

        # Phase 5: 生成报告
        report = self.reporter.generate(final_picks)

        return final_picks, report
```

---

## 五、技术选型

| 类别 | 选择 | 理由 |
|------|------|------|
| 语言 | Python 3.10+ | 生态最完善 |
| Agent框架 | LangGraph | TradingAgents/AI Hedge Fund 均采用，成熟可靠 |
| LLM | DeepSeek-V3/R1（主）+ Qwen（备） | 中文能力最强，成本低 |
| 数据源-实时 | akshare | 免费、免注册、A股覆盖最全 |
| 数据源-历史 | baostock | 历史K线稳定、复权准确 |
| 技术指标 | TA-Lib | 行业标准，指标最全 |
| 回测 | backtrader | 成熟稳定，文档丰富 |
| 数据缓存 | SQLite | 轻量、无需额外服务 |
| 任务并行 | asyncio + ThreadPoolExecutor | Agent并行分析 |
| 后端框架 | FastAPI | 异步、高性能、自动生成API文档 |
| 前端框架 | React 18 + TypeScript | 组件生态丰富，类型安全 |
| UI组件库 | Ant Design 5 | 国内最流行的React组件库，表格/表单/布局完善 |
| 图表 | ECharts 5 | 金融图表最强（K线、技术指标、回测曲线） |
| 状态管理 | Zustand | 轻量、简洁，比Redux少样板代码 |
| 构建工具 | Vite | 开发体验好，HMR快 |

---

## 六、实施路线图

### Phase 1：基础框架（第1-2周）
- [ ] 项目骨架搭建（目录结构、配置管理、依赖管理）
- [ ] 数据层实现（akshare + baostock 双数据源 + 缓存）
- [ ] BaseAgent 基类 + LLM 调用封装

### Phase 2：LLM Agent 选股（第3-4周）
- [ ] 基本面分析师 Agent
- [ ] 情绪分析师 Agent
- [ ] 新闻分析师 Agent
- [ ] 多空辩论机制
- [ ] 基金经理 Agent（综合决策）
- [ ] Agent 单元测试 + 联调

### Phase 3：量化筛选层（第5周）
- [ ] TA-Lib 指标计算封装
- [ ] K线形态识别
- [ ] 筛选规则引擎（YAML配置）
- [ ] 综合评分模型

### Phase 4：工作流编排 + 回测（第6周）
- [ ] Pipeline 主流程串联
- [ ] 回测引擎集成
- [ ] 报告生成模块

### Phase 5：优化迭代（第7-8周）
- [ ] Prompt 调优
- [ ] 策略参数优化
- [ ] 性能优化（并行、缓存）
- [ ] 历史回测验证

---

## 七、关键设计决策

### 7.1 为什么用 LangGraph 而不是自研？

LangGraph 提供了 StateGraph、条件边、checkpoint 等开箱即用的能力。TradingAgents 和 AI Hedge Fund 都基于它构建，经过大量验证。自研 Agent 框架的工作量大且容易踩坑，不值得。

### 7.2 为什么分两层而不是让 LLM 一步到位？

- LLM 擅长定性分析（理解财报、新闻）但不擅长精确计算
- 量化指标（RSI、MACD）需要数值精确性，LLM 容易算错
- 分层架构让每层可独立测试、优化、替换
- 可以量化对比"纯LLM" vs "LLM+量化" 的效果差异

### 7.3 为什么选 DeepSeek 作为主力 LLM？

- 中文理解能力在国产模型中顶尖
- API 价格远低于 GPT-4/Claude
- DeepSeek-R1 的推理能力适合基金经理角色的综合决策
- 支持本地部署（隐私敏感的金融数据）

### 7.4 成本控制

| 场景 | 预估调用次数 | 单次成本(DeepSeek-V3) | 预估总成本 |
|------|-------------|---------------------|-----------|
| 预筛（量化规则） | 0次LLM调用 | ¥0 | ¥0 |
| 沪深300粗筛后分析 | ~300次（100股×3Agent） | ¥0.001 | ¥0.3/次 |
| 初选后量化筛选 | 0次LLM调用 | ¥0 | ¥0 |
| 基金经理决策 | 1次 | ¥0.01 | ¥0.01/次 |
| **单次运行总计** | | | **~¥0.3/次** |

---

## 八、风险与注意事项

1. **LLM 幻觉风险**：Agent 输出的数据指标必须与实际数据交叉验证，不能完全信任 LLM 生成的数字
2. **数据延迟**：akshare 实时数据可能有数秒到数分钟延迟，不适合高频策略
3. **合规风险**：本系统仅供研究学习，不构成投资建议，不可直接用于实盘交易
4. **API 限流**：akshare 的上游数据源（东方财富、新浪）有反爬机制，需要控制请求频率
5. **回测偏差**：历史回测不代表未来表现，需注意幸存者偏差、前视偏差等常见问题

---

## 九、Harness 工作流架构

本项目采用 Harness 风格工作流，将 AI 辅助开发规范化，核心思路是 **需求→设计→实现→评审** 的闭环管控。

### 9.1 核心理念

| 理念 | 说明 |
|------|------|
| **OpenSpec 驱动** | 没有变更工件不允许直接开发 |
| **实现与评审分离** | reviewer 子Agent 只读审查，不修改文件 |
| **分层约束** | 通过 CLAUDE.md 规则 + Hooks 硬约束双重保障 |
| **知识库先行** | docs/ 中维护架构、规范、隐性约定 |

### 9.2 工作流全景

```
新需求 → /opsx:propose → proposal.md
                          design.md
                          tasks.md
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
        /opsx:apply      CLAUDE.md       Hooks 保护
        （执行实现）     （规则约束）    （写入保护/上下文校验）
              │               │               │
              └───────────────┼───────────────┘
                              ▼
                     /opsx:verify（校验）
                              │
                    ┌─────────┼─────────┐
                    ▼         ▼         ▼
              Skills检查  子Agent评审  测试运行
                    │         │         │
                    └─────────┼─────────┘
                              ▼
                     /opsx:archive（归档）
```

### 9.3 文件职责映射（Java → Python 量化适配）

| 原 Java Harness | 本项目适配 | 说明 |
|----------------|-----------|------|
| Spring Boot 分层规则 | 量化系统分层规则 | workflow/agents/quant/data/backtest 五层 |
| Maven 测试命令 | pytest 命令 | Python 测试体系 |
| SQL/Mapper 风险检查 | 数据管道风险检查 | 前视偏差、数据格式、缓存策略 |
| Spring 架构检查 | 量化架构检查 | 分层、依赖方向、跨层耦合 |
| application.yml 保护 | config/secrets 保护 | API Key 等敏感配置 |
| 编译 Hook | 语法检查 Hook | py_compile + pytest |
| 隐性约定（status字段） | 隐性约定（股票代码格式、复权） | A股特有数据约定 |

### 9.4 Settings 配置

`.claude/settings.json` 需要手动从 `docs/settings_reference.md` 复制创建，包含：
- **allow**：pytest、black、mypy、git status 等安全命令
- **ask**：其他 Bash、Edit、Write 操作需确认
- **deny**：git push、rm -rf、secrets 读写
- **PreToolUse Hooks**：写入保护 + OpenSpec 上下文校验
- **PostToolUse Hooks**：代码变更后自动检查

### 9.5 开发流程示例

```
1. 创建 OpenSpec change
   mkdir -p openspec/changes/001-data-layer/{specs}
   编写 proposal.md → design.md → tasks.md

2. 执行实现
   Claude Code 读取 change 文件，按 tasks.md 实现
   Hooks 自动校验上下文和保护目录

3. 代码检查
   PostToolUse Hook 自动触发 pytest（如有代码变更）
   /quant-architecture-review 检查分层
   /data-pipeline-review 检查数据风险

4. 评审
   reviewer 子Agent 对照 OpenSpec 工件审查
   /prepare-review 生成变更摘要

5. 归档
   /opsx:archive 归档 change 到 archive/
```
