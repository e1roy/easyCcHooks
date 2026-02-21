# Hook 框架测试

本目录包含所有测试相关的文件和脚本。

## 目录结构

```
tests/
├── README.md                 # 测试说明 (本文件)
├── example_hooks.py          # 示例 hook 实现 (ValidateBashCommand, WatchPreToolUse, InjectContext)
├── test_input_dangerous.json # 危险命令测试输入
├── test_input_safe.json      # 安全命令测试输入
└── test_input_session.json   # 会话启动测试输入
```

## 快速测试

示例 hook 位于 `example_hooks.py`,需要先复制到上级目录才能被框架自动加载。

### 1. 复制示例 hook 到 hooks 目录

```bash
cp example_hooks.py ../
```

### 2. 测试特定 Hook

```bash
# 测试危险命令验证
python3 ../easyCcHooks.py test ValidateBashCommand --input test_input_dangerous.json

# 测试安全命令验证
python3 ../easyCcHooks.py test ValidateBashCommand --input test_input_safe.json

# 测试上下文注入
python3 ../easyCcHooks.py test InjectContext --input test_input_session.json
```

### 3. 测试 stdin 执行

```bash
# 模拟 Claude Code 调用方式
cat test_input_safe.json | python3 ../easyCcHooks.py execute ValidateBashCommand
```

### 4. 扫描确认注册

```bash
python3 ../easyCcHooks.py scan
python3 ../easyCcHooks.py list
```

## 测试输入文件说明

### test_input_dangerous.json

测试危险命令验证功能。

**内容**: `rm -rf /`
**预期结果**: `deny` (拒绝执行)

```json
{
  "session_id": "test-001",
  "hook_event_name": "PreToolUse",
  "tool_name": "Bash",
  "tool_input": {"command": "rm -rf /"},
  "transcript_path": "/tmp/test.jsonl",
  "cwd": "/tmp",
  "permission_mode": "default",
  "tool_use_id": "test-001"
}
```

### test_input_safe.json

测试安全命令验证功能。

**内容**: `ls -la`
**预期结果**: `allow` (允许执行)

```json
{
  "session_id": "test-002",
  "hook_event_name": "PreToolUse",
  "tool_name": "Bash",
  "tool_input": {"command": "ls -la"},
  "transcript_path": "/tmp/test.jsonl",
  "cwd": "/tmp",
  "permission_mode": "default",
  "tool_use_id": "test-002"
}
```

### test_input_session.json

测试会话启动时的上下文注入。

**预期结果**: 返回项目信息

```json
{
  "session_id": "test-003",
  "hook_event_name": "SessionStart",
  "transcript_path": "/tmp/test.jsonl",
  "cwd": "/Users/elroysu/Desktop/cowork",
  "permission_mode": "default",
  "source": "startup"
}
```

## 创建自定义测试

### 步骤 1: 创建测试输入文件

```bash
cat > test_input_custom.json <<EOF
{
  "session_id": "test-custom",
  "hook_event_name": "PreToolUse",
  "tool_name": "Bash",
  "tool_input": {"command": "sudo rm -rf /tmp"},
  "transcript_path": "/tmp/test.jsonl",
  "cwd": "/tmp",
  "permission_mode": "default",
  "tool_use_id": "test-custom"
}
EOF
```

### 步骤 2: 运行测试

```bash
python3 ../easyCcHooks.py test ValidateBashCommand --input test_input_custom.json
```

## 示例 hook 说明

`example_hooks.py` 包含 3 个示例实现:

| Hook | 类型 | 功能 |
| ---- | ---- | ---- |
| ValidateBashCommand | IPreToolUse | 验证 Bash 命令安全性,阻止危险命令 |
| WatchPreToolUse | IPreToolUse | 监控所有工具调用,记录到日志 |
| InjectContext | ISessionStart | 在会话开始时注入项目上下文 |

要在正式项目中使用这些 hook,将 `example_hooks.py` 复制到 `.claude/hooks/` 目录下,然后运行:

```bash
python3 ../easyCcHooks.py scan
python3 ../easyCcHooks.py update-config
```
