"""
Centralized configuration for the Setup Agent.

All settings are loaded from environment variables with sensible defaults.
Every module imports from here instead of reading .env directly.
"""

import os
from pathlib import Path
from dataclasses import dataclass, field
from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Config:
    """Immutable application configuration — loaded once at startup."""

    # ── LLM ──────────────────────────────────────────────────────────────
    llm_model: str = os.getenv("LLM_MODEL", "llama-3.3-70b-versatile")
    groq_api_key: str = os.getenv("GROQAPI", "")

    # ── Notification (ntfy.sh) ───────────────────────────────────────────
    ntfy_base_url: str = os.getenv("NTFY_BASE_URL", "https://ntfy.sh")
    ntfy_inbox_topic: str = os.getenv("NTFY_INBOX_TOPIC", "")
    ntfy_update_topic: str = os.getenv("NTFY_UPDATE_TOPIC", "")

    # ── Sandbox ──────────────────────────────────────────────────────────
    projects_dir: Path = field(
        default_factory=lambda: Path(
            os.getenv("PROJECTS_DIR", str(Path.home() / "Desktop" / "Projects"))
        ).resolve()
    )
    max_command_length: int = int(os.getenv("MAX_COMMAND_LENGTH", "500"))
    max_path_depth: int = int(os.getenv("MAX_PATH_DEPTH", "6"))
    default_command_timeout: int = int(os.getenv("DEFAULT_COMMAND_TIMEOUT", "120"))
    heavy_command_timeout: int = int(os.getenv("HEAVY_COMMAND_TIMEOUT", "300"))

    # ── Agent ────────────────────────────────────────────────────────────
    max_iterations: int = int(os.getenv("MAX_AGENT_ITERATIONS", "30"))
    max_output_chars: int = int(os.getenv("MAX_OUTPUT_CHARS", "4000"))

    # ── Input validation ─────────────────────────────────────────────────
    min_message_length: int = 3
    max_message_length: int = 500

    # ── Notifications ────────────────────────────────────────────────────
    notification_cooldown_seconds: float = 5.0

    # ── Post-setup hooks ─────────────────────────────────────────────────
    hook_open_vscode: bool = os.getenv("HOOK_OPEN_VSCODE", "true").lower() == "true"
    hook_show_commands: bool = os.getenv("HOOK_SHOW_COMMANDS", "true").lower() == "true"

    # ── Web dashboard ────────────────────────────────────────────────────
    web_port: int = int(os.getenv("WEB_PORT", "8745"))

    def validate(self) -> list[str]:
        """Return a list of configuration warnings (empty = all good)."""
        warnings = []
        if not self.groq_api_key:
            warnings.append("GROQAPI is not set — LLM calls will fail")
        if not self.ntfy_inbox_topic:
            warnings.append("NTFY_INBOX_TOPIC is not set — listener won't work")
        if not self.ntfy_update_topic:
            warnings.append("NTFY_UPDATE_TOPIC is not set — notifications won't send")
        if not self.projects_dir.exists():
            warnings.append(f"Projects directory does not exist: {self.projects_dir}")
        return warnings


# ── Singleton ────────────────────────────────────────────────────────────────
# Every module does: from .config import cfg
cfg = Config()
