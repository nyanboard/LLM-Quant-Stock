## 1. 数据层基础设施（先实现，其他层都依赖它）

- [x] 1.1 扩展 `data/cache.py`：新增 `init_metrics_table()` 创建 `stock_metrics` 表，包含 symbol(PK)、name、industry、list_date、market_cap、pe、pb、roe、debt_ratio、revenue、operating_cashflow、synced_at 字段
- [x] 1.2 扩展 `data/cache.py`：新增 `get_metrics(symbols, ttl)` 方法，批量查询 stock_metrics 表，过期或缺失返回 None
- [x] 1.3 扩展 `data/cache.py`：新增 `upsert_metrics(df)` 方法，批量 INSERT OR REPLACE
- [x] 1.4 扩展 `data/cache.py`：新增 `init_pool_table()` 创建 `stock_pools` 表（pool_id PK, universe, symbols JSON, count, synced_at）
- [x] 1.5 扩展 `data/cache.py`：新增 `init_screening_tables()` 创建 `screening_results` 表（screening_id PK, pool_id FK, universe, total_count, passed_count, excluded_count, dimension_breakdown JSON, created_at）和 `screening_stocks` 表（screening_id FK, symbol, name, passed, exclusion_reasons JSON, market_cap, pe, pb, roe, price）
- [x] 1.6 扩展 `data/cache.py`：新增 `save_stock_pool(universe, symbols)` 和 `get_latest_pool(universe)` 方法
- [x] 1.7 扩展 `data/cache.py`：新增 `save_screening_result(result, pool_id)` 方法，写入 screening_results（含 pool_id）+ screening_stocks 两张表
- [x] 1.6 扩展 `data/cache.py`：新增 `get_latest_screening()`、`get_screening(screening_id)`、`list_screenings(limit)` 查询方法
- [x] 1.7 扩展 `data/datasource.py` 抽象接口：新增 `get_stock_metrics(symbols: List[str]) -> DataFrame`
- [x] 1.8 实现 `data/akshare_source.py` 的 `get_stock_metrics()`：从 akshare 获取市值、PE/PB、行业、上市日期等基础指标，返回统一格式 DataFrame（股票代码转纯数字格式）
- [x] 1.9 实现 `data/baostock_source.py` 的 `get_stock_metrics()`：从 baostock 获取 ROE、负债率、营收、经营现金流等财报指标，返回统一格式 DataFrame（股票代码转纯数字格式）
- [x] 1.10 验证股票代码格式：确认两个数据源实现输出的 symbol 均为纯数字格式（隐性约定兼容检查）

## 2. 数据同步模块

- [x] 2.1 创建 `data/sync.py`：实现 `MetricsSyncer` 类，构造函数接收 DataSource 和 DataCache
- [x] 2.2 实现 `sync_if_stale(symbols)` 方法：检查缓存 TTL → 过期则调用 datasource.get_stock_metrics() → cache.upsert_metrics()，未过期直接返回缓存
- [x] 2.3 实现批量拉取的限流保护：请求间隔 0.3-0.5 秒，失败重试 3 次，记录失败股票
- [x] 2.4 创建 `data/scheduler.py`：实现 `DataScheduler` 类，按顺序执行每日同步流程：同步股票池快照 → 同步慢数据 → 执行预筛
- [x] 2.5 实现 `scheduler.run_daily()` 方法：调用 datasource.get_stock_list → cache.save_stock_pool → syncer.sync_if_stale → screener.screen → cache.save_screening_result(pool_id)
- [x] 2.6 实现过期检测兜底：Pipeline 启动时检查最新 screening_results 是否超过 1 天，超过则触发 scheduler.run_daily()
- [x] 2.7 编写 `data/sync.py` 和 `data/scheduler.py` 单元测试：mock DataSource，验证过期触发同步、未过期跳过、完整每日流程

## 3. 预筛核心引擎

