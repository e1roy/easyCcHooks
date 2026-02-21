#!/usr/bin/env python3
"""
EasyCcHooks - Claude Code Hooks 一体化工具

包含:
- 数据模型 (dataclass)
- 抽象基类 & Hook 接口
- 注册中心 & 执行器 & 配置管理器
- CLI 命令行工具

Hook 实现放在同目录下的 .py 文件中,scan 时自动加载。
示例实现见 tests/example_hooks.py。

使用方式:
    python3 easyCcHooks.py scan                         # 扫描并注册所有 hook
    python3 easyCcHooks.py list                         # 列出已注册的 hook
    python3 easyCcHooks.py update-config                 # 更新 settings.json
    python3 easyCcHooks.py test <hook> --input <file>    # 测试 hook
    python3 easyCcHooks.py execute <hook>               # 执行 hook (由 Claude Code 调用)
    python3 easyCcHooks.py upgrade                       # 检查更新并升级

╔══════════════════════════════════════════════════════════════════════════════╗
║  示例: 在 .claude/hooks/ 下创建 .py 文件,继承对应接口,实现 execute 即可            ║
║  以下 5 个 Demo 覆盖了常用 hook 类型,可直接复制使用                                ║
╚══════════════════════════════════════════════════════════════════════════════╝

┌──────────────────────────────────────────────────────────────────────────────┐
│ Demo 1/5 — PreToolUse: 阻止危险 Bash 命令                                      │
└──────────────────────────────────────────────────────────────────────────────┘

from easyCcHooks import IPreToolUse, PreToolUseInput, PreToolUseOutput, ToolName

class DenyDangerousRm(IPreToolUse):
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

┌──────────────────────────────────────────────────────────────────────────────┐
│ Demo 2/5 — PostToolUse: 写文件后自动提示                                        │
└──────────────────────────────────────────────────────────────────────────────┘

from easyCcHooks import IPostToolUse, PostToolUseInput, PostToolUseOutput, ToolName

class NotifyOnWrite(IPostToolUse):
    @property
    def matcher(self) -> str:
        return ToolName.Write

    def execute(self, input_data: PostToolUseInput) -> PostToolUseOutput:
        file_path = input_data.tool_input.get("file_path", "")
        return PostToolUseOutput(
            additional_context=f"文件已写入: {file_path},请检查内容是否正确"
        )

┌──────────────────────────────────────────────────────────────────────────────┐
│ Demo 3/5 — SessionStart: 注入项目上下文                                        │
└──────────────────────────────────────────────────────────────────────────────┘

from easyCcHooks import ISessionStart, SessionStartInput, SessionStartOutput

class ProjectInfo(ISessionStart):
    def execute(self, input_data: SessionStartInput) -> SessionStartOutput:
        cwd = Path(input_data.cwd)
        info = [f"项目目录: {cwd.name}"]
        if (cwd / ".git").exists():
            info.append("Git 仓库")
        return SessionStartOutput(
            additional_context="\\n".join(info) if info else None
        )

┌──────────────────────────────────────────────────────────────────────────────┐
│ Demo 4/5 — UserPromptSubmit: 过滤敏感信息                                      │
└──────────────────────────────────────────────────────────────────────────────┘

from easyCcHooks import IUserPromptSubmit, UserPromptSubmitInput, UserPromptSubmitOutput

class FilterSecrets(IUserPromptSubmit):
    def execute(self, input_data: UserPromptSubmitInput) -> UserPromptSubmitOutput:
        import re
        if re.search(r"(sk-|AKIA|ghp_|xox[bsp]-)\\w{10,}", input_data.prompt):
            return UserPromptSubmitOutput(
                decision="block",
                reason="检测到可能的 API Key,请移除后再提交"
            )
        return UserPromptSubmitOutput()

┌──────────────────────────────────────────────────────────────────────────────┐
│ Demo 5/5 — Stop: 阻止意外退出                                                  │
└──────────────────────────────────────────────────────────────────────────────┘

from easyCcHooks import IStop, StopInput, StopOutput

class PreventStop(IStop):
    def execute(self, input_data: StopInput) -> StopOutput:
        if not input_data.stop_hook_active:
            return StopOutput(decision="block", reason="任务可能未完成,请继续")
        return StopOutput()
"""

