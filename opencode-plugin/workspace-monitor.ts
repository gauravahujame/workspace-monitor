/**
 * Workspace Monitor Plugin for OpenCode
 * 
 * This plugin integrates OpenCode with the Workspace Monitor system,
 * tracking projects, sessions, and git actions across your workspace.
 * 
 * Installation:
 * 1. Copy this file to ~/.config/opencode/plugins/workspace-monitor.ts
 * 2. Add to your opencode.jsonc:
 *    {
 *      "plugins": [
 *        "~/.config/opencode/plugins/workspace-monitor.ts"
 *      ]
 *    }
 * 3. Restart OpenCode
 */

import type { Plugin } from "@opencode-ai/plugin";
import { Database } from "bun:sqlite";
import { join, dirname, basename } from "path";
import { existsSync } from "fs";

// Configuration
const CONFIG = {
  // Where to store the dashboard database
  // On macOS: ~/Library/Application Support/workspace-monitor/
  // On Linux: ~/.workspace-monitor/
  dataDir: (() => {
    const home = process.env.HOME || process.env.USERPROFILE || "/tmp";
    if (process.platform === "darwin") {
      return join(home, "Library", "Application Support", "workspace-monitor");
    }
    return join(home, ".workspace-monitor");
  })(),
  
  // Default workspace root
  workspaceRoot: join(process.env.HOME || "~", "workspace"),
  
  // Enable debug logging
  debug: process.env.WORKSPACE_MONITOR_DEBUG === "1",
};

// Initialize database connection
let db: Database | null = null;

function getDatabase(): Database {
  if (!db) {
    const dbPath = join(CONFIG.dataDir, "dashboard.db");
    
    // Ensure directory exists
    const { mkdirSync } = require("fs");
    try {
      mkdirSync(CONFIG.dataDir, { recursive: true });
    } catch (e) {
      // Directory might already exist
    }
    
    db = new Database(dbPath);
    initializeSchema(db);
  }
  return db;
}

function initializeSchema(db: Database): void {
  db.run(`
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
    )
  `);

  db.run(`
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
    )
  `);

  db.run(`
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
    )
  `);

  db.run(`
    CREATE TABLE IF NOT EXISTS opencode_sessions (
      session_id TEXT PRIMARY KEY,
      project_path TEXT,
      title TEXT,
      created_at TIMESTAMP,
      updated_at TIMESTAMP,
      message_count INTEGER DEFAULT 0,
      is_active BOOLEAN DEFAULT 1
    )
  `);

  // Create indexes
  db.run(`CREATE INDEX IF NOT EXISTS idx_projects_status ON projects(git_status)`);
  db.run(`CREATE INDEX IF NOT EXISTS idx_chats_project ON chats(project_path)`);
  db.run(`CREATE INDEX IF NOT EXISTS idx_chats_time ON chats(timestamp)`);
  db.run(`CREATE INDEX IF NOT EXISTS idx_git_actions_project ON git_actions(project_path)`);
}

function log(...args: any[]): void {
  if (CONFIG.debug) {
    console.log("[workspace-monitor]", ...args);
  }
}

function detectProjectPath(directory: string, worktree?: string): string | null {
  // Use worktree if available, otherwise directory
  const basePath = worktree || directory;
  
  // Check if this is a git repository
  if (!existsSync(join(basePath, ".git"))) {
    // Try to find .git in parent directories
    let current = basePath;
    while (current !== dirname(current)) {
      if (existsSync(join(current, ".git"))) {
        return current;
      }
      current = dirname(current);
    }
    return null;
  }
  
  return basePath;
}

function detectLanguage(projectPath: string): string {
  const languageFiles: Record<string, string[]> = {
    "Python": ["requirements.txt", "setup.py", "pyproject.toml", "Pipfile"],
    "JavaScript": ["package.json", "yarn.lock", "pnpm-lock.yaml"],
    "TypeScript": ["tsconfig.json"],
    "Go": ["go.mod", "go.sum"],
    "Rust": ["Cargo.toml", "Cargo.lock"],
    "Java": ["pom.xml", "build.gradle"],
    "Ruby": ["Gemfile", "Gemfile.lock"],
    "PHP": ["composer.json"],
  };

  const { readdirSync, statSync } = require("fs");
  
  try {
    // Check for language-specific files
    for (const [lang, files] of Object.entries(languageFiles)) {
      for (const file of files) {
        if (existsSync(join(projectPath, file))) {
          return lang;
        }
      }
    }

    // Check file extensions
    const files = readdirSync(projectPath);
    const extCounts: Record<string, number> = {};
    
    for (const file of files) {
      const ext = file.split(".").pop()?.toLowerCase();
      if (ext) {
        extCounts[ext] = (extCounts[ext] || 0) + 1;
      }
    }

    const extToLang: Record<string, string> = {
      py: "Python", js: "JavaScript", ts: "TypeScript",
      go: "Go", rs: "Rust", java: "Java",
    };

    const sortedExts = Object.entries(extCounts).sort((a, b) => b[1] - a[1]);
    for (const [ext] of sortedExts) {
      if (extToLang[ext]) {
        return extToLang[ext];
      }
    }
  } catch (e) {
    log("Error detecting language:", e);
  }

  return "Unknown";
}

