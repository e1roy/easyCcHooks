#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────
#  EasyCcHooks Installer
#  One-line install:
#    bash <(curl -fsSL https://raw.githubusercontent.com/e1roy/easyCcHooks/main/install.sh)
# ─────────────────────────────────────────────────────────
set -euo pipefail

RAW_URL="https://raw.githubusercontent.com/e1roy/easyCcHooks/refs/heads/main/.claude/hooks/easyCcHooks.py"
VERSION_URL="https://raw.githubusercontent.com/e1roy/easyCcHooks/refs/heads/main/version.txt"
TARGET_DIR=".claude/hooks"
TARGET_FILE="${TARGET_DIR}/easyCcHooks.py"

# ── Check dependencies ──────────────────────────────────
if ! command -v curl &>/dev/null; then
    echo "Error: curl is required but not installed."
    exit 1
fi

if ! command -v python3 &>/dev/null; then
    echo "Error: python3 is required but not installed."
    exit 1
fi

# ── Check .claude directory ─────────────────────────────
if [ ! -d ".claude" ]; then
    echo "No .claude directory found in the current project."
    read -rp "Create .claude/hooks/ directory? [y/N] " answer
    case "$answer" in
        [yY]|[yY][eE][sS])
            mkdir -p "$TARGET_DIR"
            echo "Created ${TARGET_DIR}/"
            ;;
        *)
            echo "Aborted."
            exit 0
            ;;
    esac
elif [ ! -d "$TARGET_DIR" ]; then
    mkdir -p "$TARGET_DIR"
    echo "Created ${TARGET_DIR}/"
fi

# ── Download ────────────────────────────────────────────
if [ -f "$TARGET_FILE" ]; then
    read -rp "easyCcHooks.py already exists. Overwrite? [y/N] " answer
    case "$answer" in
        [yY]|[yY][eE][sS]) ;;
        *)
            echo "Aborted."
            exit 0
            ;;
    esac
fi

echo "Downloading easyCcHooks.py ..."
if curl -fsSL "$RAW_URL" -o "$TARGET_FILE"; then
    VERSION=$(curl -fsSL "$VERSION_URL" 2>/dev/null || echo "unknown")
    echo "Installed to ${TARGET_FILE} (v${VERSION})"
else
    echo "Error: download failed."
    exit 1
fi

# ── Done ────────────────────────────────────────────────
echo ""
echo "──────────────────────────────────────────"
echo "  EasyCcHooks installed successfully!"
echo "──────────────────────────────────────────"
echo ""
echo "  Quick start:"
echo ""
echo "  1. Create a hook file in .claude/hooks/:"
echo ""
echo "     from easyCcHooks import IPreToolUse, PreToolUseInput, PreToolUseOutput, ToolName"
echo ""
echo "     class MyHook(IPreToolUse):"
echo "         @property"
echo "         def matcher(self) -> str:"
echo "             return ToolName.Bash"
echo ""
echo "         def execute(self, input_data: PreToolUseInput) -> PreToolUseOutput:"
echo "             return PreToolUseOutput(permission_decision=\"allow\")"
echo ""
echo "  2. Register and activate:"
echo ""
echo "     cd .claude/hooks"
echo "     python3 easyCcHooks.py scan"
echo "     python3 easyCcHooks.py update-config"
echo ""
echo "  Docs:    python3 .claude/hooks/easyCcHooks.py --help"
echo "  Upgrade: python3 .claude/hooks/easyCcHooks.py upgrade"
echo ""