import sys
import json
import inspect
import argparse
import importlib.util
from abc import ABC, abstractmethod
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, asdict, field
from typing import Optional, Dict, Any, List, Type, Literal, TypeVar
from enum import Enum

T = TypeVar('T')

__version__ = "0.1.0"

# 项目根目录 (easyCcHooks.py 位于 .claude/hooks/)
PROJECT_ROOT = Path(__file__).parent.parent.parent

# 远程版本文件 URL
_VERSION_URL = "https://raw.githubusercontent.com/e1roy/easyCcHooks/refs/heads/main/version.txt"
_REMOTE_PY_URL = "https://raw.githubusercontent.com/e1roy/easyCcHooks/refs/heads/main/.claude/hooks/easyCcHooks.py"


# ============================================================================
# 工具名称枚举 - 用于 matcher 匹配
# ============================================================================

class ToolName(str, Enum):
    """Claude Code 工具名称枚举,可用于 hook 的 matcher 属性"""

    # 终端 & 文件操作
    Bash = "Bash"                        # 执行 shell 命令
    Read = "Read"                        # 读取文件内容
    Write = "Write"                      # 写入 / 创建文件
    Edit = "Edit"                        # 编辑已有文件 (字符串替换)
    NotebookEdit = "NotebookEdit"        # 编辑 Jupyter Notebook

    # 搜索
    Glob = "Glob"                        # 按文件名模式搜索
    Grep = "Grep"                        # 按内容正则搜索

    # 网络
    WebFetch = "WebFetch"                # 抓取网页内容
    WebSearch = "WebSearch"              # 搜索引擎查询

    # 代理 & 任务
    Task = "Task"                        # 启动子代理执行任务
    TodoWrite = "TodoWrite"              # 管理待办事项列表

    # 交互
    AskUserQuestion = "AskUserQuestion"  # 向用户提问
    EnterPlanMode = "EnterPlanMode"      # 进入计划模式

    # 团队协作
    SendMessage = "SendMessage"          # 发送团队消息
    TeamCreate = "TeamCreate"            # 创建团队
    TeamDelete = "TeamDelete"            # 删除团队

    # 其他
    Skill = "Skill"                      # 调用技能 (slash command)
    # all
    All = "*"


# ============================================================================
# 数据模型 - 公共基类
# ============================================================================

@dataclass
class HookInputBase:
    """Hook 输入基类 - 所有 hook 共有的字段"""
    session_id: str
    transcript_path: str
    cwd: str
    permission_mode: str
    hook_event_name: str

    @classmethod
    def from_dict(cls: Type[T], data: Dict[str, Any]) -> T:
        """从字典创建实例"""
        fields = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
        return cls(**fields)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return asdict(self)


@dataclass
class HookOutputBase:
    """Hook 输出基类"""
    continue_execution: bool = True
    suppress_output: bool = False
    system_message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        result = {}
        if not self.continue_execution:
            result["continue"] = False
        if self.suppress_output:
            result["suppressOutput"] = True
        if self.system_message:
            result["systemMessage"] = self.system_message
        return result


# ============================================================================
# 数据模型 - PreToolUse
# ============================================================================

@dataclass
class PreToolUseInput(HookInputBase):
    tool_name: str = ""
    tool_input: Dict[str, Any] = field(default_factory=dict)
    tool_use_id: str = ""


@dataclass
class PreToolUseOutput(HookOutputBase):
    permission_decision: Literal["allow", "deny", "ask"] = "allow"
    permission_decision_reason: str = ""
    updated_input: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        result = super().to_dict()
        result["hookSpecificOutput"] = {
            "hookEventName": "PreToolUse",
            "permissionDecision": self.permission_decision,
            "permissionDecisionReason": self.permission_decision_reason,
        }
        if self.updated_input is not None:
            result["hookSpecificOutput"]["updatedInput"] = self.updated_input
        return result


