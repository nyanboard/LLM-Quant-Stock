# LLM-Quant-Stock 项目蓝图总览

> 面向 A 股的 LLM 多Agent选股 + 量化二次筛选系统 | 生成日期：2026-05-20

---

## 一句话定位

用 LLM 做定性分析（读财报、理解新闻），用量化指标做精确筛选，两层叠在一起从几百只股票里筛出 3-5 只标的。

---

## 核心流程

```
股票池（沪深300/中证500）
        │  300~500只
        ▼
┌─────────────────────────┐
│ 预筛层：基础量化粗筛      │  300只 → 50~100只
│ ST/市值/流动性/财务健康   │  用确定性规则快速排除不合格标的
│ /估值/盈利/价格           │  减少 LLM 调用量 60~80%
└────────┬────────────────┘
         │ 粗筛后候选池
         ▼
┌─────────────────────────┐
│ 第一层：LLM 多Agent选股  │  50~100只 → 5~20只
│ 基本面/情绪/新闻 并行分析 │
│ → 多空辩论 → 基金经理决策 │
└────────┬────────────────┘
         │ 初选名单 + 评分
         ▼
┌─────────────────────────┐
│ 第二层：量化二次筛选      │  5~20只 → 3~5只
│ RSI/MACD/KDJ + K线形态   │
│ + 资金流向 → 综合评分     │
└────────┬────────────────┘
         │ 最终标的
         ▼
    回测验证 → 报告输出
```

---

## 5 个 Agent 职责

| Agent | 干什么 | 输出 |
|-------|--------|------|
| **基本面分析师** | 读财报（营收、利润、ROE、负债率） | 财务健康分 1-10 |
| **情绪分析师** | 看新闻标题、股吧、龙虎榜 | 情绪分 1-10 + 情绪标签 |
| **新闻分析师** | 公司公告、行业政策、宏观数据 | 政策影响分 1-10 |
| **多空研究员** | 拿上面三个结果进行辩论（2-3轮） | 多空论据 + 共识/分歧 |
| **基金经理** | 综合所有分析做最终决策 | 初选名单 5-20 只 + 评分 |

Agent 协作顺序：**基本面/情绪/新闻（并行）→ 多空辩论 → 基金经理决策**

---

## 预筛层（新增）

在进入 LLM 分析之前，先用确定性规则快速排除不合格标的，减少 LLM 调用量和成本。

| 维度 | 典型规则 | 目的 |
|------|---------|------|
| **上市状态** | 排除 ST/\*ST、退市风险警示、停牌、次新股（<1年） | 避免不可交易标的 |
| **市值** | 50亿 ~ 5000亿（可配置） | 过滤流动性差的小盘和盘子太大的 |
| **流动性** | 日均成交额 > 3000万，换手率 > 0.5% | 确保能进出 |
| **估值** | PE > 0 且 < 100，PB > 0 且 < 20 | 排除亏损股和泡沫股 |
| **盈利能力** | 最近一期 ROE > 3%，营收 > 0 | 基本赚钱能力 |
| **财务健康** | 资产负债率 < 80%，经营现金流为正 | 排除高负债/造血能力差的 |
| **价格** | 股价 > 2元 | 排除低价仙股 |
| **涨跌停** | 非涨停/跌停状态 | 避免追涨杀跌 |

代码位置：`quant/screener.py`，规则配置在 `config/quant_rules.yaml` 的 `pre_screen` 段落。

### 预筛结果持久化

每次预筛结果写入 SQLite 的两张表，形成完整数据链路：

```
stock_pools（定时任务每日同步）       screening_results（每次预筛一条）
├── pool_id (PK)                      ├── screening_id (PK)
├── universe                          ├── pool_id (FK → stock_pools)
├── symbols (JSON数组)                ├── universe
├── count                             ├── total/passed/excluded count
├── synced_at                         ├── dimension_breakdown (JSON)
                                      ├── created_at

screening_stocks（每只股票一条）
├── screening_id (FK)
├── symbol, name
├── passed (0/1)
├── exclusion_reasons (JSON)
├── market_cap, pe, pb, roe, price
```

数据链路：`stock_pools → screening_results → [LLM] → agent_results → [量化] → final_picks`
每条记录是**时点快照**，不可变，不同日期结果可以不同。好处：断点恢复、历史可查、回测可回放。

### 每日定时同步

