# Workspace Monitor

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

A comprehensive system-wide dashboard for monitoring all git repositories under `~/workspace`, with tight integration into the [Windsurf](https://codeium.com/windsurf) IDE.

## Features

- 📊 **Project Overview**: All repositories with git status, language detection, and metadata
- 🔴 **Live Monitoring**: Real-time Windsurf session tracking via hooks
- 💬 **Chat History**: Complete Cascade conversation tracking across all projects
- 📈 **Activity Timeline**: 14-day visualization of chats and commits
- 🔍 **Search & Filter**: Find projects by name, language, or status
- 🌐 **Web Dashboard**: Beautiful dark-themed web interface
- 🖥️ **CLI Tool**: Command-line interface for quick operations
- 🔗 **Windsurf Integration**: Automatic data collection via hooks

## Installation

### Quick Install (One-Click)

```bash
curl -fsSL https://raw.githubusercontent.com/gauravahujame/workspace-monitor/main/install.sh | sh
```

### With UV (Recommended)

[UV](https://github.com/astral-sh/uv) is a fast Python package installer (10-100x faster than pip).

```bash
# Install UV (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Create virtual environment and install
git clone https://github.com/gauravahujame/workspace-monitor.git
cd workspace-monitor
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
uv pip install -e ".[web]"
```

### With pip (Traditional)

```bash
pip install workspace-monitor[web]
```

### From Source

```bash
git clone https://github.com/gauravahujame/workspace-monitor.git
cd workspace-monitor
pip install -e ".[web]"
```

### macOS Specific

On macOS, the data directory is automatically set to `~/Library/Application Support/workspace-monitor/` following macOS conventions.

```bash
# Install with UV (recommended)
uv pip install workspace-monitor[web]

# Or with Homebrew
brew install workspace-monitor
```

## Quick Start

### 1. Start the Web Dashboard

```bash
wsd server
# or
workspace-dashboard
```

Opens at http://127.0.0.1:8765

### 2. Configure Windsurf Hooks

Add to `~/.codeium/windsurf/hooks.json`:

```json
{
  "hooks": {
    "post_cascade_response_with_transcript": [
      {
        "command": "~/.workspace-monitor/venv/bin/python -m workspace_monitor.hooks.processor",
        "show_output": false
      }
    ],
    "post_write_code": [
      {
        "command": "~/.workspace-monitor/venv/bin/python -m workspace_monitor.hooks.processor",
        "show_output": false
      }
    ],
    "pre_run_command": [
      {
        "command": "~/.workspace-monitor/venv/bin/python -m workspace_monitor.hooks.processor",
        "show_output": false
      }
    ],
    "post_run_command": [
      {
        "command": "~/.workspace-monitor/venv/bin/python -m workspace_monitor.hooks.processor",
        "show_output": false
      }
    ]
  }
}
```

**Note**: If you installed from source or used a different venv location, adjust the path accordingly.

### 3. Scan Your Projects

```bash
wsd scan
```

## CLI Commands

| Command | Description |
|---------|-------------|
| `wsd list` | List all projects |
| `wsd list --status dirty` | Show only dirty projects |
| `wsd list --sort chats` | Sort by chat count |
| `wsd status myproject` | Detailed project status |
| `wsd stats` | Workspace statistics |
| `wsd chats` | Recent conversations |
| `wsd server` | Start web dashboard |
| `wsd scan` | Discover new projects |
| `wsd search "backend"` | Search projects |
| `wsd git status` | Run git status on all projects |
| `wsd export` | Export data to JSON |

## Web Dashboard

![Dashboard Preview](https://via.placeholder.com/800x400/0d1117/58a6ff?text=Workspace+Monitor+Dashboard)

### Features

- **Stats Grid**: Total projects, active sessions, chats today/total, needs attention
- **Activity Chart**: 14-day timeline of chats/commits (visual bar chart)
- **Projects Table**: Sortable, filterable with status badges
- **Live Indicators**: Pulsing green dot for active Windsurf sessions
- **Auto-refresh**: Every 30 seconds
- **WebSocket**: Real-time updates (FastAPI mode)

### Status Badges

- ✓ **Clean**: Green - repository in sync
- ✕ **Dirty**: Red - uncommitted changes
- ↑ **Ahead**: Yellow - commits to push
- ↓ **Behind**: Yellow - commits to pull
- ⚠ **Diverged**: Purple - needs merge

## OpenCode Integration

Workspace Monitor also works with [OpenCode](https://opencode.ai/):

### OpenCode Plugin

A TypeScript plugin is included for native OpenCode integration:

```bash
# Install plugin
mkdir -p ~/.config/opencode/plugins
cp opencode-plugin/workspace-monitor.ts ~/.config/opencode/plugins/

# Add to opencode.jsonc
{
  "plugins": [
    "~/.config/opencode/plugins/workspace-monitor.ts"
  ]
}
```

### OpenCode Features

The plugin provides:
- **Real-time session tracking** via OpenCode events
- **Git action logging** via `tool.execute.before` hooks
- **AI-accessible tools**:
  - `workspace.list_projects` - List all projects
  - `workspace.project_status` - Get project details
  - `workspace.stats` - Workspace statistics
  - `workspace.scan` - Discover new repositories

See [opencode-plugin/README.md](opencode-plugin/README.md) for details.

## Windsurf Workflows

Once installed, you can use these Windsurf slash commands:

| Command | Purpose |
|---------|---------|
| `/workspace-dashboard` | Launch web dashboard |
| `/project-status` | Check current project status |
| `/for-every-project` | Execute commands across all projects |
| `/setup-project` | Generate AGENTS.md and skills |

## Python API

```python
from workspace_monitor import WorkspaceDashboard

dashboard = WorkspaceDashboard()

# Scan for projects
projects = dashboard.scan_projects()

# Get all projects
all_projects = dashboard.get_projects()

# Filter by status
needs_attention = dashboard.get_projects(status_filter="dirty")

# Get recent chats
chats = dashboard.get_chats(limit=50)

# Get statistics
stats = dashboard.get_stats()

# Export data
dashboard.export_data("/path/to/export.json")
```

## Database Schema

SQLite database stored at:
- **Linux**: `~/.workspace-monitor/dashboard.db`
- **macOS**: `~/Library/Application Support/workspace-monitor/dashboard.db`

### Tables

- **projects**: Repository metadata, git status, chat counts
- **chats**: Cascade conversation history
- **git_actions**: Commits, pushes, pulls, merges
- **windsurf_sessions**: Active/past session tracking

## Configuration

### Environment Variables

| Variable | Description |
|----------|-------------|
| `WORKSPACE_ROOT` | Override workspace directory (default: `~/workspace`) |
| `WORKSPACE_MONITOR_DATA` | Override data directory |

### CLI Options

```bash
# Custom workspace
wsd --workspace /path/to/projects list

# Custom data directory
wsd --data-dir /path/to/data stats
```

## Development

```bash
# Clone repository
git clone https://github.com/gauravahujame/workspace-monitor.git
cd workspace-monitor

# Install UV (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install dev dependencies with UV
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
uv pip install -e ".[dev,web]"

# Run tests
pytest

# Format code
black src/
ruff src/

# Type check
mypy src/workspace_monitor
```

## Troubleshooting

### Dashboard won't start

```bash
# Check port usage
lsof -i :8765

# Use different port
wsd server --port 8766
```

### Projects not appearing

```bash
# Scan for projects
wsd scan

# Check workspace path
echo $WORKSPACE_ROOT
```

### Chat history missing

1. Verify hooks are configured:
   ```bash
   cat ~/.codeium/windsurf/hooks.json
   ```

2. Check transcript directory:
   ```bash
   ls ~/.windsurf/transcripts/
   ```

3. Check hook processor logs:
   ```bash
   # Linux
   cat ~/.workspace-monitor/hook_errors.log

   # macOS
   cat ~/Library/Application\ Support/workspace-monitor/hook_errors.log
   ```

### Hook processor not found

```bash
# Verify installation
which wsd
~/.workspace-monitor/venv/bin/python -c "import workspace_monitor; print(workspace_monitor.__version__)"

# Test hook processor
~/.workspace-monitor/venv/bin/python -m workspace_monitor.hooks.processor
```

## Cross-IDE Compatibility

Workspace Monitor supports multiple AI coding IDEs:

| IDE | Integration | Status |
|-----|-------------|--------|
| [Windsurf](https://codeium.com/windsurf) | Shell hooks + JSONL transcripts | ✅ Full support |
| [OpenCode](https://opencode.ai/) | TypeScript plugin + SQLite | ✅ Full support |
| Cursor | Planned | 🚧 Coming soon |
| Claude Code | Planned | 🚧 Coming soon |

All IDEs write to the **same SQLite database**, enabling:
- Unified project tracking across IDEs
- Cross-IDE chat history
- Shared git action logs
- Single web dashboard view

See [docs/IDE_INTEGRATION_ANALYSIS.md](docs/IDE_INTEGRATION_ANALYSIS.md) for technical details.

## Platform Support

| Platform | Status | Notes |
|----------|--------|-------|
| Linux | ✅ Supported | Primary development platform |
| macOS | ✅ Supported | Tested on macOS 13+ |
| Windows | ⚠️ Partial | CLI works, limited testing |

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

MIT License - see [LICENSE](LICENSE) file for details.

## Acknowledgments

- Inspired by [git-status-dash](https://github.com/ejfox/git-status-dash) by EJ Fox
- Built for the [Windsurf](https://codeium.com/windsurf) editor by Codeium

## Support

- 🐛 [Report bugs](https://github.com/gauravahujame/workspace-monitor/issues)
- 💡 [Request features](https://github.com/gauravahujame/workspace-monitor/issues)
- 📧 Email: your.email@example.com
