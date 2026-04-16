"""
Workspace Monitor Web Server
Provides a web interface for viewing and managing workspace projects.
"""

import sys
import json
import asyncio
import threading
import webbrowser
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
import sqlite3

try:
    from fastapi import FastAPI, Query, WebSocket, WebSocketDisconnect
    from fastapi.staticfiles import StaticFiles
    from fastapi.responses import HTMLResponse, JSONResponse
    from fastapi.middleware.cors import CORSMiddleware
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    try:
        from flask import Flask, jsonify, request, Response
        USE_FASTAPI = False
    except ImportError:
        raise ImportError("Neither FastAPI nor Flask is installed. "
                         "Install with: pip install fastapi uvicorn python-multipart")

from ..core import WorkspaceDashboard, ProjectInfo


class DashboardServer:
    """Web dashboard server for workspace monitor."""

    def __init__(self, host: str = "0.0.0.0", port: int = 8765,
                 dashboard: Optional[WorkspaceDashboard] = None) -> None:
        self.host = host
        self.port = port
        self.dashboard = dashboard or WorkspaceDashboard()
        self.app = self._create_app()
        self.websocket_clients: set = set() if USE_FASTAPI else set()
        self._setup_routes()

        # Start background scanner
        self.scanner_thread = threading.Thread(target=self._background_scanner, daemon=True)
        self.scanner_thread.start()

    def _create_app(self) -> Any:
        """Create the web application."""
        if USE_FASTAPI:
            app = FastAPI(title="Workspace Monitor", version="1.0.0")

            app.add_middleware(
                CORSMiddleware,
                allow_origins=["*"],
                allow_credentials=True,
                allow_methods=["*"],
                allow_headers=["*"],
            )

            return app
        else:
            app = Flask(__name__)
            return app

    def _setup_routes(self) -> None:
        """Setup URL routes."""
        if USE_FASTAPI:
            self._setup_fastapi_routes()
        else:
            self._setup_flask_routes()

    def _setup_fastapi_routes(self) -> None:
        """Setup FastAPI routes."""

        @self.app.get("/", response_class=HTMLResponse)
        async def root() -> str:
            return self._get_dashboard_html()

        @self.app.get("/api/projects")
        async def api_projects(
            status: Optional[str] = Query(None),
            sort: str = Query("last_commit_time"),
            search: Optional[str] = Query(None)
        ) -> JSONResponse:
            projects = self.dashboard.get_projects(
                status_filter=status,
                sort_by=sort,
                search=search
            )
            return JSONResponse(content=[p.to_dict() for p in projects])

        @self.app.get("/api/projects/{project_path:path}")
        async def api_project_detail(project_path: str) -> JSONResponse:
            project_path = project_path.replace("%20", " ")
            full_path = str(self.dashboard.workspace_root / project_path)

            projects = self.dashboard.get_projects()
            project = next((p for p in projects if p.path == full_path), None)

            if not project:
                return JSONResponse(content={"error": "Project not found"}, status_code=404)

            chats = self.dashboard.get_chats(project_path=full_path, limit=50)
            git_actions = self.dashboard.get_git_actions(project_path=full_path, limit=50)

            return JSONResponse(content={
                "project": project.to_dict(),
                "chats": [c.to_dict() for c in chats],
                "git_actions": [a.to_dict() for a in git_actions]
            })

        @self.app.get("/api/stats")
        async def api_stats() -> JSONResponse:
            stats = self.dashboard.get_stats()
            return JSONResponse(content=stats)

        @self.app.get("/api/chats")
        async def api_chats(limit: int = Query(100)) -> JSONResponse:
            chats = self.dashboard.get_chats(limit=limit)
            return JSONResponse(content=[c.to_dict() for c in chats])

        @self.app.get("/api/activity")
        async def api_activity(days: int = Query(7)) -> JSONResponse:
            activity = self._get_activity_timeline(days)
            return JSONResponse(content=activity)

        @self.app.post("/api/refresh")
        async def api_refresh() -> JSONResponse:
            self.dashboard.scan_projects()
            await self._broadcast_update()
            return JSONResponse(content={"status": "ok"})

        @self.app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket) -> None:
            await websocket.accept()
            self.websocket_clients.add(websocket)
            try:
                while True:
                    await asyncio.sleep(5)
                    stats = self.dashboard.get_stats()
                    await websocket.send_json({
                        "type": "stats_update",
                        "data": stats
                    })
            except WebSocketDisconnect:
                self.websocket_clients.discard(websocket)

    def _setup_flask_routes(self) -> None:
        """Setup Flask routes."""

        @self.app.route("/")
        def root() -> str:
            return self._get_dashboard_html()

        @self.app.route("/api/projects")
        def api_projects() -> Any:
            status = request.args.get("status")
            sort = request.args.get("sort", "last_commit_time")
            search = request.args.get("search")

            projects = self.dashboard.get_projects(
                status_filter=status,
                sort_by=sort,
                search=search
            )
            return jsonify([p.to_dict() for p in projects])

        @self.app.route("/api/projects/<path:project_path>")
        def api_project_detail(project_path: str) -> Any:
            full_path = str(self.dashboard.workspace_root / project_path)

            projects = self.dashboard.get_projects()
            project = next((p for p in projects if p.path == full_path), None)

            if not project:
                return jsonify({"error": "Project not found"}), 404

            chats = self.dashboard.get_chats(project_path=full_path, limit=50)
            git_actions = self.dashboard.get_git_actions(project_path=full_path, limit=50)

            return jsonify({
                "project": project.to_dict(),
                "chats": [c.to_dict() for c in chats],
                "git_actions": [a.to_dict() for a in git_actions]
            })

        @self.app.route("/api/stats")
        def api_stats() -> Any:
            stats = self.dashboard.get_stats()
            return jsonify(stats)

        @self.app.route("/api/chats")
        def api_chats() -> Any:
            limit = request.args.get("limit", 100, type=int)
            chats = self.dashboard.get_chats(limit=limit)
            return jsonify([c.to_dict() for c in chats])

        @self.app.route("/api/activity")
        def api_activity() -> Any:
            days = request.args.get("days", 7, type=int)
            activity = self._get_activity_timeline(days)
            return jsonify(activity)

        @self.app.route("/api/refresh", methods=["POST"])
        def api_refresh() -> Any:
            self.dashboard.scan_projects()
            return jsonify({"status": "ok"})

    def _get_activity_timeline(self, days: int = 7) -> List[Dict[str, Any]]:
        """Get activity timeline for the last N days."""
        db_path = self.dashboard.db_path

        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)

        timeline = []

        with sqlite3.connect(db_path) as conn:
            cursor = conn.execute("""
                SELECT DATE(timestamp) as date, COUNT(*) as count
                FROM chats
                WHERE timestamp >= ?
                GROUP BY DATE(timestamp)
                ORDER BY date
            """, (start_date.isoformat(),))

            chat_counts = {row[0]: row[1] for row in cursor.fetchall()}

            cursor = conn.execute("""
                SELECT DATE(timestamp) as date, action_type, COUNT(*) as count
                FROM git_actions
                WHERE timestamp >= ?
                GROUP BY DATE(timestamp), action_type
                ORDER BY date
            """, (start_date.isoformat(),))

            git_counts: Dict[str, Dict[str, int]] = {}
            for row in cursor.fetchall():
                date, action, count = row
                if date not in git_counts:
                    git_counts[date] = {}
                git_counts[date][action] = count

            current = start_date
            while current <= end_date:
                date_str = current.strftime("%Y-%m-%d")
                timeline.append({
                    "date": date_str,
                    "chats": chat_counts.get(date_str, 0),
                    "git_actions": git_counts.get(date_str, {}),
                    "total_commits": git_counts.get(date_str, {}).get("commit", 0)
                })
                current += timedelta(days=1)

        return timeline

    async def _broadcast_update(self) -> None:
        """Broadcast update to all connected WebSocket clients."""
        if USE_FASTAPI and self.websocket_clients:
            stats = self.dashboard.get_stats()
            message = {
                "type": "refresh",
                "data": stats
            }

            disconnected = set()
            for client in self.websocket_clients:
                try:
                    await client.send_json(message)
                except:
                    disconnected.add(client)

            self.websocket_clients -= disconnected

    def _background_scanner(self) -> None:
        """Background thread to periodically scan projects."""
        import time

        while True:
            try:
                time.sleep(300)  # 5 minutes
                self.dashboard.scan_projects()

                if USE_FASTAPI and self.websocket_clients:
                    asyncio.run(self._broadcast_update())

            except Exception as e:
                print(f"Background scanner error: {e}")

    def _get_dashboard_html(self) -> str:
        """Generate the main dashboard HTML."""
        return """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Workspace Monitor</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            background: #0d1117;
            color: #c9d1d9;
            line-height: 1.6;
        }
        .container { max-width: 1400px; margin: 0 auto; padding: 20px; }
        header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 20px 0;
            border-bottom: 1px solid #30363d;
            margin-bottom: 30px;
        }
        h1 { color: #58a6ff; font-size: 28px; }
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        .stat-card {
            background: #161b22;
            border: 1px solid #30363d;
            border-radius: 12px;
            padding: 20px;
            transition: transform 0.2s;
        }
        .stat-card:hover { transform: translateY(-2px); border-color: #58a6ff; }
        .stat-value {
            font-size: 36px;
            font-weight: bold;
            color: #58a6ff;
        }
        .stat-label { color: #8b949e; font-size: 14px; margin-top: 5px; }
        .controls {
            display: flex;
            gap: 15px;
            margin-bottom: 20px;
            flex-wrap: wrap;
        }
        input, select, button {
            background: #21262d;
            border: 1px solid #30363d;
            color: #c9d1d9;
            padding: 10px 15px;
            border-radius: 6px;
            font-size: 14px;
        }
        button {
            background: #238636;
            border-color: #238636;
            cursor: pointer;
            font-weight: 500;
        }
        button:hover { background: #2ea043; }
        .projects-table {
            width: 100%;
            border-collapse: collapse;
            background: #161b22;
            border-radius: 12px;
            overflow: hidden;
        }
        .projects-table th, .projects-table td {
            padding: 12px 15px;
            text-align: left;
            border-bottom: 1px solid #30363d;
        }
        .projects-table th {
            background: #21262d;
            font-weight: 600;
            color: #8b949e;
            font-size: 12px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        .projects-table tr:hover { background: #1c2128; }
        .status-badge {
            display: inline-block;
            padding: 4px 10px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 500;
        }
        .status-clean { background: #23863633; color: #3fb950; }
        .status-dirty { background: #da363333; color: #f85149; }
        .status-ahead { background: #9e424233; color: #ffa657; }
        .status-behind { background: #9e424233; color: #ffa657; }
        .status-diverged { background: #8957e533; color: #a371f7; }
        .windsurf-indicator {
            display: inline-block;
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: #3fb950;
            box-shadow: 0 0 8px #3fb950;
            animation: pulse 2s infinite;
        }
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }
        .language-tag {
            display: inline-block;
            padding: 2px 8px;
            background: #30363d;
            border-radius: 4px;
            font-size: 11px;
            color: #8b949e;
        }
        .activity-chart {
            height: 200px;
            background: #161b22;
            border-radius: 12px;
            padding: 20px;
            margin-bottom: 30px;
            display: flex;
            align-items: flex-end;
            gap: 4px;
        }
        .chart-bar {
            flex: 1;
            background: #58a6ff;
            border-radius: 4px 4px 0 0;
            min-height: 5px;
            transition: all 0.3s;
            position: relative;
        }
        .chart-bar:hover {
            background: #79c0ff;
            transform: scaleX(1.1);
        }
        .chart-bar::after {
            content: attr(data-date);
            position: absolute;
            bottom: -20px;
            left: 50%;
            transform: translateX(-50%);
            font-size: 10px;
            color: #8b949e;
            white-space: nowrap;
        }
        .loading { text-align: center; padding: 40px; color: #8b949e; }
        .hidden { display: none; }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>📊 Workspace Monitor</h1>
            <div>
                <span id="last-updated">Last updated: --</span>
            </div>
        </header>

        <div class="stats-grid" id="stats-container">
            <div class="stat-card">
                <div class="stat-value" id="total-projects">--</div>
                <div class="stat-label">Total Projects</div>
            </div>
            <div class="stat-card">
                <div class="stat-value" id="active-sessions">--</div>
                <div class="stat-label">Active Windsurf Sessions</div>
            </div>
            <div class="stat-card">
                <div class="stat-value" id="chats-today">--</div>
                <div class="stat-label">Chats Today</div>
            </div>
            <div class="stat-card">
                <div class="stat-value" id="total-chats">--</div>
                <div class="stat-label">Total Chats</div>
            </div>
            <div class="stat-card">
                <div class="stat-value" id="needs-attention">--</div>
                <div class="stat-label">Need Attention</div>
            </div>
        </div>

        <div class="activity-chart" id="activity-chart">
            <div class="loading">Loading activity data...</div>
        </div>

        <div class="controls">
            <input type="text" id="search-input" placeholder="🔍 Search projects...">
            <select id="status-filter">
                <option value="">All Status</option>
                <option value="clean">Clean</option>
                <option value="dirty">Dirty</option>
                <option value="ahead">Ahead</option>
                <option value="behind">Behind</option>
                <option value="diverged">Diverged</option>
            </select>
            <select id="sort-by">
                <option value="last_commit_time">Last Commit</option>
                <option value="name">Name</option>
                <option value="git_status">Status</option>
                <option value="total_chats">Chats</option>
                <option value="language">Language</option>
            </select>
            <button onclick="refreshData()">🔄 Refresh</button>
            <button onclick="exportData()">📥 Export</button>
        </div>

        <table class="projects-table">
            <thead>
                <tr>
                    <th>Project</th>
                    <th>Status</th>
                    <th>Branch</th>
                    <th>Language</th>
                    <th>Windsurf</th>
                    <th>Chats</th>
                    <th>Last Commit</th>
                </tr>
            </thead>
            <tbody id="projects-tbody">
                <tr><td colspan="7" class="loading">Loading projects...</td></tr>
            </tbody>
        </table>
    </div>

    <script>
        let projects = [];
        let ws = null;

        async function fetchStats() {
            try {
                const res = await fetch('/api/stats');
                const stats = await res.json();

                document.getElementById('total-projects').textContent = stats.total_projects || 0;
                document.getElementById('active-sessions').textContent = stats.active_sessions || 0;
                document.getElementById('chats-today').textContent = stats.chats_today || 0;
                document.getElementById('total-chats').textContent = stats.total_chats || 0;

                const needsAttention = (stats.status_counts?.dirty || 0) +
                                      (stats.status_counts?.ahead || 0) +
                                      (stats.status_counts?.behind || 0) +
                                      (stats.status_counts?.diverged || 0);
                document.getElementById('needs-attention').textContent = needsAttention;

                document.getElementById('last-updated').textContent =
                    'Last updated: ' + new Date().toLocaleTimeString();
            } catch (e) {
                console.error('Error fetching stats:', e);
            }
        }

        async function fetchActivity() {
            try {
                const res = await fetch('/api/activity?days=14');
                const data = await res.json();

                const chart = document.getElementById('activity-chart');
                chart.innerHTML = '';

                const maxVal = Math.max(...data.map(d => d.chats), 1);

                data.forEach(day => {
                    const bar = document.createElement('div');
                    bar.className = 'chart-bar';
                    bar.style.height = `${(day.chats / maxVal) * 100}%`;
                    bar.setAttribute('data-date', day.date.slice(5));
                    bar.title = `${day.date}: ${day.chats} chats, ${day.total_commits || 0} commits`;
                    chart.appendChild(bar);
                });
            } catch (e) {
                console.error('Error fetching activity:', e);
            }
        }

        async function fetchProjects() {
            try {
                const search = document.getElementById('search-input').value;
                const status = document.getElementById('status-filter').value;
                const sort = document.getElementById('sort-by').value;

                let url = `/api/projects?sort=${sort}`;
                if (status) url += `&status=${status}`;
                if (search) url += `&search=${encodeURIComponent(search)}`;

                const res = await fetch(url);
                projects = await res.json();

                renderProjects();
            } catch (e) {
                console.error('Error fetching projects:', e);
            }
        }

        function renderProjects() {
            const tbody = document.getElementById('projects-tbody');

            if (projects.length === 0) {
                tbody.innerHTML = '<tr><td colspan="7" class="loading">No projects found</td></tr>';
                return;
            }

            tbody.innerHTML = projects.map(p => {
                const statusClass = `status-${p.git_status}`;
                const statusText = p.git_status === 'clean' ? '✓ Clean' :
                                  p.git_status === 'dirty' ? `✕ ${p.uncommitted_files} changes` :
                                  p.git_status === 'ahead' ? `↑ ${p.commits_ahead} ahead` :
                                  p.git_status === 'behind' ? `↓ ${p.commits_behind} behind` :
                                  p.git_status === 'diverged' ? '⚠ Diverged' : p.git_status;

                const timeAgo = p.last_commit_time ?
                    timeSince(new Date(p.last_commit_time)) : 'Never';

                return `<tr>
                    <td><strong>${escapeHtml(p.name)}</strong><br>
                        <small style="color:#8b949e">${escapeHtml(p.path)}</small></td>
                    <td><span class="status-badge ${statusClass}">${statusText}</span></td>
                    <td><code>${escapeHtml(p.git_branch)}</code></td>
                    <td><span class="language-tag">${escapeHtml(p.language || 'Unknown')}</span></td>
                    <td>${p.is_windsurf_open ? '<span class="windsurf-indicator" title="Active in Windsurf"></span>' : ''}</td>
                    <td>${p.total_chats || 0}</td>
                    <td>${timeAgo}</td>
                </tr>`;
            }).join('');
        }

        function timeSince(date) {
            const seconds = Math.floor((new Date() - date) / 1000);
            const intervals = {
                year: 31536000,
                month: 2592000,
                week: 604800,
                day: 86400,
                hour: 3600,
                minute: 60
            };

            for (const [unit, secondsInUnit] of Object.entries(intervals)) {
                const interval = Math.floor(seconds / secondsInUnit);
                if (interval >= 1) {
                    return `${interval} ${unit}${interval > 1 ? 's' : ''} ago`;
                }
            }
            return 'Just now';
        }

        function escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }

        async function refreshData() {
            await fetch('/api/refresh', { method: 'POST' });
            await Promise.all([fetchStats(), fetchActivity(), fetchProjects()]);
        }

        function exportData() {
            window.open('/api/export', '_blank');
        }

        function connectWebSocket() {
            const wsUrl = `ws://${window.location.host}/ws`;
            ws = new WebSocket(wsUrl);

            ws.onmessage = (event) => {
                const msg = JSON.parse(event.data);
                if (msg.type === 'refresh' || msg.type === 'stats_update') {
                    fetchStats();
                    fetchProjects();
                }
            };

            ws.onclose = () => {
                setTimeout(connectWebSocket, 5000);
            };
        }

        document.getElementById('search-input').addEventListener('input',
            debounce(fetchProjects, 300));
        document.getElementById('status-filter').addEventListener('change', fetchProjects);
        document.getElementById('sort-by').addEventListener('change', fetchProjects);

        function debounce(fn, ms) {
            let timeout;
            return function(...args) {
                clearTimeout(timeout);
                timeout = setTimeout(() => fn.apply(this, args), ms);
            };
        }

        Promise.all([fetchStats(), fetchActivity(), fetchProjects()]);

        setInterval(() => {
            fetchStats();
            fetchProjects();
        }, 30000);

        if (window.location.protocol === 'http:' || window.location.protocol === 'https:') {
            connectWebSocket();
        }
    </script>
</body>
</html>
"""

    def run(self) -> None:
        """Start the server."""
        print(f"🚀 Starting Workspace Monitor at http://{self.host}:{self.port}")

        if USE_FASTAPI:
            uvicorn.run(self.app, host=self.host, port=self.port)
        else:
            self.app.run(host=self.host, port=self.port, debug=False)


def run_server(host: str = "127.0.0.1", port: int = 8765,
               open_browser: bool = True) -> None:
    """Run the dashboard server."""
    if open_browser:
        webbrowser.open(f"http://{host}:{port}")

    server = DashboardServer(host=host, port=port)
    server.run()
