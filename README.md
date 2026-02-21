# Claude Code Hooks Framework

[简体中文](README_CN.md) | English

A type-safe, automated Claude Code Hook template system.

> See [ARCHITECTURE.md](ARCHITECTURE.md) for framework architecture and implementation details

## Features

- Type-safe: Using Python dataclass and type hints
- Auto-configuration: Automatically generate and update settings.json
- Clear interfaces: Abstract base classes for 10 hook types
- Single-file framework: All framework code in `easyCcHooks.py`
- Easy testing: Provides testing tools and CLI

## Installation

Run one-click installation in your project root directory:

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/e1roy/easyCcHooks/main/install.sh)
```

The installation script will download `easyCcHooks.py` to the `.claude/hooks/` directory. If the project doesn't have a `.claude` directory, the script will ask whether to create it.

## Upgrade

```bash
python3 .claude/hooks/easyCcHooks.py upgrade
```

This command checks the remote version and updates automatically. Use `-y` to skip confirmation prompts.

## Quick Start

### 1. Create Hook Implementation

Create your hook implementation file in the `.claude/hooks/` directory:

```python
# .claude/hooks/MyBashValidator.py
from easyCcHooks import IPreToolUse, PreToolUseInput, PreToolUseOutput, ToolName

class MyBashValidator(IPreToolUse):
    """
    Custom Bash command validator

    Features:
    - Block dangerous rm commands
    - Log all commands
    """

    @property
    def matcher(self) -> str:
        return ToolName.Bash  # Only match Bash tool

    def execute(self, input_data: PreToolUseInput) -> PreToolUseOutput:
        command = input_data.tool_input.get("command", "")

        # Check for dangerous commands
        if "rm -rf /" in command:
            return PreToolUseOutput(
                permission_decision="deny",
                permission_decision_reason="Root directory deletion is forbidden"
            )

        # Allow execution
        return PreToolUseOutput(
            permission_decision="allow",
            permission_decision_reason="Command is safe"
        )
```

### 2. Scan and Register

```bash
cd .claude/hooks
python3 easyCcHooks.py scan
```

Output:
```
Scanning hook implementations...
Registered: PreToolUse.MyBashValidator
Scan complete, 1 hook registered
```

### 3. Update Configuration

```bash
python3 easyCcHooks.py update-config
```

Output:
```
Updating configuration...
Configuration updated: .claude/settings.json
Configuration update complete
```

### 4. Verify Activation

The hook will be automatically loaded and take effect the next time Claude Code starts.

## CLI Commands

All commands are executed through `easyCcHooks.py`:

### scan - Scan and Register Hooks

```bash
python3 easyCcHooks.py scan
```

Scan `.py` files in the `.claude/hooks/` directory and register all hook implementations.

### update-config - Update Configuration

```bash
python3 easyCcHooks.py update-config
```

Automatically update the `.claude/settings.json` configuration file.

### list - List All Hooks

```bash
python3 easyCcHooks.py list
```

Display all registered hooks and their descriptions.

### test - Test Hooks

```bash
# Use existing test files (located in tests/ directory)
python3 easyCcHooks.py test ValidateBashCommand --input tests/test_input_dangerous.json

# Or create custom test input
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

# Test the hook
python3 easyCcHooks.py test MyBashValidator --input tests/test_input_custom.json
```

See [tests/README.md](tests/README.md) for more testing usage.

### execute - Execute Hook (Internal Use)

```bash
# Automatically called by Claude Code
echo '{"hook_event_name":"PreToolUse",...}' | python3 easyCcHooks.py execute MyBashValidator
```

### upgrade - Check Updates and Upgrade

```bash
python3 easyCcHooks.py upgrade
```

Check the latest remote version, and automatically download updates after confirmation. Use `-y` to skip confirmation:

```bash
python3 easyCcHooks.py upgrade -y
```

## Hook Interfaces

The framework provides 10 hook interfaces, all defined in `easyCcHooks.py`:

| Interface | Trigger Timing | Use Cases |
| ---- | -------- | -------- |
| IPreToolUse | Before tool invocation | Validate commands, modify parameters, log |
| IPermissionRequest | On permission request | Auto-approve, log permission requests |
| IPostToolUse | After tool invocation | Validate results, trigger follow-up actions |
| IUserPromptSubmit | On user prompt submission | Inject context, preprocess input |
| INotification | On system notification | Log notifications, forward to external systems |
| IStop | On session stop | Clean up resources, save state |
| ISubagentStop | On subagent stop | Clean up subagent resources |
| IPreCompact | Before context compaction | Save snapshots, trigger backups |
| ISessionStart | On session start | Initialize resources, inject context |
| ISessionEnd | On session end | Clean up resources, generate reports |

## Example Implementations

See [tests/example_hooks.py](tests/example_hooks.py) for complete examples. Here are several demos covering different hook types:

### Demo 1: PreToolUse - Block Dangerous Bash Commands

```python
# .claude/hooks/DenyDangerousRm.py
from easyCcHooks import IPreToolUse, PreToolUseInput, PreToolUseOutput, ToolName

