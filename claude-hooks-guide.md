# Claude Code Hooks 完整使用指南

## 目录

- [什么是 Hooks](#什么是-hooks)
- [Hook 事件类型](#hook-事件类型)
- [配置方式](#配置方式)
- [Hook 输入输出](#hook-输入输出)
- [实战示例](#实战示例)
- [安全注意事项](#安全注意事项)
- [调试技巧](#调试技巧)

---

## 什么是 Hooks

Claude Code Hooks 是用户自定义的 shell 命令，在 Claude Code 工作流的特定时刻自动执行。Hooks 让你能够：

- **确定性控制**：确保某些操作总是发生，而不依赖 LLM 的选择
- **自动化工作流**：代码格式化、测试运行、通知等
- **安全防护**：阻止危险操作、保护敏感文件
- **增强功能**：自动注入上下文、记录操作日志

> ⚠️ **安全警告**：Hooks 在代理循环期间使用当前环境凭证自动运行。恶意 hook 可能泄露数据。注册前务必审查实现。

---

## Hook 事件类型

### 1. PreToolUse

**触发时机**：工具调用前（可阻止执行）

**常见匹配器**：
- `Bash` - Shell 命令
- `Read` - 文件读取
- `Edit` - 文件编辑
- `Write` - 文件写入
- `Glob` - 文件模式匹配
- `Grep` - 内容搜索
- `Task` - Subagent 任务
- `WebFetch`/`WebSearch` - Web 操作

**使用场景**：
- 验证命令安全性
- 自动批准安全操作
- 阻止危险操作
- 修改工具输入参数

**输入数据结构**：
```json
{
  "session_id": "abc123",
  "transcript_path": "~/.claude/projects/.../session.jsonl",
  "cwd": "/path/to/project",
  "permission_mode": "default",
  "hook_event_name": "PreToolUse",
  "tool_name": "Write",
  "tool_input": {
    "file_path": "/path/to/file.txt",
    "content": "file content"
  },
  "tool_use_id": "toolu_01ABC123..."
}
```

**控制选项**：
```json
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "allow",  // "allow" | "deny" | "ask"
    "permissionDecisionReason": "理由说明",
    "updatedInput": {  // 可选：修改工具输入
      "field_to_modify": "new value"
    }
  }
}
```

---

### 2. PermissionRequest

**触发时机**：显示权限对话框时

**使用场景**：
- 自动批准安全操作
- 自动拒绝危险操作
- 代替用户做决策

**输入数据结构**：同 PreToolUse

**控制选项**：
```json
{
  "hookSpecificOutput": {
    "hookEventName": "PermissionRequest",
    "decision": {
      "behavior": "allow",  // "allow" | "deny"
      "updatedInput": {  // 可选：修改工具输入
        "command": "npm run lint"
      },
      "message": "拒绝原因",  // deny 时可选
      "interrupt": true  // deny 时可选：停止 Claude
    }
  }
}
```

---

### 3. PostToolUse

**触发时机**：工具成功完成后

**使用场景**：
- 代码格式化（编辑后运行 prettier、eslint）
- 验证输出（检查生成的代码）
- 记录操作日志
- 触发后续操作

**输入数据结构**：
```json
{
  "session_id": "abc123",
  "hook_event_name": "PostToolUse",
  "tool_name": "Write",
  "tool_input": {
    "file_path": "/path/to/file.txt",
    "content": "file content"
  },
  "tool_response": {
    "filePath": "/path/to/file.txt",
    "success": true
  },
  "tool_use_id": "toolu_01ABC123..."
}
```

**控制选项**：
```json
{
  "decision": "block",  // 可选：向 Claude 提供反馈
  "reason": "需要修正的问题说明",
  "hookSpecificOutput": {
    "hookEventName": "PostToolUse",
    "additionalContext": "为 Claude 添加的额外上下文"
  }
}
```

---

### 4. UserPromptSubmit

**触发时机**：用户提交提示时（Claude 处理前）

**使用场景**：
- 注入额外上下文（当前时间、环境信息）
- 验证提示内容
- 阻止敏感信息提交
- 自动添加项目约定

**输入数据结构**：
```json
{
  "session_id": "abc123",
  "hook_event_name": "UserPromptSubmit",
  "prompt": "用户输入的提示内容"
}
```

**添加上下文的两种方式**：

1. **简单方式**：直接打印到 stdout（退出码 0）
```bash
#!/bin/bash
echo "当前时间: $(date)"
echo "项目状态: 所有测试通过"
exit 0
```

2. **JSON 方式**：结构化控制
```json
{
  "decision": "block",  // 可选：阻止提示处理
  "reason": "阻止原因（显示给用户）",
  "hookSpecificOutput": {
    "hookEventName": "UserPromptSubmit",
    "additionalContext": "注入的上下文内容"
  }
}
```

---

### 5. Notification

**触发时机**：Claude Code 发送通知时

**常见匹配器**：
- `permission_prompt` - 权限请求
- `idle_prompt` - 等待用户输入（空闲 60 秒后）
- `auth_success` - 认证成功
- `elicitation_dialog` - MCP 工具引出

**使用场景**：
- 自定义通知方式（桌面通知、声音提示）
- 记录通知历史
- 触发自动化流程

**输入数据结构**：
```json
{
  "session_id": "abc123",
  "hook_event_name": "Notification",
  "message": "Claude needs your permission to use Bash",
  "notification_type": "permission_prompt"
}
```

---

### 6. Stop

**触发时机**：主 Claude Code agent 完成响应时（用户中断不触发）

**使用场景**：
- 智能判断任务是否真正完成
- 强制继续未完成的工作
- 检查错误状态

**输入数据结构**：
```json
{
  "session_id": "abc123",
  "hook_event_name": "Stop",
  "stop_hook_active": true  // 是否已因 stop hook 继续过
}
```

**控制选项**：
```json
{
  "decision": "block",  // 阻止停止
  "reason": "必须继续的原因（提供给 Claude）"
}
```

---

### 7. SubagentStop

**触发时机**：Subagent（Task 工具调用）完成响应时

**使用场景**：与 Stop 类似，但针对子任务

**输入数据结构**：同 Stop

---

### 8. PreCompact

**触发时机**：压缩操作前

**匹配器**：
- `manual` - 从 `/compact` 调用
- `auto` - 自动压缩（上下文窗口满）

**使用场景**：
- 保存重要上下文
- 记录压缩历史
- 触发备份

**输入数据结构**：
```json
{
  "session_id": "abc123",
  "hook_event_name": "PreCompact",
  "trigger": "manual",  // "manual" | "auto"
  "custom_instructions": "用户传入的自定义指令"
}
```

---

### 9. SessionStart

**触发时机**：会话启动或恢复时

**匹配器**：
- `startup` - 启动
- `resume` - 恢复（`--resume`、`--continue`、`/resume`）
- `clear` - 清除（`/clear`）
- `compact` - 压缩后

**使用场景**：
- 加载项目上下文
- 设置环境变量
- 安装依赖
- 检查项目状态

**输入数据结构**：
```json
{
  "session_id": "abc123",
  "hook_event_name": "SessionStart",
  "source": "startup"  // "startup" | "resume" | "clear" | "compact"
}
```

**持久化环境变量**：
```bash
#!/bin/bash
if [ -n "$CLAUDE_ENV_FILE" ]; then
  echo 'export NODE_ENV=production' >> "$CLAUDE_ENV_FILE"
  echo 'export API_KEY=your-api-key' >> "$CLAUDE_ENV_FILE"
fi
exit 0
```

**捕获环境变化**：
```bash
#!/bin/bash
ENV_BEFORE=$(export -p | sort)

# 修改环境的命令
source ~/.nvm/nvm.sh
nvm use 20

if [ -n "$CLAUDE_ENV_FILE" ]; then
  ENV_AFTER=$(export -p | sort)
  comm -13 <(echo "$ENV_BEFORE") <(echo "$ENV_AFTER") >> "$CLAUDE_ENV_FILE"
fi
exit 0
```

---

### 10. SessionEnd

**触发时机**：会话结束时

**原因类型**：
- `clear` - `/clear` 命令
- `logout` - 用户注销
- `prompt_input_exit` - 提示输入时退出
- `other` - 其他原因

**使用场景**：
- 清理任务
- 记录会话统计
- 保存会话状态

**输入数据结构**：
```json
{
  "session_id": "abc123",
  "hook_event_name": "SessionEnd",
  "reason": "clear"  // "clear" | "logout" | "prompt_input_exit" | "other"
}
```

---

## 配置方式

### 配置文件位置

按优先级排序：
1. **托管策略设置**（企业）
2. **用户设置**：`~/.claude/settings.json`（全局）
3. **项目设置**：`.claude/settings.json`（提交到仓库）
4. **本地项目设置**：`.claude/settings.local.json`（不提交）

### 基本配置结构

```json
{
  "hooks": {
    "EventName": [
      {
        "matcher": "ToolPattern",  // 仅 PreToolUse/PermissionRequest/PostToolUse 需要
        "hooks": [
          {
            "type": "command",  // "command" | "prompt"
            "command": "your-command-here",  // type=command 时
            "prompt": "your-prompt-here",  // type=prompt 时
            "timeout": 60  // 可选：超时秒数
          }
        ]
      }
    ]
  }
}
```

### Matcher 模式

- **精确匹配**：`"Write"` 仅匹配 Write 工具
- **正则表达式**：`"Edit|Write"` 或 `"Notebook.*"`
- **匹配所有**：`"*"` 或 `""`

### 项目脚本引用

使用 `$CLAUDE_PROJECT_DIR` 环境变量：

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Write|Edit",
        "hooks": [
          {
            "type": "command",
            "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/check-style.sh"
          }
        ]
      }
    ]
  }
}
```

### 交互式配置

运行 `/hooks` 斜杠命令，通过 UI 配置 hooks。

---

## Hook 输入输出

### 公共输入字段

所有 hook 事件都包含：
```json
{
  "session_id": "会话 ID",
  "transcript_path": "对话记录路径",
  "cwd": "当前工作目录",
  "permission_mode": "权限模式",
  "hook_event_name": "事件名称"
}
```

### 退出码含义

- **退出码 0**：成功
  - stdout 在详细模式（Ctrl+O）显示
  - UserPromptSubmit/SessionStart：stdout 添加到上下文
  - 如果 stdout 是 JSON，会解析为结构化控制

- **退出码 2**：阻止错误
  - stderr 作为错误消息反馈给 Claude
  - stdout 中的 JSON **不会**被处理
  - 不同事件的行为见下表

- **其他退出码**：非阻止错误
  - stderr 在详细模式显示
  - 执行继续

### 退出码 2 的行为

| Hook 事件 | 行为 |
|-----------|------|
| PreToolUse | 阻止工具调用，向 Claude 显示 stderr |
| PermissionRequest | 拒绝权限，向 Claude 显示 stderr |
| PostToolUse | 向 Claude 显示 stderr（工具已运行） |
| Notification | 不适用，仅向用户显示 stderr |
| UserPromptSubmit | 阻止提示处理，擦除提示，仅向用户显示 stderr |
| Stop | 阻止停止，向 Claude 显示 stderr |
| SubagentStop | 阻止停止，向 Subagent 显示 stderr |
| PreCompact | 不适用，仅向用户显示 stderr |
| SessionStart | 不适用，仅向用户显示 stderr |
| SessionEnd | 不适用，仅向用户显示 stderr |

### JSON 输出公共字段

```json
{
  "continue": true,  // 是否继续（默认 true）
  "stopReason": "停止原因",  // continue=false 时
  "suppressOutput": true,  // 隐藏 stdout（默认 false）
  "systemMessage": "警告消息"  // 可选：显示给用户
}
```

### 基于提示的 Hooks（type: "prompt"）

使用 LLM 做智能决策，适用于所有事件（尤其是 Stop/SubagentStop）：

```json
{
  "hooks": {
    "Stop": [
      {
        "hooks": [
          {
            "type": "prompt",
            "prompt": "评估 Claude 是否应停止：$ARGUMENTS。检查所有任务是否完成。",
            "timeout": 30
          }
        ]
      }
    ]
  }
}
```

LLM 响应格式：
```json
{
  "ok": true,  // true=允许，false=阻止
  "reason": "决策原因"  // ok=false 时必需
}
```

---

## 实战示例

### 1. 记录 Bash 命令

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "jq -r '\"\\(.tool_input.command) - \\(.tool_input.description // \\\"No description\\\")\"' >> ~/.claude/bash-log.txt"
          }
        ]
      }
    ]
  }
}
```

### 2. 自动格式化 TypeScript

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [
          {
            "type": "command",
            "command": "jq -r '.tool_input.file_path' | { read file_path; if echo \"$file_path\" | grep -q '\\.ts$'; then npx prettier --write \"$file_path\"; fi; }"
          }
        ]
      }
    ]
  }
}
```

### 3. Markdown 自动格式化

配置：
```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [
          {
            "type": "command",
            "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/markdown_formatter.py"
          }
        ]
      }
    ]
  }
}
```

脚本（`.claude/hooks/markdown_formatter.py`）：
```python
#!/usr/bin/env python3
"""
Markdown 格式化工具
修复缺失的语言标签和格式问题
"""
import json
import sys
import re
import os

