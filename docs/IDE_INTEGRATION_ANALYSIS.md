# Cross-IDE Integration Analysis

## Executive Summary

The Workspace Monitor architecture is **highly adaptable** to OpenCode and other AI IDEs. Both systems use event-driven hooks, but differ in:
- **Event System**: Windsurf uses JSON hook configs + shell commands; OpenCode uses TypeScript/JavaScript plugins with typed events
- **Data Storage**: Windsurf stores transcripts as JSONL files; OpenCode uses SQLite database
- **Configuration**: Windsurf uses `~/.codeium/windsurf/`; OpenCode uses `~/.config/opencode/`

## Architecture Comparison

### Windsurf Architecture
```
┌─────────────────────────────────────────────────────────────┐
│                    Windsurf IDE                             │
├─────────────────────────────────────────────────────────────┤
│  Cascade Agent                                              │
│     ├── hooks.json (shell commands)                         │
│     ├── post_cascade_response_with_transcript               │
│     ├── post_write_code                                     │
│     └── pre_run_command / post_run_command                │
├─────────────────────────────────────────────────────────────┤
│  Data Storage                                               │
│     ├── ~/.windsurf/transcripts/*.jsonl                     │
│     └── ~/.workspace-monitor/dashboard.db (SQLite)          │
└─────────────────────────────────────────────────────────────┘
```

### OpenCode Architecture
```
┌─────────────────────────────────────────────────────────────┐
│                    OpenCode IDE                             │
├─────────────────────────────────────────────────────────────┤
│  Plugin System (TypeScript/JavaScript)                      │
│     ├── Event Handlers                                      │
│     │   ├── session.created / session.updated               │
│     │   ├── message.updated / message.removed               │
│     │   ├── file.edited / file.watcher.updated              │
│     │   ├── tool.execute.before / tool.execute.after        │
│     │   └── command.executed                                │
│     ├── Custom Tools                                        │
│     └── Chat Message Hooks                                  │
├─────────────────────────────────────────────────────────────┤
│  Data Storage                                               │
│     ├── ~/.local/share/opencode/opencode.db (SQLite)        │
│     └── ~/.config/opencode/ (config + plugins)              │
└─────────────────────────────────────────────────────────────┘
```

## Event/Hook Mapping

| Workspace Monitor Feature | Windsurf Hook | OpenCode Event |
|---------------------------|---------------|----------------|
| **Chat Tracking** | `post_cascade_response_with_transcript` | `session.updated`, `message.updated` |
| **File Edits** | `post_write_code` | `file.edited`, `file.watcher.updated` |
| **Git Actions** | `pre_run_command` / `post_run_command` | `tool.execute.before` / `tool.execute.after` |
| **Session Start** | N/A (transcript parsing) | `session.created` |
| **Command Execution** | `pre_run_command` | `command.executed`, `tool.execute.before` |

## Implementation Strategy for OpenCode

### Option 1: Native OpenCode Plugin (Recommended)

Create a TypeScript plugin that integrates directly with OpenCode's event system:

```typescript
// ~/.config/opencode/plugins/workspace-monitor.ts
import type { Plugin } from "@opencode-ai/plugin";
import { Database } from "bun:sqlite"; // OpenCode uses Bun runtime

export const WorkspaceMonitorPlugin: Plugin = async (ctx) => {
  const db = new Database(`${process.env.HOME}/.workspace-monitor/dashboard.db`);
  
  return {
    // Track session updates (equivalent to post_cascade_response_with_transcript)
    "session.updated": async ({ event }) => {
      const session = event.payload.session;
      
      // Extract project path from session
      const projectPath = session.worktree || session.directory;
      
      // Record chat entry
      db.run(`
        INSERT OR REPLACE INTO chats 
        (trajectory_id, project_path, timestamp, message_count, file_edits, commands_run)
        VALUES (?, ?, ?, ?, ?, ?)
      `, [
        session.id,
        projectPath,
        new Date().toISOString(),
        session.messages?.length || 0,
        0, // Calculate from session diffs
        0  // Calculate from tool executions
      ]);
    },
    
    // Track file edits (equivalent to post_write_code)
    "file.edited": async ({ event }) => {
      const file = event.payload.file;
      const projectPath = detectProject(file.path);
      
      // Update project timestamp
      db.run(`
        UPDATE projects SET updated_at = ? WHERE path = ?
      `, [new Date().toISOString(), projectPath]);
    },
    
    // Track git commands (equivalent to pre_run_command)
    "tool.execute.before": async ({ input }, { args }) => {
      if (input.tool === "bash" && args.command?.startsWith("git ")) {
        const gitAction = parseGitCommand(args.command);
        const projectPath = detectProject(args.cwd || process.cwd());
        
        // Store pending action
        db.run(`
          INSERT INTO git_actions (project_path, action_type, timestamp, details)
          VALUES (?, ?, ?, ?)
        `, [projectPath, gitAction, new Date().toISOString(), args.command]);
      }
    },
    
    // Custom tool for dashboard queries
    tool: {
      "workspace.dashboard": {
        description: "Query workspace dashboard",
        args: {
          action: {
            type: "string",
            enum: ["list", "status", "stats"],
            description: "Dashboard action"
          },
          project: {
            type: "string",
            optional: true,
            description: "Project name (for status action)"
          }
        },
        async execute(args, context) {
          const projects = db.query("SELECT * FROM projects").all();
          return JSON.stringify(projects, null, 2);
        }
      }
    }
  };
};
```

