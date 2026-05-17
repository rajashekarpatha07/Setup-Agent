"""
Tools for the Setup Agent.

Each function here is a capability the LLM agent can invoke:
  - run_command:       Execute a shell command in a sandboxed directory
  - create_file:       Write content to a file
  - read_directory:    List directory contents
  - create_project_dir: Create a new project folder
  - append_to_file:    Append content to an existing file
  - file_exists:       Check if a file or directory exists

All tools validate through the sandbox before executing anything.
Output is truncated to prevent LLM context overflow.
"""

import subprocess
import time
from pathlib import Path
from sandbox import validate, is_path_safe, ALLOWED_BASE
from config import cfg
from logger import get_logger
from notifier import send
from rollback import get_tracker
from history import history_db

log = get_logger("tools")


def _truncate_output(output: str, max_chars: int | None = None) -> str:
    """Truncate command output to prevent LLM context window overflow."""
    limit = max_chars or cfg.max_output_chars
    if len(output) <= limit:
        return output
    half = limit // 2
    return (
        output[:half]
        + f"\n\n... [TRUNCATED — {len(output) - limit} chars omitted] ...\n\n"
        + output[-half:]
    )


# ── Dashboard Integration ────────────────────────────────────────────────────
# The dashboard object is set by main.py at startup.
# We keep a module-level reference so tools can emit step events.
_dashboard = None


def set_dashboard(dash):
    """Called by main.py to provide the dashboard reference."""
    global _dashboard
    _dashboard = dash


def _emit_dashboard_step(command: str, status: str, duration: float = 0.0):
    """Push a step update to the Rich dashboard if available."""
    if _dashboard:
        try:
            _dashboard.add_step(command, status.lower(), duration)
        except Exception:
            pass  # never crash on dashboard errors


def run_command(command: str, working_dir: str, timeout: int | None = None) -> str:
    """
    Validates and executes a shell command inside a specific directory.

    Args:
        command:     The shell command to run
        working_dir: Absolute path to the working directory
        timeout:     Optional timeout in seconds (defaults to config value)

    Returns a status string the agent can parse:
        [SUCCESS] or [FAILED] followed by exit code and output.
    """
    # Sandbox check — ALWAYS before anything else
    is_safe, reason = validate(command, working_dir)
    if not is_safe:
        blocked_msg = f"BLOCKED: {reason}"
        log.warning(f"Command blocked: {command[:80]} — {reason}")
        send(f"⛔ Command blocked: {command[:50]}\nReason: {reason}", title="Blocked", level="error")
        return blocked_msg

    # Determine timeout — use provided value, or detect heavy commands
    if timeout is None:
        heavy_commands = ["npx create-", "npm create", "flutter create", "cargo init", "uv init", "django-admin"]
        timeout = cfg.heavy_command_timeout if any(h in command for h in heavy_commands) else cfg.default_command_timeout

    log.info(f"Running: {command[:80]} (timeout={timeout}s)")

    # Track in rollback
    tracker = get_tracker()
    if tracker:
        tracker.record_command(command)

    start_time = time.time()

    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=working_dir,
        )

        elapsed = time.time() - start_time

        # Combine stdout and stderr — tools like npm write important info to stderr
        output = result.stdout + result.stderr

        if result.returncode == 0:
            status = "SUCCESS"
            log.info(f"Command succeeded: {command[:60]}")
            # Record step in history
            if tracker:
                history_db.record_step(tracker.project_name, command, status)
        else:
            status = "FAILED"
            log.warning(f"Command failed (exit {result.returncode}): {command[:60]}")
            send(f"❌ Failed: {command[:50]}", title="Command Error", level="error")
            if tracker:
                history_db.record_step(tracker.project_name, command, f"FAILED: exit {result.returncode}")

        # Emit dashboard event
        _emit_dashboard_step(command, status, elapsed)

        truncated = _truncate_output(output)
        return f"[{status}] Exit code {result.returncode}\n{truncated}"

    except subprocess.TimeoutExpired:
        log.error(f"Command timed out ({timeout}s): {command[:60]}")
        return f"FAILED: Command timed out after {timeout} seconds"

    except Exception as e:
        log.error(f"Unexpected error running command: {e}")
        return f"FAILED: Unexpected error — {str(e)}"


def create_file(filepath: str, content: str) -> str:
    """
    Creates a file with the given content.

    Validates the filepath through sandbox before writing.
    Creates parent directories automatically if they don't exist.
    """
    is_safe, reason = is_path_safe(filepath)
    if not is_safe:
        log.warning(f"File creation blocked: {filepath} — {reason}")
        return f"BLOCKED: {reason}"

    try:
        path = Path(filepath).expanduser().resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

        # Track in rollback
        tracker = get_tracker()
        if tracker:
            tracker.record_file(str(path))

        log.info(f"Created file: {path.name}")
        return f"SUCCESS: Created file at {path}"

    except Exception as e:
        log.error(f"Failed to create file {filepath}: {e}")
        return f"FAILED: Could not create file — {str(e)}"


