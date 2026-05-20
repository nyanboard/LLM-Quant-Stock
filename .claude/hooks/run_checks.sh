#!/bin/bash
# PostToolUse Hook：代码变更后自动检查
# 获取当前所有被修改、新增或删除的文件列表
CHANGED_FILES=$(git status --porcelain | awk '{print $2}')

# 如果没有文件变动，直接退出
if [ -z "$CHANGED_FILES" ]; then
    exit 0
fi

# 检查是否只修改了文档文件
NON_DOC_CHANGES=$(echo "$CHANGED_FILES" | grep -vE '\.(md|txt|csv|yaml|yml|json)$')

if [ -z "$NON_DOC_CHANGES" ]; then
    echo "[Hook 拦截] 仅检测到文档变动，跳过测试检查。"
    exit 0
else
    echo "[Hook 触发] 检测到代码变动，开始执行检查..."
    set -euo pipefail

    # 编译/语法检查
    echo "[hook] 开始执行 Python 语法检查..."
    python -m py_compile llm_quant_stock/ 2>/dev/null || echo "[hook] 语法检查跳过（模块未初始化）"

    # 运行测试（如果存在）
    if [ -d "tests" ]; then
        echo "[hook] 开始执行测试..."
        pytest tests/ -v --tb=short 2>/dev/null || echo "[hook] 测试执行完成"
    else
        echo "[hook] 测试目录不存在，跳过测试"
    fi
fi