### Option 2: Universal Python Bridge (Cross-IDE Compatible)

Create a Python service that both IDEs can communicate with:

```python
# workspace_monitor/bridge.py
import asyncio
import json
import sqlite3
from pathlib import Path
from dataclasses import asdict
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Optional

class MonitorBridge:
    """Universal bridge for IDE integrations."""
    
    def __init__(self, db_path: Optional[Path] = None):
        if db_path is None:
            db_path = Path.home() / ".workspace-monitor" / "dashboard.db"
        self.db_path = db_path
    
    # Windsurf-style transcript parsing
    def process_windsurf_transcript(self, transcript_path: Path, trajectory_id: str) -> dict:
        """Parse Windsurf JSONL transcript."""
        from .transcript_parsers import WindsurfParser
        parser = WindsurfParser()
        return parser.parse(transcript_path, trajectory_id)
    
    # OpenCode-style session data
    def process_opencode_session(self, session_data: dict) -> dict:
        """Process OpenCode session data."""
        from .transcript_parsers import OpenCodeParser
        parser = OpenCodeParser()
        return parser.parse(session_data)
    
    # Generic chat recording
    def record_chat(self, project_path: str, trajectory_id: str,
                   message_count: int = 0, file_edits: int = 0,
                   commands_run: int = 0, summary: str = "") -> None:
        """Record a chat session (IDE-agnostic)."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO chats 
                (trajectory_id, project_path, timestamp, message_count,
                 file_edits, commands_run, summary)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                trajectory_id, project_path, datetime.now().isoformat(),
                message_count, file_edits, commands_run, summary
            ))
    
    # Generic git action recording
    def record_git_action(self, project_path: str, action_type: str,
                         command: str) -> None:
        """Record a git action (IDE-agnostic)."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO git_actions 
                (project_path, action_type, timestamp, details)
                VALUES (?, ?, ?, ?)
            """, (project_path, action_type, datetime.now().isoformat(), command))
```

## Modular Architecture Design

To make the system pluggable across IDEs, implement these modules:

```
workspace_monitor/
├── core/                      # IDE-agnostic core
│   ├── __init__.py
│   ├── database.py           # SQLite operations
│   ├── git_analyzer.py       # Git repo analysis
│   ├── project_scanner.py    # Project discovery
│   └── models.py             # Data classes
├── ide_plugins/              # IDE-specific integrations
│   ├── __init__.py
│   ├── base.py               # Abstract base class
│   ├── windsurf/
│   │   ├── __init__.py
│   │   ├── hooks.py          # Windsurf hook processor
│   │   ├── transcript_parser.py  # JSONL parsing
│   │   └── config.py         # ~/.codeium/windsurf/ integration
│   ├── opencode/
│   │   ├── __init__.py
│   │   ├── plugin.ts         # TypeScript plugin
│   │   ├── session_adapter.py # SQLite session reading
│   │   └── config.py         # ~/.config/opencode/ integration
│   └── cursor/               # Future: Cursor IDE
│       └── ...
├── api/                      # Shared API layer
│   ├── __init__.py
│   ├── server.py             # FastAPI/Flask web server
│   ├── routes.py
│   └── websocket.py
├── cli/                      # Command-line interface
│   ├── __init__.py
│   └── commands.py
└── web/                      # Web dashboard (static)
    └── ...
```

## Key Abstractions

### 1. IDE Adapter Interface

