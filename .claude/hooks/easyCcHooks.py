#!/usr/bin/env python3
"""
EasyCcHooks - Claude Code Hooks All-in-One Tool

Contains:
- Data Models (dataclass)
- Abstract Base Classes & Hook Interfaces
- Registry & Executor & Config Manager
- CLI Command-line Tool

Hook implementations are placed in .py files in the same directory and auto-loaded during scan.
See tests/example_hooks.py for example implementations.

Usage:
    # 
    python3 .claude/hooks/easyCcHooks.py update-config                    # Update settings.json
    python3 .claude/hooks/easyCcHooks.py upgrade                          # Check for updates and upgrade
    # 
    python3 .claude/hooks/easyCcHooks.py scan                             # Scan and register all hooks
    python3 .claude/hooks/easyCcHooks.py list                             # List registered hooks
    python3 .claude/hooks/easyCcHooks.py test <hook> --input <file>       # Test a hook
    python3 .claude/hooks/easyCcHooks.py execute <hook>                   # Execute hook (called by Claude Code)

╔══════════════════════════════════════════════════════════════════════════════╗
║  Example: Create .py files in .claude/hooks/, inherit interfaces, implement  ║
║  execute method. The following 5 demos cover common hook types for direct use║
╚══════════════════════════════════════════════════════════════════════════════╝

┌──────────────────────────────────────────────────────────────────────────────┐
│ Demo 1/5 — PreToolUse: Block Dangerous Bash Commands                         │
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
                permission_decision_reason="Root directory deletion is forbidden"
            )
        return PreToolUseOutput(permission_decision="allow")

┌──────────────────────────────────────────────────────────────────────────────┐
│ Demo 2/5 — PostToolUse: Auto Notification After File Write                   │
└──────────────────────────────────────────────────────────────────────────────┘

from easyCcHooks import IPostToolUse, PostToolUseInput, PostToolUseOutput, ToolName

class NotifyOnWrite(IPostToolUse):
    @property
    def matcher(self) -> str:
        return ToolName.Write

    def execute(self, input_data: PostToolUseInput) -> PostToolUseOutput:
        file_path = input_data.tool_input.get("file_path", "")
        return PostToolUseOutput(
            additional_context=f"File written: {file_path}, please verify the content"
        )

┌──────────────────────────────────────────────────────────────────────────────┐
│ Demo 3/5 — SessionStart: Inject Project Context                              │
└──────────────────────────────────────────────────────────────────────────────┘

from easyCcHooks import ISessionStart, SessionStartInput, SessionStartOutput

class ProjectInfo(ISessionStart):
    def execute(self, input_data: SessionStartInput) -> SessionStartOutput:
        cwd = Path(input_data.cwd)
        info = [f"Project directory: {cwd.name}"]
        if (cwd / ".git").exists():
            info.append("Git repository")
        return SessionStartOutput(
            additional_context="\\n".join(info) if info else None
        )

┌──────────────────────────────────────────────────────────────────────────────┐
│ Demo 4/5 — UserPromptSubmit: Filter Sensitive Information                    │
└──────────────────────────────────────────────────────────────────────────────┘

from easyCcHooks import IUserPromptSubmit, UserPromptSubmitInput, UserPromptSubmitOutput

class FilterSecrets(IUserPromptSubmit):
    def execute(self, input_data: UserPromptSubmitInput) -> UserPromptSubmitOutput:
        import re
        if re.search(r"(sk-|AKIA|ghp_|xox[bsp]-)\\w{10,}", input_data.prompt):
            return UserPromptSubmitOutput(
                decision="block",
                reason="Possible API Key detected, please remove before submitting"
            )
        return UserPromptSubmitOutput()

┌──────────────────────────────────────────────────────────────────────────────┐
│ Demo 5/5 — Stop: Prevent Accidental Exit                                     │
└──────────────────────────────────────────────────────────────────────────────┘

from easyCcHooks import IStop, StopInput, StopOutput

class PreventStop(IStop):
    def execute(self, input_data: StopInput) -> StopOutput:
        if not input_data.stop_hook_active:
            return StopOutput(decision="block", reason="Task may be incomplete, please continue")
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

# Project root directory (easyCcHooks.py is located in .claude/hooks/)
PROJECT_ROOT = Path(__file__).parent.parent.parent

# Remote version file URL
_VERSION_URL = "https://raw.githubusercontent.com/e1roy/easyCcHooks/refs/heads/main/version.txt"
_REMOTE_PY_URL = "https://raw.githubusercontent.com/e1roy/easyCcHooks/refs/heads/main/.claude/hooks/easyCcHooks.py"


# ============================================================================
# Tool Name Enumeration - For matcher matching
# ============================================================================

class ToolName(str, Enum):
    """Claude Code tool name enumeration, can be used for hook's matcher property"""

    # Terminal & File Operations
    Bash = "Bash"                        # Execute shell commands
    Read = "Read"                        # Read file content
    Write = "Write"                      # Write / create file
    Edit = "Edit"                        # Edit existing file (string replacement)
    NotebookEdit = "NotebookEdit"        # Edit Jupyter Notebook

    # Search
    Glob = "Glob"                        # Search by filename pattern
    Grep = "Grep"                        # Search by content regex

    # Network
    WebFetch = "WebFetch"                # Fetch web content
    WebSearch = "WebSearch"              # Search engine query

    # Agent & Task
    Task = "Task"                        # Launch subagent to execute task
    TodoWrite = "TodoWrite"              # Manage todo list

    # Interaction
    AskUserQuestion = "AskUserQuestion"  # Ask user a question
    EnterPlanMode = "EnterPlanMode"      # Enter planning mode

    # Team Collaboration
    SendMessage = "SendMessage"          # Send team message
    TeamCreate = "TeamCreate"            # Create team
    TeamDelete = "TeamDelete"            # Delete team

    # Others
    Skill = "Skill"                      # Invoke skill (slash command)
    # all
    All = "*"


