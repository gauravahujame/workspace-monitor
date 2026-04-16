#!/usr/bin/env python3
"""
Workspace Monitor CLI
Command-line interface for the workspace dashboard.
"""

import sys
import json
import subprocess
import platform
from pathlib import Path
from typing import Optional
from datetime import datetime

import click

from .core import WorkspaceDashboard, ProjectInfo, ChatEntry, GitAction


class Colors:
    """ANSI color codes for terminal output."""
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    END = '\033[0m'
    BOLD = '\033[1m'

    @classmethod
    def enabled(cls) -> bool:
        """Check if colors should be enabled."""
        return sys.stdout.isatty() and platform.system() != 'Windows'

    @classmethod
    def get(cls, color: str) -> str:
        """Get color code if enabled, else empty string."""
        return getattr(cls, color.upper(), '') if cls.enabled() else ''


def get_status_color(status: str) -> str:
    """Get ANSI color for status."""
    colors = {
        "clean": Colors.GREEN,
        "dirty": Colors.RED,
        "ahead": Colors.YELLOW,
        "behind": Colors.YELLOW,
        "diverged": Colors.RED,
    }
    return colors.get(status, Colors.END)


def format_status(project: ProjectInfo) -> str:
    """Format status string."""
    if project.git_status == "clean":
        return "✓ Clean"
    elif project.git_status == "dirty":
        return f"✕ {project.uncommitted_files} changes"
    elif project.git_status == "ahead":
        return f"↑ {project.commits_ahead} ahead"
    elif project.git_status == "behind":
        return f"↓ {project.commits_behind} behind"
    elif project.git_status == "diverged":
        return "⚠ Diverged"
    return project.git_status


def time_ago(dt: Optional[datetime]) -> str:
    """Convert datetime to time ago string."""
    from datetime import datetime

    if not dt:
        return "Never"

    diff = datetime.now() - dt

    if diff.days > 365:
        return f"{diff.days // 365}y ago"
    elif diff.days > 30:
        return f"{diff.days // 30}mo ago"
    elif diff.days > 0:
        return f"{diff.days}d ago"
    elif diff.seconds > 3600:
        return f"{diff.seconds // 3600}h ago"
    elif diff.seconds > 60:
        return f"{diff.seconds // 60}m ago"
    else:
        return "Just now"


@click.group()
@click.version_option(version="1.0.0", prog_name="wsd")
@click.option('--data-dir', type=click.Path(), help='Custom data directory')
@click.option('--workspace', type=click.Path(), help='Custom workspace root')
@click.pass_context
def cli(ctx: click.Context, data_dir: Optional[str], workspace: Optional[str]) -> None:
    """Workspace Monitor CLI - Dashboard for git repositories with Windsurf integration."""
    ctx.ensure_object(dict)
    ctx.obj['dashboard'] = WorkspaceDashboard(
        workspace_root=workspace,
        data_dir=data_dir
    )


@cli.command()
@click.option('--status', '-s', help='Filter by git status')
@click.option('--sort', default='last_commit_time',
              type=click.Choice(['name', 'status', 'last_commit_time', 'chats', 'language']),
              help='Sort field')
@click.option('--search', help='Search projects')
@click.option('--json', 'as_json', is_flag=True, help='Output as JSON')
@click.pass_context
def list(ctx: click.Context, status: Optional[str], sort: str,
         search: Optional[str], as_json: bool) -> None:
    """List all projects."""
    dashboard: WorkspaceDashboard = ctx.obj['dashboard']
    projects = dashboard.get_projects(
        status_filter=status,
        sort_by=sort,
        search=search
    )

    if not projects:
        click.echo(f"{Colors.YELLOW}No projects found{Colors.END}")
        return

    if as_json:
        click.echo(json.dumps([p.to_dict() for p in projects], indent=2))
        return

    # Table header
    click.echo(f"\n{Colors.BOLD}{'Project':<30} {'Status':<15} {'Branch':<20} {'Language':<12} {'Chats':<6} {'Last Commit':<15}{Colors.END}")
    click.echo("-" * 110)

    for p in projects:
        status_color = get_status_color(p.git_status)
        status_text = format_status(p)
        time_str = time_ago(p.last_commit_time)

        click.echo(f"{p.name:<30} {status_color}{status_text:<15}{Colors.END} "
                  f"{p.git_branch:<20} {p.language:<12} {p.total_chats:<6} {time_str:<15}")

    click.echo(f"\n{Colors.CYAN}Total: {len(projects)} projects{Colors.END}")