每日收盘后（15:30，可配置）自动执行 `data/scheduler.py`：

```
Step 1: 同步股票池快照 → stock_pools 表（HS300 成分股列表）
Step 2: 同步慢数据指标 → stock_metrics 表（市值/PE/ROE/财报）
Step 3: 执行预筛 → screening_results + screening_stocks 表
```

Pipeline 启动时如果检测到数据过期（>1天），自动补跑同步。也可通过 `POST /api/v1/screener/run` 手动触发。

### 预筛数据策略：本地缓存 + 实时补查

预筛需要的数据分为两类，采用**混合策略**避免全量实时查询：

| 数据类型 | 变化频率 | 策略 | 存储位置 |
|---------|---------|------|---------|
| 市值、PE/PB、ROE、负债率、现金流、上市日期 | 日更/季更 | **每日同步到 SQLite** | data/cache/stock_data.db |
| ST状态、停牌、涨跌停、实时价格、换手率 | 实时 | **实时查 + 5分钟短缓存** | 内存缓存 |

**运行时流程**：

```
run.py --universe hs300
    │
    ├─ 1. 检查慢数据缓存是否过期（TTL=1天）
    │     过期 → 批量拉取300只的市值/PE/财报写入 SQLite（stock_metrics 表）
    │     未过期 → 跳过，直接查 SQLite
    │
    ├─ 2. 预筛主体：查 SQLite 做市值/估值/财务过滤（毫秒级，零API调用）
    │
    └─ 3. 实时补查：仅对粗筛后的50~100只查 ST/停牌/涨跌停/价格
          API调用量从300只降到50~100只，不会被限流
```

代码位置：`data/cache.py` 扩展 `stock_metrics` 表，`data/sync.py` 新增每日同步逻辑。

---

## 量化评分权重

```
综合评分 = LLM评分×40% + 技术指标×30% + 形态信号×20% + 资金流×10%
```

技术指标：RSI、MACD、均线(5/10/20/60)、布林带、KDJ、量比
K线形态：锤子线、吞没、晨星、十字星等（TA-Lib）
一票否决：RSI>85（极度超买）、跌停

---

## 系统分层架构

```
┌──────────────┐
│  web/        │  React 前端（Ant Design + ECharts）
├──────────────┤
│  api/        │  FastAPI 薄 API 层，只做转发
├──────────────┤
│  workflow/   │  流程编排，串联各层，不写核心逻辑
├──────────────┤
│  agents/     │  LLM Agent 层（定性分析）
├──────────────┤
│  quant/      │  量化层（预筛、技术指标、形态、评分）
├──────────────┤
│  data/       │  数据层（akshare + baostock + SQLite缓存/同步）
├──────────────┤
│  backtest/   │  回测层（策略回测、绩效报告）
├──────────────┤
│  config/     │  配置层（全局配置、提示词模板、筛选规则）
└──────────────┘
```

**依赖方向**：workflow → agents/quant → data，agents 和 quant 互不依赖。流程：`股票池 → quant/screener（预筛）→ agents（LLM）→ quant/filters+scorer（二次筛选）`

---

## 技术栈

| 类别 | 选型 |
|------|------|
| 后端 | Python 3.10+ / FastAPI / Pydantic |
| 前端 | React 18 / TypeScript / Vite / Ant Design 5 / ECharts 5 |
| 状态管理 | Zustand |
| LLM | DeepSeek-V3/R1（主）、Qwen（备） |
| Agent框架 | LangGraph |
| 数据源 | baostock（历史K线）、akshare（实时行情、新闻、资金流） |
| 技术指标 | TA-Lib |
| 回测 | backtrader |
| 缓存 | SQLite |
| 测试 | pytest |

---

## 数据源分工

| 数据类型 | 主数据源 | 说明 |
|---------|---------|------|
| 历史日K线 | baostock | 稳定、复权准确 |
| 实时行情 | akshare | 覆盖广、免费 |
| 财报数据 | baostock | 利润表、资产负债表、现金流 |
| 新闻/公告 | akshare | 个股新闻、公告 |
| 资金流向 | akshare | 主力资金、龙虎榜 |

---

## 前端页面

