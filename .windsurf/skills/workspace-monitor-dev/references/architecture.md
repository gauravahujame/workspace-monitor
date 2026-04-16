# Architecture Reference

Detailed system architecture for Workspace Monitor.

## System Overview

Workspace Monitor is a cross-IDE dashboard system that:
- Monitors git repositories under `~/workspace`
- Integrates with Windsurf (shell hooks) and OpenCode (TypeScript plugin)
- Uses SQLite for unified data storage
- Provides web dashboard and CLI tool (`wsd`)
- Uses UV for fast Python package management

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         User Interface                           │
├─────────────────────────────────────────────────────────────────┤
│  CLI (wsd)              │  Web Dashboard (FastAPI/Flask)        │
│  - List projects        │  - Project table                      │
│  - Show status          │  - Activity chart                      │
│  - Scan workspace       │  - Search & filter                     │
│  - Run git commands     │  - Real-time updates                   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Core Library (workspace_monitor)               │
├─────────────────────────────────────────────────────────────────┤
│  Core Module            │  Web Module          │  Hooks Module   │
│  - Database operations  │  - API endpoints     │  - Event         │
│  - Project scanning     │  - HTML generation   │    processing    │
│  - Git analysis         │  - WebSocket support │  - Transcript    │
│  - Language detection   │  - Static serving    │    parsing       │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Data Layer (SQLite)                           │
├─────────────────────────────────────────────────────────────────┤
│  Projects Table  │  Chats Table  │  Git Actions Table            │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    IDE Integration Layer                         │
├─────────────────────────────────────────────────────────────────┤
│  Windsurf Adapter    │  OpenCode Adapter  │  Future Adapters   │
│  - Shell hooks       │  - TypeScript      │  - Cursor          │
│  - JSONL transcripts │    plugin          │  - Claude Code     │
└─────────────────────────────────────────────────────────────────┘
```

## Module Structure

### Core Module (`src/workspace_monitor/core.py`)

**Responsibilities**:
- Database schema initialization and management
- Project scanning and git repository detection
- Git status analysis (branch, ahead/behind, dirty state)
- Language detection
- Data retrieval and statistics

**Key Classes**:
- `WorkspaceDashboard`: Main dashboard class
- `ProjectInfo`: Data class for project metadata
- `ChatEntry`: Data class for chat/session records
- `GitAction`: Data class for git action records

**Key Methods**:
```python
class WorkspaceDashboard:
    def __init__(self, db_path: Optional[Path] = None)
    def scan_projects(self, root: Path, max_depth: int = 3) -> List[ProjectInfo]
    def get_projects(self, status_filter: Optional[str] = None) -> List[ProjectInfo]
    def get_chats(self, project_path: Optional[str] = None) -> List[ChatEntry]
    def get_git_actions(self, project_path: Optional[str] = None) -> List[GitAction]
    def get_stats(self) -> Dict[str, Any]
    def export_data(self, export_path: Path) -> None
```

### CLI Module (`src/workspace_monitor/cli.py`)

**Responsibilities**:
- Command-line interface implementation
- User interaction and output formatting
- Command argument parsing

**Key Commands**:
```python
@cli.command()
def list_projects(status, sort, limit, json)

@cli.command()
def scan()

@cli.command()
def status(project_name)

@cli.command()
def stats()

@cli.command()
def chats(limit)

@cli.command()
def server(host, port)

@cli.command()
def search(query)

@cli.command()
def git(command)

@cli.command()
def open_project(project_name)

@cli.command()
def export(output)
```

### Web Module (`src/workspace_monitor/web/server.py`)

**Responsibilities**:
- Web API endpoints
- HTML dashboard generation
- WebSocket support for real-time updates
- Static file serving

**API Endpoints**:
```python
GET  /api/projects          # List projects
GET  /api/projects/{path}   # Get specific project
GET  /api/stats             # Get statistics
GET  /api/chats             # Get recent chats
GET  /api/activity          # Get activity timeline
GET  /api/refresh           # Trigger project refresh
GET  /api/export            # Export data
WS   /ws                    # WebSocket for real-time updates
```

### Hooks Module (`src/workspace_monitor/hooks/processor.py`)

**Responsibilities**:
- Process Windsurf hook events
- Parse transcript files
- Track git commands
- Update database based on events

**Event Handlers**:
```python
def process_post_cascade_response(transcript_path: str)
def process_post_write_code(file_path: str)
def process_pre_run_command(command: str)
def process_post_run_command(command: str)
```

## Data Flow

### Project Discovery Flow

```
User runs "wsd scan"
    ↓
scan_projects() called
    ↓
Walk ~/workspace directory (max_depth: 3)
    ↓
For each directory:
    - Check if .git exists
    - If yes, analyze_git_status()
    - Detect language
    - Update/create project record
    ↓
