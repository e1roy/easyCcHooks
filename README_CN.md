# Claude Code Hooks 框架

简体中文 | [English](README.md)

一个类型安全、自动化的 Claude Code Hook 模板系统。

> 查看 [ARCHITECTURE.md](ARCHITECTURE.md) 了解框架的架构设计和实现原理

## 特性

- 类型安全: 使用 Python dataclass 和类型提示
- 自动配置: 自动生成和更新 settings.json
- 清晰接口: 10 种 hook 类型的抽象基类
- 单文件框架: 所有框架代码集中在 `easyCcHooks.py`
- 便于测试: 提供测试工具和 CLI

## 安装

在项目根目录下执行一键安装：

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/e1roy/easyCcHooks/main/install.sh)
```

安装脚本会将 `easyCcHooks.py` 下载到 `.claude/hooks/` 目录。如果项目中没有 `.claude` 目录，脚本会询问是否创建。

## 升级

```bash
python3 .claude/hooks/easyCcHooks.py upgrade
```

该命令会检查远程版本并自动更新。使用 `-y` 跳过确认提示。

## 快速开始

### 1. 创建 Hook 实现

在 `.claude/hooks/` 目录下创建你的 hook 实现文件:

```python
# .claude/hooks/MyBashValidator.py
from easyCcHooks import IPreToolUse, PreToolUseInput, PreToolUseOutput, ToolName

class MyBashValidator(IPreToolUse):
    """
    自定义 Bash 命令验证器

    功能:
    - 阻止危险的 rm 命令
    - 记录所有命令到日志
    """

    @property
    def matcher(self) -> str:
        return ToolName.Bash  # 仅匹配 Bash 工具

    def execute(self, input_data: PreToolUseInput) -> PreToolUseOutput:
        command = input_data.tool_input.get("command", "")

        # 检查危险命令
        if "rm -rf /" in command:
            return PreToolUseOutput(
                permission_decision="deny",
                permission_decision_reason="禁止删除根目录"
            )

        # 允许执行
        return PreToolUseOutput(
            permission_decision="allow",
            permission_decision_reason="命令安全"
        )
```

### 2. 扫描并注册

```bash
cd .claude/hooks
python3 easyCcHooks.py scan
```

输出:
```
扫描 hook 实现...
已注册: PreToolUse.MyBashValidator
扫描完成,共注册 1 个 hook
```

### 3. 更新配置

```bash
python3 easyCcHooks.py update-config
```

输出:
```
更新配置...
配置已更新: .claude/settings.json
配置更新完成
```

### 4. 验证生效

下次启动 Claude Code 时,hook 会自动加载并生效。

## CLI 命令

所有命令通过 `easyCcHooks.py` 执行:

### scan - 扫描并注册 hook

```bash
python3 easyCcHooks.py scan
```

扫描 `.claude/hooks/` 目录下的 `.py` 文件,注册所有 hook 实现。

### update-config - 更新配置

```bash
python3 easyCcHooks.py update-config
```

自动更新 `.claude/settings.json` 配置文件。

### list - 列出所有 hook

```bash
python3 easyCcHooks.py list
```

显示所有已注册的 hook 及其描述。

### test - 测试 hook

```bash
# 使用已有的测试文件 (位于 tests/ 目录)
python3 easyCcHooks.py test ValidateBashCommand --input tests/test_input_dangerous.json

# 或创建自定义测试输入
cat > tests/test_input_custom.json <<EOF
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

# 测试 hook
python3 easyCcHooks.py test MyBashValidator --input tests/test_input_custom.json
```

查看 [tests/README.md](tests/README.md) 了解更多测试用法。

### execute - 执行 hook (内部使用)

```bash
# 由 Claude Code 自动调用
echo '{"hook_event_name":"PreToolUse",...}' | python3 easyCcHooks.py execute MyBashValidator
```

### upgrade - 检查更新并升级

```bash
python3 easyCcHooks.py upgrade
```

检查远程最新版本，确认后自动下载更新。加 `-y` 跳过确认：

```bash
python3 easyCcHooks.py upgrade -y
```

## Hook 接口

框架提供 10 种 hook 接口,全部定义在 `easyCcHooks.py` 中:

| 接口 | 触发时机 | 使用场景 |
| ---- | -------- | -------- |
| IPreToolUse | 工具调用前 | 验证命令、修改参数、记录日志 |
| IPermissionRequest | 权限请求时 | 自动批准、记录权限请求 |
| IPostToolUse | 工具调用后 | 验证结果、触发后续操作 |
| IUserPromptSubmit | 用户提交提示词时 | 注入上下文、预处理输入 |
| INotification | 系统通知时 | 记录通知、转发到外部系统 |
| IStop | 会话停止时 | 清理资源、保存状态 |
| ISubagentStop | 子代理停止时 | 清理子代理资源 |
| IPreCompact | 上下文压缩前 | 保存快照、触发备份 |
| ISessionStart | 会话开始时 | 初始化资源、注入上下文 |
| ISessionEnd | 会话结束时 | 清理资源、生成报告 |

## 示例实现

完整示例见 [tests/example_hooks.py](tests/example_hooks.py)。以下是几个覆盖不同 hook 类型的 demo：

### Demo 1: PreToolUse - 阻止危险 Bash 命令

```python
# .claude/hooks/DenyDangerousRm.py
from easyCcHooks import IPreToolUse, PreToolUseInput, PreToolUseOutput, ToolName