def detect_language(code):
    """检测代码语言"""
    s = code.strip()

    # JSON 检测
    if re.search(r'^\s*[{\[]', s):
        try:
            json.loads(s)
            return 'json'
        except:
            pass

    # Python 检测
    if re.search(r'^\s*def\s+\w+\s*\(', s, re.M) or \
       re.search(r'^\s*(import|from)\s+\w+', s, re.M):
        return 'python'

    # JavaScript 检测
    if re.search(r'\b(function\s+\w+\s*\(|const\s+\w+\s*=)', s) or \
       re.search(r'=>|console\.(log|error)', s):
        return 'javascript'

    # Bash 检测
    if re.search(r'^#!.*\b(bash|sh)\b', s, re.M) or \
       re.search(r'\b(if|then|fi|for|in|do|done)\b', s):
        return 'bash'

    # SQL 检测
    if re.search(r'\b(SELECT|INSERT|UPDATE|DELETE|CREATE)\s+', s, re.I):
        return 'sql'

    return 'text'

def format_markdown(content):
    """格式化 markdown 内容"""
    # 修复未标记的代码块
    def add_lang_to_fence(match):
        indent, info, body, closing = match.groups()
        if not info.strip():
            lang = detect_language(body)
            return f"{indent}```{lang}\n{body}{closing}\n"
        return match.group(0)

    fence_pattern = r'(?ms)^([ \t]{0,3})```([^\n]*)\n(.*?)(\n\1```)\s*$'
    content = re.sub(fence_pattern, add_lang_to_fence, content)

    # 修复过多空行
    content = re.sub(r'\n{3,}', '\n\n', content)

    return content.rstrip() + '\n'

