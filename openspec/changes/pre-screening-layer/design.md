## Context

系统当前流程是 `股票池 → LLM Agent 分析 → 量化二次筛选`，300-500 只股票直接进入 LLM 分析层。这意味着每次选股需要约 900 次 LLM 调用（300股 × 3 Agent），成本约 1 元/次，耗时长。

本次变更新增预筛层，将流程改为 `股票池 → 预筛（量化粗筛）→ LLM Agent 分析 → 量化二次筛选`。预筛基于确定性规则（市值、PE/PB、ROE、ST 状态等），不调用 LLM，目标是把候选池从 300 只压缩到 50-100 只。

预筛规则已在 `config/quant_rules.yaml` 的 `pre_screen` 段落中定义（8 个维度），本轮直接使用。

## Goals / Non-Goals

**Goals:**

- 实现预筛核心模块 `quant/screener.py`，支持 8 个维度的确定性规则过滤
- 实现数据同步 `data/sync.py`，将慢数据（市值、PE/PB、ROE 等）每日同步到 SQLite
- 扩展 `data/cache.py` 新增 `stock_metrics` 专用表 + `screening_results`/`screening_stocks` 持久化表
- 扩展 `data/datasource.py` 和两个数据源实现，新增 `get_stock_metrics()` 方法
- 更新 `workflow/pipeline.py` 在 Agent 之前插入预筛步骤
- 新增 FastAPI 预筛相关 API（触发预筛、查看结果、统计）
- 新增 React 前端预筛结果展示（集成到 Dashboard）

**Non-Goals:**

- 不改动 LLM Agent 层逻辑（agents/ 不动）
- 不改动量化二次筛选层（quant/filters.py、quant/scorer.py 不动）
- 不改动回测引擎
- 不引入新数据库（继续用 SQLite）
- 不实现实时行情推送（WebSocket 预筛进度为可选，优先级低）

## Decisions

### D1: 预筛放在 quant/ 层而非新模块

**选择**：在 `quant/` 下新增 `screener.py`，不创建新的顶层目录。

**理由**：预筛本质是量化筛选，只是时机在 Agent 之前。与现有 `filters.py`（Agent 之后的技术筛选）职责不同但同属量化层，放一起语义清晰，目录结构不变。

**备选方案**：创建 `screener/` 顶层模块 → 过度设计，一个文件的事。

### D2: 混合数据策略（本地缓存 + 实时补查）

**选择**：慢数据（市值、PE/PB、ROE、财报）每日同步到 SQLite `stock_metrics` 表；实时数据（ST 状态、停牌、涨跌停、价格）实时查询 + 5 分钟内存短缓存。

**理由**：300 只股票逐个调 API 获取 PE/PB/ROE 需要 5-10 分钟，本地查询毫秒级。实时数据量小（只查粗筛后的 50-100 只），不会被限流。

**备选方案**：全量实时查询 → 太慢，会被数据源限流。全量本地缓存 → 实时数据（ST、停牌）可能过时。

### D3: 定时任务同步数据，而非 Pipeline 触发

**选择**：新增 `data/scheduler.py` 定时任务模块，每日收盘后（如 15:30）自动执行三项同步：股票池快照 → 慢数据指标同步 → 预筛执行。Pipeline 启动时直接读 DB，不再触发同步。

**理由**：
- **数据时点一致性**：股票池、慢数据、预筛结果在同一时间窗口内同步完成，避免 Pipeline 运行时数据半新半旧
- **用户体验**：用户触发选股时数据已就绪，无需等待同步（同步可能需要 5-10 分钟）
- **可审计**：每日数据快照可追溯，回测时可精确回放

**备选方案**：Pipeline 触发同步 → 同步耗时长，用户等待久；数据时点不一致（股票池和指标可能不同步）。

**定时任务流程**：

```
每日 15:30 自动执行（data/scheduler.py）
    │
    ├─ Step 1: 同步股票池快照
    │   akshare.get_stock_list("hs300") → 写入 stock_pools 表（pool_id, universe, symbols, date）
    │
    ├─ Step 2: 同步慢数据指标
    │   按 Step 1 的股票列表，批量拉取市值/PE/ROE → 更新 stock_metrics 表
    │
    └─ Step 3: 执行预筛
        screener.screen(最新 pool 的 symbols) → 写入 screening_results + screening_stocks
        screening_results 关联 pool_id

手动触发兜底：
    POST /api/v1/screener/run 也可触发完整流程（同步 → 预筛）
```

### D4: 股票池快照表（新增）

**选择**：新增 `stock_pools` 表，每次同步股票池时写入一条新记录（不覆盖历史）。

**表设计**：

```
stock_pools（每次同步一条记录）
├── pool_id (PK, autoincrement)
├── universe (TEXT, 如 "hs300")
├── symbols (TEXT, JSON数组: ["600519", "000858", ...])
├── count (INTEGER)
├── synced_at (REAL, timestamp)
```

**理由**：
- 指数成分股半年调仓一次，保留历史可追溯
- 预筛结果通过 pool_id 关联到当时的股票池，数据链路完整
- 回测时可精确使用当时的成分股列表

screening_results 表增加 `pool_id (FK → stock_pools)` 字段，形成完整链路：

