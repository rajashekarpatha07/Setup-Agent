"""
Post-setup hooks for the Setup Agent.

Automatically runs actions after a successful project setup:
  - Open the project in VS Code
  - Display getting-started commands
  - Custom hook support

Hooks are configurable via environment variables:
  HOOK_OPEN_VSCODE=true|false   (default: true)
  HOOK_SHOW_COMMANDS=true|false (default: true)
"""

import subprocess
import shutil
from pathlib import Path
from .config import cfg
from .logger import get_logger

log = get_logger("hooks")


# ── Getting Started Commands ─────────────────────────────────────────────────
GETTING_STARTED = {
    "react-vite": ["cd {path}", "npm run dev"],
    "nextjs": ["cd {path}", "npm run dev"],
    "express-ts": ["cd {path}", 'npx ts-node src/index.ts', "# or: npx nodemon --exec ts-node src/index.ts"],
    "typescript": ["cd {path}", "npx ts-node src/index.ts"],
    "vite-vanilla": ["cd {path}", "npm run dev"],
    "svelte": ["cd {path}", "npm run dev"],
    "python-uv": ["cd {path}", "uv run python main.py"],
    "flask": ["cd {path}", "uv run python app/main.py"],
    "django": ["cd {path}", "uv run python manage.py runserver"],
    "fastapi": ["cd {path}", "uv run uvicorn app.main:app --reload"],
    "rust": ["cd {path}", "cargo run"],
    "go": ["cd {path}", "go run cmd/main.go"],
    "flutter": ["cd {path}", "flutter run"],
}


def open_in_vscode(project_path: str) -> bool:
    """Open the project directory in VS Code."""
    if not cfg.hook_open_vscode:
        log.debug("VS Code hook disabled")
        return False
    if not shutil.which("code"):
        log.warning("VS Code 'code' command not found in PATH — skipping")
        return False
    try:
        subprocess.Popen(
            ["code", project_path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        log.info(f"Opened project in VS Code: {project_path}")
        return True
    except Exception as e:
        log.warning(f"Failed to open VS Code: {e}")
        return False


def get_start_commands(project_type: str, project_path: str) -> list[str]:
    """Get the getting-started commands for a project type."""
    commands = GETTING_STARTED.get(project_type, [f"cd {project_path}"])
    return [cmd.format(path=project_path) for cmd in commands]


def format_start_commands(project_type: str, project_path: str) -> str:
    """Format getting-started commands as a nice string for display/notification."""
    commands = get_start_commands(project_type, project_path)
    if not commands:
        return ""
    lines = ["", "🚀 Getting started:"]
    for cmd in commands:
        lines.append(f"   $ {cmd}")
    return "\n".join(lines)


def run_post_setup_hooks(project_name: str, project_type: str, project_path: str) -> dict:
    """
    Run all post-setup hooks.
    Returns a dict with results:
        {"vscode_opened": True/False, "start_commands": ["cd ...", "npm run dev"]}
    """
    log.info(f"Running post-setup hooks for '{project_name}' ({project_type})")
    results = {}
    results["vscode_opened"] = open_in_vscode(project_path)
    results["start_commands"] = get_start_commands(project_type, project_path)
    if results["start_commands"]:
        log.info(f"Getting started: {' → '.join(results['start_commands'])}")
    return results