# 主执行
try:
    input_data = json.load(sys.stdin)
    file_path = input_data.get('tool_input', {}).get('file_path', '')

    if not file_path.endswith(('.md', '.mdx')):
        sys.exit(0)  # 非 markdown 文件

    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        formatted = format_markdown(content)

        if formatted != content:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(formatted)
            print(f"✓ 已修复 markdown 格式：{file_path}")

except Exception as e:
    print(f"格式化 markdown 出错：{e}", file=sys.stderr)
    sys.exit(1)
```

设置执行权限：
```bash
chmod +x .claude/hooks/markdown_formatter.py
```

### 4. 桌面通知

```json
{
  "hooks": {
    "Notification": [
      {
        "matcher": "idle_prompt",
        "hooks": [
          {
            "type": "command",
            "command": "notify-send 'Claude Code' '等待您的输入'"
          }
        ]
      }
    ]
  }
}
```

### 5. 保护敏感文件

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [
          {
            "type": "command",
            "command": "python3 -c \"import json, sys; data=json.load(sys.stdin); path=data.get('tool_input',{}).get('file_path',''); sys.exit(2 if any(p in path for p in ['.env', 'package-lock.json', '.git/']) else 0)\""
          }
        ]
      }
    ]
  }
}
```

### 6. Bash 命令验证

