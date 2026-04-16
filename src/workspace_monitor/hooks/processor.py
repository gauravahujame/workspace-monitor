#!/usr/bin/env python3
"""
Windsurf Hook Processor for Workspace Monitor
Processes various hook events and updates the dashboard database.
"""

import sys
import json
import os
import re
from pathlib import Path
from datetime import datetime
import sqlite3
from typing import Optional, Dict, Any

from ..core import WorkspaceDashboard, ChatEntry, GitAction


class HookProcessor:
    """Process Windsurf hook events and update dashboard."""

    def __init__(self) -> None:
        self.dashboard = WorkspaceDashboard()
        self.workspace_root = Path.home() / "workspace"

    def process_hook(self, hook_data: dict) -> None:
        """Process incoming hook data from Windsurf."""
        agent_action = hook_data.get("agent_action_name", "")

        handlers = {
            "post_cascade_response_with_transcript": self._handle_transcript,
            "post_cascade_response": self._handle_response,
            "pre_run_command": self._handle_pre_command,
            "post_run_command": self._handle_post_command,
            "pre_write_code": self._handle_pre_write,
            "post_write_code": self._handle_post_write,
        }

        handler = handlers.get(agent_action)
        if handler:
            try:
                handler(hook_data)
            except Exception as e:
                self._log_error(f"Error processing {agent_action}: {e}")

    def _get_project_path(self, file_path: Optional[str] = None, cwd: Optional[str] = None) -> Optional[Path]:
        """Determine project path from file path or working directory."""
        path_str = file_path or cwd or os.getcwd()
        path = Path(path_str).resolve()

        while path != path.parent:
            if (path / ".git").exists():
                return path
            path = path.parent

        try:
            rel_path = path.relative_to(self.workspace_root)
            project = self.workspace_root / rel_path.parts[0]
            if (project / ".git").exists():
                return project
        except Exception:
            pass

        return None

    def _handle_transcript(self, hook_data: dict) -> None:
        """Process post_cascade_response_with_transcript hook."""
        tool_info = hook_data.get("tool_info", {})
        transcript_path = tool_info.get("transcript_path")
        trajectory_id = hook_data.get("trajectory_id", "")

        if not transcript_path or not os.path.exists(transcript_path):
            return

        try:
            project_path, stats = self._parse_transcript(transcript_path)

            if project_path:
                entry = ChatEntry(
                    trajectory_id=trajectory_id,
                    project_path=str(project_path),
                    timestamp=datetime.now(),
                    message_count=stats.get("message_count", 0),
                    file_edits=stats.get("file_edits", 0),
                    commands_run=stats.get("commands_run", 0),
                    transcript_path=transcript_path,
                    summary=stats.get("summary", "")
                )

                self.dashboard.record_chat(entry)
                self._update_project_session(project_path, trajectory_id, active=True)

        except Exception as e:
            self._log_error(f"Error parsing transcript: {e}")

    def _handle_response(self, hook_data: dict) -> None:
        """Process post_cascade_response hook."""
        tool_info = hook_data.get("tool_info", {})
        response = tool_info.get("response", "")
        trajectory_id = hook_data.get("trajectory_id", "")

        project_path = self._extract_project_from_response(response)

        if project_path:
            file_edits = response.count("*Created file") + response.count("*Modified file")
            commands = response.count("```bash") + response.count("```shell")

            entry = ChatEntry(
                trajectory_id=trajectory_id,
                project_path=str(project_path),
                timestamp=datetime.now(),
                file_edits=file_edits,
                commands_run=commands,
                summary=self._extract_summary(response)
            )

            self.dashboard.record_chat(entry)

    def _handle_pre_command(self, hook_data: dict) -> None:
        """Process pre_run_command hook."""
        tool_info = hook_data.get("tool_info", {})
        command = tool_info.get("command_line", "")
        cwd = tool_info.get("cwd", "")

        git_action = self._parse_git_command(command)
        if git_action:
            project_path = self._get_project_path(cwd=cwd)
            if project_path:
                self._store_pending_action(project_path, git_action, command)

    def _handle_post_command(self, hook_data: dict) -> None:
        """Process post_run_command hook."""
        tool_info = hook_data.get("tool_info", {})
        command = tool_info.get("command_line", "")
        cwd = tool_info.get("cwd", "")

        git_action = self._parse_git_command(command)
        if git_action:
            project_path = self._get_project_path(cwd=cwd)
            if project_path:
                self._complete_git_action(project_path, git_action, command)

    def _handle_pre_write(self, hook_data: dict) -> None:
        """Process pre_write_code hook."""
        pass

    def _handle_post_write(self, hook_data: dict) -> None:
        """Process post_write_code hook."""
        tool_info = hook_data.get("tool_info", {})
        file_path = tool_info.get("file_path", "")

        project_path = self._get_project_path(file_path=file_path)
        if project_path:
            self._trigger_project_refresh(project_path)

    def _parse_transcript(self, transcript_path: str) -> tuple:
        """Parse Windsurf transcript file and extract stats."""
        stats: Dict[str, Any] = {
            "message_count": 0,
            "file_edits": 0,
            "commands_run": 0,
            "summary": ""
        }

        project_path = None
        messages = []

        try:
            with open(transcript_path, 'r') as f:
                for line in f:
                    try:
                        entry = json.loads(line.strip())
                        entry_type = entry.get("type", "")

                        if entry_type == "user_input":
                            stats["message_count"] += 1
                            user_input = entry.get("user_input", {})
                            user_response = user_input.get("user_response", "")
                            if user_response:
                                messages.append(user_response[:100])

                        elif entry_type == "code_action":
                            stats["file_edits"] += 1
                            code_action = entry.get("code_action", {})
                            path = code_action.get("path", "")
                            if path and not project_path:
                                project_path = self._get_project_path(file_path=path)

                        elif entry_type == "terminal_command":
                            stats["commands_run"] += 1
                            terminal = entry.get("terminal_command", {})
                            cwd = terminal.get("cwd", "")
                            if cwd and not project_path:
                                project_path = self._get_project_path(cwd=cwd)

                        elif entry_type == "planner_response":
                            planner = entry.get("planner_response", {})
                            response = planner.get("response", "")
                            if response:
                                if not project_path:
                                    project_path = self._extract_project_from_response(response)

                    except json.JSONDecodeError:
                        continue

            if messages:
                stats["summary"] = messages[0][:200]

        except Exception as e:
            self._log_error(f"Error reading transcript: {e}")

        return project_path, stats

    def _extract_project_from_response(self, response: str) -> Optional[Path]:
        """Extract project path from Cascade response text."""
        patterns = [
            r'`(/[^`]+/[^`]+)`',
            r'\*Created file `([^`]+)`',
            r'\*Modified file `([^`]+)`',
            r'path["\']?\s*:\s*["\']([^"\']+)["\']',
        ]

        for pattern in patterns:
            matches = re.findall(pattern, response)
            for match in matches:
                path = Path(match)
                if path.exists():
                    project = self._get_project_path(file_path=str(path))
                    if project:
                        return project

        return None

    def _extract_summary(self, response: str) -> str:
        """Extract a summary from the response."""
        lines = response.strip().split('\n')
        for line in lines:
            line = line.strip()
            if line and not line.startswith('#') and len(line) > 10:
                return line[:200]
        return ""

    def _parse_git_command(self, command: str) -> Optional[str]:
        """Parse git command and return action type."""
        if not command.startswith("git "):
            return None

        parts = command.split()
        if len(parts) < 2:
            return None

        subcommand = parts[1]

        action_map = {
            "commit": "commit", "push": "push", "pull": "pull",
            "fetch": "fetch", "merge": "merge", "rebase": "rebase",
            "checkout": "branch", "branch": "branch",
            "reset": "reset", "revert": "revert",
            "tag": "tag", "stash": "stash",
        }

        return action_map.get(subcommand)

    def _store_pending_action(self, project_path: Path, action_type: str, command: str) -> None:
        """Store a pending git action for completion tracking."""
        pending_file = self.dashboard.data_dir / ".pending_action"
        try:
            data = {
                "project_path": str(project_path),
                "action_type": action_type,
                "command": command,
                "timestamp": datetime.now().isoformat()
            }
            with open(pending_file, 'w') as f:
                json.dump(data, f)
        except:
            pass

    def _complete_git_action(self, project_path: Path, action_type: str, command: str) -> None:
        """Complete and record a git action."""
        action = GitAction(
            project_path=str(project_path),
            action_type=action_type,
            timestamp=datetime.now(),
            details=command
        )

        self.dashboard.record_git_action(action)

        pending_file = self.dashboard.data_dir / ".pending_action"
        if pending_file.exists():
            pending_file.unlink()

    def _update_project_session(self, project_path: Path, trajectory_id: str, active: bool = True) -> None:
        """Update project windsurf session status."""
        db_path = self.dashboard.db_path
        try:
            with sqlite3.connect(db_path) as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO windsurf_sessions
                    (trajectory_id, project_path, start_time, is_active)
                    VALUES (?, ?, ?, ?)
                """, (trajectory_id, str(project_path), datetime.now().isoformat(), active))

                conn.execute("""
                    UPDATE projects SET is_windsurf_open = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE path = ?
                """, (active, str(project_path)))
        except Exception as e:
            self._log_error(f"Error updating session: {e}")

    def _trigger_project_refresh(self, project_path: Path) -> None:
        """Trigger a background refresh of project info."""
        pass

    def _log_error(self, message: str) -> None:
        """Log error to file."""
        log_file = self.dashboard.data_dir / "hook_errors.log"
        timestamp = datetime.now().isoformat()
        with open(log_file, 'a') as f:
            f.write(f"[{timestamp}] {message}\n")


def main() -> None:
    """Main entry point - read JSON from stdin."""
    try:
        hook_data = json.load(sys.stdin)
        processor = HookProcessor()
        processor.process_hook(hook_data)
        sys.exit(0)

    except json.JSONDecodeError as e:
        print(f"Invalid JSON input: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error processing hook: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
