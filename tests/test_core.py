"""Tests for workspace_monitor.core module."""

import tempfile
import shutil
from pathlib import Path
from datetime import datetime
import pytest

from workspace_monitor.core import (
    WorkspaceDashboard,
    ProjectInfo,
    ChatEntry,
    GitAction
)


class TestProjectInfo:
    """Test ProjectInfo dataclass."""
    
    def test_basic_creation(self):
        """Test creating a ProjectInfo instance."""
        project = ProjectInfo(
            path="/home/user/workspace/test",
            name="test",
            git_branch="main"
        )
        
        assert project.path == "/home/user/workspace/test"
        assert project.name == "test"
        assert project.git_branch == "main"
        assert project.git_status == "clean"
    
    def test_to_dict(self):
        """Test converting ProjectInfo to dict."""
        now = datetime.now()
        project = ProjectInfo(
            path="/home/user/workspace/test",
            name="test",
            last_commit_time=now
        )
        
        data = project.to_dict()
        
        assert data["path"] == "/home/user/workspace/test"
        assert data["name"] == "test"
        assert data["last_commit_time"] == now.isoformat()


class TestWorkspaceDashboard:
    """Test WorkspaceDashboard class."""
    
    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for testing."""
        temp_path = tempfile.mkdtemp()
        yield Path(temp_path)
        shutil.rmtree(temp_path)
    
    @pytest.fixture
    def dashboard(self, temp_dir):
        """Create a test dashboard instance."""
        data_dir = temp_dir / "data"
        workspace = temp_dir / "workspace"
        workspace.mkdir()
        
        return WorkspaceDashboard(
            workspace_root=workspace,
            data_dir=data_dir
        )
    
    def test_initialization(self, dashboard, temp_dir):
        """Test dashboard initialization."""
        assert dashboard.workspace_root.exists()
        assert dashboard.data_dir.exists()
        assert dashboard.db_path.exists()
    
    def test_scan_empty_workspace(self, dashboard):
        """Test scanning an empty workspace."""
        projects = dashboard.scan_projects()
        assert projects == []
    
    def test_record_chat(self, dashboard):
        """Test recording a chat entry."""
        entry = ChatEntry(
            trajectory_id="test-123",
            project_path="/test/project",
            timestamp=datetime.now(),
            message_count=5,
            file_edits=3,
            summary="Test chat"
        )
        
        dashboard.record_chat(entry)
        
        chats = dashboard.get_chats()
        assert len(chats) == 1
        assert chats[0].trajectory_id == "test-123"
        assert chats[0].message_count == 5
    
    def test_get_stats_empty(self, dashboard):
        """Test getting stats with no data."""
        stats = dashboard.get_stats()
        
        assert stats["total_projects"] == 0
        assert stats["total_chats"] == 0
        assert stats["active_sessions"] == 0
        assert stats["chats_today"] == 0
    
    def test_export_data(self, dashboard, temp_dir):
        """Test exporting data to JSON."""
        output_path = temp_dir / "export.json"
        result = dashboard.export_data(output_path)
        
        assert Path(result).exists()
        assert Path(result).read_text()


class TestChatEntry:
    """Test ChatEntry dataclass."""
    
    def test_to_dict(self):
        """Test converting ChatEntry to dict."""
        now = datetime.now()
        entry = ChatEntry(
            trajectory_id="test-123",
            project_path="/test/project",
            timestamp=now,
            message_count=10
        )
        
        data = entry.to_dict()
        
        assert data["trajectory_id"] == "test-123"
        assert data["timestamp"] == now.isoformat()
        assert data["message_count"] == 10


class TestGitAction:
    """Test GitAction dataclass."""
    
    def test_to_dict(self):
        """Test converting GitAction to dict."""
        now = datetime.now()
        action = GitAction(
            project_path="/test/project",
            action_type="commit",
            timestamp=now,
            details="Initial commit",
            files_changed=5
        )
        
        data = action.to_dict()
        
        assert data["action_type"] == "commit"
        assert data["files_changed"] == 5
