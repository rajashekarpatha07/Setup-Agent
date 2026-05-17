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
from .config import cfg
from .logger import get_logger

log = get_logger("sandbox")

# Resolve the allowed base directory from config
ALLOWED_BASE = cfg.projects_dir

BLOCKED_PATTERNS = [
    "sudo", "doas", "su ",
    "rm -rf", "rm -r", "rm -f", "rmdir", "shred",
    "mkfs", "dd if", "shutdown", "reboot", "halt",
    "kill", "pkill", "killall", "chmod 777", "chown",
    "curl | bash", "curl |bash", "wget | sh", "wget |sh", "curl | sh",
    "> /dev/", ">> /dev/", "../",
    "&&", "||", ";", "$(", "`",
    ">>",
]

ALLOWED_COMMANDS = [
    "npm", "npx", "node", "pnpm", "yarn", "tsc", "bun",
    "python3", "pip", "pip3", "uv",
    "cargo", "rustc", "go",
    "flutter", "dart",
    "composer", "php",
    "git",
    "mkdir", "ls", "cat", "touch", "cp", "mv", "echo",
    "find", "head", "tail", "wc",
]


def is_path_safe(path: str) -> tuple[bool, str]:
    """
    Checks if a given path is inside ALLOWED_BASE and within depth limits.
    Returns (is_safe, reason).
    """
    try:
        target = Path(path).expanduser().resolve()
        ALLOWED_BASE.mkdir(parents=True, exist_ok=True)

        if not target.is_relative_to(ALLOWED_BASE):
            log.warning(f"Path blocked (outside allowed dir): {target}")
            return False, f"Path '{target}' is outside allowed directory '{ALLOWED_BASE}'"

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
      5. No pipe chaining (|)
    """
    command_stripped = command.strip()

    if not command_stripped:
        return False, "Empty command"

    if len(command_stripped) > cfg.max_command_length:
        log.warning(f"Command blocked (too long): {len(command_stripped)} chars")
        return False, f"Command is too long ({len(command_stripped)} chars, max {cfg.max_command_length})"

    for pattern in BLOCKED_PATTERNS:
        if pattern in command_stripped:
            log.warning(f"Command blocked (pattern '{pattern}'): {command_stripped[:80]}")
            return False, f"Blocked pattern detected: '{pattern}'"

    if " | " in command_stripped:
        log.warning(f"Command blocked (pipe chaining): {command_stripped[:80]}")
        return False, "Pipe chaining (|) is not allowed for security"

    first_word = command_stripped.split()[0] if command_stripped else ""
    first_word_base = first_word.split("/")[-1] if "/" in first_word else first_word

    if first_word_base not in ALLOWED_COMMANDS:
        log.warning(f"Command blocked (not allowed): {first_word_base}")
        return False, f"Command '{first_word_base}' is not in the allowed list: {ALLOWED_COMMANDS}"

    return True, "ok"


def validate(command: str, working_dir: str) -> tuple[bool, str]:
    """
    Single entry point for tools.py.
    Both the command AND the directory must pass validation.
    """
    cmd_safe, cmd_reason = is_command_safe(command)
    if not cmd_safe:
        return False, cmd_reason

    path_safe, path_reason = is_path_safe(working_dir)
    if not path_safe:
        return False, path_reason

    log.debug(f"Validated: {command[:60]} in {working_dir}")
    return True, "ok"
