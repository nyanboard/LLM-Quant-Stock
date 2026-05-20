@AGENTS.md
# Claude Code 项目规则

## 你的角色
你是一个在 harness 工作流中执行实现和评审任务的代理，负责构建 LLM 选股 + 量化筛选系统。

## 必须遵守的工作流程
1. 开始实现前，必须先阅读对应的 OpenSpec change：
   - `openspec/changes/<change-id>/proposal.md`
   - `openspec/changes/<change-id>/design.md`
   - `openspec/changes/<change-id>/tasks.md`
2. 修改代码前，先总结本次需求范围
3. 只允许实现 `tasks.md` 中明确列出的内容
4. 每完成一个里程碑，必须执行相关检查
5. 最终输出简短总结，包括：
   - 改动了哪些模块/文件
   - 跑了哪些测试
   - 还存在哪些风险

## Python 项目架构规则
- `workflow/` 只负责流程编排，不写核心分析逻辑
- Agent 逻辑必须放在 `agents/` 层，每个 Agent 独立可测试
- 数据获取逻辑必须放在 `data/` 层，通过抽象接口解耦
- 量化计算逻辑必须放在 `quant/` 层，禁止在 Agent 中直接调用 TA-Lib
- 配置参数统一通过 `config/` 管理，禁止在代码中硬编码
- LLM 提示词模板放在 `config/prompts/` 中，禁止内嵌在 Python 代码里
- `api/` 是薄 API 层，只做数据转发和格式转换，不包含业务逻辑

## FastAPI 后端规则
- Router 只负责参数接收、校验和返回，不写核心业务逻辑
- 业务逻辑必须调用 `workflow/` 或 `agents/`/`quant/` 层
- 请求/响应格式通过 `api/schemas.py` 的 Pydantic 模型定义
- WebSocket 用于实时推送 Agent 分析进度
- API 接口必须包含错误处理和合理的 HTTP 状态码
- 长时间运行的任务（选股、回测）必须异步执行，返回 task_id

## React 前端规则
- 页面组件放在 `web/src/pages/`，按功能模块分目录
- 通用组件放在 `web/src/components/`，保持复用性
- API 调用统一通过 `web/src/services/api.ts` 封装
- 状态管理使用 Zustand，store 放在 `web/src/stores/`
- TypeScript 类型定义放在 `web/src/types/`
- ECharts 图表组件统一主题配置在 `web/src/utils/echarts.ts`
- 不允许在组件中直接拼接 API URL，必须通过 services 层
- 表格组件优先使用 Ant Design Table，图表优先使用 ECharts

## 数据与金融规则
- 所有金融数据必须标注来源和获取时间
- 不允许使用未来数据（前视偏差）
- 回测必须使用复权后的价格数据
- 数据缓存必须设置合理的 TTL，避免使用过期数据
- 涉及外部 API 调用时，必须实现重试和降级机制

## 测试规则
- Agent 输出格式变更必须补充对应测试
- 量化指标计算必须补单元测试（含边界值）
- 数据获取接口必须 mock 外部 API 进行测试
- 策略变更必须跑历史回测对比
- 修改提示词模板时，至少跑 3 个样本验证输出格式

## 安全规则
- API Key 禁止硬编码，必须通过环境变量或配置文件读取
- 不允许在日志中输出完整的 API 请求/响应内容
- 不允许执行实盘交易命令（本系统仅供研究）
- 缓存数据不允许包含个人敏感信息

## 常用命令
- 测试：`pytest tests/ -v`
- 类型检查：`mypy llm_quant_stock/ --ignore-missing-imports`
- 格式化：`black llm_quant_stock/ tests/`
- 运行选股：`python run.py --universe hs300`
- 回测：`python -m backtest.runner --strategy llm_quant --period 2024-01-01:2024-12-31`
- 启动后端：`uvicorn api.main:app --reload --port 8000`
- 启动前端：`cd web && npm run dev`
- 前端构建：`cd web && npm run build`
- 前端测试：`cd web && npm test`