# ============================================================================
# Data Models - Common Base Classes
# ============================================================================

@dataclass
class HookInputBase:
    """Hook input base class - fields common to all hooks"""
    session_id: str
    transcript_path: str
    cwd: str
    permission_mode: str
    hook_event_name: str

    @classmethod
    def from_dict(cls: Type[T], data: Dict[str, Any]) -> T:
        """Create instance from dictionary"""
        fields = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
        return cls(**fields)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)


@dataclass
class HookOutputBase:
    """Hook output base class"""
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
# Abstract Base Classes
# ============================================================================

class BaseHook(ABC):
    """Hook abstract base class"""

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
            return lines[0] if lines else "No description"
        return "No description"

    @property
    def matcher(self) -> str:
        return "*"

    @property
    def timeout(self) -> int:
        return 10

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}: {self.description}>"


class ToolHook(BaseHook, ABC):
    """Tool-level hook base class"""
    @property
    def matcher(self) -> str:
        return "*"


class SessionHook(BaseHook, ABC):
    """Session-level hook base class"""
    pass


class PromptHook(BaseHook, ABC):
    """Prompt-level hook base class"""
    pass


class NotificationHook(BaseHook, ABC):
    """Notification-level hook base class"""
    pass


class StopHook(BaseHook, ABC):
    """Stop-level hook base class"""
    pass


class CompactHook(BaseHook, ABC):
    """Compact-level hook base class"""
    pass


# ============================================================================
# Hook Interface Definitions
# ============================================================================

class IPreToolUse(ToolHook, ABC):
    """PreToolUse Hook Interface - Before tool invocation"""
    @abstractmethod
    def execute(self, input_data: PreToolUseInput) -> PreToolUseOutput:
        pass


class IPermissionRequest(ToolHook, ABC):
    """PermissionRequest Hook Interface - When user is requested for permission"""
    @abstractmethod
    def execute(self, input_data: PermissionRequestInput) -> PermissionRequestOutput:
        pass


class IPostToolUse(ToolHook, ABC):
    """PostToolUse Hook Interface - After tool invocation"""
    @abstractmethod
    def execute(self, input_data: PostToolUseInput) -> PostToolUseOutput:
        pass


class IUserPromptSubmit(PromptHook, ABC):
    """UserPromptSubmit Hook Interface - When user submits prompt"""
    @abstractmethod
    def execute(self, input_data: UserPromptSubmitInput) -> UserPromptSubmitOutput:
        pass