脚本（`.claude/hooks/bash_validator.py`）：
```python
#!/usr/bin/env python3
import json
import re
import sys

# 验证规则
VALIDATION_RULES = [
    (
        r"\bgrep\b(?!.*\|)",
        "建议使用 'rg' (ripgrep) 代替 'grep'，性能更好"
    ),
    (
        r"\bfind\s+\S+\s+-name\b",
        "建议使用 'rg --files -g pattern' 代替 'find -name'"
    ),
    (
        r"\brm\s+-rf\s+/",
        "危险命令：禁止删除根目录"
    ),
]

def validate_command(command: str) -> list[str]:
    issues = []
    for pattern, message in VALIDATION_RULES:
        if re.search(pattern, command):
            issues.append(message)
    return issues

try:
    input_data = json.load(sys.stdin)
except json.JSONDecodeError as e:
    print(f"错误：无效的 JSON 输入：{e}", file=sys.stderr)
    sys.exit(1)

tool_name = input_data.get("tool_name", "")
tool_input = input_data.get("tool_input", {})
command = tool_input.get("command", "")

if tool_name != "Bash" or not command:
    sys.exit(0)

# 验证命令
issues = validate_command(command)

if issues:
    for message in issues:
        print(f"• {message}", file=sys.stderr)
    # 退出码 2 阻止命令执行
    sys.exit(2)
```