function parseGitCommand(command: string): string | null {
  if (!command.startsWith("git ")) {
    return null;
  }

  const parts = command.split(" ");
  if (parts.length < 2) {
    return null;
  }

  const subcommand = parts[1];
  const actionMap: Record<string, string> = {
    commit: "commit", push: "push", pull: "pull",
    fetch: "fetch", merge: "merge", rebase: "rebase",
    checkout: "branch", branch: "branch",
  };

  return actionMap[subcommand] || null;
}

function updateProjectFromSession(session: any): void {
  const projectPath = detectProjectPath(session.directory, session.worktree);
  if (!projectPath) {
    log("Could not detect project path for session:", session.id);
    return;
  }

  const db = getDatabase();
  const name = basename(projectPath);
  const language = detectLanguage(projectPath);
  
  // Count messages
  const messageCount = session.messages?.length || 0;

  // Insert or update project
  db.run(`
    INSERT OR REPLACE INTO projects 
    (path, name, language, total_chats, last_chat_time, is_windsurf_open, updated_at)
    VALUES (?, ?, ?, 
      (SELECT COUNT(*) FROM opencode_sessions WHERE project_path = ?),
      ?, 1, ?)
  `, [projectPath, name, language, projectPath, new Date().toISOString(), new Date().toISOString()]);

  log("Updated project:", name, "with", messageCount, "messages");
}