class INotification(NotificationHook, ABC):
    """Notification Hook Interface - When system sends notification"""
    @abstractmethod
    def execute(self, input_data: NotificationInput) -> NotificationOutput:
        pass


class IStop(StopHook, ABC):
    """Stop Hook Interface - When session stops"""
    @abstractmethod
    def execute(self, input_data: StopInput) -> StopOutput:
        pass


class ISubagentStop(StopHook, ABC):
    """SubagentStop Hook Interface - When subagent stops"""
    @abstractmethod
    def execute(self, input_data: SubagentStopInput) -> SubagentStopOutput:
        pass


class IPreCompact(CompactHook, ABC):
    """PreCompact Hook Interface - Before context compaction"""
    @abstractmethod
    def execute(self, input_data: PreCompactInput) -> PreCompactOutput:
        pass


class ISessionStart(SessionHook, ABC):
    """SessionStart Hook Interface - When session starts"""
    @abstractmethod
    def execute(self, input_data: SessionStartInput) -> SessionStartOutput:
        pass


class ISessionEnd(SessionHook, ABC):
    """SessionEnd Hook Interface - When session ends"""
    @abstractmethod
    def execute(self, input_data: SessionEndInput) -> SessionEndOutput:
        pass


# ============================================================================
# Hook Registry
# ============================================================================

class HookRegistry:
    """Hook registry center"""

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
        """Register hook"""
        if hook_type not in cls._hooks:
            raise ValueError(f"Unknown hook type: {hook_type}")
        # Deduplicate by class name to avoid different class objects from repeated importlib loading
        existing_names = [h.__name__ for h in cls._hooks[hook_type]]
        if hook_class.__name__ in existing_names:
            return
        cls._hooks[hook_type].append(hook_class)
        if not quiet:
            print(f"✓ Registered: {hook_type}.{hook_class.__name__}")

    @classmethod
    def _register_from_module(cls, module, quiet: bool = False):
        """Scan and register hook implementations from module"""
        for _, obj in inspect.getmembers(module, inspect.isclass):
            for hook_type, interface in cls._INTERFACE_MAP.items():
                if issubclass(obj, interface) and obj != interface:
                    if hasattr(obj, "_hook_config"):
                        if not obj._hook_config.get("enabled", True):
                            continue
                    cls.register(hook_type, obj, quiet=quiet)

    @classmethod
    def scan_and_register(cls, quiet: bool = False, include_tests: bool = False):
        """Scan and register hook implementations in current file and .py files in the same directory"""
        # 1. Scan current file
        cls._register_from_module(sys.modules[__name__], quiet=quiet)

        # 2. Recursively scan .py files in the same directory and subdirectories
        hooks_dir = Path(__file__).parent
        for py_file in hooks_dir.rglob("*.py"):
            if py_file.name == Path(__file__).name:
                continue
            # Skip tests/ directory by default to avoid loading example hooks as production hooks
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
                print(f"⚠️  Failed to load {py_file.name}: {e}", file=sys.stderr)

    @classmethod
    def get_hook(cls, hook_class_name: str) -> Optional[Type[BaseHook]]:
        """Get hook by class name"""
        for hooks in cls._hooks.values():
            for hook in hooks:
                if hook.__name__ == hook_class_name:
                    return hook
        return None

    @classmethod
    def get_all(cls) -> Dict[str, List[Type[BaseHook]]]:
        """Get all registered hooks"""
        return cls._hooks

    @classmethod
    def generate_config(cls) -> dict:
        """Generate settings.json configuration"""
        config = {"hooks": {}}
        for hook_type, hooks in cls._hooks.items():
            if not hooks:
                continue
            hook_configs = []
            for hook in hooks:
                try:
                    instance = hook()
                except Exception as e:
                    print(f"⚠️  Cannot create instance: {hook.__name__} - {e}")
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
        """List all registered hooks"""
        total = 0
        for hook_type, hooks in cls._hooks.items():
            if hooks:
                print(f"\n{hook_type}:")
                for hook in hooks:
                    instance = hook()
                    print(f"  - {hook.__name__}: {instance.description}")
                    total += 1
        print(f"\nTotal: {total} hooks")