Return list of ProjectInfo objects
```

### Chat Tracking Flow (Windsurf)

```
User completes chat in Windsurf
    ↓
Windsurf triggers post_cascade_response_with_transcript
    ↓
Hook processor called with transcript path
    ↓
Parse JSONL transcript file:
    - Count messages
    - Count file edits
    - Count commands run
    ↓
Update chats table
    ↓
Update projects table (total_chats, last_chat_time)
```

### Git Action Tracking Flow

```
User runs git command
    ↓
Windsurf triggers pre_run_command
    ↓
Hook processor detects git command
    ↓
Parse command (commit, push, pull, etc.)
    ↓
Store pending action in git_actions table
    ↓
Command completes
    ↓
Windsurf triggers post_run_command
    ↓
Confirm action, update details (files changed, insertions, deletions)
```

### Web Dashboard Data Flow

```
User opens http://127.0.0.1:8765
    ↓
FastAPI serves index.html
    ↓
Frontend requests /api/projects
    ↓
WorkspaceDashboard.get_projects() called
    ↓
Query SQLite database
    ↓
Return JSON to frontend
    ↓
Frontend renders project table
    ↓
WebSocket connection established for real-time updates
```

## Cross-IDE Data Flow

```
┌─────────────┐
│  Windsurf   │
│  Session    │
└─────────────┘
      │
      │ post_cascade_response hook
      ▼
┌─────────────────────────────────┐
│  Hook Processor (Python)        │
│  - Parse transcript             │
│  - Extract metadata             │
└─────────────────────────────────┘
      │
      │ Write to SQLite
      ▼
┌─────────────────────────────────┐
│  SQLite Database                │
│  - projects table              │
│  - chats table                 │
│  - git_actions table           │
└─────────────────────────────────┘
      │
      │ Read by web dashboard
      ▼
┌─────────────────────────────────┐
│  Web Dashboard                 │
│  - Unified project view        │
│  - Cross-IDE activity          │
└─────────────────────────────────┘

┌─────────────┐
│  OpenCode   │
│  Session    │
└─────────────┘
      │
      │ session.updated event
      ▼
┌─────────────────────────────────┐
│  TypeScript Plugin             │
│  - Extract session data        │
│  - Track events                │
└─────────────────────────────────┘
      │
      │ Write to SQLite (same DB!)
      ▼
┌─────────────────────────────────┐
│  SQLite Database (Shared)      │
└─────────────────────────────────┘
```

## Configuration Management

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `WORKSPACE_ROOT` | Workspace directory | `~/workspace` |
| `WORKSPACE_MONITOR_DATA` | Data directory | Platform-specific |
| `WORKSPACE_MONITOR_DEBUG` | Enable debug logging | `false` |

### Configuration File

`~/.workspace-monitor/config.yaml`:

```yaml
general:
  workspace_root: ~/workspace
  data_dir: ~/.workspace-monitor
  web_port: 8765

ides:
  windsurf:
    enabled: true
    hooks_path: ~/.codeium/windsurf/hooks.json
    transcript_path: ~/.windsurf/transcripts
    
  opencode:
    enabled: true
    plugin_path: ~/.config/opencode/plugins/workspace-monitor.ts

features:
  chat_tracking: true
  git_tracking: true
  file_watch: true
  auto_scan: true
```

## Performance Considerations

### Database Optimization
- WAL mode enabled for concurrent access
- Indexes on frequently queried columns
- Connection pooling for web server
- Parameterized queries to prevent SQL injection

### Scanning Optimization
- Configurable `max_depth` for project discovery
- Skip excluded directories (.git, node_modules, etc.)
- Cache git status results with short TTL
- Batch database operations

### Web Server Optimization
- Static file caching
- WebSocket for real-time updates (reduces polling)
- Response compression (gzip)
- Rate limiting on API endpoints

## Security Considerations

- All data stored locally (no cloud sync)
- Respect IDE-specific privacy settings
- Allow users to exclude sensitive projects
- Never log credentials or sensitive data
- Validate all user inputs
- Use parameterized queries to prevent SQL injection

## Extensibility

### Adding New CLI Commands
1. Add `@cli.command()` decorator in `cli.py`
2. Implement command logic
3. Update help text
4. Add tests

### Adding New API Endpoints
1. Add route in `web/server.py`
2. Implement endpoint logic
3. Add error handling
4. Update API documentation

### Adding New IDE Support
1. Create adapter implementing `IDEAdapter` interface
2. Implement hook/event processing
3. Write to same SQLite database
4. Update documentation
5. Add installation instructions

### Adding New Database Tables
1. Update `initialize_schema()` in `core.py`
2. Add migration logic if needed
3. Document schema changes
4. Update data classes
5. Add tests
