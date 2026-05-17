"""
Sandbox — security layer for the Setup Agent.

Every command and file path passes through here before execution.
The sandbox enforces:
  1. Commands must start with an allowed program
  2. No blocked patterns (shell injection, destructive ops)
  3. No shell chaining (&&, ||, ;, |, backticks, $())
  4. All paths must resolve inside ALLOWED_BASE
  5. Command length limit (LLM hallucination guard)
  6. Path depth limit (prevent deeply nested traversal tricks)
"""

import re
from pathlib import Path
from config import cfg
from logger import get_logger

log = get_logger("sandbox")

# Resolve the allowed base directory from config
ALLOWED_BASE = cfg.projects_dir

# ── Blocked Patterns ─────────────────────────────────────────────────────────
# These strings should NEVER appear anywhere in a command.
# Even if a command starts with an allowed program, these stop it.

BLOCKED_PATTERNS = [
    # Privilege escalation
    "sudo",
    "doas",
    "su ",

    # Destructive file operations
    "rm -rf",
    "rm -r",
    "rm -f",
    "rmdir",
    "shred",

    # System-level operations
    "mkfs",
    "dd if",
    "shutdown",
    "reboot",
    "halt",
    "kill",
    "pkill",
    "killall",
    "chmod 777",
    "chown",

    # Network attacks / remote execution
    "curl | bash",
    "curl |bash",
    "wget | sh",
    "wget |sh",
    "curl | sh",

    # Device writes
    "> /dev/",
    ">> /dev/",

    # Path traversal
    "../",

    # Shell chaining / injection (critical!)
    "&&",
    "||",
    ";",
    "$(", 
    "`",

    # Output redirection (prevents overwriting system files)
    ">>",
]

# ── Allowed Commands ─────────────────────────────────────────────────────────
# Only programs in this list may be executed.
# The agent cannot run anything else.

ALLOWED_COMMANDS = [
    # JavaScript / TypeScript ecosystem
    "npm", "npx", "node", "pnpm", "yarn", "tsc", "bun",

    # Python ecosystem
    "python3", "pip", "pip3", "uv",

    # Systems languages
    "cargo", "rustc", "go",

    # Mobile
    "flutter", "dart",

    # PHP
    "composer", "php",

    # Version control
    "git",

    # Safe filesystem commands
    "mkdir", "ls", "cat", "touch", "cp", "mv", "echo",
    "find", "head", "tail", "wc",
]


def is_path_safe(path: str) -> tuple[bool, str]:
    """
    Checks if a given path is inside ALLOWED_BASE and within depth limits.

    Returns (is_safe, reason).
    resolve() converts any path to its real absolute form, so tricks
    like ~/../../etc/passwd get caught.
    """
    try:
        target = Path(path).expanduser().resolve()

        # Ensure ALLOWED_BASE exists
        ALLOWED_BASE.mkdir(parents=True, exist_ok=True)

        # Check: inside allowed directory?
        if not target.is_relative_to(ALLOWED_BASE):
            log.warning(f"Path blocked (outside allowed dir): {target}")
            return False, f"Path '{target}' is outside allowed directory '{ALLOWED_BASE}'"

        # Check: depth limit (prevent deeply nested traversal tricks)
        relative = target.relative_to(ALLOWED_BASE)
        depth = len(relative.parts)
        if depth > cfg.max_path_depth:
            log.warning(f"Path blocked (too deep): {target} (depth={depth})")
            return False, f"Path is too deeply nested ({depth} levels, max {cfg.max_path_depth})"

        return True, "ok"

    except Exception as e:
        log.error(f"Path validation error: {e}")
        return False, f"Path check failed: {str(e)}"


def is_command_safe(command: str) -> tuple[bool, str]:
    """
    Multi-layer command validation:
      1. Not empty
      2. Under length limit
      3. No blocked patterns
      4. Starts with an allowed program
      5. No pipe chaining (|) — checked separately because | is used in
         legitimate contexts but we block it as a shell operator
    """
    command_stripped = command.strip()

    # Check 0: not empty
    if not command_stripped:
        return False, "Empty command"

    # Check 1: length limit (LLM hallucination guard)
    if len(command_stripped) > cfg.max_command_length:
        log.warning(f"Command blocked (too long): {len(command_stripped)} chars")
        return False, f"Command is too long ({len(command_stripped)} chars, max {cfg.max_command_length})"

    # Check 2: blocked patterns anywhere in the command
    for pattern in BLOCKED_PATTERNS:
        if pattern in command_stripped:
            log.warning(f"Command blocked (pattern '{pattern}'): {command_stripped[:80]}")
            return False, f"Blocked pattern detected: '{pattern}'"

    # Check 3: pipe operator (separate check because we can't put just "|"
    # in BLOCKED_PATTERNS — it would match too many things)
    # We check for " | " (pipe with spaces) which is the shell pipe operator
    if " | " in command_stripped:
        log.warning(f"Command blocked (pipe chaining): {command_stripped[:80]}")
        return False, "Pipe chaining (|) is not allowed for security"

    # Check 4: must start with an allowed command
    first_word = command_stripped.split()[0] if command_stripped else ""

    # Handle path-prefixed commands like /usr/bin/npm → npm
    first_word_base = first_word.split("/")[-1] if "/" in first_word else first_word

    if first_word_base not in ALLOWED_COMMANDS:
        log.warning(f"Command blocked (not allowed): {first_word_base}")
        return False, f"Command '{first_word_base}' is not in the allowed list: {ALLOWED_COMMANDS}"

    return True, "ok"


def validate(command: str, working_dir: str) -> tuple[bool, str]:
    """
    Single entry point for tools.py.
    Both the command AND the directory must pass validation.
    If either fails, the whole operation is blocked.
    """
    cmd_safe, cmd_reason = is_command_safe(command)
    if not cmd_safe:
        return False, cmd_reason

    path_safe, path_reason = is_path_safe(working_dir)
    if not path_safe:
        return False, path_reason

    log.debug(f"Validated: {command[:60]} in {working_dir}")
    return True, "ok"