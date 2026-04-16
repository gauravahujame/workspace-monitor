# IDE Integration Guide

How to add support for new IDEs to Workspace Monitor.

## Architecture

Workspace Monitor uses a modular adapter pattern for IDE integration:

```
┌─────────────────────────────────────────────────────────────┐
│                    IDE Layer (Pluggable)                    │
├─────────────┬─────────────┬─────────────┬─────────────────┤
│  Windsurf   │  OpenCode   │   Cursor    │  Claude Code    │
│  (Hooks)    │  (Plugin)   │  (Future)   │   (Future)      │
└─────────────┴─────────────┴─────────────┴─────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│              Universal Bridge (workspace_monitor)            │
└─────────────────────────────────────────────────────────────┘
```

## IDEAdapter Interface

All IDE adapters must implement this interface:

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

## Adding a New IDE

### Step 1: Create Adapter

Create file: `src/workspace_monitor/ide_adapters/myide.py`

```python
from .base import IDEAdapter
from pathlib import Path
from typing import Dict, Any, Optional

class MyIDEAdapter(IDEAdapter):
    """Adapter for MyIDE integration."""
    
    @property
    def name(self) -> str:
        return "myide"
    
    @property
    def config_dir(self) -> Path:
        return Path.home() / ".config" / "myide"
    
    def install_hooks(self) -> bool:
        """Install hooks into MyIDE."""
        hooks_config = self.config_dir / "hooks.json"
        
        hooks_config.write_text(json.dumps({
            "hooks": {
                "post_edit": [{
                    "command": "~/.workspace-monitor/venv/bin/python -m workspace_monitor.ide_adapters.myide",
                    "show_output": False
                }]
            }
        }))
        
        return True
    
    def uninstall_hooks(self) -> bool:
        """Remove hooks from MyIDE."""
        hooks_config = self.config_dir / "hooks.json"
        if hooks_config.exists():
            hooks_config.unlink()
        return True
    
    def is_active(self) -> bool:
        """Check if hooks are installed."""
        hooks_config = self.config_dir / "hooks.json"
        return hooks_config.exists()
    
    def get_session_data(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve session data from MyIDE."""
        sessions_dir = self.config_dir / "sessions"
        session_file = sessions_dir / f"{session_id}.json"
        
        if not session_file.exists():
            return None
        
        with open(session_file, 'r') as f:
            return json.load(f)
```

### Step 2: Register Adapter

Update `src/workspace_monitor/ide_adapters/__init__.py`:

```python
from .myide import MyIDEAdapter

ADAPTERS = {
    "windsurf": WindsurfAdapter,
    "opencode": OpenCodeAdapter,
    "myide": MyIDEAdapter,
}
```

### Step 3: Create Hook Processor

Create `src/workspace_monitor/ide_adapters/myide_processor.py`:

```python
import sys
import json
from pathlib import Path

def main():
    """Process MyIDE hook events."""
    # Read JSON from stdin
    data = json.load(sys.stdin)
    
    event_type = data.get("event_type")
    event_data = data.get("data", {})
    
    if event_type == "post_edit":
        file_path = event_data.get("file_path")
        project_path = detect_project_path(file_path)
        
        # Update project in database
        from workspace_monitor.core import WorkspaceDashboard
        dashboard = WorkspaceDashboard()
        dashboard.refresh_project(project_path)

def detect_project_path(file_path: str) -> Path:
    """Detect project path from file path."""
    path = Path(file_path)
    
    # Find .git directory
    current = path
    while current != current.parent:
        if (current / ".git").exists():
            return current
        current = current.parent
    
    return path

if __name__ == "__main__":
    main()
```

### Step 4: Update Documentation

Update `docs/IDE_INTEGRATION_ANALYSIS.md`:

```markdown
## MyIDE Integration

### Event Mapping

| Workspace Monitor Feature | MyIDE Event |
|---------------------------|-------------|
| **Chat Tracking** | `session.updated` |
| **File Edits** | `post_edit` |
| **Git Actions** | `command.executed` |

### Installation

```bash
# Install hooks
wsd install-hooks myide

