"""
Project history database for the Setup Agent.

Uses SQLite (Python stdlib) to track every project ever created.
Stores: project name, type, path, duration, status, command log, packages.

Usage:
    from .history import history_db
    history_db.record_start("my-app", "react-vite", "/path/to/my-app")
    history_db.record_step("my-app", "npm init -y", "SUCCESS")
    history_db.record_complete("my-app", status="success")
    history_db.get_all()        # list of all projects
    history_db.get_stats()      # aggregate stats
"""

import sqlite3
import json
import time
from pathlib import Path
from datetime import datetime, timezone
from dataclasses import dataclass, field
from .logger import get_logger

log = get_logger("history")

# Database stored at project root's data/ directory
_PROJECT_ROOT = Path(__file__).parent.parent.parent
DB_PATH = _PROJECT_ROOT / "data" / "history.db"


@dataclass
class ProjectRecord:
    """A single project setup record."""
    id: int = 0
    name: str = ""
    project_type: str = ""
    path: str = ""
    status: str = "in_progress"
    started_at: str = ""
    completed_at: str = ""
    duration_seconds: float = 0.0
    command_log: list = field(default_factory=list)
    packages: list = field(default_factory=list)
    error_message: str = ""
    user_message: str = ""


class HistoryDB:
    """SQLite-backed project history database."""

    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
        self._start_times: dict[str, float] = {}

    def _init_db(self):
        """Create tables if they don't exist."""
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS projects (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    project_type TEXT DEFAULT '',
                    path TEXT DEFAULT '',
                    status TEXT DEFAULT 'in_progress',
                    started_at TEXT NOT NULL,
                    completed_at TEXT DEFAULT '',
                    duration_seconds REAL DEFAULT 0.0,
                    command_log TEXT DEFAULT '[]',
                    packages TEXT DEFAULT '[]',
                    error_message TEXT DEFAULT '',
                    user_message TEXT DEFAULT ''
                )
            """)
            conn.commit()
        log.debug(f"History database initialized at {self.db_path}")

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def record_start(self, name: str, project_type: str = "", path: str = "", user_message: str = "") -> int:
        """Record the start of a new project setup. Returns the record ID."""
        self._start_times[name] = time.time()
        with self._connect() as conn:
            cursor = conn.execute(
                """INSERT INTO projects (name, project_type, path, status, started_at, user_message)
                   VALUES (?, ?, ?, 'in_progress', ?, ?)""",
                (name, project_type, path, self._now(), user_message),
            )
            conn.commit()
            record_id = cursor.lastrowid
            log.info(f"History: started recording project '{name}' (id={record_id})")
            return record_id

    def record_step(self, name: str, command: str, result: str):
        """Append a command step to the project's command log."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT id, command_log FROM projects WHERE name = ? ORDER BY id DESC LIMIT 1",
                (name,),
            ).fetchone()
            if not row:
                return
            log_entries = json.loads(row["command_log"])
            log_entries.append({
                "command": command,
                "result": result[:200],
                "timestamp": self._now(),
            })
            conn.execute(
                "UPDATE projects SET command_log = ? WHERE id = ?",
                (json.dumps(log_entries), row["id"]),
            )
            conn.commit()

    def update_project_info(self, name: str, project_type: str = None, path: str = None):
        """Update project type and path (often discovered during agent run)."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT id FROM projects WHERE name = ? ORDER BY id DESC LIMIT 1",
                (name,),
            ).fetchone()
            if not row:
                return
            updates = []
            params = []
            if project_type is not None:
                updates.append("project_type = ?")
                params.append(project_type)
            if path is not None:
                updates.append("path = ?")
                params.append(path)
            if updates:
                params.append(row["id"])
                conn.execute(
                    f"UPDATE projects SET {', '.join(updates)} WHERE id = ?",
                    params,
                )
                conn.commit()

    def record_complete(self, name: str, status: str = "success", error_message: str = "", packages: list = None):
        """Record the completion of a project setup."""
        elapsed = time.time() - self._start_times.pop(name, time.time())
        with self._connect() as conn:
            row = conn.execute(
                "SELECT id FROM projects WHERE name = ? ORDER BY id DESC LIMIT 1",
                (name,),
            ).fetchone()
            if not row:
                return
            conn.execute(
                """UPDATE projects SET
                    status = ?, completed_at = ?, duration_seconds = ?,
                    error_message = ?, packages = ?
                   WHERE id = ?""",
                (status, self._now(), round(elapsed, 1), error_message, json.dumps(packages or []), row["id"]),
            )
            conn.commit()
            log.info(f"History: project '{name}' → {status} ({elapsed:.1f}s)")

    def get_all(self, limit: int = 50) -> list[dict]:
        """Get all project records, most recent first."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM projects ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
            return [self._row_to_dict(r) for r in rows]

    def get_recent(self, count: int = 5) -> list[dict]:
        """Get the N most recent projects."""
        return self.get_all(limit=count)

    def get_by_name(self, name: str) -> dict | None:
        """Get a project by name."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM projects WHERE name = ? ORDER BY id DESC LIMIT 1",
                (name,),
            ).fetchone()
            return self._row_to_dict(row) if row else None

    def get_stats(self) -> dict:
        """Get aggregate statistics."""
        with self._connect() as conn:
            total = conn.execute("SELECT COUNT(*) as c FROM projects").fetchone()["c"]
            success = conn.execute("SELECT COUNT(*) as c FROM projects WHERE status = 'success'").fetchone()["c"]
            failed = conn.execute("SELECT COUNT(*) as c FROM projects WHERE status = 'failed'").fetchone()["c"]
            rolled_back = conn.execute("SELECT COUNT(*) as c FROM projects WHERE status = 'rolled_back'").fetchone()["c"]
            in_progress = conn.execute("SELECT COUNT(*) as c FROM projects WHERE status = 'in_progress'").fetchone()["c"]
            avg_duration = conn.execute(
                "SELECT AVG(duration_seconds) as avg FROM projects WHERE status = 'success' AND duration_seconds > 0"
            ).fetchone()["avg"] or 0.0
            type_rows = conn.execute(
                "SELECT project_type, COUNT(*) as c FROM projects WHERE project_type != '' GROUP BY project_type ORDER BY c DESC"
            ).fetchall()
            by_type = {r["project_type"]: r["c"] for r in type_rows}
            recent_rows = conn.execute(
                """SELECT DATE(started_at) as day, COUNT(*) as c
                   FROM projects
                   WHERE started_at >= datetime('now', '-7 days')
                   GROUP BY DATE(started_at) ORDER BY day"""
            ).fetchall()
            daily_activity = {r["day"]: r["c"] for r in recent_rows}

            return {
                "total": total,
                "success": success,
                "failed": failed,
                "rolled_back": rolled_back,
                "in_progress": in_progress,
                "success_rate": round((success / total * 100) if total > 0 else 0, 1),
                "avg_duration_seconds": round(avg_duration, 1),
                "by_type": by_type,
                "daily_activity": daily_activity,
            }

    def _row_to_dict(self, row: sqlite3.Row) -> dict:
        """Convert a database row to a dictionary with parsed JSON fields."""
        d = dict(row)
        d["command_log"] = json.loads(d.get("command_log", "[]"))
        d["packages"] = json.loads(d.get("packages", "[]"))
        return d


# ── Singleton ────────────────────────────────────────────────────────────────
history_db = HistoryDB()