// Main plugin export
export const WorkspaceMonitorPlugin: Plugin = async (ctx) => {
  log("Workspace Monitor plugin initialized");
  log("Data directory:", CONFIG.dataDir);

  return {
    // Session events - track project activity
    "session.created": async ({ event }) => {
      const session = event.payload.session;
      log("Session created:", session.id);
      
      const projectPath = detectProjectPath(session.directory, session.worktree);
      if (!projectPath) return;

      const db = getDatabase();
      db.run(`
        INSERT OR REPLACE INTO opencode_sessions 
        (session_id, project_path, title, created_at, updated_at, is_active)
        VALUES (?, ?, ?, ?, ?, 1)
      `, [
        session.id,
        projectPath,
        session.title || basename(projectPath),
        new Date().toISOString(),
        new Date().toISOString(),
      ]);

      updateProjectFromSession(session);
    },

    "session.updated": async ({ event }) => {
      const session = event.payload.session;
      log("Session updated:", session.id);
      
      const projectPath = detectProjectPath(session.directory, session.worktree);
      if (!projectPath) return;

      const db = getDatabase();
      
      // Update session record
      db.run(`
        UPDATE opencode_sessions 
        SET updated_at = ?, message_count = ?, is_active = 1
        WHERE session_id = ?
      `, [new Date().toISOString(), session.messages?.length || 0, session.id]);

      // Update project chat count
      db.run(`
        UPDATE projects 
        SET total_chats = (SELECT COUNT(*) FROM opencode_sessions WHERE project_path = ?),
            last_chat_time = ?,
            updated_at = ?
        WHERE path = ?
      `, [projectPath, new Date().toISOString(), new Date().toISOString(), projectPath]);
    },

    "session.deleted": async ({ event }) => {
      const session = event.payload.session;
      log("Session deleted:", session.id);
      
      const db = getDatabase();
      db.run(`DELETE FROM opencode_sessions WHERE session_id = ?`, [session.id]);
    },

    // Message events - track individual messages
    "message.updated": async ({ event }) => {
      const message = event.payload.message;
      log("Message updated:", message.id, "in session:", message.sessionID);
    },

    // File events - track file edits
    "file.edited": async ({ event }) => {
      const file = event.payload.file;
      log("File edited:", file.path);
      
      const projectPath = detectProjectPath(dirname(file.path));
      if (!projectPath) return;

      const db = getDatabase();
      
      // Update project timestamp
      db.run(`
        UPDATE projects 
        SET updated_at = ?
        WHERE path = ?
      `, [new Date().toISOString(), projectPath]);

      // Record in chats table (if we can find a recent chat for this project)
      const recentChat = db.query(`
        SELECT trajectory_id FROM chats 
        WHERE project_path = ? 
        ORDER BY timestamp DESC 
        LIMIT 1
      `).get(projectPath) as { trajectory_id: string } | null;

      if (recentChat) {
        db.run(`
          UPDATE chats 
          SET file_edits = file_edits + 1
          WHERE trajectory_id = ?
        `, [recentChat.trajectory_id]);
      }
    },

    "file.watcher.updated": async ({ event }) => {
      log("File watcher updated:", event.payload.files?.length, "files");
    },

    // Tool execution events - track git commands
    "tool.execute.before": async ({ input }, { args }) => {
      if (input.tool === "bash" && args.command?.startsWith("git ")) {
        const gitAction = parseGitCommand(args.command);
        if (!gitAction) return;

        const cwd = args.cwd || ctx.directory;
        const projectPath = detectProjectPath(cwd);
        if (!projectPath) return;

        log("Git action detected:", gitAction, "in project:", basename(projectPath));

        const db = getDatabase();
        
        // Store pending action (will be confirmed in tool.execute.after)
        db.run(`
          INSERT INTO git_actions (project_path, action_type, timestamp, details)
          VALUES (?, ?, ?, ?)
        `, [projectPath, gitAction, new Date().toISOString(), args.command]);
      }
    },

    "tool.execute.after": async ({ input }, { output }) => {
      log("Tool executed:", input.tool);
    },

    // Command events
    "command.executed": async ({ event }) => {
      const command = event.payload.command;
      log("Command executed:", command.name);
    },

    // Custom tools exposed to the AI
    tool: {
      // Tool: Query workspace dashboard
      "workspace.list_projects": {
        description: "List all projects in the workspace with their status",
        args: {
          status: {
            type: "string",
            optional: true,
            description: "Filter by status: clean, dirty, ahead, behind, diverged"
          },
          limit: {
            type: "number",
            optional: true,
            description: "Maximum number of projects to return"
          }
        },
        async execute(args: { status?: string; limit?: number }) {
          const db = getDatabase();
          
          let query = "SELECT * FROM projects";
          const params: any[] = [];
          
          if (args.status) {
            query += " WHERE git_status = ?";
            params.push(args.status);
          }
          
          query += " ORDER BY last_chat_time DESC NULLS LAST";
          
          if (args.limit) {
            query += " LIMIT ?";
            params.push(args.limit);
          }

          const projects = db.query(query).all(...params);
          
          return JSON.stringify(projects, null, 2);
        }
      },

      // Tool: Get project status
      "workspace.project_status": {
        description: "Get detailed status of a specific project",
        args: {
          project_name: {
            type: "string",
            description: "Name of the project to check"
          }
        },
        async execute(args: { project_name: string }) {
          const db = getDatabase();
          
          const project = db.query(`
            SELECT * FROM projects WHERE name = ?
          `).get(args.project_name);

          if (!project) {
            return `Project "${args.project_name}" not found`;
          }

          // Get recent chats
          const chats = db.query(`
            SELECT * FROM chats WHERE project_path = ?
            ORDER BY timestamp DESC LIMIT 5
          `).all(project.path);

          return JSON.stringify({ project, recent_chats: chats }, null, 2);
        }
      },

      // Tool: Get workspace statistics
      "workspace.stats": {
        description: "Get overall workspace statistics",
        args: {},
        async execute() {
          const db = getDatabase();
          
          const totalProjects = db.query("SELECT COUNT(*) as count FROM projects").get() as { count: number };
          const activeSessions = db.query("SELECT COUNT(*) as count FROM opencode_sessions WHERE is_active = 1").get() as { count: number };
          const totalChats = db.query("SELECT COUNT(*) as count FROM chats").get() as { count: number };
          
          const statusCounts = db.query(`
            SELECT git_status, COUNT(*) as count 
            FROM projects 
            GROUP BY git_status
          `).all() as { git_status: string; count: number }[];

          return JSON.stringify({
            total_projects: totalProjects.count,
            active_sessions: activeSessions.count,
            total_chats: totalChats.count,
            status_distribution: Object.fromEntries(
              statusCounts.map(s => [s.git_status, s.count])
            )
          }, null, 2);
        }
      },

      // Tool: Scan for new projects
      "workspace.scan": {
        description: "Scan the workspace for new git repositories",
        args: {},
        async execute() {
          const { readdirSync, statSync, existsSync } = require("fs");
          const { join } = require("path");
          
          const found: string[] = [];
          
          try {
            const entries = readdirSync(CONFIG.workspaceRoot);
            
            for (const entry of entries) {
              const fullPath = join(CONFIG.workspaceRoot, entry);
              
              try {
                const stat = statSync(fullPath);
                if (stat.isDirectory()) {
                  if (existsSync(join(fullPath, ".git"))) {
                    found.push(entry);
                  }
                }
              } catch (e) {
                // Skip inaccessible directories
              }
            }
          } catch (e) {
            return `Error scanning workspace: ${e}`;
          }

          return JSON.stringify({ 
            scanned: CONFIG.workspaceRoot,
            projects_found: found.length,
            projects: found 
          }, null, 2);
        }
      }
    },

    // Configuration hook
    config: async (config: any) => {
      // Add custom configuration options
      if (!config.workspaceMonitor) {
        config.workspaceMonitor = {};
      }
      
      config.workspaceMonitor.enabled = true;
      config.workspaceMonitor.dataDir = CONFIG.dataDir;
      
      log("Configuration updated");
    }
  };
};

export default WorkspaceMonitorPlugin;
