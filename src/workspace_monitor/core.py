#!/usr/bin/env python3
"""
Workspace Monitor Core
Monitors all projects under ~/workspace and maintains a real-time dashboard.
"""

import os
import json
import sqlite3
import subprocess
import platform
from pathlib import Path
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict, field
from typing import List, Dict, Optional, Any, Union
from threading import Lock


@dataclass
class ProjectInfo:
    path: str
    name: str
    git_branch: str = ""
    git_status: str = "clean"  # clean, dirty, ahead, behind, diverged
    last_commit: str = ""
    last_commit_time: Optional[datetime] = None
    commits_ahead: int = 0
    commits_behind: int = 0
    uncommitted_files: int = 0
    is_windsurf_open: bool = False
    total_chats: int = 0
    last_chat_time: Optional[datetime] = None
    todos_count: int = 0
    todos_done: int = 0
    tags: List[str] = field(default_factory=list)
    language: str = ""

    def __post_init__(self) -> None:
        if isinstance(self.last_commit_time, str):
            self.last_commit_time = datetime.fromisoformat(self.last_commit_time)
        if isinstance(self.last_chat_time, str):
            self.last_chat_time = datetime.fromisoformat(self.last_chat_time)

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data['last_commit_time'] = self.last_commit_time.isoformat() if self.last_commit_time else None
        data['last_chat_time'] = self.last_chat_time.isoformat() if self.last_chat_time else None
        return data


@dataclass
class ChatEntry:
    trajectory_id: str
    project_path: str
    timestamp: datetime
    message_count: int = 0
    file_edits: int = 0
    commands_run: int = 0
    transcript_path: Optional[str] = None
    summary: str = ""

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        return data


@dataclass
class GitAction:
    project_path: str
    action_type: str  # commit, push, pull, merge, branch
    timestamp: datetime
    details: str = ""
    files_changed: int = 0
    insertions: int = 0
    deletions: int = 0

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        return data