- [x] 3.1 创建 `quant/screener.py`：实现 `StockScreener` 类，构造函数接收 DataCache 和 rules_path
- [x] 3.2 实现 YAML 规则加载：从 `config/quant_rules.yaml` 的 `pre_screen` 段落加载配置
- [x] 3.3 实现 `screen(symbols, realtime_data=None)` 方法：查询 stock_metrics 做慢数据过滤 → 合并 realtime_data 做实时过滤 → 返回 ScreenResult(passed, excluded, stats)
- [x] 3.4 实现 8 个维度的独立过滤方法：_filter_status、_filter_market_cap、_filter_liquidity、_filter_valuation、_filter_profitability、_filter_financial_health、_filter_price、_filter_limit
- [x] 3.5 实现统计输出：统计每个维度的淘汰数量，返回 dimension_breakdown
- [x] 3.6 编写 `quant/screener.py` 单元测试：构造 mock 数据，测试各维度过滤逻辑、边界值、全通过/全失败场景

## 4. Pipeline 集成

- [x] 4.1 更新 `workflow/pipeline.py`：在 `run()` 方法中插入预筛步骤（get_stock_list → sync_if_stale → screener.screen → save_screening_result to DB → agents.analyze(从DB读取)）
- [x] 4.2 实现 LLM 从 DB 读取候选池：agents 通过 screening_id 查询 screening_stocks 表获取 passed stocks
- [x] 4.3 实现断点恢复：pipeline 启动时检测最新 screening_results，如果未过期且 LLM 未完成则复用预筛结果
- [x] 4.4 添加 `skip_screener` 参数支持：`run(universe, skip_screener=False)` 用于调试和对比
- [x] 4.5 验证完整流程：用 mock 数据跑通 pipeline，确认预筛结果正确落盘、LLM 从 DB 读取
- [x] 4.6 更新 `run.py` CLI 入口：支持 `--skip-screener` 参数

## 5. FastAPI 接口

- [x] 5.1 创建 `api/routers/screener.py`：定义 4 个端点（POST /run、GET /result、GET /stats、GET /history）
- [x] 5.2 在 `api/schemas.py` 新增 Pydantic 模型：ScreenRequest、ScreenResultResponse、ScreenStatsResponse、ScreeningSummary
- [x] 5.3 在 `api/main.py` 注册 screener router
- [x] 5.4 实现异步任务执行：POST /run 触发后台预筛任务，返回 task_id
- [x] 5.5 编写 `api/routers/screener.py` 测试：用 TestClient 验证 3 个端点的请求/响应格式

## 6. React 前端

- [x] 6.1 在 `web/src/services/api.ts` 新增预筛 API 调用：triggerScreening()、getScreeningResult()、getScreeningStats()、getScreeningHistory()
- [x] 6.2 在 `web/src/types/index.ts` 新增 TypeScript 类型：ScreeningResult、ScreeningStats、ScreeningStock、ScreeningSummary
- [x] 6.3 在 `web/src/stores/` 新增 `useScreenerStore.ts`：管理预筛结果状态（Zustand）
- [x] 6.4 创建 `web/src/pages/Screening/` 目录结构：index.tsx（主页面）、ScreeningStats.tsx（统计卡片）、ScreeningTable.tsx（结果表格）、ScreeningHistory.tsx（历史对比）
- [x] 6.5 实现 ScreeningStats 组件：3 个统计卡片（原始/通过/被过滤数量）
- [x] 6.6 实现 ScreeningTable 组件：Ant Design Table，列包含 symbol、name、market_cap、PE、PB、ROE、price、状态，支持排序和筛选
- [x] 6.7 实现维度淘汰统计图表：ECharts 横向柱状图，展示各维度淘汰数量
- [x] 6.8 实现 ScreeningHistory 组件：历史预筛记录列表，支持日期选择和对比
- [x] 6.9 在导航栏新增「预筛分析」入口，位于「选股看板」和「回测分析」之间
- [x] 6.10 在 App.tsx 注册 /screening 路由

## 7. 集成验证

- [x] 7.1 端到端验证：启动后端 + 前端，在 Dashboard 触发预筛，确认数据流转正确
- [x] 7.2 数据格式兼容验证：确认 stock_metrics 表输出的 symbol 为纯数字格式，与上层模块兼容
- [x] 7.3 运行 `pytest tests/ -v`，确认所有新增测试通过，现有测试不受影响