# ============================================================================
# Hook Executor
# ============================================================================

class HookExecutor:
    """Hook executor"""

    @staticmethod
    def execute_from_stdin(hook_class_name: str):
        """Read input from stdin and execute specified hook"""
        try:
            input_data = json.load(sys.stdin)
            hook_event = input_data.get("hook_event_name")
            if not hook_event:
                raise ValueError("Missing hook_event_name field")

            hook_class = HookRegistry.get_hook(hook_class_name)
            if not hook_class:
                raise ValueError(f"Hook not found: {hook_class_name}")

            input_model_class = INPUT_MODEL_MAP.get(hook_event)
            if not input_model_class:
                raise ValueError(f"Unknown hook event: {hook_event}")

            input_model = input_model_class.from_dict(input_data)
            output = hook_class().execute(input_model)
            print(json.dumps(output.to_dict(), ensure_ascii=False))
            sys.exit(0)

        except Exception as e:
            print(f"Hook execution error: {e}", file=sys.stderr)
            print(json.dumps({"continue": True, "suppressOutput": False}))
            sys.exit(1)

    @staticmethod
    def test_hook(hook_class_name: str, input_file: str):
        """Test specified hook"""
        try:
            with open(input_file) as f:
                input_data = json.load(f)

            hook_event = input_data.get("hook_event_name")
            if not hook_event:
                raise ValueError("Missing hook_event_name field")

            hook_class = HookRegistry.get_hook(hook_class_name)
            if not hook_class:
                raise ValueError(f"Hook not found: {hook_class_name}")

            input_model_class = INPUT_MODEL_MAP.get(hook_event)
            if not input_model_class:
                raise ValueError(f"Unknown hook event: {hook_event}")

            input_model = input_model_class.from_dict(input_data)

            print(f"🧪 Testing {hook_class_name}...")
            print(f"📥 Input: {input_data}")
            print()

            output = hook_class().execute(input_model)
            print(f"📤 Output:")
            print(json.dumps(output.to_dict(), indent=2, ensure_ascii=False))
            print()
            print("✅ Test passed")

        except Exception as e:
            print(f"❌ Test failed: {e}", file=sys.stderr)
            sys.exit(1)


# ============================================================================
# Config Manager
# ============================================================================

class ConfigManager:
    """settings.json configuration manager"""

    @staticmethod
    def _is_managed_command(command: str) -> bool:
        """Check if command is an automatically generated managed command by easyCcHooks"""
        if not isinstance(command, str):
            return False
        return command.startswith('python3 "$CLAUDE_PROJECT_DIR"/.claude/hooks/easyCcHooks.py execute ')

    @classmethod
    def _is_managed_hook_entry(cls, hook_entry: Any) -> bool:
        """Check if hook entry is automatically managed by easyCcHooks"""
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
        """Merge hooks:
        - Replace managed entries (prevent stale entries)
        - Preserve user-written entries
        """
        if not isinstance(existing_hooks, dict):
            existing_hooks = {}

        merged_hooks = {}

        # First preserve user-written entries in original order, then append currently scanned managed entries
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

        # New managed hook types
        for hook_type, generated_entries in generated_hooks.items():
            if hook_type in merged_hooks:
                continue
            if generated_entries:
                merged_hooks[hook_type] = generated_entries

        return merged_hooks

    @staticmethod
    def update_settings(settings_path: Path, backup: bool = True):
        """Update settings.json and inject hook configuration"""
        if settings_path.exists():
            with open(settings_path, encoding="utf-8") as f:
                config = json.load(f)
            if backup:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_filename = f"{settings_path.stem}.backup.{timestamp}.json"
                backup_path = settings_path.parent / backup_filename
                with open(backup_path, "w", encoding="utf-8") as f:
                    json.dump(config, f, indent=2, ensure_ascii=False)
                print(f"✓ Backed up: {backup_path}")
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
        print(f"✓ Configuration updated: {settings_path}")


# ============================================================================
# CLI Commands
# ============================================================================

SETTINGS_PATH = PROJECT_ROOT / ".claude/settings.json"