# ============================================================================
# 数据模型 - PermissionRequest
# ============================================================================

@dataclass
class PermissionRequestInput(HookInputBase):
    tool_name: str = ""
    tool_input: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PermissionRequestOutput(HookOutputBase):
    behavior: Literal["allow", "deny"] = "allow"
    message: Optional[str] = None
    interrupt: bool = False
    updated_input: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        result = super().to_dict()
        decision = {"behavior": self.behavior}
        if self.message:
            decision["message"] = self.message
        if self.interrupt:
            decision["interrupt"] = True
        if self.updated_input is not None:
            decision["updatedInput"] = self.updated_input
        result["hookSpecificOutput"] = {
            "hookEventName": "PermissionRequest",
            "decision": decision
        }
        return result


# ============================================================================
# 数据模型 - PostToolUse
# ============================================================================

@dataclass
class PostToolUseInput(HookInputBase):
    tool_name: str = ""
    tool_input: Dict[str, Any] = field(default_factory=dict)
    tool_response: Dict[str, Any] = field(default_factory=dict)
    tool_use_id: str = ""


@dataclass
class PostToolUseOutput(HookOutputBase):
    decision: Optional[Literal["block"]] = None
    reason: Optional[str] = None
    additional_context: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        result = super().to_dict()
        if self.decision == "block":
            result["decision"] = "block"
            if self.reason:
                result["reason"] = self.reason
        if self.additional_context:
            result["hookSpecificOutput"] = {
                "hookEventName": "PostToolUse",
                "additionalContext": self.additional_context
            }
        return result


# ============================================================================
# 数据模型 - UserPromptSubmit
# ============================================================================

@dataclass
class UserPromptSubmitInput(HookInputBase):
    prompt: str = ""


@dataclass
class UserPromptSubmitOutput(HookOutputBase):
    decision: Optional[Literal["block"]] = None
    reason: Optional[str] = None
    additional_context: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        result = super().to_dict()
        if self.decision == "block":
            result["decision"] = "block"
            if self.reason:
                result["reason"] = self.reason
        if self.additional_context:
            result["hookSpecificOutput"] = {
                "hookEventName": "UserPromptSubmit",
                "additionalContext": self.additional_context
            }
        return result


# ============================================================================
# 数据模型 - Notification
# ============================================================================

@dataclass
class NotificationInput(HookInputBase):
    message: str = ""
    notification_type: str = ""


@dataclass
class NotificationOutput(HookOutputBase):
    pass


# ============================================================================
# 数据模型 - Stop
# ============================================================================

@dataclass
class StopInput(HookInputBase):
    stop_hook_active: bool = False


@dataclass
class StopOutput(HookOutputBase):
    decision: Optional[Literal["block"]] = None
    reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        result = super().to_dict()
        if self.decision == "block":
            result["decision"] = "block"
            if self.reason:
                result["reason"] = self.reason
        return result


# ============================================================================
# 数据模型 - SubagentStop
# ============================================================================

@dataclass
class SubagentStopInput(HookInputBase):
    stop_hook_active: bool = False


@dataclass
class SubagentStopOutput(HookOutputBase):
    decision: Optional[Literal["block"]] = None
    reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        result = super().to_dict()
        if self.decision == "block":
            result["decision"] = "block"
            if self.reason:
                result["reason"] = self.reason
        return result


# ============================================================================
# 数据模型 - PreCompact
# ============================================================================

@dataclass
class PreCompactInput(HookInputBase):
    trigger: Literal["manual", "auto"] = "manual"
    custom_instructions: str = ""


@dataclass
class PreCompactOutput(HookOutputBase):
    pass


# ============================================================================
# 数据模型 - SessionStart
# ============================================================================

@dataclass
class SessionStartInput(HookInputBase):
    source: Literal["startup", "resume", "clear", "compact"] = "startup"


