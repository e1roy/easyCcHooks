#!/usr/bin/env python3
"""
示例 Hook 实现

这些是用于演示和测试的 Hook 实现。
如果需要在正式项目中使用,请复制到 .claude/hooks/ 目录并在 easyCcHooks.py 中注册。
"""

import re
import sys
from pathlib import Path
from datetime import datetime

# 将 hooks 目录加入 path,以便导入 easyCcHooks
HOOKS_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(HOOKS_DIR))

from easyCcHooks import (
    IPreToolUse,
    ISessionStart,
    PreToolUseInput,
    PreToolUseOutput,
    SessionStartInput,
    SessionStartOutput,
    ToolName,
)


# ============================================================================
# Hook 实现 - ValidateBashCommand
# ============================================================================

class ValidateBashCommand(IPreToolUse):
    """
    验证 Bash 命令安全性

    功能:
    - 阻止危险命令 (rm -rf /)
    - 阻止路径遍历
    - 请求用户确认 sudo 命令
    """

    @property
    def matcher(self) -> str:
        return ToolName.Bash

    def execute(self, input_data: PreToolUseInput) -> PreToolUseOutput:
        command = input_data.tool_input.get("command", "")

        if re.search(r"\brm\s+.*-rf\s+/\s*$", command):
            return PreToolUseOutput(
                permission_decision="deny",
                permission_decision_reason="🚫 禁止删除根目录"
            )

        dangerous_paths = ["/bin", "/boot", "/dev", "/etc", "/lib", "/proc", "/sbin", "/sys", "/usr"]
        for path in dangerous_paths:
            if re.search(rf"\brm\s+.*-rf\s+{path}", command):
                return PreToolUseOutput(
                    permission_decision="deny",
                    permission_decision_reason=f"🚫 禁止删除系统目录: {path}"
                )

        if "sudo" in command:
            return PreToolUseOutput(
                permission_decision="ask",
                permission_decision_reason="⚠️  需要管理员权限,请确认"
            )

        return PreToolUseOutput(
            permission_decision="allow",
            permission_decision_reason="✓ 命令安全"
        )


# ============================================================================
# Hook 实现 - WatchPreToolUse
# ============================================================================

class WatchPreToolUse(IPreToolUse):
    """
    监控所有工具调用,记录到日志

    功能:
    - 记录工具名称和输入参数
    - 记录调用时间
    - 不阻止任何操作
    """

    @property
    def matcher(self) -> str:
        return ToolName.All

    def execute(self, input_data: PreToolUseInput) -> PreToolUseOutput:
        log_file = Path(__file__).parent / "watch.log"
        log_file.parent.mkdir(parents=True, exist_ok=True)

        with open(log_file, "a", encoding="utf-8") as f:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            f.write(f"[{timestamp}] {input_data.tool_name}: {input_data.tool_input}\n")

        return PreToolUseOutput(
            permission_decision="allow",
            permission_decision_reason="✓ 监控记录完成"
        )


# ============================================================================
# Hook 实现 - InjectContext
# ============================================================================

class InjectContext(ISessionStart):
    """
    在会话开始时注入项目上下文

    功能:
    - 读取项目配置文件
    - 注入项目元信息
    - 提供工作环境信息
    """

    def execute(self, input_data: SessionStartInput) -> SessionStartOutput:
        context_parts = []
        cwd = Path(input_data.cwd)
        context_parts.append(f"📁 项目目录: {cwd}")

        if (cwd / "CLAUDE.md").exists():
            context_parts.append("📄 已加载 CLAUDE.md 项目说明")
        if (cwd / ".git").exists():
            context_parts.append("🔀 项目使用 Git 版本控制")
        if (cwd / ".venv").exists():
            context_parts.append("🐍 已检测到 Python 虚拟环境")
        if (cwd / "requirements.txt").exists():
            context_parts.append("📦 已检测到 requirements.txt")

        if context_parts:
            context_message = "\n".join([
                "",
                "=== 项目上下文 ===",
                *context_parts,
                "==================",
                ""
            ])
            return SessionStartOutput(additional_context=context_message)

        return SessionStartOutput()
