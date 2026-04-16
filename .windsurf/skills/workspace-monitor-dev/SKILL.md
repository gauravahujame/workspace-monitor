# Workspace Monitor Development Skill

This skill provides specialized assistance for developing the workspace-monitor project.

## Project Context

Workspace Monitor is a cross-IDE dashboard system that:
- Monitors git repositories under `~/workspace`
- Integrates with Windsurf (shell hooks) and OpenCode (TypeScript plugin)
- Uses SQLite for unified data storage
- Provides web dashboard and CLI tool (`wsd`)
- Uses UV for fast Python package management

## When to Use This Skill

Use this skill when:
- Adding new features to workspace-monitor
- Fixing bugs in the core system
- Adding support for new IDEs
- Modifying database schema
- Updating CLI commands
- Working on web dashboard
- Integrating with Windsurf or OpenCode

## Architecture Overview

```
src/workspace_monitor/
├── core.py              # Database, project scanning, git analysis
├── cli.py               # CLI commands (wsd)
├── web/server.py        # FastAPI/Flask web dashboard
└── hooks/processor.py   # Windsurf hook integration

opencode-plugin/
└── workspace-monitor.ts # TypeScript plugin for OpenCode
```

## Key Technologies

- **Python 3.8+** with UV package manager (NOT pip)
- **SQLite** with WAL mode for concurrency
- **FastAPI/Flask** for web server
- **Click** for CLI
- **TypeScript** for OpenCode plugin
- **Shell hooks** for Windsurf integration

## Development Guidelines

### Code Style

- Use **black** for formatting (line-length: 100)
- Use **ruff** for linting
- Use **mypy** for type checking (strict mode)
- All functions must have type hints
- Use Google-style docstrings

### Database Operations

When modifying database schema:
1. Update `initialize_schema()` in `core.py`
2. Add migration logic if needed
3. Document changes in AGENTS.md
4. Ensure backward compatibility

### Adding CLI Commands

Add to `src/workspace_monitor/cli.py`:
```python
@cli.command()
@click.option('--option', default='value', help='Description')
def mycommand(option):
    """Command description."""
    pass
```

### Adding API Endpoints

Add to `src/workspace_monitor/web/server.py`:
```python
@app.get("/api/endpoint")
def endpoint():
    return {"data": "response"}
```

### Adding IDE Support

To add support for a new IDE:
1. Create adapter in `src/workspace_monitor/ide_adapters/`
2. Implement `IDEAdapter` interface
3. Write to same SQLite database for unified tracking
4. Update `docs/IDE_INTEGRATION_ANALYSIS.md`
5. Add installation instructions to README.md

## Common Patterns

### Database Query Pattern

```python
def get_projects(self, status_filter: Optional[str] = None) -> List[ProjectInfo]:
    """Get projects with optional filtering."""
    query = "SELECT * FROM projects"
    params = []
    
    if status_filter:
        query += " WHERE git_status = ?"
        params.append(status_filter)
    
    return [ProjectInfo(**row) for row in self.db.execute(query, params).fetchall()]
```

### Git Status Analysis Pattern

```python
def analyze_git_status(self, project_path: Path) -> Dict[str, Any]:
    """Analyze git repository status."""
    # Get branch
    branch = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        cwd=project_path,
        capture_output=True,
        text=True
    ).stdout.strip()
    
    # Get status
    status = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=project_path,
        capture_output=True,
        text=True
    ).stdout
    
    # Parse and return status info
    return {
        "branch": branch,
        "dirty": len(status) > 0,
        "changes": len(status.splitlines())
    }
```

### Hook Processor Pattern

```python
def process_hook_event(self, event_type: str, data: Dict[str, Any]) -> None:
    """Process Windsurf hook event."""
    if event_type == "post_cascade_response_with_transcript":
        self._process_transcript(data.get("transcript_path"))
    elif event_type == "post_write_code":
        self._refresh_project(data.get("file_path"))
```

## Platform-Specific Considerations

### macOS
- Data directory: `~/Library/Application Support/workspace-monitor/`
- Use `platform.system() == 'Darwin'` for detection
- Test on macOS before releasing

### Linux
- Data directory: `~/.workspace-monitor/`
- Use `platform.system() == 'Linux'` for detection

## Testing

Run tests with:
```bash
uv venv
source .venv/bin/activate
uv pip install -e ".[dev]"
pytest
```

## Installation for Development

```bash
# Install UV if not present
curl -LsSf https://astral.sh/uv/install.sh | sh

# Clone and install
git clone https://github.com/gauravahujame/workspace-monitor.git
cd workspace-monitor
uv venv
source .venv/bin/activate
uv pip install -e ".[dev,web]"
```

## Common Issues

### Database Locked
- Ensure WAL mode is enabled
- Check for long-running transactions
- Use connection pooling

### Git Status Slow
- Limit max_depth in project scanning
- Cache results with short TTL
- Skip excluded directories (.git, node_modules, etc.)

### Hook Not Firing
- Check hook command path (use absolute paths)
- Verify hook is executable
- Check Windsurf/OpenCode logs

## Documentation Updates

When making significant changes:
1. Update AGENTS.md with decision rationale
2. Update README.md if user-facing changes
3. Update docs/IDE_INTEGRATION_ANALYSIS.md for IDE changes
4. Add/update type hints for all new functions

## Release Checklist

Before releasing:
- [ ] Run all tests
- [ ] Check type hints with mypy
- [ ] Format with black
- [ ] Lint with ruff
- [ ] Test on macOS (if applicable)
- [ ] Update version in pyproject.toml
- [ ] Update CHANGELOG.md
- [ ] Test one-click installer
- [ ] Test Windsurf hooks
- [ ] Test OpenCode plugin (if changed)