# Or manually
cp ~/.workspace-monitor/ide_adapters/myide_hooks.json ~/.config/myide/hooks.json
```
```

### Step 5: Update README.md

Add to README:

```markdown
### MyIDE Integration

```bash
# Install hooks
wsd install-hooks myide
```

See [docs/IDE_INTEGRATION_ANALYSIS.md](docs/IDE_INTEGRATION_ANALYSIS.md) for details.
```

## Event Mapping Reference

### Windsurf Events

| Hook | Purpose |
|------|---------|
| `post_cascade_response_with_transcript` | Chat tracking |
| `post_write_code` | File edit detection |
| `pre_run_command` | Git command detection |
| `post_run_command` | Git action confirmation |

### OpenCode Events

| Event | Purpose |
|-------|---------|
| `session.created` | Session start |
| `session.updated` | Chat updates |
| `file.edited` | File edit detection |
| `tool.execute.before` | Git command detection |
| `tool.execute.after` | Command confirmation |

### MyIDE (Example)

| Event | Purpose |
|-------|---------|
| `post_edit` | File edit detection |
| `session.updated` | Chat updates |
| `command.executed` | Git command tracking |

## Data Storage

All IDEs write to the **same SQLite database** for unified tracking:

```python
# Database location
if platform.system() == "darwin":
    db_path = Path.home() / "Library" / "Application Support" / "workspace-monitor" / "dashboard.db"
else:
    db_path = Path.home() / ".workspace-monitor" / "dashboard.db"
```

This enables:
- Cross-IDE project tracking
- Unified chat history
- Shared git action logs
- Single web dashboard view

## Configuration

IDE-specific configuration stored in `~/.workspace-monitor/config.yaml`:

```yaml
ides:
  windsurf:
    enabled: true
    hooks_path: ~/.codeium/windsurf/hooks.json
    transcript_path: ~/.windsurf/transcripts
    
  opencode:
    enabled: true
    plugin_path: ~/.config/opencode/plugins/workspace-monitor.ts
    database_path: ~/.local/share/opencode/opencode.db
    
  myide:
    enabled: true
    hooks_path: ~/.config/myide/hooks.json
```

## Testing IDE Integration

### Unit Tests

```python
def test_ide_adapter():
    """Test IDE adapter interface."""
    adapter = MyIDEAdapter()
    
    assert adapter.name == "myide"
    assert adapter.config_dir == Path.home() / ".config" / "myide"
    assert isinstance(adapter.is_active(), bool)
```

### Integration Tests

```python
def test_hook_processing():
    """Test hook event processing."""
    # Simulate hook event
    event_data = {
        "event_type": "post_edit",
        "data": {"file_path": "/path/to/file.py"}
    }
    
    # Process event
    process_event(event_data)
    
    # Verify database updated
    dashboard = WorkspaceDashboard()
    projects = dashboard.get_projects()
    assert len(projects) > 0
```

## Troubleshooting IDE Integration

### Hook Not Firing

1. Check hook configuration file exists
2. Verify hook command path is correct
3. Check IDE logs for errors
4. Test hook manually from command line

### Session Data Missing

1. Verify IDE session storage location
2. Check file permissions
3. Test `get_session_data()` method
4. Check database connection

### Event Mapping Issues

1. Verify event names match IDE documentation
2. Check event payload structure
3. Add debug logging to hook processor
4. Test with sample event data

## Best Practices

1. **Use absolute paths** for hook commands
2. **Graceful degradation** - if hook fails, log error but don't crash
3. **Type hints** on all adapter methods
4. **Error handling** - catch and log exceptions
5. **Documentation** - document all events and their payloads
6. **Testing** - unit test adapter methods, integration test hook processing
7. **Idempotency** - install/uninstall should be safe to run multiple times