| 页面 | 功能 |
|------|------|
| Dashboard | 首页看板，选股摘要 + 最近回测绩效 |
| **Screening** | **预筛分析（独立页面）：统计卡片 + 维度淘汰图表 + 结果表格 + 历史对比** |
| StockResult | 选股结果表格 + K线图 + Agent评分雷达图 |
| Backtest | 回测净值曲线 + 基准对比 + 绩效指标 |
| AgentView | Agent 分析时间线，查看每个 Agent 的推理过程 |
| Settings | 系统配置（LLM参数、权重、筛选规则） |

导航栏：`Logo | 选股看板 | 预筛分析 | 回测分析 | Agent详情 | 系统配置`

---

## 关键隐性约定（容易踩坑）

- **股票代码格式**：内部统一用纯数字（`000001`），数据层做转换，不在 Agent/Quant 层转换
- **复权**：回测必须用前复权（qfq）数据，实时分析用不复权
- **停牌**：数据层标记停牌状态，选股流程必须过滤
- **Agent 输出**：score 1-10，confidence 0-1，reasoning 中文，格式变更必须改测试
- **前视偏差**：禁止使用未来数据，回测必须验证

---

## 实施阶段

| 阶段 | 内容 | 预估 |
|------|------|------|
| Phase 1 | 项目骨架 + 数据层 + BaseAgent + 预筛层 | 第1-2周 |
| Phase 2 | 5个Agent实现 + 提示词调优 | 第3-4周 |
| Phase 3 | 量化筛选层（指标+形态+规则引擎+评分） | 第5周 |
| Phase 4 | Pipeline编排 + 回测引擎 + 报告 | 第6周 |
| Phase 5 | Prompt调优 + 参数优化 + 性能优化 | 第7-8周 |

---

## 当前实现状态（2026-05-20）

### 已完成
- [x] 项目目录结构和架构设计
- [x] CLAUDE.md / AGENTS.md 项目规则
- [x] OpenSpec 工作流骨架
- [x] 配置管理（config/settings.py, quant_rules.yaml）
- [x] Agent 提示词模板（config/prompts/）
- [x] Agent 基类和信号格式（agents/base.py）
- [x] 技术指标计算骨架（quant/indicators.py）
- [x] K线形态识别骨架（quant/patterns.py）
- [x] 评分排序骨架（quant/scorer.py）
- [x] FastAPI 路由结构（api/routers/）
- [x] React 前端骨架（web/）

### 未实现（核心缺口）
- [ ] 预筛模块（quant/screener.py）
- [ ] 股票池快照表（data/cache.py stock_pools）
- [ ] 预筛数据同步（data/sync.py）+ stock_metrics 表（data/cache.py）
- [ ] 每日定时同步（data/scheduler.py）
- [ ] LLM 实际调用（agents 的 _call_llm 是占位方法）
- [ ] 数据批量获取（pipeline 的 _batch_fetch_data 为空）
- [ ] 量化分析执行（pipeline 的 _quant_analyze 为空）
- [ ] 回测引擎（backtest/ 基本为空）
- [ ] 测试用例（tests/ 目录为空）
- [ ] WebSocket 实时推送

### 风险提醒
1. 无测试覆盖，任何改动无法自动验证
2. LLM 未接入，整个第一层选股无法运行
3. 数据抓取未实现，无法获取真实数据
4. 加入预筛层后，成本预估 ~0.2-0.4元/次（粗筛后仅 50-100 只进 LLM）

---

## 常用命令速查

```bash
pytest tests/ -v                          # 跑测试
python run.py --universe hs300            # 运行选股（沪深300）
python -m backtest.runner --strategy llm_quant --period 2024-01-01:2024-12-31  # 回测
uvicorn api.main:app --reload --port 8000 # 启动后端
cd web && npm run dev                     # 启动前端
cd web && npm run build                   # 构建前端
```

---

## 详细文档索引

| 文档 | 路径 | 内容 |
|------|------|------|
| 系统设计详案 | docs/system_design.md | 完整设计（700+行） |
| 架构总览 | docs/architecture/index.md | 分层、依赖方向、模块职责 |
| 隐性约定 | docs/architecture/implicit-contracts.md | 股票代码、复权、停牌等坑 |
| 测试规范 | docs/standards/testing.md | 测试要求 |
| 量化规范 | docs/standards/quant_rules.md | 量化策略规则 |
| Agent规范 | docs/standards/agent_rules.md | Agent 开发规范 |
| 配置参考 | docs/settings_reference.md | Claude settings 配置 |
