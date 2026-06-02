## Why

当前数据模型设计了 4 张表（stock_metrics、stock_pools、screening_results、screening_stocks）来支持预筛历史记录和追溯，但实际使用中：
1. 用户只关注当前最新指标，不回看历史预筛结果
2. LLM 深度分析阶段可以直接通过 SQL 条件过滤（PE > x, ROE > y），不需要独立的预筛流程
3. 多表关联增加了同步逻辑的复杂度，却未带来实际价值

## What Changes

- **BREAKING**: 删除 `screening_results` 表和 `screening_stocks` 表（预筛历史记录不再保留）
- **BREAKING**: 删除 `stock_pools` 表（股票池快照不再需要）
- **BREAKING**: 将实时行情字段（is_st, is_suspended, is_limit_up, is_limit_down, price, turnover_rate, avg_amount）合并进 `stock_metrics` 表，形成全量宽表
- 移除 `quant/screener.py`（StockScreener）独立预筛引擎，过滤逻辑由 LLM 分析阶段按需 SQL 查询完成
- 简化 `data/scheduler.py`（DataScheduler）编排流程：同步股票池 → 同步全量指标（含实时）→ 写入 stock_metrics
- 简化 `api/routers/screener.py` 端点：从"触发预筛+查结果"模式改为"触发全量同步+查询指标"模式
- 更新前端筛选页面：从展示预筛结果改为直接查询 stock_metrics 并动态过滤

## Capabilities

### New Capabilities
- `unified-metrics-sync`: 统一的全量指标同步能力——一次同步将慢数据（PE/PB/ROE 等）和实时数据（ST/停牌/涨跌停/价格/换手率/成交额）合并写入 stock_metrics 宽表
- `data-sync-ui`: 数据同步管理前端页面——提供股票池选择、同步数据查询展示、手动触发同步、定时同步开关等功能

### Modified Capabilities
（无现有 specs 需要修改——项目尚未建立 specs）

## Impact

- **数据库**: 删除 3 张表（stock_pools, screening_results, screening_stocks），扩展 stock_metrics 表结构（+7 个字段）
- **数据层**: `data/cache.py` 删除 screening/pools 相关方法，新增实时字段写入；`data/sync.py` 合并实时数据同步；`data/scheduler.py` 简化编排流程
- **量化层**: `quant/screener.py` 整体移除
- **API 层**: `api/routers/screener.py` 端点重写，`api/schemas.py` 响应模型调整
- **前端**: 筛选页面改为动态查询模式，历史记录功能移除
- **数据迁移**: 需要重建 stock_metrics 表（DROP + CREATE），旧数据库数据不兼容需重新同步
