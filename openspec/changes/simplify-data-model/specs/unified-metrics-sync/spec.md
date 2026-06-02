## ADDED Requirements

### Requirement: 全量指标同步写入宽表
MetricsSyncer SHALL 在一次同步中将慢数据（PE/PB/ROE/市值/负债率/营收/现金流）和实时数据（ST 状态/停牌/涨跌停/价格/换手率/成交额）合并写入 stock_metrics 表。

#### Scenario: 慢数据和实时数据均成功获取
- **WHEN** 调用 sync_if_stale(symbols)，且主数据源和实时数据源均正常返回
- **THEN** stock_metrics 表中每只股票包含完整的慢数据字段和实时字段，synced_at 更新为当前时间戳

#### Scenario: 实时数据源不可用
- **WHEN** AkShare 实时行情接口失败（网络错误、限流等）
- **THEN** 慢数据字段正常写入，实时字段（is_st, is_suspended, is_limit_up, is_limit_down, price, turnover_rate, avg_amount）设为 NULL，不阻塞同步流程

#### Scenario: 缓存未过期
- **WHEN** 调用 sync_if_stale(symbols, ttl=86400)，且 stock_metrics 中所有 symbols 的 synced_at 均在 TTL 内
- **THEN** 直接返回缓存数据，不调用外部 API

### Requirement: stock_metrics 表包含实时行情字段
stock_metrics 表 SHALL 包含以下实时行情字段：is_st (INTEGER, 0/1)、is_suspended (INTEGER, 0/1)、is_limit_up (INTEGER, 0/1)、is_limit_down (INTEGER, 0/1)、price (REAL)、turnover_rate (REAL)、avg_amount (REAL)。

#### Scenario: 表初始化
- **WHEN** 首次调用 init_metrics_table()
- **THEN** 创建包含 symbol + 慢数据字段 + 实时字段的完整宽表，symbol 为主键

#### Scenario: 已有旧表缺少实时字段
- **WHEN** 数据库中的 stock_metrics 表缺少实时字段列
- **THEN** init_metrics_table() SHALL 通过 ALTER TABLE ADD COLUMN 补齐缺失字段（兼容已有数据）

### Requirement: 删除预筛相关表
系统 SHALL 不再创建 stock_pools、screening_results、screening_stocks 三张表。对应的 init 方法、写入方法、查询方法 SHALL 从 DataCache 中移除。

#### Scenario: 首次启动（全新数据库）
- **WHEN** 应用启动并初始化数据库
- **THEN** 只创建 stock_metrics 表，不创建 stock_pools / screening_results / screening_stocks 表

#### Scenario: 已有旧数据库包含这些表
- **WHEN** 应用启动时检测到数据库中存在 stock_pools / screening_results / screening_stocks 表
- **THEN** 自动 DROP 这些表并记录日志（开发阶段，无需数据迁移）

### Requirement: 同步流程简化为拉取全 A 指标
DataScheduler.run_daily() SHALL 简化为：获取全 A 股票列表 → 调用 MetricsSyncer 同步全量指标写入 stock_metrics。不再执行独立的预筛步骤。

#### Scenario: 执行每日同步
- **WHEN** 调用 scheduler.run_daily()
- **THEN** 从 AkShare 获取全 A 股票代码列表，调用 syncer.sync_if_stale(symbols) 同步所有指标，不执行 StockScreener

### Requirement: API 端点改为同步触发 + 指标查询
API SHALL 提供 POST /metrics/sync（触发全量同步）和 GET /metrics/query（带条件查询 stock_metrics），替代原有 screener 端点。

#### Scenario: 触发全量同步
- **WHEN** 调用 POST /metrics/sync
- **THEN** 后台执行全量指标同步，立即返回 status="running"

#### Scenario: 带条件查询指标
- **WHEN** 调用 GET /metrics/query?pe_min=5&roe_min=3&is_st=0
- **THEN** 返回满足所有条件的股票指标列表

#### Scenario: 无条件查询全部
- **WHEN** 调用 GET /metrics/query（无过滤参数）
- **THEN** 返回 stock_metrics 中所有股票的最新指标
