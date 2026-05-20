# Agent 开发规范

## 基本规则
- 每个 Agent 独立一个文件，继承 BaseAgent 基类
- Agent 的提示词必须放在 `config/prompts/` 目录下的模板文件中
- Agent 输出必须遵循统一的 AgentSignal 数据类
- Agent 不允许直接调用外部 API，必须通过数据层获取数据
- Agent 不允许直接调用 TA-Lib，量化计算由 quant 层负责

## Agent 生命周期

```
初始化 → 加载提示词模板 → 获取数据 → 构建上下文 → 调用LLM → 解析输出 → 返回信号
```

## 新增 Agent 检查清单
- [ ] 继承 BaseAgent 基类
- [ ] 提示词模板放在 `config/prompts/<agent_name>.md`
- [ ] 输出遵循 AgentSignal 数据类
- [ ] 通过数据层获取数据，不直接调用 API
- [ ] 包含单元测试（mock LLM 响应）
- [ ] 在 `config/settings.py` 中注册 Agent 配置
- [ ] 更新 `docs/architecture/index.md` 中的模块说明

## 提示词模板规范
- 使用 Markdown 格式
- 必须包含：角色定义、输入格式说明、输出格式要求、评分标准
- 输出格式要求必须指定 JSON 结构
- 禁止在模板中硬编码具体股票名称或日期
- 变量使用 `{{variable}}` 格式

## 多 Agent 协作
- 分析师 Agent 之间并行执行，互不依赖
- 多空研究员依赖所有分析师的信号
- 基金经理依赖研究员的辩论结果
- 协作流程通过 `workflow/pipeline.py` 编排，Agent 自身不感知流程

## LLM 调用规范
- 调用失败时必须重试（最多 3 次，指数退避）
- 必须处理 LLM 输出格式异常（JSON 解析失败时降级处理）
- 必须记录 token 使用量，用于成本监控
- 同一请求的 LLM 响应必须缓存，避免重复调用