@dataclass
class SessionStartOutput(HookOutputBase):
    additional_context: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        result = super().to_dict()
        if self.additional_context:
            result["hookSpecificOutput"] = {
                "hookEventName": "SessionStart",
                "additionalContext": self.additional_context
            }
        return result


# ============================================================================
# 数据模型 - SessionEnd
# ============================================================================

@dataclass
class SessionEndInput(HookInputBase):
    reason: Literal["clear", "logout", "prompt_input_exit", "other"] = "other"


@dataclass
class SessionEndOutput(HookOutputBase):
    pass


# ============================================================================
# 类型映射表
# ============================================================================

INPUT_MODEL_MAP: Dict[str, Type[HookInputBase]] = {
    "PreToolUse": PreToolUseInput,
    "PermissionRequest": PermissionRequestInput,
    "PostToolUse": PostToolUseInput,
    "UserPromptSubmit": UserPromptSubmitInput,
    "Notification": NotificationInput,
    "Stop": StopInput,
    "SubagentStop": SubagentStopInput,
    "PreCompact": PreCompactInput,
    "SessionStart": SessionStartInput,
    "SessionEnd": SessionEndInput,
}


# ============================================================================
# 抽象基类
# ============================================================================

class BaseHook(ABC):
    """Hook 抽象基类"""

    @abstractmethod
    def execute(self, input_data: HookInputBase) -> HookOutputBase:
        pass

    @property
    def name(self) -> str:
        return self.__class__.__name__

    @property
    def description(self) -> str:
        doc = self.__class__.__doc__
        if doc:
            lines = [line.strip() for line in doc.strip().split('\n') if line.strip()]
            return lines[0] if lines else "无描述"
        return "无描述"

    @property
    def matcher(self) -> str:
        return "*"

    @property
    def timeout(self) -> int:
        return 10

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}: {self.description}>"


class ToolHook(BaseHook):
    """工具级 Hook 基类"""
    @property
    def matcher(self) -> str:
        return "*"


class SessionHook(BaseHook):
    """会话级 Hook 基类"""
    pass


class PromptHook(BaseHook):
    """提示级 Hook 基类"""
    pass


class NotificationHook(BaseHook):
    """通知级 Hook 基类"""
    pass


class StopHook(BaseHook):
    """停止级 Hook 基类"""
    pass


class CompactHook(BaseHook):
    """压缩级 Hook 基类"""
    pass


# ============================================================================
# Hook 接口定义
# ============================================================================

class IPreToolUse(ToolHook):
    """PreToolUse Hook 接口 - 工具调用前"""
    @abstractmethod
    def execute(self, input_data: PreToolUseInput) -> PreToolUseOutput:
        pass


class IPermissionRequest(ToolHook):
    """PermissionRequest Hook 接口 - 用户被请求授权时"""
    @abstractmethod
    def execute(self, input_data: PermissionRequestInput) -> PermissionRequestOutput:
        pass


class IPostToolUse(ToolHook):
    """PostToolUse Hook 接口 - 工具调用后"""
    @abstractmethod
    def execute(self, input_data: PostToolUseInput) -> PostToolUseOutput:
        pass


class IUserPromptSubmit(PromptHook):
    """UserPromptSubmit Hook 接口 - 用户提交提示词时"""
    @abstractmethod
    def execute(self, input_data: UserPromptSubmitInput) -> UserPromptSubmitOutput:
        pass


class INotification(NotificationHook):
    """Notification Hook 接口 - 系统发送通知时"""
    @abstractmethod
    def execute(self, input_data: NotificationInput) -> NotificationOutput:
        pass


class IStop(StopHook):
    """Stop Hook 接口 - 会话停止时"""
    @abstractmethod
    def execute(self, input_data: StopInput) -> StopOutput:
        pass


class ISubagentStop(StopHook):
    """SubagentStop Hook 接口 - 子代理停止时"""
    @abstractmethod
    def execute(self, input_data: SubagentStopInput) -> SubagentStopOutput:
        pass


