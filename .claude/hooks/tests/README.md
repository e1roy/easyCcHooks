# easyCcHooks 测试指南

这份文档用于回答三个问题：
1. Hook 逻辑是否按预期工作？
2. 上线前如何快速验证“拒绝/放行/询问”策略？
3. 出问题时如何快速定位？

## 测试目录结构

```text
tests/
├── README.md
├── example_hooks.py
├── test_input_dangerous.json
├── test_input_safe.json
└── test_input_session.json
```

## 1 分钟快速验证

在 `tests/` 目录中执行：

```bash
# 危险命令应被拒绝
python3 ../easyCcHooks.py test ValidateBashCommand --input test_input_dangerous.json

# 安全命令应被允许
python3 ../easyCcHooks.py test ValidateBashCommand --input test_input_safe.json

# SessionStart 应返回 additionalContext
python3 ../easyCcHooks.py test InjectContext --input test_input_session.json
```

预期结果：
- 第一条输出包含 `permissionDecision: "deny"`
- 第二条输出包含 `permissionDecision: "allow"`
- 第三条输出包含 `hookSpecificOutput.additionalContext`

## 测试与生产加载的区别

- `test` 命令会扫描 `tests/`，可直接测试 `example_hooks.py` 中的示例类
- `scan` 默认不包含 `tests/`，避免把测试 Hook 注册到生产配置

如果你想把示例 Hook 真实启用到项目中，请在项目根目录执行：

```bash
cp .claude/hooks/tests/example_hooks.py .claude/hooks/
python3 .claude/hooks/easyCcHooks.py scan
python3 .claude/hooks/easyCcHooks.py update-config
```

## 测试输入文件说明

### `test_input_dangerous.json`

- 场景：危险命令拦截
- 输入：`rm -rf /`
- 预期：`deny`

### `test_input_safe.json`

- 场景：安全命令放行
- 输入：`ls -la`
- 预期：`allow`

### `test_input_session.json`

- 场景：会话启动上下文注入
- 预期：返回项目上下文（`additionalContext`）

## 自定义测试用例

### 1. 新建输入文件

```bash
cat > test_input_custom.json <<'EOF'
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

### 2. 执行测试

```bash
python3 ../easyCcHooks.py test ValidateBashCommand --input test_input_custom.json
```

### 3. 看什么算通过

- 返回 `permissionDecision` 且值符合你的策略
- 返回 `permissionDecisionReason`，便于审计与排查
- 退出码为 `0`

## 模拟 Claude Code 真实调用（stdin）

```bash
cat test_input_safe.json | python3 ../easyCcHooks.py execute ValidateBashCommand
```

这个方式可验证 `execute` 入口与 JSON 序列化流程是否正常。

## 示例 Hook 覆盖能力

`example_hooks.py` 提供了 3 个实用样例：

| Hook 类名 | 接口 | 目的 |
| --- | --- | --- |
| `ValidateBashCommand` | `IPreToolUse` | 危险命令拦截、sudo 询问确认 |
| `WatchPreToolUse` | `IPreToolUse` | 记录工具调用，便于审计 |
| `InjectContext` | `ISessionStart` | 会话启动时注入项目信息 |

## 常见问题排查

### 报错 `Hook not found`

1. 类名是否和命令参数完全一致
2. 该类是否继承了正确 Hook 接口
3. 是否在 `tests/` 下执行，且 `--input` 路径正确

### 输出不符合预期

1. 打印并检查输入 JSON 字段是否完整
2. 检查 `hook_event_name` 是否匹配实现接口
3. 检查正则/条件是否覆盖你当前输入场景

### 生产不生效

1. 确认 Hook 文件在 `.claude/hooks/` 下，而不是 `tests/`
2. 执行 `python3 .claude/hooks/easyCcHooks.py scan`
3. 执行 `python3 .claude/hooks/easyCcHooks.py update-config`
4. 重启 Claude Code 会话
