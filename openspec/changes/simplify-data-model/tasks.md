## 1. 数据层：stock_metrics 宽表改造

- [x] 1.1 修改 `data/cache.py` 的 `init_metrics_table()`：在 CREATE TABLE 中增加 7 个实时字段（is_st, is_suspended, is_limit_up, is_limit_down, price, turnover_rate, avg_amount）
- [x] 1.2 修改 `data/cache.py` 的 `upsert_metrics()`：metric_cols 列表增加 7 个实时字段，确保 upsert 时写入新字段
- [x] 1.3 修改 `data/cache.py` 的 `get_metrics()`：验证新字段能正确查询返回
- [x] 1.4 从 `data/cache.py` 删除 `init_screening_tables()`、`save_screening_result()`、`get_screening()`、`get_latest_screening()`、`list_screenings()` 方法
- [x] 1.5 从 `data/cache.py` 删除 `init_stock_pools_table()`、`save_stock_pool()`、`get_latest_pool()` 等股票池相关方法
- [x] 1.6 从 `data/cache.py` 的 `init_all_tables()` 中移除对 screening/pools 表初始化的调用
- [x] 1.7 在 `init_metrics_table()` 中增加兼容逻辑：检测已有表是否缺少实时字段，缺少则 ALTER TABLE ADD COLUMN 补齐

## 2. 数据层：同步逻辑改造

- [x] 2.1 修改 `data/sync.py` 的 `MetricsSyncer`：在 `_fetch_with_retry()` 中，拉取慢数据后继续调用 `self.secondary_datasource.get_realtime_quotes(symbols)` 获取实时数据，用 `_merge_metrics()` 合并到同一个 DataFrame
- [x] 2.2 修改 `data/sync.py` 的 `_merge_metrics()`：实时字段（is_st 等）也纳入合并逻辑
- [x] 2.3 修改 `data/akshare_source.py` 的 `get_stock_metrics()`：返回的 DataFrame 中增加实时行情字段列（从 get_realtime_quotes 获取后合并进 get_stock_metrics 结果）
- [x] 2.4 编写单元测试：mock BaoStock + AkShare，验证同步后 stock_metrics 包含慢数据 + 实时字段

## 3. 调度层：简化编排流程

- [x] 3.1 修改 `data/scheduler.py` 的 `DataScheduler`：`run_daily()` 简化为获取全 A 股票列表 → 调用 syncer.sync_if_stale(symbols)，移除预筛步骤和结果保存步骤
- [x] 3.2 修改 `data/scheduler.py`：移除 screener 依赖参数，`__init__` 不再接收 StockScreener
- [x] 3.3 从 `data/scheduler.py` 移除 `save_screening_result` 和 `save_stock_pool` 相关调用
- [x] 3.4 验证：运行 `python -c "from data.scheduler import DataScheduler"` 确认无 import 错误

## 4. 量化层：移除预筛引擎

- [x] 4.1 删除 `quant/screener.py` 文件
- [x] 4.2 检查并移除所有对 `quant.screener` / `StockScreener` 的 import 引用（api/routers/、data/scheduler/、tests/）
- [x] 4.3 删除 `config/quant_rules.yaml` 中的 `pre_screen` 段落（如有其他段落保留）
- [x] 4.4 删除 `quant/screener.py` 相关的测试文件

## 5. API 层：端点重写

- [x] 5.1 重命名 `api/routers/screener.py` 为 `api/routers/metrics.py`，路由前缀改为 `/metrics`
- [x] 5.2 实现 `POST /metrics/sync`：接受 universe 参数，后台触发全量同步，立即返回 `{"status": "running", "sync_id": "..."}`
- [x] 5.3 实现 `GET /metrics/query`：接受 universe + 可选过滤参数（pe_min, pe_max, roe_min, market_cap_min, is_st, is_suspended 等），查询 stock_metrics 返回结果
- [x] 5.4 实现 `GET /metrics/sync/status`：返回当前同步状态（idle/running）、最近同步时间、已同步股票数
- [ ] 5.5 实现 `POST /metrics/sync/schedule`：开启/关闭定时同步，接受 enabled + interval 参数，后端使用 APScheduler 管理定时任务（延后实现，当前通过前端定时器模拟）
- [x] 5.6 删除原有 screener 端点（/run, /result, /stats, /history）
- [x] 5.7 更新 `api/schemas.py`：删除 ScreenRequest/ScreenResultResponse/ScreenStatsResponse/ScreeningSummary/ScreeningStockItem，新增 SyncRequest/SyncStatusResponse/ScheduleRequest/MetricsQueryResponse
- [x] 5.8 更新 `api/main.py`：路由注册从 screener 改为 metrics，移除 screener 相关的 import
- [ ] 5.9 验证：启动 uvicorn，测试 `POST /metrics/sync`、`GET /metrics/query`、`GET /metrics/sync/status` 返回正确数据（需要先关闭占用 DB 的进程）

## 6. 前端：数据同步管理页面

- [x] 6.1 更新 `web/src/services/api.ts`：删除 screener 相关 API 调用，新增 triggerSync()、queryMetrics()、getSyncStatus()、toggleSchedule()
- [x] 6.2 更新 `web/src/types/`：删除 Screening 相关类型，新增 MetricsItem、SyncStatus、SyncSchedule 类型定义
- [x] 6.3 创建 `web/src/stores/useDataSyncStore.ts`（Zustand）：管理同步状态、数据列表、定时配置、loading/error 状态
- [x] 6.4 创建 `web/src/pages/DataSync/index.tsx` 主页面：顶部操作栏（股票池 Select + 立即同步 Button）+ 状态指示器 + 数据表格
- [x] 6.5 创建 `web/src/pages/DataSync/SyncStatus.tsx`：展示当前同步状态（idle/running）、最近同步时间、已同步股票数
- [x] 6.6 创建 `web/src/pages/DataSync/MetricsTable.tsx`：Ant Design Table 展示 stock_metrics 数据，支持分页和列排序
- [x] 6.7 删除旧筛选页面 `web/src/pages/Screening/` 目录及组件
- [x] 6.8 删除旧 screener store `web/src/stores/useScreenerStore.ts`
- [x] 6.9 更新路由配置：将 /screening 路由替换为 /data-sync，指向 DataSync 页面
- [x] 6.10 更新侧边栏导航：将"预筛分析"改为"数据同步"，图标改为 DatabaseOutlined

## 7. 清理与验证

- [ ] 7.1 删除旧数据库文件 `data/cache/stock_data.db`，确认首次运行时自动重建（文件被占用，需关闭占用进程后删除）
- [ ] 7.2 全量运行同步，验证 stock_metrics 宽表包含全 A 数据和完整字段（需要运行环境）
- [x] 7.3 运行 `pytest tests/ -v`，修复因删除代码导致的测试失败（12/12 passed）
- [ ] 7.4 检查 `docs/` 文档中涉及 screener/预筛的描述，更新或删除过时内容