配置：
```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/bash_validator.py"
          }
        ]
      }
    ]
  }
}
```

### 7. 注入项目上下文（UserPromptSubmit）

脚本（`.claude/hooks/inject_context.py`）：
```python
#!/usr/bin/env python3
import json
import sys
import datetime
import subprocess

# 收集项目信息
def get_project_context():
    context = []

    # 当前时间
    context.append(f"当前时间：{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Git 状态
    try:
        branch = subprocess.check_output(
            ["git", "branch", "--show-current"],
            stderr=subprocess.DEVNULL
        ).decode().strip()
        context.append(f"当前分支：{branch}")
    except:
        pass

    # 最近的 commit
    try:
        commit = subprocess.check_output(
            ["git", "log", "-1", "--oneline"],
            stderr=subprocess.DEVNULL
        ).decode().strip()
        context.append(f"最近提交：{commit}")
    except:
        pass

    return "\n".join(context)

try:
    input_data = json.load(sys.stdin)
    prompt = input_data.get("prompt", "")

    # 检查敏感内容
    import re
    sensitive_patterns = [
        (r"(?i)\b(password|secret|key|token)\s*[:=]", "包含潜在敏感信息"),
    ]

    for pattern, message in sensitive_patterns:
        if re.search(pattern, prompt):
            # 阻止提示
            output = {
                "decision": "block",
                "reason": f"安全策略违规：{message}。请在不包含敏感信息的情况下重新表述。"
            }
            print(json.dumps(output))
            sys.exit(0)

    # 注入上下文（简单方式）
    context = get_project_context()
    print(f"--- 项目上下文 ---\n{context}\n--- 结束 ---")

    sys.exit(0)

except Exception as e:
    print(f"错误：{e}", file=sys.stderr)
    sys.exit(1)
```

配置：
```json
{
  "hooks": {
    "UserPromptSubmit": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/inject_context.py"
          }
        ]
      }
    ]
  }
}
```

### 8. 智能 Stop Hook（基于提示）

```json
{
  "hooks": {
    "Stop": [
      {
        "hooks": [
          {
            "type": "prompt",
            "prompt": "你正在评估 Claude 是否应该停止工作。上下文：$ARGUMENTS\n\n分析对话并判断：\n1. 所有用户请求的任务是否已完成\n2. 是否有错误需要处理\n3. 是否需要后续工作\n\n返回 JSON：{\"ok\": true} 允许停止，或 {\"ok\": false, \"reason\": \"你的解释\"} 继续工作。",
            "timeout": 30
          }
        ]
      }
    ]
  }
}
```

### 9. SessionStart 加载开发上下文