def append_to_file(filepath: str, content: str) -> str:
    """
    Appends content to an existing file.

    If the file doesn't exist, creates it.
    Useful for adding lines to .gitignore, appending env vars, etc.
    """
    is_safe, reason = is_path_safe(filepath)
    if not is_safe:
        log.warning(f"File append blocked: {filepath} — {reason}")
        return f"BLOCKED: {reason}"

    try:
        path = Path(filepath).expanduser().resolve()
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, "a", encoding="utf-8") as f:
            f.write(content)

        log.info(f"Appended to file: {path.name}")
        return f"SUCCESS: Appended content to {path}"

    except Exception as e:
        log.error(f"Failed to append to file {filepath}: {e}")
        return f"FAILED: Could not append to file — {str(e)}"


def file_exists(filepath: str) -> str:
    """
    Checks if a file or directory exists at the given path.

    Returns a clear yes/no so the agent can decide whether
    to create or skip a file.
    """
    is_safe, reason = is_path_safe(filepath)
    if not is_safe:
        return f"BLOCKED: {reason}"

    try:
        path = Path(filepath).expanduser().resolve()

        if path.is_file():
            size = path.stat().st_size
            return f"EXISTS: File found at {path} ({size} bytes)"
        elif path.is_dir():
            count = len(list(path.iterdir()))
            return f"EXISTS: Directory found at {path} ({count} items)"
        else:
            return f"NOT_FOUND: Nothing exists at {path}"

    except Exception as e:
        return f"FAILED: Could not check path — {str(e)}"


def read_directory(dirpath: str) -> str:
    """
    Lists all files and folders inside a directory.

    Returns a formatted string with folders and files separated,
    so the agent can understand the project structure.
    """
    is_safe, reason = validate("ls", dirpath)
    if not is_safe:
        return f"BLOCKED: {reason}"

    try:
        path = Path(dirpath).expanduser().resolve()

        if not path.exists():
            return f"Directory does not exist: {dirpath}"

        if not path.is_dir():
            return f"Not a directory: {dirpath}"

        items = sorted(path.iterdir(), key=lambda x: (not x.is_dir(), x.name))

        if not items:
            return "Directory is empty"

        # Separate files and folders with icons
        entries = []
        for item in items:
            if item.name.startswith(".") and item.name in (".git", ".venv", "node_modules", "__pycache__"):
                continue  # skip noisy directories
            if item.is_dir():
                entries.append(f"📁 {item.name}/")
            else:
                size = item.stat().st_size
                entries.append(f"📄 {item.name} ({size} bytes)")

        result = "\n".join(entries)
        return f"Contents of {path}:\n{result}"

    except Exception as e:
        log.error(f"Failed to read directory {dirpath}: {e}")
        return f"FAILED: Could not read directory — {str(e)}"


def create_project_dir(project_name: str) -> str:
    """
    Creates a new folder inside ALLOWED_BASE with the given name.

    Sanitizes the name — only alphanumeric, hyphens, underscores allowed.
    This prevents shell injection through project names.
    """
    # Sanitize: only allow safe characters
    safe_name = "".join(
        c if c.isalnum() or c in "-_" else "-"
        for c in project_name
    ).strip("-")

    if not safe_name:
        return "FAILED: Invalid project name — must contain at least one alphanumeric character"

    if len(safe_name) > 100:
        return "FAILED: Project name is too long (max 100 characters)"

    project_path = ALLOWED_BASE / safe_name

    # Check if directory already exists
    if project_path.exists():
        items = list(project_path.iterdir())
        if items:
            log.warning(f"Project directory already exists and is not empty: {safe_name}")
            return (
                f"WARNING: Directory '{safe_name}' already exists at {project_path} "
                f"with {len(items)} items. Use a different name or clean it first."
            )
        else:
            log.info(f"Project directory exists but is empty: {safe_name}")
            return f"SUCCESS: Project directory already exists (empty) at {project_path}"

    try:
        project_path.mkdir(parents=True, exist_ok=True)

        # Track in rollback
        tracker = get_tracker()
        if tracker:
            tracker.record_dir(str(project_path))

        log.info(f"Created project directory: {safe_name}")
        send(f"📁 Project folder ready: {safe_name}", title="Folder Created", level="milestone")
        return f"SUCCESS: Project directory created at {project_path}"

    except Exception as e:
        log.error(f"Failed to create project directory: {e}")
        return f"FAILED: Could not create directory — {str(e)}"