class IPreCompact(CompactHook):
    """PreCompact Hook 接口 - 上下文压缩前"""
    @abstractmethod
    def execute(self, input_data: PreCompactInput) -> PreCompactOutput:
        pass


class ISessionStart(SessionHook):
    """SessionStart Hook 接口 - 会话开始时"""
    @abstractmethod
    def execute(self, input_data: SessionStartInput) -> SessionStartOutput:
        pass


class ISessionEnd(SessionHook):
    """SessionEnd Hook 接口 - 会话结束时"""
    @abstractmethod
    def execute(self, input_data: SessionEndInput) -> SessionEndOutput:
        pass


# ============================================================================
# Hook 注册中心
# ============================================================================

class HookRegistry:
    """Hook 注册中心"""

    _hooks: Dict[str, List[Type[BaseHook]]] = {
        "PreToolUse": [],
        "PermissionRequest": [],
        "PostToolUse": [],
        "UserPromptSubmit": [],
        "Notification": [],
        "Stop": [],
        "SubagentStop": [],
        "PreCompact": [],
        "SessionStart": [],
        "SessionEnd": [],
    }

    _INTERFACE_MAP: Dict[str, Type] = {
        "PreToolUse": IPreToolUse,
        "PermissionRequest": IPermissionRequest,
        "PostToolUse": IPostToolUse,
        "UserPromptSubmit": IUserPromptSubmit,
        "Notification": INotification,
        "Stop": IStop,
        "SubagentStop": ISubagentStop,
        "PreCompact": IPreCompact,
        "SessionStart": ISessionStart,
        "SessionEnd": ISessionEnd,
    }

    @classmethod
    def register(cls, hook_type: str, hook_class: Type[BaseHook], quiet: bool = False):
        """注册 hook"""
        if hook_type not in cls._hooks:
            raise ValueError(f"未知的 hook 类型: {hook_type}")
        # 用类名去重,避免 importlib 重复加载时产生不同类对象
        existing_names = [h.__name__ for h in cls._hooks[hook_type]]
        if hook_class.__name__ in existing_names:
            return
        cls._hooks[hook_type].append(hook_class)
        if not quiet:
            print(f"✓ 已注册: {hook_type}.{hook_class.__name__}")

    @classmethod
    def _register_from_module(cls, module, quiet: bool = False):
        """从模块中扫描并注册 hook 实现"""
        for _, obj in inspect.getmembers(module, inspect.isclass):
            for hook_type, interface in cls._INTERFACE_MAP.items():
                if issubclass(obj, interface) and obj != interface:
                    if hasattr(obj, "_hook_config"):
                        if not obj._hook_config.get("enabled", True):
                            continue
                    cls.register(hook_type, obj, quiet=quiet)

    @classmethod
    def scan_and_register(cls, quiet: bool = False, include_tests: bool = False):
        """扫描当前文件及同目录下的 .py 文件中的 hook 实现并注册"""
        # 1. 扫描当前文件
        cls._register_from_module(sys.modules[__name__], quiet=quiet)

        # 2. 递归扫描同目录及子目录下的 .py 文件
        hooks_dir = Path(__file__).parent
        for py_file in hooks_dir.rglob("*.py"):
            if py_file.name == Path(__file__).name:
                continue
            # 默认跳过 tests/ 目录,避免示例 hook 被当作生产 hook 加载
            if not include_tests:
                try:
                    py_file.relative_to(hooks_dir / "tests")
                    continue
                except ValueError:
                    pass
            module_name = py_file.stem
            try:
                spec = importlib.util.spec_from_file_location(module_name, py_file)
                if spec and spec.loader:
                    mod = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(mod)
                    cls._register_from_module(mod, quiet=quiet)
            except Exception as e:
                print(f"⚠️  加载 {py_file.name} 失败: {e}", file=sys.stderr)

    @classmethod
    def get_hook(cls, hook_class_name: str) -> Optional[Type[BaseHook]]:
        """根据类名获取 hook"""
        for hooks in cls._hooks.values():
            for hook in hooks:
                if hook.__name__ == hook_class_name:
                    return hook
        return None

    @classmethod
    def get_all(cls) -> Dict[str, List[Type[BaseHook]]]:
        """获取所有已注册的 hooks"""
        return cls._hooks

    @classmethod
    def generate_config(cls) -> dict:
        """生成 settings.json 配置"""
        config = {"hooks": {}}
        for hook_type, hooks in cls._hooks.items():
            if not hooks:
                continue
            hook_configs = []
            for hook in hooks:
                try:
                    instance = hook()
                except Exception as e:
                    print(f"⚠️  无法创建实例: {hook.__name__} - {e}")
                    continue

                if hasattr(hook, "_hook_config"):
                    hook_config = hook._hook_config
                else:
                    hook_config = {
                        "matcher": getattr(instance, "matcher", "*"),
                        "timeout": getattr(instance, "timeout", 10)
                    }

                hook_entry = {
                    "hooks": [{
                        "type": "command",
                        "command": f'python3 "$CLAUDE_PROJECT_DIR"/.claude/hooks/easyCcHooks.py execute {hook.__name__}',
                        "timeout": hook_config.get("timeout", 10)
                    }]
                }

                tool_level_hooks = ["PreToolUse", "PermissionRequest", "PostToolUse", "Notification", "PreCompact"]
                if hook_type in tool_level_hooks:
                    hook_entry["matcher"] = hook_config.get("matcher", "*")

                hook_configs.append(hook_entry)
            config["hooks"][hook_type] = hook_configs
        return config

    @classmethod
    def list_hooks(cls):
        """列出所有已注册的 hook"""
        total = 0
        for hook_type, hooks in cls._hooks.items():
            if hooks:
                print(f"\n{hook_type}:")
                for hook in hooks:
                    instance = hook()
                    print(f"  - {hook.__name__}: {instance.description}")
                    total += 1
        print(f"\n总计: {total} 个 hook")


