## Context

当前系统使用 4 张 SQLite 表支撑预筛流程：
- `stock_metrics`：每只股票一条记录，UPSERT 覆盖，存储慢数据指标（PE/PB/ROE 等）
- `stock_pools`：每次同步一条快照，记录股票池成分股列表
- `screening_results`：每次预筛一条汇总记录
- `screening_stocks`：每次预筛 N 条明细（含指标快照）

实际使用中，用户只关心当前最新数据，从不回看历史预筛结果。LLM 分析阶段可以直接 SQL 查询过滤，无需独立预筛流程。当前 4 表设计带来了不必要的复杂度。

## Goals / Non-Goals

**Goals:**
- 将 stock_metrics 扩展为全量宽表，一次同步写入所有指标（慢数据 + 实时数据）
- 删除不使用的表（stock_pools, screening_results, screening_stocks）及相关代码
- 简化数据同步流程为：拉取全 A 指标 → 写入 stock_metrics
- API 和前端从"触发预筛+查结果"模式改为"触发同步+查询指标"模式

**Non-Goals:**
- 不做预筛历史记录保留（用户明确不需要）
- 不改回测模块（backtest 使用独立的前复权数据，不受影响）
- 不改 LLM Agent 的分析逻辑（只是输入来源从预筛结果改为 SQL 查询）
- 不做数据库版本迁移工具（项目早期，直接 DROP + CREATE 重建）

## Decisions

### Decision 1: stock_metrics 扩展为宽表，合并实时字段

**选择**: 在现有 stock_metrics 表上新增 7 个字段（is_st, is_suspended, is_limit_up, is_limit_down, price, turnover_rate, avg_amount），同步时一并写入。

**备选方案**:
- A) 新建独立表存实时数据 → 需要 JOIN 查询，增加复杂度
- B) 实时数据在查询时临时拉取 → 每次查询都要调 AkShare API，延迟高且可能被限流

**理由**: 实时数据本质上是"每日更新一次"的数据（盘后就是收盘价），跟 PE/PB 等慢数据更新频率相同，合并到一张表最简单。同步时 MetricsSyncer 先拉慢数据再拉实时数据，合并后一次 upsert。

### Decision 2: 删除 quant/screener.py 预筛引擎

**选择**: 移除 StockScreener 类，不再有独立的"8 维度预筛"步骤。

**理由**: 用户明确表示过滤条件由 LLM 分析阶段按需 SQL 查询（如 `WHERE pe > 5 AND roe > 3 AND is_st = 0`），不需要硬编码的预筛规则。配置文件 `config/quant_rules.yaml` 中的 pre_screen 段落也一并移除。

### Decision 3: 同步流程简化为两步

**选择**: DataScheduler.run_daily() 简化为：
1. 拉取全 A 股票列表 → 确定同步范围
2. 调用 MetricsSyncer 同步全量指标（慢数据 + 实时数据合并写入 stock_metrics）

**备选方案**: 保留三步流程但跳过预筛 → 不够彻底，遗留无用的编排逻辑

**理由**: 去掉预筛步骤后，同步 → 写库 两步足够。股票池信息不需要单独建表，同步时直接从 AkShare 拉全 A 列表即可。

### Decision 4: API 端点重新设计

**选择**: screener 路由改为 metrics 路由：
- `POST /metrics/sync` — 触发全量同步（后台执行）
- `GET /metrics/query` — 查询 stock_metrics（支持 WHERE 条件过滤）
- 删除 `/screener/run`, `/screener/result`, `/screener/stats`, `/screener/history`

### Decision 5: 不做数据迁移

**选择**: 直接删除旧数据库文件，首次运行时自动重建表结构。

**理由**: 项目处于开发早期，无生产数据需要保留。重建表比写迁移脚本简单得多。

## Risks / Trade-offs

- **[风险] 全 A 同步耗时长** → 当前只同步指数成分股（300-500 只），扩展到全 A（5000+ 只）后 BaoStock 逐只查询财报需 30+ 分钟。缓解：先同步 AkShare 快数据（全量批量），BaoStock 财报数据按需补齐或异步后台分批同步。
- **[风险] 删除预筛后 LLM 输入量变大** → 原本预筛过滤到 50 只再送 LLM，现在全量送入。缓解：LLM 分析前仍可 SQL 过滤（只是条件由调用方动态指定而非硬编码），实际输入量可控。
- **[权衡] 丧失历史对比能力** → 无法回看"上周筛出了哪些股"。用户已明确接受。