class DenyDangerousRm(IPreToolUse):
    """Block dangerous deletion commands like rm -rf /"""

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
```

### Demo 2: PostToolUse - Auto Notification After File Write

```python
# .claude/hooks/NotifyOnWrite.py
from easyCcHooks import IPostToolUse, PostToolUseInput, PostToolUseOutput, ToolName

class NotifyOnWrite(IPostToolUse):
    """Inject notification message after Write tool completes"""

    @property
    def matcher(self) -> str:
        return ToolName.Write

    def execute(self, input_data: PostToolUseInput) -> PostToolUseOutput:
        file_path = input_data.tool_input.get("file_path", "")
        return PostToolUseOutput(
            additional_context=f"File written: {file_path}, please verify the content"
        )
```

### Demo 3: SessionStart - Inject Project Context

```python
# .claude/hooks/ProjectInfo.py
from pathlib import Path
from easyCcHooks import ISessionStart, SessionStartInput, SessionStartOutput

class ProjectInfo(ISessionStart):
    """Inject project information at session start"""

    def execute(self, input_data: SessionStartInput) -> SessionStartOutput:
        cwd = Path(input_data.cwd)
        info = [f"Project directory: {cwd.name}"]
        if (cwd / "package.json").exists():
            info.append("Node.js project")
        if (cwd / "requirements.txt").exists():
            info.append("Python project")
        if (cwd / ".git").exists():
            info.append("Git repository")
        return SessionStartOutput(
            additional_context="\n".join(info) if info else None
        )
```

### Demo 4: UserPromptSubmit - Filter Sensitive Information

```python
# .claude/hooks/FilterSecrets.py
import re
from easyCcHooks import IUserPromptSubmit, UserPromptSubmitInput, UserPromptSubmitOutput

class FilterSecrets(IUserPromptSubmit):
    """Detect sensitive information in user prompts"""

    def execute(self, input_data: UserPromptSubmitInput) -> UserPromptSubmitOutput:
        prompt = input_data.prompt
        # Detect API key formats
        if re.search(r"(sk-|AKIA|ghp_|xox[bsp]-)\w{10,}", prompt):
            return UserPromptSubmitOutput(
                decision="block",
                reason="Possible API Key detected, please remove before submitting"
            )
        return UserPromptSubmitOutput()
```

### Demo 5: Stop - Prevent Accidental Exit

```python
# .claude/hooks/PreventStop.py
from easyCcHooks import IStop, StopInput, StopOutput

class PreventStop(IStop):
    """Prevent exit when stop_hook is not active, let Claude continue working"""

    def execute(self, input_data: StopInput) -> StopOutput:
        if not input_data.stop_hook_active:
            return StopOutput(
                decision="block",
                reason="Task may be incomplete, please continue"
            )
        return StopOutput()
```

Each demo only needs to be placed in the `.claude/hooks/` directory, then run `python3 easyCcHooks.py update-config` to take effect.

## Directory Structure

```
.claude/hooks/
├── easyCcHooks.py      # Framework core (data models + interfaces + registry + executor + CLI)
├── *.py                   # User-defined hook implementations (placed in same directory, auto-loaded)
├── ARCHITECTURE.md        # Architecture documentation
├── README.md              # Usage documentation (this file)
└── tests/                 # Test files
    ├── example_hooks.py   # Example hook implementations
    ├── README.md          # Testing guide
    ├── test_input_dangerous.json
    ├── test_input_safe.json
    └── test_input_session.json
```

## Advanced Usage

### Modify Tool Input

```python
def execute(self, input_data: PreToolUseInput) -> PreToolUseOutput:
    # Modify command parameters
    modified_input = input_data.tool_input.copy()
    modified_input["timeout"] = 30

    return PreToolUseOutput(
        permission_decision="allow",
        permission_decision_reason="Timeout adjusted",
        updated_input=modified_input
    )
```

### Custom Timeout

```python
class MyHook(IPreToolUse):
    @property
    def timeout(self) -> int:
        return 30  # 30 seconds timeout
```

### Match Specific Tools

```python
class MyHook(IPreToolUse):
    @property
    def matcher(self) -> str:
        return f"{ToolName.Bash}|{ToolName.Edit}|{ToolName.Write}"  # Match multiple tools (regex)
```

## Troubleshooting

### Hook Not Working

1. Check if scanned: `python3 easyCcHooks.py scan`
2. Check if configuration updated: `python3 easyCcHooks.py update-config`
3. Verify that settings.json contains hook configuration
4. Restart Claude Code

### Test Failure

Use the correct test input format, refer to the [Testing Guide](#test---test-hooks)
