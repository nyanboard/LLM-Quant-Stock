# 测试规范

## 最低要求
- Agent 输出格式变更：至少补 1 个对应测试
- 量化指标计算：必须补单元测试，含边界值测试
- 数据获取接口：必须 mock 外部 API 测试
- 策略/规则变更：必须跑历史回测对比
- 提示词模板修改：至少跑 3 个样本验证输出格式和内容

## 测试分层

| 层级 | 测试类型 | 工具 | 说明 |
|------|---------|------|------|
| `data/` | 单元测试 | pytest + mock | mock 外部 API，测试数据转换、缓存逻辑 |
| `agents/` | 单元测试 | pytest + mock | mock LLM 响应，测试输出格式、评分逻辑 |
| `quant/` | 单元测试 | pytest | 测试指标计算正确性（含已知数据的期望值） |
| `workflow/` | 集成测试 | pytest | 测试完整流程串联（可用 mock 替换 LLM 和数据源） |
| `backtest/` | 回归测试 | pytest + backtrader | 对比历史策略绩效，检测偏差 |

## 常用命令
- 全量测试：`pytest tests/ -v`
- 单模块测试：`pytest tests/test_agents/ -v`
- 带覆盖率：`pytest tests/ --cov=llm_quant_stock --cov-report=term-missing`
- 类型检查：`mypy llm_quant_stock/ --ignore-missing-imports`

## 评审要求
提交 review 时必须说明：
- 跑了哪些测试
- 哪些部分没有测
- 为什么跳过这些检查仍然可以接受
- 是否进行了回测对比（如涉及策略变更）

## 数据 Mock 规范
- mock 外部 API 时，使用真实的响应结构（可脱敏）
- 禁止使用空的或过于简单的 mock 数据
- 金融数据 mock 必须包含：时间戳、OHLCV、复权标志
