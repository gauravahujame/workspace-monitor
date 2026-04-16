#!/bin/bash
# Workspace Monitor One-Click Installer
# This script installs UV (if needed) and workspace-monitor

set -e

echo "🚀 Installing Workspace Monitor..."

# Detect platform
PLATFORM="$(uname -s)"
case "${PLATFORM}" in
    Linux*)     MACHINE=Linux;;
    Darwin*)    MACHINE=Mac;;
    *)          MACHINE="UNKNOWN:${PLATFORM}"
esac

echo "📦 Detected platform: ${MACHINE}"

# Check if uv is installed
if ! command -v uv &> /dev/null; then
    echo "📥 Installing UV (fast Python package installer)..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"

    # Source shell configuration
    if [ -f "$HOME/.bashrc" ]; then
        source "$HOME/.bashrc"
    elif [ -f "$HOME/.zshrc" ]; then
        source "$HOME/.zshrc"
    fi

    echo "✅ UV installed"
else
    echo "✅ UV already installed"
fi

# Create virtual environment if it doesn't exist
VENV_DIR="$HOME/.workspace-monitor/venv"
if [ ! -d "$VENV_DIR" ]; then
    echo "📦 Creating virtual environment at $VENV_DIR..."
    uv venv "$VENV_DIR"
fi

# Activate virtual environment
source "$VENV_DIR/bin/activate"

# Install workspace-monitor
echo "📦 Installing workspace-monitor with web dashboard..."
uv pip install -e ".[web]"

# Create symlink for wsd command
BIN_DIR="$HOME/.local/bin"
mkdir -p "$BIN_DIR"
ln -sf "$VENV_DIR/bin/wsd" "$BIN_DIR/wsd" 2>/dev/null || true
ln -sf "$VENV_DIR/bin/workspace-monitor" "$BIN_DIR/workspace-monitor" 2>/dev/null || true

echo "✅ Installation complete!"
echo ""
echo "🎉 Workspace Monitor is now installed!"
echo ""
echo "Quick start:"
echo "  wsd server          # Start the web dashboard"
echo "  wsd list            # List all projects"
echo "  wsd scan            # Scan for new projects"
echo ""
echo "Virtual environment: $VENV_DIR"
echo "Add to PATH: export PATH=\"$HOME/.local/bin:\$PATH\""
echo ""
echo "📦 IDE Integration:"
echo ""
echo "Windsurf integration:"
echo '  Add to ~/.codeium/windsurf/hooks.json:'
echo '    "post_cascade_response_with_transcript": [{"command": "'"$VENV_DIR/bin/python"' -m workspace_monitor.hooks.processor", "show_output": false}]'
echo ""
echo "OpenCode integration:"
echo "  mkdir -p ~/.config/opencode/plugins"
echo "  cp opencode-plugin/workspace-monitor.ts ~/.config/opencode/plugins/"
echo "  Add to ~/.config/opencode/opencode.jsonc:"
echo '    "plugins": ["~/.config/opencode/plugins/workspace-monitor.ts"]'
echo ""
echo "See opencode-plugin/README.md for detailed OpenCode setup."