```python
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from pathlib import Path

class IDEAdapter(ABC):
    """Abstract base for IDE integrations."""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """IDE name (e.g., 'windsurf', 'opencode')."""
        pass
    
    @property
    @abstractmethod
    def config_dir(self) -> Path:
        """IDE configuration directory."""
        pass
    
    @abstractmethod
    def install_hooks(self) -> bool:
        """Install hooks/plugin into IDE."""
        pass
    
    @abstractmethod
    def uninstall_hooks(self) -> bool:
        """Remove hooks/plugin from IDE."""
        pass
    
    @abstractmethod
    def is_active(self) -> bool:
        """Check if IDE integration is active."""
        pass
    
    @abstractmethod
    def get_session_data(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve session data from IDE storage."""
        pass
```

### 2. Transcript Parser Interface

```python
class TranscriptParser(ABC):
    """Parse IDE-specific conversation data."""
    
    @abstractmethod
    def parse(self, source: Any) -> ChatEntry:
        """Parse transcript into standardized ChatEntry."""
        pass
    
    @abstractmethod
    def detect_project(self, data: Any) -> Optional[Path]:
        """Extract project path from transcript."""
        pass


class WindsurfParser(TranscriptParser):
    """Parse Windsurf JSONL transcripts."""
    
    def parse(self, transcript_path: Path) -> ChatEntry:
        # Parse JSONL format
        # Extract message counts, file edits, commands
        pass


class OpenCodeParser(TranscriptParser):
    """Parse OpenCode session data from SQLite."""
    
    def parse(self, session_data: dict) -> ChatEntry:
        # Parse SQLite session record
        # Extract message counts, tool executions
        pass
```

## Implementation Roadmap

### Phase 1: Core Modularization (1-2 weeks)
- [ ] Extract core database operations from Windsurf-specific code
- [ ] Create `IDEAdapter` abstract base class
- [ ] Implement Windsurf adapter as reference implementation
- [ ] Add adapter discovery/loading system

### Phase 2: OpenCode Plugin (1 week)
- [ ] Create TypeScript plugin following OpenCode conventions
- [ ] Implement session event handlers
- [ ] Add file edit tracking
- [ ] Implement git command detection
- [ ] Test with OpenCode CLI and VS Code extension

### Phase 3: Universal Bridge (1 week)
- [ ] Create Python bridge service
- [ ] Add IPC mechanism (HTTP or Unix socket)
- [ ] Implement transcript parsers for both IDEs
- [ ] Add adapter auto-detection

### Phase 4: Multi-IDE Support (2 weeks)
- [ ] Cursor IDE adapter
- [ ] Claude Code adapter (if possible)
- [ ] Aider adapter
- [ ] Generic LSP-based adapter (for any LSP-compatible IDE)

## Configuration for Multiple IDEs

```yaml
# ~/.workspace-monitor/config.yaml
ides:
  windsurf:
    enabled: true
    hooks_path: ~/.codeium/windsurf/hooks.json
    transcript_path: ~/.windsurf/transcripts
    
  opencode:
    enabled: true
    plugin_path: ~/.config/opencode/plugins/workspace-monitor.ts
    database_path: ~/.local/share/opencode/opencode.db
    
  cursor:
    enabled: false  # Future support
    
general:
  workspace_root: ~/workspace
  database_path: ~/.workspace-monitor/dashboard.db
  web_port: 8765
  
features:
  chat_tracking: true
  git_tracking: true
  file_watch: true
  auto_scan: true
```

## Benefits of Modular Architecture

1. **Single Dashboard, Multiple IDEs**: Users can switch between Windsurf and OpenCode while maintaining unified project tracking

2. **Consistent Data Model**: All IDEs write to the same SQLite schema, enabling cross-IDE analytics

3. **IDE-Agnostic Web Dashboard**: The web interface works regardless of which IDE generated the data

4. **Future-Proof**: Adding support for new AI IDEs only requires implementing the adapter interface

5. **Selective Enablement**: Users can enable/disable IDE integrations as needed

## Technical Considerations

### SQLite Concurrency
- Both Windsurf and OpenCode use WAL mode for SQLite
- Multiple IDE adapters can write concurrently
- Use proper transaction isolation

### Data Normalization
- Standardize chat message counting across IDEs
- Normalize file path formats (absolute vs relative)
- Handle timestamp format differences

### Privacy & Security
- Keep all data local (no cloud sync)
- Respect IDE-specific privacy settings
- Allow users to exclude sensitive projects

## Conclusion

The Workspace Monitor architecture is **fully portable** to OpenCode and other AI IDEs. The modular design with clear separation between:
- Core database and analytics
- IDE-specific adapters
- Generic web dashboard

...enables seamless multi-IDE support. OpenCode's TypeScript plugin system is actually **more powerful** than Windsurf's shell-based hooks, offering typed events and direct database access.

**Recommendation**: Prioritize the native OpenCode TypeScript plugin approach for best integration, while maintaining the Python bridge for cross-IDE compatibility.
