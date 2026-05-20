## Why

当前系统将 300~500 只股票直接丢给 LLM Agent 分析，成本高（~1元/次）、速度慢（数百次 LLM 调用）。需要在 LLM 分析之前增加一个量化预筛层，用确定性规则快速排除不合格标的（ST、停牌、市值过小、财务不健康等），将 LLM 调用量减少 60-80%，成本降至 ~0.3元/次。

## What Changes

- 新增 `quant/screener.py` 预筛模块，基于 `config/quant_rules.yaml` 的 `pre_screen` 配置执行 8 个维度的基础筛选
- 新增 `data/sync.py` 预筛数据同步器，每日批量拉取慢数据（市值、PE/PB、ROE 等）写入 SQLite `stock_metrics` 表
- 扩展 `data/cache.py`，新增 `stock_metrics` 专用表和批量查询接口
- 扩展 `data/datasource.py` 抽象接口，新增 `get_stock_metrics()` 批量获取方法
- 扩展 `data/akshare_source.py` 和 `data/baostock_source.py`，实现 `get_stock_metrics()`
- 更新 `workflow/pipeline.py`，在 LLM Agent 分析前插入预筛步骤
- 新增 FastAPI 接口：触发预筛、查看预筛结果、预筛统计
- 新增 React 前端页面：预筛结果展示（表格 + 统计卡片），集成到 Dashboard

## Capabilities

### New Capabilities

- `pre-screening`: 量化预筛核心逻辑（screener 规则引擎 + 数据同步 + API + 前端展示）

### Modified Capabilities

（无现有 specs 需要修改）

## Impact

- **数据层**：`data/cache.py` 新增 `stock_metrics` 表；`data/datasource.py` 接口扩展；两个数据源实现需补充 `get_stock_metrics()`
- **量化层**：`quant/` 新增 `screener.py`，与现有 `filters.py`（LLM 后筛选）并行但独立
- **编排层**：`workflow/pipeline.py` 流程从 `get_stock_list → agents` 变为 `get_stock_list → screener → agents`
- **API 层**：新增 2-3 个 REST 端点 + 1 个 WebSocket 事件（预筛进度）
- **前端**：Dashboard 新增预筛统计区域，新增预筛结果详情视图
- **配置**：`config/quant_rules.yaml` 已包含 `pre_screen` 段落（本轮直接使用）
- **隐性约定**：不影响现有隐性约定（股票代码格式、复权、评分范围等均不变）
