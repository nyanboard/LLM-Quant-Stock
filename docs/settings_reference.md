# Claude Settings 参考

> 复制此内容到 `.claude/settings.json`（需手动创建）

```json
{
  "defaultMode": "default",
  "permissions": {
    "allow": [
      "Bash(pytest *)",
      "Bash(python -m pytest *)",
      "Bash(python -c *)",
      "Bash(black *)",
      "Bash(mypy *)",
      "Bash(git status)",
      "Bash(git diff *)",
      "Bash(git log *)",
      "Bash(ls *)",
      "Bash(pip list*)"
    ],
    "ask": [
      "Bash(*)",
      "Edit(*)",
      "Write(*)"
    ],
    "deny": [
      "Bash(git push *)",
      "Bash(rm -rf *)",
      "Read(config/secrets/**)",
      "Edit(config/secrets/**)",
      "Write(config/secrets/**)",
      "Edit(config/api_keys/**)",
      "Write(config/api_keys/**)"
    ]
  },
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [
          {
            "type": "command",
            "command": "python .claude/hooks/guard_write.py",
            "timeout": 10
          }
        ]
      },
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "python .claude/hooks/ensure_change_context.py",
            "timeout": 10
          }
        ]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [
          {
            "type": "command",
            "command": "bash .claude/hooks/run_checks.sh",
            "timeout": 120
          }
        ]
      }
    ]
  }
}
```
