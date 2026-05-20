---
name: prepare-review
description: 在 review 或提 PR 前，整理一份选股系统变更摘要
disable-model-invocation: true
---

# 生成评审摘要

## 输入
`$ARGUMENTS` = OpenSpec 的 change id

## 必读文件
- `openspec/changes/$ARGUMENTS/proposal.md`
- `openspec/changes/$ARGUMENTS/design.md`
- `openspec/changes/$ARGUMENTS/tasks.md`
- 相关源码改动
- `docs/standards/testing.md`
- `docs/standards/quant_rules.md`
- `docs/standards/agent_rules.md`

## 输出内容
- 本次变更的目标
- 影响到的模块和文件
- 是否涉及 Agent 提示词、量化规则、数据管道、回测引擎
- 已运行测试
- 是否进行了回测对比
- 已知风险
- 仍未解决的问题

## 规则
- 不要写空洞表扬
- 保持简洁、事实化
- 优先标出风险和未完成项