脚本（`.claude/hooks/session_start.sh`）：
```bash
#!/bin/bash

# 设置环境变量
if [ -n "$CLAUDE_ENV_FILE" ]; then
  # 加载 nvm
  source ~/.nvm/nvm.sh
  nvm use 20

  # 捕获环境变化
  export NODE_ENV=development
  export DEBUG=true

  # 持久化到文件
  echo 'export NODE_ENV=development' >> "$CLAUDE_ENV_FILE"
  echo 'export DEBUG=true' >> "$CLAUDE_ENV_FILE"
fi

# 加载项目上下文
if [ -f "package.json" ]; then
  echo "--- 项目信息 ---"
  echo "名称：$(jq -r .name package.json)"
  echo "版本：$(jq -r .version package.json)"
  echo ""
fi

# 检查依赖
if [ -f "package.json" ] && [ ! -d "node_modules" ]; then
  echo "⚠️ 依赖未安装，运行：npm install"
fi

# Git 状态
if [ -d ".git" ]; then
  echo "分支：$(git branch --show-current)"
  echo "状态：$(git status --short | wc -l) 个变更"
fi

exit 0
```

配置：
```json
{
  "hooks": {
    "SessionStart": [
      {
        "matcher": "startup|resume",
        "hooks": [
          {
            "type": "command",
            "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/session_start.sh"
          }
        ]
      }
    ]
  }
}
```

### 10. MCP 工具 Hooks

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "mcp__memory__.*",
        "hooks": [
          {
            "type": "command",
            "command": "echo '记忆操作启动' >> ~/mcp-operations.log"
          }
        ]
      },
      {
        "matcher": "mcp__.*__write.*",
        "hooks": [
          {
            "type": "command",
            "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/validate-mcp-write.py"
          }
        ]
      }
    ]
  }
}
```

---

## 安全注意事项

### ⚠️ 免责声明

**使用风险自负**：Claude Code hooks 自动在系统上执行任意 shell 命令。通过使用 hooks，您承认：

- 您对配置的命令负全责
- Hooks 可以修改、删除或访问您的用户账户可访问的任何文件
- 恶意或编写不当的 hooks 可能导致数据丢失或系统损坏
- Anthropic 不提供任何保证，对因 hook 使用而导致的任何损坏不承担责任
- 您应在生产使用前在安全环境中彻底测试 hooks

**在添加任何 hook 前务必审查并理解命令！**

### 安全最佳实践

#### 1. 验证和清理输入

```python
import json
import sys
import os

input_data = json.load(sys.stdin)
file_path = input_data.get('tool_input', {}).get('file_path', '')

# 阻止路径遍历
if '..' in file_path or file_path.startswith('/'):
    print("路径遍历攻击检测", file=sys.stderr)
    sys.exit(2)

# 检查文件扩展名
allowed_exts = ['.py', '.js', '.md']
if not any(file_path.endswith(ext) for ext in allowed_exts):
    print("不允许的文件类型", file=sys.stderr)
    sys.exit(2)
```

#### 2. 始终引用 shell 变量

```bash
# ❌ 错误
command="$TOOL_INPUT"
eval $command

# ✅ 正确
command="$TOOL_INPUT"
eval "$command"
```

#### 3. 使用绝对路径

```bash
# ❌ 相对路径（危险）
./scripts/check.sh

# ✅ 绝对路径
"$CLAUDE_PROJECT_DIR"/.claude/hooks/check.sh
```

#### 4. 跳过敏感文件

```python
SENSITIVE_PATTERNS = [
    '.env',
    '.git/',
    'credentials',
    'secrets',
    'id_rsa',
    'package-lock.json',
]

file_path = input_data.get('tool_input', {}).get('file_path', '')
if any(pattern in file_path for pattern in SENSITIVE_PATTERNS):
    print("敏感文件受保护", file=sys.stderr)
    sys.exit(2)
```

#### 5. 限制命令权限

```bash
# 使用受限的 shell
command="$TOOL_INPUT"
rbash -c "$command"  # 受限 bash

# 或使用 timeout 限制执行时间
timeout 5s "$command"
```

#### 6. 记录所有操作

```bash
#!/bin/bash
LOG_FILE=~/.claude/hooks.log

# 记录输入
echo "[$(date)] Hook: $HOOK_EVENT_NAME" >> "$LOG_FILE"
cat >> "$LOG_FILE" <<< "$INPUT_JSON"

