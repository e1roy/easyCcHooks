# easyCcHooks: Type-Safe Claude Code Hooks Framework

[简体中文](README_CN.md) | English

Write Claude Code hooks as maintainable Python, instead of fragile ad-hoc shell snippets.

easyCcHooks gives you:
- A clear interface for all 10 Claude Code hook events
- Type-safe input/output models based on `dataclass`
- One-command hook discovery and `settings.json` update
- Local test tooling before you trust hooks in real sessions

> Architecture details: [`.claude/hooks/ARCHITECTURE.md`](.claude/hooks/ARCHITECTURE.md)

## Why This Project Exists

Raw hook setup usually becomes hard to maintain when your team grows:
- Hook behavior is scattered in config and shell one-liners
- No type hints, weak validation, and hard-to-debug runtime errors
- Onboarding new contributors takes too long

easyCcHooks turns hook development into normal Python engineering:
- Explicit interfaces and typed models
- Reusable logic with tests
- Predictable registration and configuration updates

## Who Should Use It

- New users who want a safe and simple way to start with Claude Code hooks
- Teams that need maintainable policy automation (security, context injection, audit)
- Advanced users who want matcher-based routing, typed payloads, and CI-friendly tests

## 3-Minute Quick Start

### 1. Install

Run in your project root:

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/e1roy/easyCcHooks/main/install.sh)
```

### 2. Create your first hook

Create `.claude/hooks/MyBashValidator.py`:

```python
from easyCcHooks import IPreToolUse, PreToolUseInput, PreToolUseOutput, ToolName


class MyBashValidator(IPreToolUse):
    """Block dangerous shell commands before execution."""

    @property
    def matcher(self) -> str:
        return ToolName.Bash

    def execute(self, input_data: PreToolUseInput) -> PreToolUseOutput:
        command = input_data.tool_input.get("command", "")
        if "rm -rf /" in command:
            return PreToolUseOutput(
                permission_decision="deny",
                permission_decision_reason="Refusing root deletion"
            )
        return PreToolUseOutput(
            permission_decision="allow",
            permission_decision_reason="Command is allowed"
        )
```

### 3. Register and apply config

```bash
python3 .claude/hooks/easyCcHooks.py scan
python3 .claude/hooks/easyCcHooks.py update-config
```

### 4. Validate before real usage

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

If output contains `permissionDecision: "deny"`, your hook is working as expected.

## How to Upgrade (upgrade)

When a new version is released, run this in your project root:

```bash
python3 .claude/hooks/easyCcHooks.py upgrade
```

For CI or non-interactive environments, skip the confirmation prompt:

```bash
python3 .claude/hooks/easyCcHooks.py upgrade -y
```

The upgrade command will:
- Show your current version and remote version
- Create an automatic backup (for example `easyCcHooks.backup.YYYYMMDD_HHMMSS.py`)
- Download and replace `.claude/hooks/easyCcHooks.py`

After upgrading, it is recommended to run:

```bash
python3 .claude/hooks/easyCcHooks.py scan
python3 .claude/hooks/easyCcHooks.py update-config
```

## Why People Stick With easyCcHooks

- Faster onboarding: one file (`easyCcHooks.py`) and consistent interfaces
- Lower risk: validate policies locally before running real sessions
- Easier extension: add new hook classes without touching framework internals
- Safer upgrades: built-in `upgrade` command and automated config merge strategy

## Common Use Cases

- Security guardrails: block dangerous shell/file commands
- Context automation: inject project metadata at session start
- Compliance and audit: log tool usage with custom policy decisions
- Quality workflows: post-tool checks and prompt filtering

## CLI Commands

Run all commands with:

```bash
python3 .claude/hooks/easyCcHooks.py <command>
```

| Command | Purpose |
| --- | --- |
| `scan` | Discover and register hook implementations |
| `update-config` | Merge generated hooks into `.claude/settings.json` |
| `list` | Show registered hooks and descriptions |
| `test <HookName> --input <json>` | Execute one hook locally with fixture input |
| `execute <HookName>` | Internal runtime entry used by Claude Code |
| `upgrade` | Check latest remote version and upgrade `easyCcHooks.py` |

## Hook Interfaces (10 Types)

| Interface | Trigger timing | Typical usage |
| --- | --- | --- |
| `IPreToolUse` | Before tool invocation | Validate commands, mutate input, enforce policy |
| `IPermissionRequest` | Permission request time | Auto-allow/deny with custom reason |
| `IPostToolUse` | After tool execution | Add context, block risky outcomes |
| `IUserPromptSubmit` | User prompt submit | Filter secrets, enrich prompt context |
| `INotification` | Notification event | Route/record notification payload |
| `IStop` | Session stop | Guard exit, run cleanup logic |
| `ISubagentStop` | Subagent stop | Subagent cleanup policies |
| `IPreCompact` | Before compaction | Persist snapshots, custom pre-compact logic |
| `ISessionStart` | Session start | Inject project metadata and instructions |
| `ISessionEnd` | Session end | Final cleanup and report hooks |

## Technical Deep Dive

### Execution model

1. `scan` recursively discovers hook classes in `.claude/hooks`
2. Registry maps class types to Claude hook events
3. `update-config` generates managed command entries in `.claude/settings.json`
4. Claude Code calls `execute <HookName>` with JSON payload via `stdin`

### Type-safety model

- Each event has a dedicated input/output dataclass model
- `from_dict` performs field-level mapping from Claude payloads
- Hook outputs are serialized into Claude-compatible JSON automatically

### Matcher and timeout

- Set `matcher` to limit hook scope (single tool, regex, or `ToolName.All`)
- Override `timeout` property per hook for slow/remote checks

### Input rewrite pattern

For tool-level hooks, you can modify tool input via `updated_input`:

```python
return PreToolUseOutput(
    permission_decision="allow",
    permission_decision_reason="Applied safe defaults",
    updated_input={**input_data.tool_input, "timeout": 30}
)
```

## Testing and Verification

- Test guide: [`.claude/hooks/tests/README.md`](.claude/hooks/tests/README.md)
- Example hooks: [`.claude/hooks/tests/example_hooks.py`](.claude/hooks/tests/example_hooks.py)

Recommendation for teams:
1. Keep test fixtures for every critical hook behavior (`allow`, `deny`, `ask`, `block`)
2. Run `test` in CI before updating hook config in production repos
3. Add regression fixtures when policy logic changes

## Directory Layout

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

## Troubleshooting

### Hook not taking effect

1. Run `python3 .claude/hooks/easyCcHooks.py scan`
2. Run `python3 .claude/hooks/easyCcHooks.py update-config`
3. Check generated entries in `.claude/settings.json`
4. Restart Claude Code session

### Hook test fails

1. Confirm `hook_event_name` matches your hook interface
2. Confirm the class name passed to `test` is exact
3. Confirm test JSON includes required fields for that hook event
