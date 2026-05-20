# AGENTS.md
## 项目说明
本仓库采用 harness 风格工作流，构建面向 A 股的 LLM 多Agent选股 + 量化二次筛选系统：
- OpenSpec 负责定义需求与变更工件
- Claude Code 在项目规则内执行
- 实现与评审分离
- Hooks、权限负责硬约束

## 首先阅读
1. `docs/architecture/index.md` — 系统架构总览
2. `docs/architecture/implicit-contracts.md` — 隐性约定与数据坑点
3. `docs/standards/testing.md` — 测试规范
4. `docs/standards/quant_rules.md` — 量化策略与数据规范
5. `docs/standards/agent_rules.md` — Agent 开发规范
6. `openspec/specs/` — 系统当前工作方式
7. `openspec/changes/<change-id>/` — 当前变更

## 工作规则
- 没有 OpenSpec change，不允许直接开始开发
- 不允许超出 `tasks.md` 自行扩需求
- 每完成一个里程碑，都必须运行相关检查
- 修改数据管道、量化策略、Agent提示词时，必须明确说明影响范围
- 合并前必须经过 review 和 verify
- 涉及金融数据处理的变更，必须说明数据来源和时效性

## 受保护目录
- `config/secrets/`
- `config/api_keys/`
- `data/cache/`
- `output/reports/`

## 主流程命令
- 新需求：`/opsx:propose`
- 实施：`/opsx:apply`
- 校验：`/opsx:verify`
- 归档：`/opsx:archive`
- 运行：`python run.py --universe hs300`
- 测试：`pytest tests/ -v`
- 回测：`python -m backtest.runner --strategy llm_quant`
