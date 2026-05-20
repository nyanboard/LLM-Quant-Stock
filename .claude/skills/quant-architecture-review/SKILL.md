---
name: quant-architecture-review
description: 检查系统分层、依赖方向和数据流是否合理
disable-model-invocation: true
---

# 量化系统架构审查

## 输入
`$ARGUMENTS` = 本次改动涉及的文件、目录或 change id

## 检查项
1. workflow/ 是否包含了分析计算逻辑（应该只有编排）
2. agents/ 是否直接调用了 TA-Lib（应该通过 quant 层）
3. quant/ 是否调用了 LLM（应该只做数值计算）
4. agents/ 是否绕过数据层直接调外部 API
5. 是否有硬编码的配置参数（应该在 config/ 中）
6. 提示词是否内嵌在 Python 代码中（应该在 config/prompts/ 中）
7. 是否存在跨层耦合

## 输出格式
- 严重问题
- 警告问题
- 建议项
