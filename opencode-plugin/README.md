# OpenCode Workspace Monitor Plugin

This TypeScript plugin integrates OpenCode with the Workspace Monitor system, enabling:

- 📊 **Project Tracking**: Automatic discovery and monitoring of git repositories
- 💬 **Session Tracking**: Record chat sessions with message counts
- 📝 **File Edit Tracking**: Track file modifications per project  
- 🔧 **Git Action Logging**: Log git commands (commit, push, pull, etc.)
- 🔍 **Dashboard Tools**: AI-accessible tools for querying workspace status

## Installation

### 1. Install the Plugin

Copy the plugin to your OpenCode plugins directory:

```bash
# macOS
mkdir -p ~/Library/Application\ Support/opencode/plugins
cp workspace-monitor.ts ~/Library/Application\ Support/opencode/plugins/

# Linux
mkdir -p ~/.config/opencode/plugins
cp workspace-monitor.ts ~/.config/opencode/plugins/
```

### 2. Configure OpenCode

Edit your `opencode.jsonc` (or `opencode.json`) to load the plugin:

```json
{
  "plugins": [
    "~/.config/opencode/plugins/workspace-monitor.ts"
  ]
}
```

### 3. Restart OpenCode

The plugin will be automatically loaded on startup.

## Features

### Automatic Project Detection

The plugin automatically detects git repositories from:
- OpenCode's `directory` context
- OpenCode's `worktree` context
- Parent directory traversal for `.git`

### Session Tracking

Records when sessions are:
- Created
- Updated (new messages)
- Deleted

### Git Action Logging

Automatically logs git commands:
- `git commit`
- `git push`
- `git pull`
- `git fetch`
- `git merge`
- `git checkout`
- `git branch`

### AI-Accessible Tools

The plugin exposes these tools to OpenCode's AI:

#### `workspace.list_projects`
List all projects with optional status filtering:

```
User: Show me all dirty projects
AI: *calls workspace.list_projects with status: "dirty"*
```

#### `workspace.project_status`
Get detailed status of a specific project:

```
User: What's the status of my backend-api project?
AI: *calls workspace.project_status with project_name: "backend-api"*
```

#### `workspace.stats`
Get overall workspace statistics:

```
User: Give me workspace statistics
AI: *calls workspace.stats*
```

#### `workspace.scan`
Scan for new git repositories:

```
User: Scan for new projects
AI: *calls workspace.scan*
```

## Data Storage

Data is stored in the same SQLite database as the Windsurf integration:

- **macOS**: `~/Library/Application Support/workspace-monitor/dashboard.db`
- **Linux**: `~/.workspace-monitor/dashboard.db`

This enables **cross-IDE project tracking** - work in Windsurf, continue in OpenCode, view unified dashboard.

## Database Schema

The plugin uses these tables:

- `projects` - Project metadata and git status
- `chats` - Chat session records
- `git_actions` - Git command history
- `opencode_sessions` - OpenCode-specific session tracking

## Configuration

Set the `WORKSPACE_MONITOR_DEBUG` environment variable to enable debug logging:

```bash
export WORKSPACE_MONITOR_DEBUG=1
opencode
```

## Troubleshooting

### Plugin not loading

Check OpenCode logs:
```bash
opencode --log-level DEBUG
```

### Database not found

Ensure the data directory is writable:
```bash
# macOS
ls -la ~/Library/Application\ Support/

# Linux
ls -la ~/.workspace-monitor/
```

### No projects showing

Verify your workspace directory exists and contains git repositories:
```bash
ls ~/workspace
```

## Comparison with Windsurf Integration

| Feature | Windsurf | OpenCode |
|---------|----------|----------|
| **Hook System** | Shell commands in `hooks.json` | TypeScript plugin with events |
| **Session Data** | JSONL transcript files | SQLite database + events |
| **Configuration** | `~/.codeium/windsurf/` | `~/.config/opencode/` |
| **Transcript Parsing** | File-based | Event-based (real-time) |
| **Custom Tools** | Not available | Native TypeScript tools |

## Development

### Building

No build step required - OpenCode uses Bun to run TypeScript directly.

### Testing

Test the plugin:
```bash
# Check TypeScript compiles
bun check workspace-monitor.ts

# Run with debug logging
WORKSPACE_MONITOR_DEBUG=1 opencode
```

### Adding New Events

To add support for additional OpenCode events, update the plugin object:

```typescript
return {
  // ... existing handlers
  
  "your.event.name": async ({ event }) => {
    log("Event received:", event.type);
    // Your logic here
  },
};
```

## License

MIT - Same as Workspace Monitor
