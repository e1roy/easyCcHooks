#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────
#  EasyCcHooks Installer
#  One-line install:
#    bash <(curl -fsSL https://raw.githubusercontent.com/e1roy/easyCcHooks/main/install.sh)
# ─────────────────────────────────────────────────────────
set -euo pipefail

RAW_URL="https://raw.githubusercontent.com/e1roy/easyCcHooks/refs/heads/main/.claude/hooks/easyCcHooks.py"
VERSION_URL="https://raw.githubusercontent.com/e1roy/easyCcHooks/refs/heads/main/version.txt"
DEFAULT_TARGET_ROOT=".claude"
TARGET_ROOT="$DEFAULT_TARGET_ROOT"
TARGET_DIR=""
TARGET_FILE=""
TARGET_SET_BY_ARG="false"

print_usage() {
    cat <<EOF
Usage: $0 [options]

Options:
  -d, --dir <directory>  Install to one of: .codebuddy, .claude, .trae
  -h, --help             Show this help message
EOF
}

normalize_target_root() {
    case "$1" in
        .codebuddy|codebuddy) echo ".codebuddy" ;;
        .claude|claude) echo ".claude" ;;
        .trae|trae) echo ".trae" ;;
        *) return 1 ;;
    esac
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        -d|--dir)
            if [[ $# -lt 2 ]]; then
                echo "Error: $1 requires a value."
                exit 1
            fi
            if ! TARGET_ROOT="$(normalize_target_root "$2")"; then
                echo "Error: invalid directory '$2'."
                echo "Allowed values: .codebuddy, .claude, .trae"
                exit 1
            fi
            TARGET_SET_BY_ARG="true"
            shift 2
            ;;
        -h|--help)
            print_usage
            exit 0
            ;;
        *)
            echo "Error: unknown argument '$1'."
            print_usage
            exit 1
            ;;
    esac
done

if [[ "$TARGET_SET_BY_ARG" != "true" ]]; then
    echo "Select install directory:"
    echo "  1) .claude (default)"
    echo "  2) .codebuddy"
    echo "  3) .trae"
    read -rp "Enter choice [1-3] (default 1): " dir_choice
    case "$dir_choice" in
        ""|1) TARGET_ROOT=".claude" ;;
        2) TARGET_ROOT=".codebuddy" ;;
        3) TARGET_ROOT=".trae" ;;
        *)
            echo "Error: invalid choice '$dir_choice'."
            exit 1
            ;;
    esac
fi

TARGET_DIR="${TARGET_ROOT}/hooks"
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

# ── Check target directory ──────────────────────────────
if [ ! -d "$TARGET_ROOT" ]; then
    echo "No ${TARGET_ROOT} directory found in the current project."
    read -rp "Create ${TARGET_DIR}/ directory? [y/N] " answer
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
echo "  1. Create a hook file in ${TARGET_DIR}/:"
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
echo "     cd ${TARGET_DIR}"
echo "     python3 easyCcHooks.py scan"
echo "     python3 easyCcHooks.py update-config"
echo ""
echo "  Docs:    python3 ${TARGET_DIR}/easyCcHooks.py --help"
echo "  Upgrade: python3 ${TARGET_DIR}/easyCcHooks.py upgrade"
echo ""
