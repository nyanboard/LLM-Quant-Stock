#!/usr/bin/env python3
"""
上下文变更保护 Hook：确保 Bash 命令在 OpenSpec change 上下文中执行
"""
import json
import os
import sys

data = json.load(sys.stdin)
tool_input = data.get("tool_input", {})
cmd = tool_input.get("command", "") or ""

safe_prefixes = [
    "git status",
    "git diff",
    "git log",
    "pytest",
    "python -m pytest",
    "black",
    "mypy",
    "pip",
    "ls",
]

if any(cmd.startswith(p) for p in safe_prefixes):
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "allow",
            "permissionDecisionReason": "安全命令，允许执行"
        }
    }))
    sys.exit(0)

change_dir = "openspec/changes"
has_change = os.path.isdir(change_dir) and any(
    os.path.isdir(os.path.join(change_dir, x))
    for x in os.listdir(change_dir)
    # 排除 archive 和 README
    if x not in ("archive", "README.md")
)

if not has_change:
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "ask",
            "permissionDecisionReason": "当前未检测到 OpenSpec change，请确认是否继续"
        }
    }))
    sys.exit(0)

print(json.dumps({
    "hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "allow",
        "permissionDecisionReason": "已检测到 OpenSpec change"
    }
}))
