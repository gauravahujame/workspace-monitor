# Workspace Monitor - AI Agent Guidelines

## Project Overview

Workspace Monitor is a cross-IDE dashboard system for monitoring git repositories under `~/workspace`. It supports Windsurf (shell hooks) and OpenCode (TypeScript plugin), with a unified SQLite database, web dashboard, and CLI tool.

## Architecture

```
workspace-monitor/
├── src/workspace_monitor/
│   ├── core.py              # Database operations, project scanning, git analysis
│   ├── cli.py               # CLI commands (wsd)
│   ├── web/server.py        # FastAPI/Flask web dashboard
│   └── hooks/processor.py   # Windsurf hook integration
├── opencode-plugin/         # TypeScript plugin for OpenCode
├── pyproject.toml           # Python packaging with UV dependency groups
├── requirements.txt         # UV-compatible requirements
└── install.sh               # One-click installer
```

## Key Technologies

- **Python 3.8+** with UV package manager (10-100x faster than pip)
- **SQLite** for persistent storage (WAL mode for concurrency)
- **FastAPI/Flask** for web dashboard
- **Click** for CLI
- **TypeScript** for OpenCode plugin
- **Shell hooks** for Windsurf integration

## Development Guidelines

### When to Log Here

Log architectural decisions, bug fixes, feature additions, or any significant changes to the codebase in the relevant documentation files.

### What to Log

- **Architectural decisions**: Changes to database schema, API design, integration approach
- **Bug fixes**: Root cause analysis and resolution
- **Feature additions**: New capabilities, their rationale, and implementation details
- **Performance improvements**: Optimization strategies and results
- **Cross-IDE compatibility**: Changes affecting Windsurf, OpenCode, or future IDE support

### Format

Use markdown with clear headings. Include:
- **Date**: When the change was made
- **Context**: Why the change was needed
- **Decision**: What was done
- **Impact**: What this affects

Example:
```markdown
## 2026-04-16 - Switched to UV Package Manager

**Context**: pip was slow for dependency resolution and installation.

**Decision**: Migrated from pip to UV (10-100x faster). Updated pyproject.toml to use `dependency-groups` instead of deprecated `tool.uv.dev-dependencies`.

**Impact**: 
- Faster installation times
- Modern Python packaging standards
- Requires UV to be installed (handled by install.sh)
- Updated README.md and Windsurf hooks to use venv path
```

## Code Style

- Use **black** for formatting (line-length: 100)
- Use **ruff** for linting
- Use **mypy** for type checking (strict mode)
- Follow PEP 8 guidelines

### Type Hints

All functions should have type hints:
```python
def scan_projects(
    root: Path,
    max_depth: int = 3
) -> List[ProjectInfo]:
    """Scan for git repositories under root directory."""
    pass
```

### Docstrings

Use Google-style docstrings:
```python
def get_projects(
    status_filter: Optional[str] = None,
    sort_by: str = "last_chat_time"
) -> List[ProjectInfo]:
    """Get all projects with optional filtering and sorting.
    
    Args:
        status_filter: Filter by git status (clean, dirty, ahead, behind)
        sort_by: Field to sort by (default: last_chat_time)
        
    Returns:
        List of ProjectInfo objects
    """
    pass
```

## Database Schema

### Projects Table
```sql
CREATE TABLE projects (
    path TEXT PRIMARY KEY,
    name TEXT,
    git_branch TEXT,
    git_status TEXT,
    last_commit TEXT,
    last_commit_time TIMESTAMP,
    commits_ahead INTEGER DEFAULT 0,
    commits_behind INTEGER DEFAULT 0,
    uncommitted_files INTEGER DEFAULT 0,
    is_windsurf_open BOOLEAN DEFAULT 0,
    total_chats INTEGER DEFAULT 0,
    last_chat_time TIMESTAMP,
    todos_count INTEGER DEFAULT 0,
    todos_done INTEGER DEFAULT 0,
    tags TEXT,
    language TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
```

### Chats Table
```sql
CREATE TABLE chats (
    trajectory_id TEXT PRIMARY KEY,
    project_path TEXT,
    timestamp TIMESTAMP,
    message_count INTEGER DEFAULT 0,
    file_edits INTEGER DEFAULT 0,
    commands_run INTEGER DEFAULT 0,
    transcript_path TEXT,
    summary TEXT,
    FOREIGN KEY (project_path) REFERENCES projects(path)
)
```

### Git Actions Table
```sql
CREATE TABLE git_actions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_path TEXT,
    action_type TEXT,
    timestamp TIMESTAMP,
    details TEXT,
    files_changed INTEGER DEFAULT 0,
    insertions INTEGER DEFAULT 0,
    deletions INTEGER DEFAULT 0,
    FOREIGN KEY (project_path) REFERENCES projects(path)
)
```

## Adding New IDE Support

To add support for a new IDE (e.g., Cursor, Claude Code):

1. Create adapter in `src/workspace_monitor/ide_adapters/`
2. Implement `IDEAdapter` interface:
   ```python
   class IDEAdapter(ABC):
       @property
       def name(self) -> str: ...
       
       def install_hooks(self) -> bool: ...
       
       def is_active(self) -> bool: ...
       
       def get_session_data(self, session_id: str) -> Optional[Dict]: ...
   ```
3. Write to same SQLite database (unified cross-IDE tracking)
4. Update `docs/IDE_INTEGRATION_ANALYSIS.md` with event mapping
5. Add installation instructions to README.md

## Testing

Run tests with:
```bash
uv venv
source .venv/bin/activate
uv pip install -e ".[dev]"
pytest
```

## Common Tasks

### Adding a new CLI command
Add to `src/workspace_monitor/cli.py`:
```python
@cli.command()
def mycommand():
    """My new command."""
    pass
```

### Adding a new API endpoint
Add to `src/workspace_monitor/web/server.py`:
```python
@app.get("/api/myendpoint")
def my_endpoint():
    return {"data": "response"}
```

### Updating database schema
1. Add migration to `src/workspace_monitor/core.py` in `initialize_schema()`
2. Document the change in AGENTS.md
3. Consider backward compatibility

## Platform-Specific Notes

### macOS
- Data directory: `~/Library/Application Support/workspace-monitor/`
- Use `platform.system() == 'Darwin'` to detect
- Test on macOS before releasing

### Linux
- Data directory: `~/.workspace-monitor/`
- Use `platform.system() == 'Linux'` to detect

## Performance Considerations

- Use WAL mode for SQLite (already enabled)
- Index frequently queried columns (already done)
- Batch database operations when possible
- Cache git status results (short TTL)
- Use async for web server (FastAPI)

## Security

- All data is local (no cloud sync)
- Respect IDE-specific privacy settings
- Allow users to exclude sensitive projects
- Never log credentials or sensitive data

## Troubleshooting Common Issues

### Database locked
- Ensure WAL mode is enabled
- Check for long-running transactions
- Use connection pooling

### Git status slow
- Limit max_depth in project scanning
- Cache results with short TTL
- Skip excluded directories (.git, node_modules, etc.)

### Hook not firing
- Check hook command path (use absolute paths)
- Verify hook is executable
- Check Windsurf/OpenCode logs
