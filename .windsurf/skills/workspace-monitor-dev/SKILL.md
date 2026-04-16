---
name: workspace-monitor-dev
description: Development of workspace-monitor cross-IDE dashboard system. TRIGGERS - workspace-monitor, wsd, dashboard, IDE integration, Windsurf, OpenCode.
allowed-tools: Read, Edit, Bash
---

# Workspace Monitor Development

> **Self-Evolving Skill**: This skill improves through use. If instructions are wrong, parameters drifted, or a workaround was needed — fix this file immediately, don't defer. Only update for real, reproducible issues.

## When to Use This Skill

Use this skill when:
- Adding new features to workspace-monitor
- Fixing bugs in the core system
- Adding support for new IDEs
- Modifying database schema
- Updating CLI commands
- Working on web dashboard
- Integrating with Windsurf or OpenCode
- Setting up development environment

## Architecture

| Component | Location | Purpose |
|-----------|----------|---------|
| **Core** | `src/workspace_monitor/core.py` | Database, project scanning, git analysis |
| **CLI** | `src/workspace_monitor/cli.py` | Command-line interface (wsd) |
| **Web Server** | `src/workspace_monitor/web/server.py` | FastAPI/Flask dashboard |
| **Hooks** | `src/workspace_monitor/hooks/processor.py` | Windsurf hook integration |
| **OpenCode Plugin** | `opencode-plugin/workspace-monitor.ts` | TypeScript plugin for OpenCode |
| **Database** | `~/.workspace-monitor/dashboard.db` (Linux) or `~/Library/Application Support/workspace-monitor/dashboard.db` (macOS) | SQLite data store |

---

## 1. Development Environment Setup

```bash
# Install UV if not present
curl -LsSf https://astral.sh/uv/install.sh | sh

# Clone and install
git clone https://github.com/gauravahujame/workspace-monitor.git
cd workspace-monitor
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
uv pip install -e ".[dev,web]"
```

---

## 2. Run Tests

```bash
source .venv/bin/activate
pytest
```

---

## 3. Add CLI Command

Add to `src/workspace_monitor/cli.py`:

```python
@cli.command()
@click.option('--option', default='value', help='Description')
def mycommand(option):
    """Command description."""
    pass
```

---

## 4. Add API Endpoint

Add to `src/workspace_monitor/web/server.py`:

```python
@app.get("/api/endpoint")
def endpoint():
    return {"data": "response"}
```

---

## 5. Modify Database Schema

```bash
# 1. Update initialize_schema() in core.py
# 2. Add migration logic if needed
# 3. Document changes in AGENTS.md
# 4. Ensure backward compatibility
```

---

## 6. Add IDE Support

To add support for a new IDE (e.g., Cursor):

```bash
# 1. Create adapter in src/workspace_monitor/ide_adapters/
# 2. Implement IDEAdapter interface
# 3. Write to same SQLite database for unified tracking
# 4. Update docs/IDE_INTEGRATION_ANALYSIS.md
# 5. Add installation instructions to README.md
```

---

## 7. Code Quality Checks

```bash
# Format with black
black src/

# Lint with ruff
ruff src/

# Type check with mypy
mypy src/workspace_monitor
```

---

## 8. Platform-Specific Testing

```bash
# macOS
export PLATFORM="darwin"
# Test data directory: ~/Library/Application Support/workspace-monitor/

# Linux
export PLATFORM="linux"
# Test data directory: ~/.workspace-monitor/
```

---

## 9. Debug Hook Issues

```bash
# Check Windsurf hooks
cat ~/.codeium/windsurf/hooks.json

# Test hook processor
~/.workspace-monitor/venv/bin/python -m workspace_monitor.hooks.processor

# Check logs
cat ~/.workspace-monitor/hook_errors.log  # Linux
cat ~/Library/Application\ Support/workspace-monitor/hook_errors.log  # macOS
```

---

## 10. Release Preparation

```bash
# 1. Run all tests
pytest

# 2. Check type hints
mypy src/workspace_monitor

# 3. Format code
black src/

# 4. Lint
ruff src/

# 5. Update version in pyproject.toml

# 6. Update CHANGELOG.md

# 7. Test one-click installer
./install.sh

# 8. Test Windsurf hooks

# 9. Test OpenCode plugin (if changed)
```

---

## Reference

- [Database Schema](./references/database-schema.md) - Complete table definitions and relationships
- [Code Patterns](./references/code-patterns.md) - Common patterns for database queries, git analysis, hooks
- [IDE Integration Guide](./references/ide-integration.md) - How to add support for new IDEs
- [Architecture](./references/architecture.md) - Detailed system architecture

**Project docs**: [AGENTS.md](../../../AGENTS.md), [README.md](../../../README.md)

---

## Troubleshooting

| Issue | Cause | Solution |
|-------|-------|----------|
| Database locked | WAL mode not enabled, long transactions | Ensure WAL mode in `initialize_schema()`, check for long-running queries |
| Git status slow | Deep scanning, no caching | Limit `max_depth`, cache results with short TTL, skip excluded dirs |
| Hook not firing | Wrong path, not executable | Use absolute path to venv python, check file permissions |
| Type errors | Missing type hints | Run mypy, add type hints to all functions |
| UV not found | Not installed | Run `curl -LsSf https://astral.sh/uv/install.sh | sh` |
| Import errors | Virtual environment not activated | Run `source .venv/bin/activate` |
| Port 8765 in use | Another instance running | Kill existing process or use `wsd server --port 8766` |
| Projects not showing | Wrong workspace path | Check `WORKSPACE_ROOT` env var or pass `--workspace` flag |

---

## Post-Execution Reflection

After this skill completes, check before closing:

1. **Did the command succeed?** — If not, fix the instruction or error table that caused the failure.
2. **Did parameters or output change?** — If the underlying tool's interface drifted, update Usage examples and Parameters table to match.
3. **Was a workaround needed?** — If you had to improvise (different flags, extra steps), update this SKILL.md so the next invocation doesn't need the same workaround.

Only update if the issue is real and reproducible — not speculative.
