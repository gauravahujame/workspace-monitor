"""
Workspace Monitor - System-wide dashboard for git repositories with Windsurf integration.
"""

__version__ = "1.0.0"
__author__ = "Gaurav Ahuja"
__email__ = "your.email@example.com"

from .core import WorkspaceDashboard, ProjectInfo, ChatEntry, GitAction

__all__ = ["WorkspaceDashboard", "ProjectInfo", "ChatEntry", "GitAction"]
