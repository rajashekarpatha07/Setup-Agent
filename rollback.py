"""
Auto-rollback system for the Setup Agent.

Tracks all actions (dirs created, files written, commands run) during a
project setup. If the setup fails, rolls back by deleting the created
project directory.

Usage:
    tracker = RollbackTracker("my-app")
    tracker.record_dir("/path/to/my-app")
    tracker.record_file("/path/to/my-app/package.json")
    tracker.record_command("npm init -y")

    # If something goes wrong:
    tracker.rollback()  # deletes the project directory
"""

import shutil
from pathlib import Path
from dataclasses import dataclass, field
from logger import get_logger

log = get_logger("rollback")


@dataclass
class RollbackTracker:
    """Tracks actions during a project setup for potential rollback."""

    project_name: str
    project_dir: Path | None = None
    dirs_created: list[str] = field(default_factory=list)
    files_created: list[str] = field(default_factory=list)
    commands_run: list[str] = field(default_factory=list)
    _rolled_back: bool = False

    def record_dir(self, path: str):
        """Record a directory that was created."""
        self.dirs_created.append(path)
        if self.project_dir is None:
            self.project_dir = Path(path)
            log.debug(f"Rollback: tracking project dir {path}")

    def record_file(self, path: str):
        """Record a file that was created."""
        self.files_created.append(path)

    def record_command(self, command: str):
        """Record a command that was executed."""
        self.commands_run.append(command)

    def rollback(self) -> bool:
        """
        Roll back the project setup by deleting the project directory.

        Returns True if rollback was performed, False if nothing to roll back.
        Only rolls back once — calling again is a no-op.
        """
        if self._rolled_back:
            log.warning("Rollback already performed — skipping")
            return False

        if self.project_dir is None:
            log.warning("No project directory recorded — nothing to roll back")
            return False

        if not self.project_dir.exists():
            log.warning(f"Project directory doesn't exist: {self.project_dir}")
            return False

        try:
            log.info(f"Rolling back project '{self.project_name}' — deleting {self.project_dir}")
            shutil.rmtree(self.project_dir)
            self._rolled_back = True
            log.info(f"Rollback complete — removed {self.project_dir}")
            return True

        except Exception as e:
            log.error(f"Rollback failed: {e}")
            return False

    def get_summary(self) -> dict:
        """Get a summary of tracked actions."""
        return {
            "project_name": self.project_name,
            "project_dir": str(self.project_dir) if self.project_dir else None,
            "dirs_created": len(self.dirs_created),
            "files_created": len(self.files_created),
            "commands_run": len(self.commands_run),
            "rolled_back": self._rolled_back,
        }


# ── Global tracker for the current run ───────────────────────────────────────
# Set/reset by main.py before each agent run
_current_tracker: RollbackTracker | None = None


def get_tracker() -> RollbackTracker | None:
    """Get the current rollback tracker."""
    return _current_tracker


def start_tracking(project_name: str) -> RollbackTracker:
    """Start a new rollback tracker for a project setup."""
    global _current_tracker
    _current_tracker = RollbackTracker(project_name=project_name)
    log.debug(f"Rollback tracking started for '{project_name}'")
    return _current_tracker


def stop_tracking():
    """Clear the current tracker."""
    global _current_tracker
    _current_tracker = None
