# Code Patterns Reference

Common patterns used throughout the workspace-monitor codebase.

## Database Query Pattern

Standard pattern for querying with optional filters:

```python
def get_projects(
    self, 
    status_filter: Optional[str] = None,
    sort_by: str = "last_chat_time"
) -> List[ProjectInfo]:
    """Get projects with optional filtering and sorting."""
    query = "SELECT * FROM projects"
    params: List[Any] = []
    
    if status_filter:
        query += " WHERE git_status = ?"
        params.append(status_filter)
    
    query += f" ORDER BY {sort_by} DESC NULLS LAST"
    
    return [ProjectInfo(**row) for row in self.db.execute(query, params).fetchall()]
```

## Git Status Analysis Pattern

Analyze git repository status using subprocess:

```python
def analyze_git_status(self, project_path: Path) -> Dict[str, Any]:
    """Analyze git repository status."""
    # Get branch
    branch = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        cwd=project_path,
        capture_output=True,
        text=True,
        check=True
    ).stdout.strip()
    
    # Get status
    status = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=project_path,
        capture_output=True,
        text=True,
        check=True
    ).stdout
    
    # Get ahead/behind
    try:
        ahead = subprocess.run(
            ["git", "rev-list", "--count", "@{u}..HEAD"],
            cwd=project_path,
            capture_output=True,
            text=True,
            check=True
        ).stdout.strip()
        behind = subprocess.run(
            ["git", "rev-list", "--count", "HEAD..@{u}"],
            cwd=project_path,
            capture_output=True,
            text=True,
            check=True
        ).stdout.strip()
    except subprocess.CalledProcessError:
        ahead = "0"
        behind = "0"
    
    return {
        "branch": branch,
        "dirty": len(status) > 0,
        "changes": len(status.splitlines()),
        "ahead": int(ahead) if ahead else 0,
        "behind": int(behind) if behind else 0
    }
```

## Hook Processor Pattern

Process Windsurf hook events with JSON input:

```python
def process_hook_event(self, event_type: str, data: Dict[str, Any]) -> None:
    """Process Windsurf hook event."""
    try:
        if event_type == "post_cascade_response_with_transcript":
            self._process_transcript(data.get("transcript_path"))
        elif event_type == "post_write_code":
            self._refresh_project(data.get("file_path"))
        elif event_type == "pre_run_command":
            self._track_git_command(data.get("command"))
        elif event_type == "post_run_command":
            self._confirm_git_action(data.get("command"))
    except Exception as e:
        # Log error but don't crash
        self._log_error(f"Hook processing failed: {e}")
```

## Data Directory Pattern

Platform-specific data directory detection:

```python
def get_data_dir() -> Path:
    """Get platform-specific data directory."""
    if platform.system() == "darwin":
        return Path.home() / "Library" / "Application Support" / "workspace-monitor"
    else:
        return Path.home() / ".workspace-monitor"
```

## CLI Command Pattern

Add Click command with options:

```python
@cli.command()
@click.option('--status', type=click.Choice(['clean', 'dirty', 'ahead', 'behind']), 
              help='Filter by git status')
@click.option('--sort', default='last_chat_time', 
              help='Sort field')
@click.option('--limit', type=int, default=50, 
              help='Maximum number of projects')
@click.option('--json', is_flag=True, help='Output as JSON')
def list_projects(status: Optional[str], sort: str, limit: int, json: bool) -> None:
    """List all projects with optional filtering."""
    dashboard = WorkspaceDashboard()
    projects = dashboard.get_projects(status_filter=status, sort_by=sort)
    
    if json:
        click.echo(json.dumps([p.__dict__ for p in projects[:limit]]))
    else:
        for project in projects[:limit]:
            click.echo(f"{project.name}: {project.git_status}")
```

## API Endpoint Pattern

FastAPI endpoint with error handling:

```python
@app.get("/api/projects")
def get_projects(
    status: Optional[str] = None,
    sort: str = "last_chat_time",
    limit: int = 50
) -> Dict[str, Any]:
    """Get projects with optional filtering."""
    try:
        dashboard = WorkspaceDashboard()
        projects = dashboard.get_projects(status_filter=status, sort_by=sort)
        
        return {
            "success": True,
            "data": [p.__dict__ for p in projects[:limit]],
            "count": len(projects)
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }
```

## Type Hints Pattern

All functions must have type hints:

```python
from typing import List, Optional, Dict, Any
from pathlib import Path

def scan_projects(
    root: Path,
    max_depth: int = 3,
    exclude_dirs: Optional[List[str]] = None
) -> List[ProjectInfo]:
    """Scan for git repositories under root directory.
    
    Args:
        root: Root directory to scan
        max_depth: Maximum depth to search
        exclude_dirs: Directories to exclude
        
    Returns:
        List of ProjectInfo objects
    """
    if exclude_dirs is None:
        exclude_dirs = [".git", "node_modules", "__pycache__"]
    
    # Implementation
    pass
```

## Error Handling Pattern

Graceful error handling with logging:

```python
import logging

logger = logging.getLogger(__name__)

def risky_operation() -> bool:
    """Perform operation with error handling."""
    try:
        # Do something risky
        result = subprocess.run(["command"], check=True)
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Command failed: {e}")
        return False
    except FileNotFoundError as e:
        logger.error(f"File not found: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return False
```

## Configuration Pattern

Environment variable with fallback:

```python
import os

def get_workspace_root() -> Path:
    """Get workspace root from environment or default."""
    workspace = os.environ.get("WORKSPACE_ROOT")
    if workspace:
        return Path(workspace)
    return Path.home() / "workspace"
```

## Database Connection Pattern

Context manager for database connections:

```python
from contextlib import contextmanager

@contextmanager
def get_db_connection(db_path: Path):
    """Context manager for database connection."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    try:
        yield conn
    finally:
        conn.close()

# Usage
with get_db_connection(db_path) as conn:
    results = conn.execute("SELECT * FROM projects").fetchall()
```

## Language Detection Pattern

Detect programming language from project files:

```python
def detect_language(project_path: Path) -> str:
    """Detect programming language from project files."""
    language_files: Dict[str, List[str]] = {
        "Python": ["requirements.txt", "setup.py", "pyproject.toml", "Pipfile"],
        "JavaScript": ["package.json", "yarn.lock", "pnpm-lock.yaml"],
        "TypeScript": ["tsconfig.json"],
        "Go": ["go.mod", "go.sum"],
        "Rust": ["Cargo.toml", "Cargo.lock"],
    }
    
    for lang, files in language_files.items():
        for file in files:
            if (project_path / file).exists():
                return lang
    
    return "Unknown"
```

## Transcript Parsing Pattern

Parse Windsurf JSONL transcripts:

```python
def parse_transcript(transcript_path: Path) -> Dict[str, Any]:
    """Parse Windsurf JSONL transcript."""
    message_count = 0
    file_edits = 0
    commands_run = 0
    
    with open(transcript_path, 'r') as f:
        for line in f:
            if not line.strip():
                continue
            
            entry = json.loads(line)
            if entry.get("type") == "message":
                message_count += 1
            elif entry.get("type") == "file_edit":
                file_edits += 1
            elif entry.get("type") == "command":
                commands_run += 1
    
    return {
        "message_count": message_count,
        "file_edits": file_edits,
        "commands_run": commands_run
    }
```

## Testing Pattern

Unit test with fixtures:

```python
import pytest
from pathlib import Path

@pytest.fixture
def temp_db(tmp_path: Path):
    """Create temporary database for testing."""
    db_path = tmp_path / "test.db"
    dashboard = WorkspaceDashboard(db_path=db_path)
    yield dashboard
    # Cleanup handled by tmp_path fixture

def test_scan_projects(temp_db: WorkspaceDashboard):
    """Test project scanning."""
    projects = temp_db.scan_projects()
    assert isinstance(projects, list)
    # More assertions
```