class DenyDangerousRm(IPreToolUse):
    """阻止 rm -rf / 等危险删除命令"""

    @property
    def matcher(self) -> str:
        return ToolName.Bash

    def execute(self, input_data: PreToolUseInput) -> PreToolUseOutput:
        cmd = input_data.tool_input.get("command", "")
        if "rm " in cmd and " -rf " in cmd and cmd.rstrip().endswith("/"):
            return PreToolUseOutput(
                permission_decision="deny",
                permission_decision_reason="禁止删除根目录"
            )
        return PreToolUseOutput(permission_decision="allow")
```

### Demo 2: PostToolUse - 写文件后自动提示

```python
# .claude/hooks/NotifyOnWrite.py
from easyCcHooks import IPostToolUse, PostToolUseInput, PostToolUseOutput, ToolName

class NotifyOnWrite(IPostToolUse):
    """在 Write 工具完成后注入提示信息"""

    @property
    def matcher(self) -> str:
        return ToolName.Write

    def execute(self, input_data: PostToolUseInput) -> PostToolUseOutput:
        file_path = input_data.tool_input.get("file_path", "")
        return PostToolUseOutput(
            additional_context=f"文件已写入: {file_path},请检查内容是否正确"
        )
```

### Demo 3: SessionStart - 注入项目上下文

```python
# .claude/hooks/ProjectInfo.py
from pathlib import Path
from easyCcHooks import ISessionStart, SessionStartInput, SessionStartOutput

class ProjectInfo(ISessionStart):
    """会话启动时注入项目基本信息"""

    def execute(self, input_data: SessionStartInput) -> SessionStartOutput:
        cwd = Path(input_data.cwd)
        info = [f"项目目录: {cwd.name}"]
        if (cwd / "package.json").exists():
            info.append("Node.js 项目")
        if (cwd / "requirements.txt").exists():
            info.append("Python 项目")
        if (cwd / ".git").exists():
            info.append("Git 仓库")
        return SessionStartOutput(
            additional_context="\n".join(info) if info else None
        )
```

### Demo 4: UserPromptSubmit - 过滤敏感信息

```python
# .claude/hooks/FilterSecrets.py
import re
from easyCcHooks import IUserPromptSubmit, UserPromptSubmitInput, UserPromptSubmitOutput

class FilterSecrets(IUserPromptSubmit):
    """检测用户提示词中是否包含敏感信息"""

    def execute(self, input_data: UserPromptSubmitInput) -> UserPromptSubmitOutput:
        prompt = input_data.prompt
        # 检测 API key 格式
        if re.search(r"(sk-|AKIA|ghp_|xox[bsp]-)\w{10,}", prompt):
            return UserPromptSubmitOutput(
                decision="block",
                reason="检测到可能的 API Key,请移除后再提交"
            )
        return UserPromptSubmitOutput()
```

### Demo 5: Stop - 阻止意外退出

```python
# .claude/hooks/PreventStop.py
from easyCcHooks import IStop, StopInput, StopOutput

class PreventStop(IStop):
    """在 stop_hook 未激活时阻止退出,让 Claude 继续工作"""

    def execute(self, input_data: StopInput) -> StopOutput:
        if not input_data.stop_hook_active:
            return StopOutput(
                decision="block",
                reason="任务可能未完成,请继续"
            )
        return StopOutput()
```

每个 demo 只需放到 `.claude/hooks/` 目录下，运行 `python3 easyCcHooks.py update-config` 即可生效。

## 目录结构

```
.claude/hooks/
├── easyCcHooks.py      # 框架核心 (数据模型 + 接口 + 注册中心 + 执行器 + CLI)
├── *.py                   # 用户自定义 hook 实现 (放在同目录下,自动加载)
├── ARCHITECTURE.md        # 架构文档
├── README.md              # 使用文档 (本文件)
└── tests/                 # 测试文件
    ├── example_hooks.py   # 示例 hook 实现
    ├── README.md          # 测试说明
    ├── test_input_dangerous.json
    ├── test_input_safe.json
    └── test_input_session.json
```

## 高级用法

### 修改工具输入

```python
def execute(self, input_data: PreToolUseInput) -> PreToolUseOutput:
    # 修改命令参数
    modified_input = input_data.tool_input.copy()
    modified_input["timeout"] = 30

    return PreToolUseOutput(
        permission_decision="allow",
        permission_decision_reason="已调整超时时间",
        updated_input=modified_input
    )
```

### 自定义超时时间

```python
class MyHook(IPreToolUse):
    @property
    def timeout(self) -> int:
        return 30  # 30 秒超时
```

### 匹配特定工具

```python
class MyHook(IPreToolUse):
    @property
    def matcher(self) -> str:
        return f"{ToolName.Bash}|{ToolName.Edit}|{ToolName.Write}"  # 匹配多个工具 (正则)
```

## 故障排除

### Hook 未生效

1. 检查是否已扫描: `python3 easyCcHooks.py scan`
2. 检查是否已更新配置: `python3 easyCcHooks.py update-config`
3. 查看 settings.json 是否包含 hook 配置
4. 重启 Claude Code

### 测试失败

使用正确的测试输入格式,参考 [测试指南](#test---测试-hook)
