# easyCcHooks：类型安全的 Claude Code Hooks 框架

简体中文 | [English](README.md)

把 Claude Code Hook 从“零散脚本配置”升级成“可维护的 Python 工程”。

easyCcHooks 提供：
- 覆盖 Claude Code 全部 10 类 Hook 事件的统一接口
- 基于 `dataclass` 的类型安全输入输出模型
- 扫描、注册、更新配置的一体化 CLI
- 可本地测试的 Hook 验证流程，降低上线风险

> 架构说明：[`.claude/hooks/ARCHITECTURE.md`](.claude/hooks/ARCHITECTURE.md)

## 这个项目解决什么问题

很多团队在 Hook 规模变大后，会遇到这些问题：
- 逻辑分散在配置和 shell 片段里，维护困难
- 缺少类型约束，运行时错误难定位
- 新同学接手成本高，改动不敢动

easyCcHooks 的目标是让 Hook 开发回归正常工程实践：
- 明确接口 + 类型提示
- 可测试、可复用、可迭代
- 自动管理配置，减少手工操作错误

## 适合谁使用

- 新手：希望快速、安全地接入 Claude Code Hooks
- 团队用户：需要长期维护安全策略、审计、上下文注入
- 进阶用户：希望按工具匹配、可控超时、可测试回归

## 3 分钟快速上手

### 1. 安装

在项目根目录执行：

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/e1roy/easyCcHooks/main/install.sh)
```

### 2. 创建第一个 Hook

创建 `.claude/hooks/MyBashValidator.py`：

```python
from easyCcHooks import IPreToolUse, PreToolUseInput, PreToolUseOutput, ToolName


class MyBashValidator(IPreToolUse):
    """在命令执行前阻止危险 Bash 指令。"""

    @property
    def matcher(self) -> str:
        return ToolName.Bash

    def execute(self, input_data: PreToolUseInput) -> PreToolUseOutput:
        command = input_data.tool_input.get("command", "")
        if "rm -rf /" in command:
            return PreToolUseOutput(
                permission_decision="deny",
                permission_decision_reason="禁止删除根目录"
            )
        return PreToolUseOutput(
            permission_decision="allow",
            permission_decision_reason="命令可执行"
        )
```

### 3. 扫描并更新配置

```bash
python3 .claude/hooks/easyCcHooks.py scan
python3 .claude/hooks/easyCcHooks.py update-config
```

### 4. 本地验证再上线

```bash
cat > /tmp/hook_test.json <<'EOF'
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
EOF

python3 .claude/hooks/easyCcHooks.py test MyBashValidator --input /tmp/hook_test.json
```

如果输出中出现 `permissionDecision: "deny"`，说明 Hook 行为符合预期。

## 为什么更值得用

- 上手快：核心能力集中在一个文件，学习成本低
- 风险低：先本地测试，再接入真实会话
- 扩展快：新增 Hook 类即可，不需要改框架内部
- 升级稳：`upgrade` + 自动配置合并，减少配置漂移

## 常见应用场景

- 安全防护：拦截危险命令、敏感输入
- 上下文增强：会话启动自动注入项目信息
- 审计留痕：记录工具调用与策略决策
- 质量兜底：工具执行后增加校验和补充提示

## CLI 命令

统一入口：

```bash
python3 .claude/hooks/easyCcHooks.py <command>
```

| 命令 | 作用 |
| --- | --- |
| `scan` | 扫描并注册 Hook 实现 |
| `update-config` | 合并并更新 `.claude/settings.json` |
| `list` | 查看当前已注册 Hook |
| `test <HookName> --input <json>` | 本地测试指定 Hook |
| `execute <HookName>` | 运行时入口（供 Claude Code 调用） |
| `upgrade` | 检查远程版本并升级 `easyCcHooks.py` |

## Hook 接口总览（10 类）

| 接口 | 触发时机 | 常见用途 |
| --- | --- | --- |
| `IPreToolUse` | 工具调用前 | 命令校验、参数修正、策略拦截 |
| `IPermissionRequest` | 权限请求时 | 自动放行/拒绝并给出原因 |
| `IPostToolUse` | 工具调用后 | 结果校验、附加上下文、阻断风险 |
| `IUserPromptSubmit` | 用户提交提示词 | 敏感信息过滤、提示词增强 |
| `INotification` | 通知事件 | 通知记录与转发 |
| `IStop` | 会话停止时 | 退出保护、资源清理 |
| `ISubagentStop` | 子代理停止时 | 子代理清理策略 |
| `IPreCompact` | 压缩前 | 快照、备份、预处理 |
| `ISessionStart` | 会话开始时 | 注入项目上下文、初始化 |
| `ISessionEnd` | 会话结束时 | 收尾、报告生成 |

## 技术深入（给进阶用户）

### 执行链路

1. `scan` 递归发现 `.claude/hooks` 下的 Hook 类
2. 注册中心按 Hook 类型归类
3. `update-config` 生成并合并 `.claude/settings.json` Hook 配置
4. Claude Code 通过 `execute <HookName>` + `stdin` JSON 触发实际执行

### 类型安全模型

- 每个 Hook 事件都有独立输入输出 dataclass
- `from_dict` 负责从事件 JSON 映射到模型字段
- 输出通过 `to_dict` 自动序列化成 Claude 兼容格式

### matcher 与 timeout

- `matcher` 控制 Hook 生效范围（单工具、正则、多工具）
- 可覆写 `timeout` 对慢操作设置更长执行窗口

### 更新工具输入

工具级 Hook 可以通过 `updated_input` 修改调用参数：

```python
return PreToolUseOutput(
    permission_decision="allow",
    permission_decision_reason="已应用安全默认值",
    updated_input={**input_data.tool_input, "timeout": 30}
)
```

## 测试与验证

- 测试指南：[`.claude/hooks/tests/README.md`](.claude/hooks/tests/README.md)
- 示例 Hook：[`.claude/hooks/tests/example_hooks.py`](.claude/hooks/tests/example_hooks.py)

团队实践建议：
1. 每个关键策略至少有 `allow` / `deny` / `ask` / `block` 样例
2. 在 CI 执行 `test`，再执行配置更新
3. 策略变更必须补回归样例，防止意外放行

## 目录结构

```text
.claude/hooks/
├── easyCcHooks.py
├── *.py
├── ARCHITECTURE.md
└── tests/
    ├── README.md
    ├── example_hooks.py
    └── test_input_*.json
```

## 故障排查

### Hook 没生效

1. 运行 `python3 .claude/hooks/easyCcHooks.py scan`
2. 运行 `python3 .claude/hooks/easyCcHooks.py update-config`
3. 检查 `.claude/settings.json` 是否包含对应配置
4. 重启 Claude Code 会话

### 测试失败

1. 确认 `hook_event_name` 与 Hook 接口匹配
2. 确认 `test` 命令中的类名与实现类完全一致
3. 确认测试 JSON 包含该事件所需字段