# ============================================================================
# Hook 执行器
# ============================================================================

class HookExecutor:
    """Hook 执行器"""

    @staticmethod
    def execute_from_stdin(hook_class_name: str):
        """从 stdin 读取输入,执行指定 hook"""
        try:
            input_data = json.load(sys.stdin)
            hook_event = input_data.get("hook_event_name")
            if not hook_event:
                raise ValueError("缺少 hook_event_name 字段")

            hook_class = HookRegistry.get_hook(hook_class_name)
            if not hook_class:
                raise ValueError(f"未找到 hook: {hook_class_name}")

            input_model_class = INPUT_MODEL_MAP.get(hook_event)
            if not input_model_class:
                raise ValueError(f"未知的 hook 事件: {hook_event}")

            input_model = input_model_class.from_dict(input_data)
            output = hook_class().execute(input_model)
            print(json.dumps(output.to_dict(), ensure_ascii=False))
            sys.exit(0)

        except Exception as e:
            print(f"Hook 执行错误: {e}", file=sys.stderr)
            print(json.dumps({"continue": True, "suppressOutput": False}))
            sys.exit(1)

    @staticmethod
    def test_hook(hook_class_name: str, input_file: str):
        """测试指定 hook"""
        try:
            with open(input_file) as f:
                input_data = json.load(f)

            hook_event = input_data.get("hook_event_name")
            if not hook_event:
                raise ValueError("缺少 hook_event_name 字段")

            hook_class = HookRegistry.get_hook(hook_class_name)
            if not hook_class:
                raise ValueError(f"未找到 hook: {hook_class_name}")

            input_model_class = INPUT_MODEL_MAP.get(hook_event)
            if not input_model_class:
                raise ValueError(f"未知的 hook 事件: {hook_event}")

            input_model = input_model_class.from_dict(input_data)

            print(f"🧪 测试 {hook_class_name}...")
            print(f"📥 输入: {input_data}")
            print()

            output = hook_class().execute(input_model)
            print(f"📤 输出:")
            print(json.dumps(output.to_dict(), indent=2, ensure_ascii=False))
            print()
            print("✅ 测试通过")

        except Exception as e:
            print(f"❌ 测试失败: {e}", file=sys.stderr)
            sys.exit(1)