# 执行并记录结果
result=$(your-command 2>&1)
echo "$result" >> "$LOG_FILE"
```

### 配置安全

- 设置文件直接编辑不会立即生效
- Claude Code 在启动时捕获 hooks 快照
- 外部修改会触发警告
- 需在 `/hooks` 菜单查看更改以应用

这防止恶意 hook 修改影响当前会话。

---

## 调试技巧

### 基本故障排除

1. **检查配置**
```bash
# 运行 Claude Code
claude

# 在 REPL 中
/hooks
```

2. **验证 JSON 语法**
```bash
jq . ~/.claude/settings.json
```

3. **测试命令**
```bash
# 手动测试 hook 命令
echo '{"tool_name":"Write","tool_input":{"file_path":"test.txt"}}' | \
  "$CLAUDE_PROJECT_DIR"/.claude/hooks/your-script.py
```

4. **检查权限**
```bash
chmod +x .claude/hooks/*.py
chmod +x .claude/hooks/*.sh
```

5. **查看详细日志**
```bash
# 启用调试模式
claude --debug

# 在会话中按 Ctrl+O 查看详细输出
```

### 常见问题

#### 问题：Hook 不执行

**检查项**：
- ✓ Matcher 是否正确（区分大小写）
- ✓ 脚本是否有执行权限
- ✓ 路径是否正确（使用 `$CLAUDE_PROJECT_DIR`）
- ✓ JSON 语法是否正确

#### 问题：JSON 输出不被识别

**原因**：
- 退出码不是 0（JSON 仅在退出码 0 时处理）
- JSON 格式错误

**解决**：
```python
import json
import sys

output = {
    "decision": "block",
    "reason": "原因"
}
print(json.dumps(output))  # 确保 JSON 格式正确
sys.exit(0)  # 必须是 0
```

#### 问题：引号转义错误

```json
{
  "command": "python3 -c \"import json; print(json.dumps({'ok': True}))\""
}
```

在 JSON 字符串中使用 `\"`。

### 高级调试

#### 1. 详细日志脚本

```python
#!/usr/bin/env python3
import json
import sys
import datetime

LOG_FILE = "/tmp/claude-hook-debug.log"

def log(message):
    with open(LOG_FILE, "a") as f:
        timestamp = datetime.datetime.now().isoformat()
        f.write(f"[{timestamp}] {message}\n")

try:
    # 记录原始输入
    input_text = sys.stdin.read()
    log(f"Raw input: {input_text}")

    # 解析 JSON
    input_data = json.loads(input_text)
    log(f"Parsed: {json.dumps(input_data, indent=2)}")

    # 你的处理逻辑
    # ...

    # 记录输出
    output = {"decision": "approve"}
    log(f"Output: {json.dumps(output)}")
    print(json.dumps(output))

    sys.exit(0)

except Exception as e:
    log(f"Error: {str(e)}")
    import traceback
    log(traceback.format_exc())
    sys.exit(1)
```

#### 2. 监控执行时间

```bash
#!/bin/bash
START_TIME=$(date +%s%N)

# 你的命令
your-command

END_TIME=$(date +%s%N)
ELAPSED=$((($END_TIME - $START_TIME) / 1000000))
echo "执行时间：${ELAPSED}ms" >> /tmp/hook-timing.log
```

#### 3. 测试 Hook 输入

创建测试输入文件（`test-input.json`）：
```json
{
  "session_id": "test-123",
  "hook_event_name": "PreToolUse",
  "tool_name": "Write",
  "tool_input": {
    "file_path": "/tmp/test.txt",
    "content": "测试内容"
  }
}
```

测试：
```bash
cat test-input.json | .claude/hooks/your-script.py
echo "退出码：$?"
```

#### 4. 调试输出示例

启用 `claude --debug` 时的输出：

```text
[DEBUG] Executing hooks for PostToolUse:Write
[DEBUG] Getting matching hook commands for PostToolUse with query: Write
[DEBUG] Found 1 hook matchers in settings
[DEBUG] Matched 1 hooks for query "Write"
[DEBUG] Found 1 hook commands to execute
[DEBUG] Executing hook command: <Your command> with timeout 60000ms
[DEBUG] Hook command completed with status 0: <Your stdout>
```

按 `Ctrl+O` 查看详细输出（非调试模式）：
```text
[Hook] PreToolUse:Bash - 运行中...
[Hook] 命令：.claude/hooks/bash_validator.py
[Hook] ✓ 完成 (125ms)
[Hook] 输出：验证通过
```

---

## 附录：环境变量

### Hook 可用的环境变量

| 变量 | 说明 | 可用范围 |
|------|------|----------|
| `CLAUDE_PROJECT_DIR` | 项目根目录绝对路径 | 所有 hooks |
| `CLAUDE_ENV_FILE` | 持久化环境变量的文件路径 | 仅 SessionStart |
| `CLAUDE_CODE_REMOTE` | 是否在远程环境（`"true"` 或未设置） | 所有 hooks |
| `CLAUDE_PLUGIN_ROOT` | 插件目录绝对路径 | 插件 hooks |

### 示例：根据环境调整行为

```bash
#!/bin/bash

if [ "$CLAUDE_CODE_REMOTE" = "true" ]; then
  # 远程环境（Web）
  notify-send() {
    # Web 环境不支持桌面通知，使用替代方案
    logger "Claude Code: $*"
  }
fi

# 发送通知
notify-send "Claude Code" "任务完成"
```

---

## 快速参考卡

### Hook 事件速查

| 事件 | 触发时机 | 主要用途 | 可阻止 |
|------|----------|----------|--------|
| PreToolUse | 工具调用前 | 验证、阻止、修改输入 | ✓ |
| PermissionRequest | 显示权限对话框时 | 自动批准/拒绝 | ✓ |
| PostToolUse | 工具完成后 | 格式化、验证、日志 | - |
| UserPromptSubmit | 用户提交提示时 | 注入上下文、验证 | ✓ |
| Notification | 发送通知时 | 自定义通知方式 | - |
| Stop | 主 agent 完成时 | 智能判断是否完成 | ✓ |
| SubagentStop | Subagent 完成时 | 智能判断子任务完成 | ✓ |
| PreCompact | 压缩前 | 保存上下文 | - |
| SessionStart | 会话启动时 | 加载上下文、设置环境 | - |
| SessionEnd | 会话结束时 | 清理、记录 | - |

### 退出码速查

| 退出码 | 含义 | 处理 |
|--------|------|------|
| 0 | 成功 | 处理 JSON 输出（如果有） |
| 2 | 阻止错误 | 使用 stderr，忽略 stdout |
| 其他 | 非阻止错误 | 显示 stderr，继续执行 |

### 常用命令模板

```bash
# 读取 JSON 输入
input_data=$(cat)

# 提取字段（jq）
file_path=$(echo "$input_data" | jq -r '.tool_input.file_path')

# 提取字段（Python）
file_path=$(echo "$input_data" | python3 -c "import json,sys; print(json.load(sys.stdin)['tool_input']['file_path'])")

# 输出 JSON（阻止操作）
cat <<EOF
{"decision": "block", "reason": "原因说明"}
EOF

# 记录到文件
echo "[$(date)] $message" >> ~/.claude/hooks.log

# 条件退出
if [ condition ]; then
  echo "错误消息" >&2
  exit 2
fi
```

---

## 资源链接

- **官方文档**：[https://code.claude.com/docs/zh-CN/hooks](https://code.claude.com/docs/zh-CN/hooks)
- **入门指南**：[https://code.claude.com/docs/zh-CN/hooks-guide](https://code.claude.com/docs/zh-CN/hooks-guide)
- **示例代码**：[https://github.com/anthropics/claude-code/tree/main/examples/hooks](https://github.com/anthropics/claude-code/tree/main/examples/hooks)
- **设置参考**：[https://code.claude.com/docs/zh-CN/settings](https://code.claude.com/docs/zh-CN/settings)
- **插件参考**：[https://code.claude.com/docs/zh-CN/plugins-reference](https://code.claude.com/docs/zh-CN/plugins-reference)

---

## 贡献

如果你有更好的示例或发现文档问题，欢迎贡献！

**最后更新**：2026-02-22