@cli.command()
@click.pass_context
def scan(ctx: click.Context) -> None:
    """Scan for new projects."""
    dashboard: WorkspaceDashboard = ctx.obj['dashboard']
    click.echo(f"{Colors.CYAN}Scanning for projects...{Colors.END}")
    projects = dashboard.scan_projects()
    click.echo(f"{Colors.GREEN}✓ Found {len(projects)} projects{Colors.END}")


@cli.command()
@click.argument('project')
@click.pass_context
def status(ctx: click.Context, project: str) -> None:
    """Show detailed status for a project."""
    dashboard: WorkspaceDashboard = ctx.obj['dashboard']

    # Resolve project path
    if not project.startswith("/"):
        project_path = str(dashboard.workspace_root / project)
    else:
        project_path = project

    projects = dashboard.get_projects()
    proj = next((p for p in projects if p.path == project_path), None)

    if not proj:
        click.echo(f"{Colors.RED}Project not found: {project}{Colors.END}")
        return

    click.echo(f"\n{Colors.BOLD}{Colors.HEADER}{proj.name}{Colors.END}")
    click.echo(f"  Path: {proj.path}")
    click.echo(f"  Language: {proj.language}")
    click.echo(f"  Branch: {proj.git_branch}")
    click.echo(f"  Status: {get_status_color(proj.git_status)}{proj.git_status}{Colors.END}")

    if proj.git_status == "dirty":
        click.echo(f"  Uncommitted files: {proj.uncommitted_files}")
    elif proj.git_status == "ahead":
        click.echo(f"  Commits ahead: {proj.commits_ahead}")
    elif proj.git_status == "behind":
        click.echo(f"  Commits behind: {proj.commits_behind}")

    click.echo(f"  Last commit: {proj.last_commit or 'N/A'}")
    click.echo(f"  Total chats: {proj.total_chats}")
    click.echo(f"  Windsurf active: {'Yes' if proj.is_windsurf_open else 'No'}")

    # Show recent chats
    chats = dashboard.get_chats(project_path=proj.path, limit=5)
    if chats:
        click.echo(f"\n{Colors.BOLD}Recent Chats:{Colors.END}")
        for chat in chats[:5]:
            click.echo(f"  • {chat.timestamp.strftime('%Y-%m-%d %H:%M')} - "
                      f"{chat.message_count} msgs, {chat.file_edits} edits")


@cli.command()
@click.option('--json', 'as_json', is_flag=True, help='Output as JSON')
@click.pass_context
def stats(ctx: click.Context, as_json: bool) -> None:
    """Show overall statistics."""
    dashboard: WorkspaceDashboard = ctx.obj['dashboard']
    stats = dashboard.get_stats()

    if as_json:
        click.echo(json.dumps(stats, indent=2))
        return

    click.echo(f"\n{Colors.BOLD}{Colors.HEADER}Workspace Statistics{Colors.END}\n")

    click.echo(f"  Total Projects: {Colors.GREEN}{stats['total_projects']}{Colors.END}")
    click.echo(f"  Active Sessions: {Colors.CYAN}{stats['active_sessions']}{Colors.END}")
    click.echo(f"  Chats Today: {Colors.YELLOW}{stats['chats_today']}{Colors.END}")
    click.echo(f"  Total Chats: {stats['total_chats']}")

    click.echo(f"\n{Colors.BOLD}Status Distribution:{Colors.END}")
    for status, count in sorted(stats.get('status_counts', {}).items(), key=lambda x: -x[1]):
        color = get_status_color(status)
        click.echo(f"  {color}{status:<12}{Colors.END}: {count}")

    click.echo(f"\n{Colors.BOLD}Languages:{Colors.END}")
    for lang, count in sorted(stats.get('languages', {}).items(), key=lambda x: -x[1])[:10]:
        click.echo(f"  {lang:<15}: {count}")