class WorkspaceDashboard:
    """Main dashboard class for workspace monitoring."""

    def __init__(self, workspace_root: Optional[Union[str, Path]] = None,
                 data_dir: Optional[Union[str, Path]] = None) -> None:
        """
        Initialize the workspace dashboard.

        Args:
            workspace_root: Root directory to scan for projects (default: ~/workspace)
            data_dir: Directory to store dashboard data (default: ~/.workspace-monitor)
        """
        self.workspace_root = Path(workspace_root) if workspace_root else Path.home() / "workspace"

        if data_dir:
            self.data_dir = Path(data_dir)
        else:
            # Use platform-appropriate config directory
            if platform.system() == "Darwin":  # macOS
                self.data_dir = Path.home() / "Library" / "Application Support" / "workspace-monitor"
            else:  # Linux and others
                self.data_dir = Path.home() / ".workspace-monitor"

        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.data_dir / "dashboard.db"
        self.lock = Lock()
        self._init_db()

    def _init_db(self) -> None:
        """Initialize SQLite database with required tables."""
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS projects (
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
                );

                CREATE TABLE IF NOT EXISTS chats (
                    trajectory_id TEXT PRIMARY KEY,
                    project_path TEXT,
                    timestamp TIMESTAMP,
                    message_count INTEGER DEFAULT 0,
                    file_edits INTEGER DEFAULT 0,
                    commands_run INTEGER DEFAULT 0,
                    transcript_path TEXT,
                    summary TEXT,
                    FOREIGN KEY (project_path) REFERENCES projects(path)
                );

                CREATE TABLE IF NOT EXISTS git_actions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_path TEXT,
                    action_type TEXT,
                    timestamp TIMESTAMP,
                    details TEXT,
                    files_changed INTEGER DEFAULT 0,
                    insertions INTEGER DEFAULT 0,
                    deletions INTEGER DEFAULT 0,
                    FOREIGN KEY (project_path) REFERENCES projects(path)
                );

                CREATE TABLE IF NOT EXISTS windsurf_sessions (
                    trajectory_id TEXT PRIMARY KEY,
                    project_path TEXT,
                    start_time TIMESTAMP,
                    end_time TIMESTAMP,
                    is_active BOOLEAN DEFAULT 1,
                    FOREIGN KEY (project_path) REFERENCES projects(path)
                );

                CREATE INDEX IF NOT EXISTS idx_projects_status ON projects(git_status);
                CREATE INDEX IF NOT EXISTS idx_chats_project ON chats(project_path);
                CREATE INDEX IF NOT EXISTS idx_chats_time ON chats(timestamp);
                CREATE INDEX IF NOT EXISTS idx_git_actions_project ON git_actions(project_path);
                CREATE INDEX IF NOT EXISTS idx_git_actions_time ON git_actions(timestamp);
            """)

    def scan_projects(self, max_depth: int = 3) -> List[ProjectInfo]:
        """
        Scan workspace for all git repositories.

        Args:
            max_depth: Maximum directory depth to search

        Returns:
            List of ProjectInfo objects
        """
        projects: List[ProjectInfo] = []

        if not self.workspace_root.exists():
            return projects

        try:
            result = subprocess.run(
                ["find", str(self.workspace_root), "-maxdepth", str(max_depth),
                 "-type", "d", "-name", ".git"],
                capture_output=True,
                text=True,
                timeout=60
            )

            for line in result.stdout.strip().split("\n"):
                if not line:
                    continue

                git_dir = Path(line)
                project_path = git_dir.parent

                project_info = self._analyze_project(project_path)
                if project_info:
                    projects.append(project_info)
                    self._save_project(project_info)

        except subprocess.TimeoutExpired:
            print("Warning: Project scan timed out")
        except Exception as e:
            print(f"Error scanning projects: {e}")

        return projects

    def _analyze_project(self, path: Path) -> Optional[ProjectInfo]:
        """Analyze a single project and return its info."""
        if not (path / ".git").exists():
            return None

        name = path.name
        info = ProjectInfo(path=str(path), name=name)

        # Detect primary language
        info.language = self._detect_language(path)

        # Get git info
        try:
            # Current branch
            result = subprocess.run(
                ["git", "-C", str(path), "branch", "--show-current"],
                capture_output=True,
                text=True,
                timeout=5
            )
            info.git_branch = result.stdout.strip()

            # Last commit
            result = subprocess.run(
                ["git", "-C", str(path), "log", "-1", "--format=%H|%ci|%s"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0 and result.stdout.strip():
                parts = result.stdout.strip().split("|", 2)
                if len(parts) >= 2:
                    info.last_commit = parts[2] if len(parts) > 2 else ""
                    info.last_commit_time = datetime.fromisoformat(
                        parts[1].replace(" ", "T").replace("Z", "+00:00")
                    )

            # Check status
            result = subprocess.run(
                ["git", "-C", str(path), "status", "--porcelain"],
                capture_output=True,
                text=True,
                timeout=5
            )
            uncommitted = len([l for l in result.stdout.strip().split("\n") if l.strip()])
            info.uncommitted_files = uncommitted

            # Check ahead/behind
            result = subprocess.run(
                ["git", "-C", str(path), "rev-list", "--left-right", "--count",
                 f"HEAD...origin/{info.git_branch}"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                counts = result.stdout.strip().split("\t")
                if len(counts) == 2:
                    info.commits_behind = int(counts[1])
                    info.commits_ahead = int(counts[0])

            # Determine status
            if info.commits_ahead > 0 and info.commits_behind > 0:
                info.git_status = "diverged"
            elif info.commits_ahead > 0:
                info.git_status = "ahead"
            elif info.commits_behind > 0:
                info.git_status = "behind"
            elif uncommitted > 0:
                info.git_status = "dirty"
            else:
                info.git_status = "clean"

        except Exception as e:
            pass  # Git commands may fail for various reasons

        # Check for windsurf/cascade sessions
        info.is_windsurf_open = self._check_windsurf_session(path)

        # Load chat count from db
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT COUNT(*), MAX(timestamp) FROM chats WHERE project_path = ?",
                (str(path),)
            )
            row = cursor.fetchone()
            if row:
                info.total_chats = row[0] or 0
                if row[1]:
                    info.last_chat_time = datetime.fromisoformat(row[1])

        return info

    def _detect_language(self, path: Path) -> str:
        """Detect primary language of project."""
        language_files = {
            "Python": ["requirements.txt", "setup.py", "pyproject.toml", "Pipfile"],
            "JavaScript": ["package.json", "yarn.lock", "pnpm-lock.yaml"],
            "TypeScript": ["tsconfig.json"],
            "Go": ["go.mod", "go.sum"],
            "Rust": ["Cargo.toml", "Cargo.lock"],
            "Java": ["pom.xml", "build.gradle", "gradlew"],
            "Ruby": ["Gemfile", "Gemfile.lock"],
            "PHP": ["composer.json", "composer.lock"],
            "Docker": ["Dockerfile", "docker-compose.yml", "compose.yaml"],
        }

        for lang, files in language_files.items():
            for file in files:
                if (path / file).exists():
                    return lang

        # Check file extensions
        ext_counts: Dict[str, int] = {}
        try:
            for entry in path.iterdir():
                if entry.is_file():
                    ext = entry.suffix.lower()
                    ext_counts[ext] = ext_counts.get(ext, 0) + 1

            ext_to_lang = {
                ".py": "Python",
                ".js": "JavaScript",
                ".ts": "TypeScript",
                ".go": "Go",
                ".rs": "Rust",
                ".java": "Java",
                ".rb": "Ruby",
                ".php": "PHP",
                ".cpp": "C++",
                ".c": "C",
                ".h": "C/C++",
            }

            for ext, count in sorted(ext_counts.items(), key=lambda x: -x[1]):
                if ext in ext_to_lang:
                    return ext_to_lang[ext]
        except:
            pass

        return "Unknown"

    def _check_windsurf_session(self, path: Path) -> bool:
        """Check if Windsurf has an active session for this project."""
        transcripts_dir = Path.home() / ".windsurf" / "transcripts"
        if not transcripts_dir.exists():
            return False

        try:
            cutoff = datetime.now() - timedelta(hours=1)
            for transcript_file in transcripts_dir.glob("*.jsonl"):
                if transcript_file.stat().st_mtime > cutoff.timestamp():
                    try:
                        with open(transcript_file, 'r') as f:
                            first_line = f.readline()
                            if str(path) in first_line:
                                return True
                    except:
                        pass
        except:
            pass

        return False

    def _save_project(self, project: ProjectInfo) -> None:
        """Save project info to database."""
        with self.lock:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO projects (
                        path, name, git_branch, git_status, last_commit, last_commit_time,
                        commits_ahead, commits_behind, uncommitted_files, is_windsurf_open,
                        total_chats, last_chat_time, todos_count, todos_done, tags, language
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    project.path, project.name, project.git_branch, project.git_status,
                    project.last_commit, project.last_commit_time,
                    project.commits_ahead, project.commits_behind, project.uncommitted_files,
                    project.is_windsurf_open, project.total_chats, project.last_chat_time,
                    project.todos_count, project.todos_done, json.dumps(project.tags),
                    project.language
                ))

    def record_chat(self, entry: ChatEntry) -> None:
        """Record a chat session."""
        with self.lock:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO chats (
                        trajectory_id, project_path, timestamp, message_count,
                        file_edits, commands_run, transcript_path, summary
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    entry.trajectory_id, entry.project_path, entry.timestamp,
                    entry.message_count, entry.file_edits, entry.commands_run,
                    entry.transcript_path, entry.summary
                ))

                conn.execute("""
                    UPDATE projects SET
                        total_chats = (SELECT COUNT(*) FROM chats WHERE project_path = ?),
                        last_chat_time = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE path = ?
                """, (entry.project_path, entry.timestamp, entry.project_path))

    def record_git_action(self, action: GitAction) -> None:
        """Record a git action."""
        with self.lock:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT INTO git_actions (
                        project_path, action_type, timestamp, details,
                        files_changed, insertions, deletions
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    action.project_path, action.action_type, action.timestamp,
                    action.details, action.files_changed, action.insertions, action.deletions
                ))

    def get_projects(self, status_filter: Optional[str] = None,
                     sort_by: str = "last_commit_time",
                     search: Optional[str] = None) -> List[ProjectInfo]:
        """Get all projects with optional filtering."""
        with sqlite3.connect(self.db_path) as conn:
            query = "SELECT * FROM projects WHERE 1=1"
            params: List[Any] = []

            if status_filter:
                query += " AND git_status = ?"
                params.append(status_filter)

            if search:
                query += " AND (name LIKE ? OR path LIKE ? OR language LIKE ?)"
                search_pattern = f"%{search}%"
                params.extend([search_pattern, search_pattern, search_pattern])

            sort_column = {
                "name": "name",
                "status": "git_status",
                "last_commit": "last_commit_time",
                "chats": "total_chats",
                "language": "language",
            }.get(sort_by, "last_commit_time")

            query += f" ORDER BY {sort_column} DESC NULLS LAST"

            cursor = conn.execute(query, params)
            rows = cursor.fetchall()

            projects = []
            for row in rows:
                project = ProjectInfo(
                    path=row[0],
                    name=row[1],
                    git_branch=row[2],
                    git_status=row[3],
                    last_commit=row[4],
                    last_commit_time=row[5],
                    commits_ahead=row[6],
                    commits_behind=row[7],
                    uncommitted_files=row[8],
                    is_windsurf_open=bool(row[9]),
                    total_chats=row[10],
                    last_chat_time=row[11],
                    todos_count=row[12],
                    todos_done=row[13],
                    tags=json.loads(row[14]) if row[14] else [],
                    language=row[15]
                )
                projects.append(project)

            return projects

    def get_chats(self, project_path: Optional[str] = None,
                  limit: int = 100) -> List[ChatEntry]:
        """Get chat history."""
        with sqlite3.connect(self.db_path) as conn:
            query = "SELECT * FROM chats"
            params: List[Any] = []

            if project_path:
                query += " WHERE project_path = ?"
                params.append(project_path)

            query += " ORDER BY timestamp DESC LIMIT ?"
            params.append(limit)

            cursor = conn.execute(query, params)
            rows = cursor.fetchall()

            chats = []
            for row in rows:
                chat = ChatEntry(
                    trajectory_id=row[0],
                    project_path=row[1],
                    timestamp=datetime.fromisoformat(row[2]),
                    message_count=row[3],
                    file_edits=row[4],
                    commands_run=row[5],
                    transcript_path=row[6],
                    summary=row[7]
                )
                chats.append(chat)

            return chats

    def get_git_actions(self, project_path: Optional[str] = None,
                        action_type: Optional[str] = None,
                        limit: int = 100) -> List[GitAction]:
        """Get git action history."""
        with sqlite3.connect(self.db_path) as conn:
            query = "SELECT * FROM git_actions WHERE 1=1"
            params: List[Any] = []

            if project_path:
                query += " AND project_path = ?"
                params.append(project_path)

            if action_type:
                query += " AND action_type = ?"
                params.append(action_type)

            query += " ORDER BY timestamp DESC LIMIT ?"
            params.append(limit)

            cursor = conn.execute(query, params)
            rows = cursor.fetchall()

            actions = []
            for row in rows:
                action = GitAction(
                    project_path=row[1],
                    action_type=row[2],
                    timestamp=datetime.fromisoformat(row[3]),
                    details=row[4],
                    files_changed=row[5],
                    insertions=row[6],
                    deletions=row[7]
                )
                actions.append(action)

            return actions

    def get_stats(self) -> Dict[str, Any]:
        """Get dashboard statistics."""
        with sqlite3.connect(self.db_path) as conn:
            stats: Dict[str, Any] = {}

            # Project counts by status
            cursor = conn.execute("""
                SELECT git_status, COUNT(*) FROM projects GROUP BY git_status
            """)
            stats['status_counts'] = dict(cursor.fetchall())

            # Total projects
            cursor = conn.execute("SELECT COUNT(*) FROM projects")
            stats['total_projects'] = cursor.fetchone()[0]

            # Active windsurf sessions
            cursor = conn.execute("SELECT COUNT(*) FROM projects WHERE is_windsurf_open = 1")
            stats['active_sessions'] = cursor.fetchone()[0]

            # Total chats today
            today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            cursor = conn.execute(
                "SELECT COUNT(*) FROM chats WHERE timestamp >= ?",
                (today.isoformat(),)
            )
            stats['chats_today'] = cursor.fetchone()[0]

            # Total chats
            cursor = conn.execute("SELECT COUNT(*) FROM chats")
            stats['total_chats'] = cursor.fetchone()[0]

            # Language distribution
            cursor = conn.execute("""
                SELECT language, COUNT(*) FROM projects
                WHERE language != 'Unknown'
                GROUP BY language ORDER BY COUNT(*) DESC
            """)
            stats['languages'] = dict(cursor.fetchall())

            return stats

    def export_data(self, output_path: Optional[Union[str, Path]] = None) -> str:
        """Export all dashboard data to JSON."""
        if output_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = self.data_dir / f"export_{timestamp}.json"
        else:
            output_path = Path(output_path)

        data = {
            "exported_at": datetime.now().isoformat(),
            "projects": [p.to_dict() for p in self.get_projects()],
            "chats": [c.to_dict() for c in self.get_chats(limit=10000)],
            "stats": self.get_stats()
        }

        with open(output_path, 'w') as f:
            json.dump(data, f, indent=2)

        return str(output_path)
