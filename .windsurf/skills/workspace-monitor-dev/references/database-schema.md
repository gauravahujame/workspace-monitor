# Database Schema Reference

Complete table definitions and relationships for Workspace Monitor's SQLite database.

## Database Location

- **Linux**: `~/.workspace-monitor/dashboard.db`
- **macOS**: `~/Library/Application Support/workspace-monitor/dashboard.db`

## Tables

### Projects Table

Stores git repository metadata and status.

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

**Indexes**:
- `idx_projects_status` on `git_status`

**Fields**:
- `path`: Absolute path to git repository (primary key)
- `name`: Repository name (basename of path)
- `git_branch`: Current git branch
- `git_status`: One of `clean`, `dirty`, `ahead`, `behind`, `diverged`
- `last_commit`: SHA of most recent commit
- `last_commit_time`: Timestamp of last commit
- `commits_ahead`: Number of commits ahead of remote
- `commits_behind`: Number of commits behind remote
- `uncommitted_files`: Count of modified/untracked files
- `is_windsurf_open`: Whether Windsurf has this project open
- `total_chats`: Total number of chat sessions
- `last_chat_time`: Timestamp of most recent chat
- `todos_count`: Total TODO count (placeholder)
- `todos_done`: Completed TODO count (placeholder)
- `tags`: Comma-separated tags
- `language`: Detected programming language
- `updated_at`: Last update timestamp

### Chats Table

Stores chat/transcript records.

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

**Indexes**:
- `idx_chats_project` on `project_path`
- `idx_chats_time` on `timestamp`

**Fields**:
- `trajectory_id`: Unique chat/trajectory identifier (primary key)
- `project_path`: Path to project (foreign key to projects)
- `timestamp`: When the chat occurred
- `message_count`: Number of messages in chat
- `file_edits`: Number of files edited
- `commands_run`: Number of commands executed
- `transcript_path`: Path to transcript file (Windsurf)
- `summary`: Chat summary

### Git Actions Table

Logs git commands and actions.

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

**Indexes**:
- `idx_git_actions_project` on `project_path`

**Fields**:
- `id`: Auto-incrementing primary key
- `project_path`: Path to project (foreign key)
- `action_type`: Type of action (commit, push, pull, merge, etc.)
- `timestamp`: When action occurred
- `details`: Command details
- `files_changed`: Number of files changed (for commits)
- `insertions`: Number of insertions (for commits)
- `deletions`: Number of deletions (for commits)

### OpenCode Sessions Table (OpenCode-specific)

Stores OpenCode session data.

```sql
CREATE TABLE opencode_sessions (
    session_id TEXT PRIMARY KEY,
    project_path TEXT,
    title TEXT,
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    message_count INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT 1
)
```

**Fields**:
- `session_id`: OpenCode session identifier
- `project_path`: Path to project
- `title`: Session title
- `created_at`: Session creation time
- `updated_at`: Last update time
- `message_count`: Number of messages
- `is_active`: Whether session is currently active

## Common Queries

### Get all projects

```sql
SELECT * FROM projects ORDER BY last_chat_time DESC NULLS LAST;
```

### Get projects by status

```sql
SELECT * FROM projects WHERE git_status = 'dirty';
```

### Get recent chats for a project

```sql
SELECT * FROM chats 
WHERE project_path = ? 
ORDER BY timestamp DESC 
LIMIT 10;
```

### Get git actions for a project

```sql
SELECT * FROM git_actions 
WHERE project_path = ? 
ORDER BY timestamp DESC 
LIMIT 20;
```

### Get project statistics

```sql
SELECT 
    COUNT(*) as total_projects,
    SUM(CASE WHEN git_status = 'dirty' THEN 1 ELSE 0 END) as dirty,
    SUM(total_chats) as total_chats
FROM projects;
```

## Migration Guidelines

When modifying schema:

1. **Add new columns**: Use `ALTER TABLE ADD COLUMN` with default values
2. **Remove columns**: Not recommended - mark as deprecated instead
3. **Modify column types**: Requires data migration
4. **Add new tables**: Create in `initialize_schema()` with `IF NOT EXISTS`
5. **Add indexes**: Create after table creation

Example migration:

```python
def add_language_column(db):
    """Add language column to projects table."""
    db.execute("""
        ALTER TABLE projects 
        ADD COLUMN language TEXT
    """)
    # Update existing records
    db.execute("""
        UPDATE projects 
        SET language = 'Unknown' 
        WHERE language IS NULL
    """)
```

## Performance Considerations

- Use WAL mode for concurrent access (already enabled)
- Index frequently queried columns
- Use parameterized queries to prevent SQL injection
- Batch operations when possible
- Avoid `SELECT *` for large tables
- Use `LIMIT` for pagination