# ============================================================================
# 配置管理器
# ============================================================================

class ConfigManager:
    """settings.json 配置管理器"""

    @staticmethod
    def _is_managed_command(command: str) -> bool:
        """判断 command 是否为 easyCcHooks 自动生成的托管命令"""
        if not isinstance(command, str):
            return False
        return command.startswith('python3 "$CLAUDE_PROJECT_DIR"/.claude/hooks/easyCcHooks.py execute ')

    @classmethod
    def _is_managed_hook_entry(cls, hook_entry: Any) -> bool:
        """判断 hook entry 是否为 easyCcHooks 自动托管项"""
        if not isinstance(hook_entry, dict):
            return False

        commands = hook_entry.get("hooks")
        if not isinstance(commands, list) or not commands:
            return False

        for command_entry in commands:
            if not isinstance(command_entry, dict):
                return False
            if command_entry.get("type") != "command":
                return False
            if not cls._is_managed_command(command_entry.get("command")):
                return False
        return True

    @classmethod
    def _merge_hooks(cls, existing_hooks: Any, generated_hooks: dict) -> dict:
        """合并 hooks:
        - 替换托管项 (防止失效项残留)
        - 保留用户手写项
        """
        if not isinstance(existing_hooks, dict):
            existing_hooks = {}

        merged_hooks = {}

        # 先按用户原有顺序保留手写项,再拼接当前扫描生成的托管项
        for hook_type, hook_entries in existing_hooks.items():
            preserved_entries = []
            if isinstance(hook_entries, list):
                preserved_entries = [
                    entry for entry in hook_entries
                    if not cls._is_managed_hook_entry(entry)
                ]
            generated_entries = generated_hooks.get(hook_type, [])
            combined_entries = preserved_entries + generated_entries
            if combined_entries:
                merged_hooks[hook_type] = combined_entries

        # 新增的托管 hook 类型
        for hook_type, generated_entries in generated_hooks.items():
            if hook_type in merged_hooks:
                continue
            if generated_entries:
                merged_hooks[hook_type] = generated_entries

        return merged_hooks

    @staticmethod
    def update_settings(settings_path: Path, backup: bool = True):
        """更新 settings.json,注入 hook 配置"""
        if settings_path.exists():
            with open(settings_path, encoding="utf-8") as f:
                config = json.load(f)
            if backup:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_filename = f"{settings_path.stem}.backup.{timestamp}.json"
                backup_path = settings_path.parent / backup_filename
                with open(backup_path, "w", encoding="utf-8") as f:
                    json.dump(config, f, indent=2, ensure_ascii=False)
                print(f"✓ 已备份: {backup_path}")
        else:
            config = {}

        new_hooks = HookRegistry.generate_config()
        config["hooks"] = ConfigManager._merge_hooks(
            config.get("hooks"),
            new_hooks.get("hooks", {})
        )

        settings_path.parent.mkdir(parents=True, exist_ok=True)
        with open(settings_path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        print(f"✓ 配置已更新: {settings_path}")


# ============================================================================
# CLI 命令
# ============================================================================

SETTINGS_PATH = PROJECT_ROOT / ".claude/settings.json"


def cmd_scan(args):
    """扫描并注册所有 hook"""
    print("🔍 扫描 hook 实现...")
    HookRegistry.scan_and_register()
    total = sum(len(hooks) for hooks in HookRegistry.get_all().values())
    print(f"\n✅ 扫描完成,共注册 {total} 个 hook")


def cmd_update_config(args):
    """更新 settings.json 配置"""
    print("📝 更新配置...")
    HookRegistry.scan_and_register()
    ConfigManager.update_settings(SETTINGS_PATH, backup=not args.no_backup)
    print("\n✅ 配置更新完成")


def cmd_list(args):
    """列出所有已注册的 hook"""
    print("📋 已注册的 hook:\n")
    HookRegistry.scan_and_register()
    HookRegistry.list_hooks()


def cmd_test(args):
    """测试特定 hook"""
    HookRegistry.scan_and_register(include_tests=True)
    HookExecutor.test_hook(args.hook_name, args.input)


def cmd_execute(args):
    """执行 hook (由 Claude Code 调用)"""
    HookRegistry.scan_and_register(quiet=True)
    HookExecutor.execute_from_stdin(args.hook_name)


def _fetch_url(url: str) -> str:
    """通过 urllib 获取 URL 内容"""
    import urllib.request
    import urllib.error
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            return resp.read().decode("utf-8")
    except urllib.error.URLError as e:
        raise RuntimeError(f"网络请求失败: {e}") from e


def cmd_upgrade(args):
    """检查更新并升级 easyCcHooks.py"""
    print(f"当前版本: {__version__}")
    print("检查远程版本...")

    try:
        remote_version = _fetch_url(_VERSION_URL).strip()
    except RuntimeError as e:
        print(f"❌ {e}", file=sys.stderr)
        sys.exit(1)

    print(f"远程版本: {remote_version}")

    if remote_version == __version__:
        print("\n✅ 已是最新版本")
        return

    if not args.yes:
        answer = input(f"\n发现新版本 {remote_version},是否升级? [y/N] ").strip()
        if answer.lower() not in ("y", "yes"):
            print("已取消")
            return

    print("下载中...")
    try:
        new_content = _fetch_url(_REMOTE_PY_URL)
    except RuntimeError as e:
        print(f"❌ {e}", file=sys.stderr)
        sys.exit(1)

    local_path = Path(__file__)

    # 备份当前文件
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = local_path.with_suffix(f".backup.{timestamp}.py")
    backup_path.write_text(local_path.read_text(encoding="utf-8"), encoding="utf-8")
    print(f"✓ 已备份: {backup_path.name}")

    # 写入新文件
    local_path.write_text(new_content, encoding="utf-8")
    print(f"✓ 已更新: {local_path.name}")
    print(f"\n✅ 升级完成: {__version__} → {remote_version}")


def main():
    parser = argparse.ArgumentParser(
        description="Claude Code Hooks 管理工具",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    subparsers = parser.add_subparsers(dest="command", help="子命令")

    subparsers.add_parser("scan", help="扫描并注册所有 hook").set_defaults(func=cmd_scan)

    p_update = subparsers.add_parser("update-config", help="更新 settings.json 配置")
    p_update.add_argument("--no-backup", action="store_true", help="不备份原配置文件")
    p_update.set_defaults(func=cmd_update_config)

    subparsers.add_parser("list", help="列出所有已注册的 hook").set_defaults(func=cmd_list)

    p_test = subparsers.add_parser("test", help="测试特定 hook")
    p_test.add_argument("hook_name", help="Hook 类名")
    p_test.add_argument("--input", required=True, help="测试输入 JSON 文件路径")
    p_test.set_defaults(func=cmd_test)

    p_exec = subparsers.add_parser("execute", help="执行 hook (由 Claude Code 调用)")
    p_exec.add_argument("hook_name", help="Hook 类名")
    p_exec.set_defaults(func=cmd_execute)

    p_upgrade = subparsers.add_parser("upgrade", help="检查更新并升级框架")
    p_upgrade.add_argument("-y", "--yes", action="store_true", help="跳过确认直接升级")
    p_upgrade.set_defaults(func=cmd_upgrade)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)
    args.func(args)


if __name__ == "__main__":
    # 确保外部 hook 文件通过 "from easyCcHooks import ..." 导入时
    # 使用的是同一个模块实例,避免类继承关系断裂
    sys.modules["easyCcHooks"] = sys.modules[__name__]
    main()