@cli.command()
@click.option('-n', '--limit', default=20, help='Number of chats to show')
@click.pass_context
def chats(ctx: click.Context, limit: int) -> None:
    """Show recent chats."""
    dashboard: WorkspaceDashboard = ctx.obj['dashboard']
    chats_list = dashboard.get_chats(limit=limit)

    if not chats_list:
        click.echo(f"{Colors.YELLOW}No chats recorded{Colors.END}")
        return

    click.echo(f"\n{Colors.BOLD}{Colors.HEADER}Recent Chats{Colors.END}\n")

    for chat in chats_list:
        project_name = Path(chat.project_path).name
        click.echo(f"  {Colors.CYAN}{chat.timestamp.strftime('%Y-%m-%d %H:%M')}{Colors.END} "
                  f"{Colors.BOLD}{project_name}{Colors.END}")
        click.echo(f"    Messages: {chat.message_count}, Edits: {chat.file_edits}, "
                  f"Commands: {chat.commands_run}")
        if chat.summary:
            click.echo(f"    Summary: {chat.summary[:80]}...")
        click.echo()


@cli.command()
@click.option('--host', default='127.0.0.1', help='Host to bind to')
@click.option('--port', '-p', default=8765, help='Port to bind to')
@click.option('--no-browser', is_flag=True, help='Do not open browser')
def server(host: str, port: int, no_browser: bool) -> None:
    """Start the web dashboard server."""
    try:
        from .web.server import run_server
        run_server(host=host, port=port, open_browser=not no_browser)
    except ImportError:
        click.echo(f"{Colors.RED}Error: Web dependencies not installed.{Colors.END}")
        click.echo("Install with: pip install workspace-monitor[web]")
        sys.exit(1)


@cli.command()
@click.option('-o', '--output', help='Output file path')
@click.pass_context
def export(ctx: click.Context, output: Optional[str]) -> None:
    """Export dashboard data to JSON."""
    dashboard: WorkspaceDashboard = ctx.obj['dashboard']
    output_path = dashboard.export_data(output)
    click.echo(f"{Colors.GREEN}✓ Exported to: {output_path}{Colors.END}")


@cli.command()
@click.argument('query')
@click.pass_context
def search(ctx: click.Context, query: str) -> None:
    """Search projects."""
    dashboard: WorkspaceDashboard = ctx.obj['dashboard']
    projects = dashboard.get_projects(search=query)

    if not projects:
        click.echo(f"{Colors.YELLOW}No projects matching '{query}'{Colors.END}")
        return

    click.echo(f"\n{Colors.BOLD}Found {len(projects)} projects matching '{query}':{Colors.END}\n")

    for p in projects:
        click.echo(f"  {Colors.CYAN}{p.name}{Colors.END} ({p.language}) - {p.git_status}")
        click.echo(f"    {p.path}")


@cli.command('git')
@click.argument('git_args', nargs=-1, required=True)
@click.pass_context
def git_command(ctx: click.Context, git_args: tuple) -> None:
    """Run git command across all projects."""
    dashboard: WorkspaceDashboard = ctx.obj['dashboard']
    projects = dashboard.get_projects()

    if not projects:
        click.echo(f"{Colors.YELLOW}No projects found{Colors.END}")
        return

    cmd = " ".join(git_args)
    click.echo(f"{Colors.CYAN}Running 'git {cmd}' across {len(projects)} projects...{Colors.END}\n")

    for p in projects:
        try:
            result = subprocess.run(
                ["git", "-C", p.path] + list(git_args),
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode == 0 and result.stdout.strip():
                click.echo(f"{Colors.BOLD}{p.name}:{Colors.END}")
                click.echo(result.stdout)
            elif result.returncode != 0:
                click.echo(f"{Colors.RED}{p.name}: Error{Colors.END}")
        except Exception as e:
            click.echo(f"{Colors.RED}{p.name}: {e}{Colors.END}")


@cli.command()
@click.argument('project')
def open_project(project: str) -> None:
    """Open project in Windsurf or VS Code."""
    if not project.startswith("/"):
        project_path = str(Path.home() / "workspace" / project)
    else:
        project_path = project

    # Try windsurf first
    for cmd in ['windsurf', 'code']:
        try:
            subprocess.run([cmd, project_path], check=False)
            return
        except FileNotFoundError:
            continue

    click.echo(f"{Colors.RED}Could not find windsurf or code command{Colors.END}")


@cli.command('todo')
def todos() -> None:
    """Show project todos (placeholder - scans for TODO files)."""
    click.echo(f"{Colors.YELLOW}Todo tracking not yet implemented{Colors.END}")


def main() -> None:
    """Main entry point."""
    from datetime import datetime  # Import here to avoid circular import
    cli()


if __name__ == "__main__":
    main()