def cmd_scan(args):
    """Scan and register all hooks"""
    print("🔍 Scanning hook implementations...")
    HookRegistry.scan_and_register()
    total = sum(len(hooks) for hooks in HookRegistry.get_all().values())
    print(f"\n✅ Scan complete, registered {total} hooks")


def cmd_update_config(args):
    """Update settings.json configuration"""
    print("📝 Updating configuration...")
    HookRegistry.scan_and_register()
    ConfigManager.update_settings(SETTINGS_PATH, backup=not args.no_backup)
    print("\n✅ Configuration update complete")


def cmd_list(args):
    """List all registered hooks"""
    print("📋 Registered hooks:\n")
    HookRegistry.scan_and_register()
    HookRegistry.list_hooks()


def cmd_test(args):
    """Test specific hook"""
    HookRegistry.scan_and_register(include_tests=True)
    HookExecutor.test_hook(args.hook_name, args.input)


def cmd_execute(args):
    """Execute hook (called by Claude Code)"""
    HookRegistry.scan_and_register(quiet=True)
    HookExecutor.execute_from_stdin(args.hook_name)


def _fetch_url(url: str) -> str:
    """Fetch URL content via urllib"""
    import urllib.request
    import urllib.error
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            return resp.read().decode("utf-8")
    except urllib.error.URLError as e:
        raise RuntimeError(f"Network request failed: {e}") from e


def cmd_upgrade(args):
    """Check for updates and upgrade easyCcHooks.py"""
    print(f"Current version: {__version__}")
    print("Checking remote version...")

    try:
        remote_version = _fetch_url(_VERSION_URL).strip()
    except RuntimeError as e:
        print(f"❌ {e}", file=sys.stderr)
        sys.exit(1)

    print(f"Remote version: {remote_version}")

    if remote_version == __version__:
        print("\n✅ Already at latest version")
        return

    if not args.yes:
        answer = input(f"\nNew version {remote_version} found, upgrade? [y/N] ").strip()
        if answer.lower() not in ("y", "yes"):
            print("Cancelled")
            return

    print("Downloading...")
    try:
        new_content = _fetch_url(_REMOTE_PY_URL)
    except RuntimeError as e:
        print(f"❌ {e}", file=sys.stderr)
        sys.exit(1)

    local_path = Path(__file__)

    # Backup current file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = local_path.with_suffix(f".backup.{timestamp}.py")
    backup_path.write_text(local_path.read_text(encoding="utf-8"), encoding="utf-8")
    print(f"✓ Backed up: {backup_path.name}")

    # Write new file
    local_path.write_text(new_content, encoding="utf-8")
    print(f"✓ Updated: {local_path.name}")
    print(f"\n✅ Upgrade complete: {__version__} → {remote_version}")


def main():
    parser = argparse.ArgumentParser(
        description="Claude Code Hooks Management Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    subparsers = parser.add_subparsers(dest="command", help="Subcommands")

    subparsers.add_parser("scan", help="Scan and register all hooks").set_defaults(func=cmd_scan)

    p_update = subparsers.add_parser("update-config", help="Update settings.json configuration")
    p_update.add_argument("--no-backup", action="store_true", help="Do not backup original config file")
    p_update.set_defaults(func=cmd_update_config)

    subparsers.add_parser("list", help="List all registered hooks").set_defaults(func=cmd_list)

    p_test = subparsers.add_parser("test", help="Test specific hook")
    p_test.add_argument("hook_name", help="Hook class name")
    p_test.add_argument("--input", required=True, help="Test input JSON file path")
    p_test.set_defaults(func=cmd_test)

    p_exec = subparsers.add_parser("execute", help="Execute hook (called by Claude Code)")
    p_exec.add_argument("hook_name", help="Hook class name")
    p_exec.set_defaults(func=cmd_execute)

    p_upgrade = subparsers.add_parser("upgrade", help="Check for updates and upgrade framework")
    p_upgrade.add_argument("-y", "--yes", action="store_true", help="Skip confirmation and upgrade directly")
    p_upgrade.set_defaults(func=cmd_upgrade)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)
    args.func(args)


if __name__ == "__main__":
    # Ensure external hook files importing via "from easyCcHooks import ..."
    # use the same module instance to avoid breaking class inheritance relationships
    sys.modules["easyCcHooks"] = sys.modules[__name__]
    main()