```
stock_pools → screening_results → [LLM] → agent_results → [量化] → final_picks
  (股票池快照)  (预筛快照)               (LLM分析)           (最终标的)
  pool_id=1     screening_id=1 (pool_id=1)
  pool_id=2     screening_id=2 (pool_id=2)
```

### D6: API 设计遵循现有模式

**选择**：新增 `api/routers/screener.py` 路由，遵循现有 Router 结构。

- `POST /api/v1/screener/run` — 触发预筛（异步，返回 task_id）
- `GET /api/v1/screener/result` — 获取最近一次预筛结果
- `GET /api/v1/screener/stats` — 获取预筛统计（原始数量、通过数量、各维度淘汰数）

**理由**：与现有 stock.py、backtest.py 路由风格一致，前端对接成本低。

### D7: 预筛结果持久化到数据库（新增）

**选择**：每次预筛结果写入 SQLite 的 `screening_results` 和 `screening_stocks` 两张表，LLM Agent 从数据库读取候选池。

**理由**：
- **断点恢复**：LLM 分析耗时长、可能中途失败，预筛结果已落盘不用重跑
- **历史可查**：可对比不同日期的预筛结果，看哪些股票反复通过/被过滤
- **前后端解耦**：前端直接查 DB 展示结果，不依赖 Pipeline 运行时状态
- **回测支撑**：回测时可回放历史预筛结果

**表设计**：

```
screening_results（每次预筛一条记录）
├── screening_id (PK, autoincrement)
├── pool_id (FK → stock_pools)
├── universe (TEXT, 如 "hs300")
├── total_count (INTEGER)
├── passed_count (INTEGER)
├── excluded_count (INTEGER)
├── dimension_breakdown (TEXT, JSON: {"ST": 15, "市值": 30, ...})
├── created_at (REAL, timestamp)

screening_stocks（每只股票一条记录）
├── screening_id (FK → screening_results)
├── symbol (TEXT)
├── name (TEXT)
├── passed (INTEGER, 0/1)
├── exclusion_reasons (TEXT, JSON: ["市值过低", "ROE不足"])
├── market_cap (REAL)
├── pe (REAL)
├── pb (REAL)
├── roe (REAL)
├── price (REAL)
```

**备选方案**：只在内存中传递 → LLM 失败需重跑预筛，前端无法查询历史，回测无法回放。

### D8: 预筛前端独立页面，不集成到 Dashboard

**选择**：新增独立的 `Screening` 页面（`web/src/pages/Screening/`），包含统计卡片、维度淘汰图表、结果表格、历史记录。导航栏新增「预筛分析」入口。

**理由**：预筛模块信息量大（股票池快照、8 维度统计、历史对比），塞进 Dashboard 会导致页面臃肿。独立页面可以展示更完整的预筛数据，也方便后续扩展（如历史对比、规则调优）。

**页面布局**：

```
┌─────────────────────────────────────────────────┐
│ 顶部统计卡片：原始300 | 通过85 | 过滤215          │
├─────────────────────────────────────────────────┤
│ 维度淘汰图表（ECharts 横向柱状图）                │
│ ST:15  市值:30  流动性:20  估值:10  ...           │
├─────────────────────────────────────────────────┤
│ 结果表格（Ant Design Table，支持排序/筛选/分页）   │
│ 代码|名称|市值|PE|PB|ROE|价格|状态               │
├─────────────────────────────────────────────────┤
│ 历史记录（可选）：日期选择器对比两次预筛差异        │
└─────────────────────────────────────────────────┘
```

**前端目录**：

```
web/src/pages/Screening/
├── index.tsx              ← 预筛主页面
├── ScreeningStats.tsx     ← 统计卡片
├── ScreeningTable.tsx     ← 结果表格
└── ScreeningHistory.tsx   ← 历史对比（可选）
```

**导航栏更新**：

```
Logo | 选股看板 | 预筛分析 | 回测分析 | Agent详情 | 系统配置
```

**备选方案**：集成到 Dashboard → 页面臃肿，预筛数据和选股结果混在一起不好管理。

## Risks / Trade-offs

- **[数据源 API 限流]** → 批量拉取 300 只的慢数据时可能触发限流。缓解：加请求间隔（每次间隔 0.3-0.5 秒），失败重试 3 次，每日只同步一次。
- **[数据时效性]** → 慢数据 TTL=1 天，财报数据可能滞后。缓解：财报更新频率本身是季度级别，1 天 TTL 足够。关键决策用 LLM 验证。
- **[预筛规则过严/过松]** → 可能过滤掉好股票或放过太多。缓解：规则通过 YAML 配置可调，前端展示各维度淘汰统计便于调优。
- **[SQLite 并发]** → 多用户同时触发同步。缓解：同步前检查 `synced_at`，如果未过期直接返回，写操作加锁。
- **[隐性约定兼容]** → 本变更不触及隐性约定（股票代码格式、复权、评分范围），`screener` 输入输出都使用纯数字代码格式。
- **[定时任务可靠性]** → 定时任务依赖系统调度（cron/APScheduler），如果某天未执行则数据过期。缓解：Pipeline 启动时检测数据新鲜度，过期则补跑同步；前端展示最近同步时间提醒用户。
