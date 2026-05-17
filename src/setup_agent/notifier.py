"""
Notification system for the Setup Agent.

Handles two-way communication with your phone via ntfy.sh:
  - send()         → push a notification to your phone
  - send_summary() → push a rich final summary
  - listen()       → stream incoming messages from your phone

Features:
  - Notification levels (info, success, error, progress)
  - Rate limiting to prevent notification spam
  - Exponential backoff on connection loss
  - Message batching for progress updates
"""

import json
import time
import threading
import requests
from .config import cfg
from .logger import get_logger

log = get_logger("notifier")

_last_send_time = 0.0
_send_lock = threading.Lock()

LEVEL_CONFIG = {
    "info": {"priority": "low", "tags": "information_source"},
    "progress": {"priority": "low", "tags": "hourglass_flowing_sand"},
    "success": {"priority": "default", "tags": "white_check_mark"},
    "error": {"priority": "high", "tags": "x"},
    "milestone": {"priority": "default", "tags": "rocket"},
}


def send(message: str, title: str = "Setup Agent", level: str = "info", force: bool = False) -> bool:
    """
    Sends a notification to your phone via ntfy.sh.

    Args:
        message:  The notification body text
        title:    Bold heading in the notification
        level:    One of: info, progress, success, error, milestone
        force:    If True, bypass rate limiting (for errors and summaries)

    Returns True if sent successfully, False otherwise.
    The agent keeps running even if notifications fail.
    """
    global _last_send_time

    if not cfg.ntfy_update_topic:
        log.warning("NTFY_UPDATE_TOPIC not set — skipping notification")
        return False

    if not force:
        with _send_lock:
            now = time.time()
            elapsed = now - _last_send_time
            if elapsed < cfg.notification_cooldown_seconds:
                log.debug(f"Rate limited — skipping notification ({elapsed:.1f}s since last)")
                return False

    level_cfg = LEVEL_CONFIG.get(level, LEVEL_CONFIG["info"])

    try:
        response = requests.post(
            f"{cfg.ntfy_base_url}/{cfg.ntfy_update_topic}",
            data=message.encode("utf-8"),
            headers={
                "Title": title.encode("utf-8"),
                "Priority": level_cfg["priority"],
                "Tags": level_cfg["tags"],
            },
            timeout=10,
        )

        with _send_lock:
            _last_send_time = time.time()

        if response.status_code == 200:
            log.debug(f"Notification sent: {title}")
            return True
        else:
            log.warning(f"ntfy returned status {response.status_code}")
            return False

    except requests.RequestException as e:
        log.error(f"Failed to send notification: {e}")
        return False


def send_summary(project_name: str, project_type: str, path: str, extras: list[str] | None = None) -> bool:
    """Sends a rich, formatted final summary notification."""
    lines = [
        f"📁 Project: {project_name}",
        f"🔧 Type: {project_type}",
        f"📍 Path: {path}",
    ]
    if extras:
        lines.append("")
        lines.append("📦 What was set up:")
        for item in extras:
            lines.append(f"  • {item}")
    message = "\n".join(lines)
    return send(message, title="Setup Complete ✅", level="success", force=True)


def listen(on_message):
    """
    Opens a persistent streaming connection to ntfy.sh and waits for messages.
    Uses exponential backoff on connection loss (5s → 10s → 20s → 60s cap).
    """
    if not cfg.ntfy_inbox_topic:
        log.error("NTFY_INBOX_TOPIC not set — cannot listen for messages")
        return

    url = f"{cfg.ntfy_base_url}/{cfg.ntfy_inbox_topic}/json"
    log.info(f"Listening on topic: {cfg.ntfy_inbox_topic}")
    backoff = 5

    while True:
        try:
            with requests.get(url, stream=True, timeout=None) as response:
                backoff = 5
                for raw_line in response.iter_lines():
                    if not raw_line:
                        continue
                    try:
                        event = json.loads(raw_line)
                    except json.JSONDecodeError:
                        log.warning(f"Invalid JSON from ntfy: {raw_line[:100]}")
                        continue

                    if event.get("event") == "message":
                        message_text = event.get("message", "").strip()
                        if message_text:
                            log.info(f"Received message: {message_text}")
                            on_message(message_text)
                        else:
                            log.debug("Received empty message — ignoring")

        except requests.RequestException as e:
            log.warning(f"Connection lost: {e}. Reconnecting in {backoff}s...")
            time.sleep(backoff)
            backoff = min(backoff * 2, 60)
        except Exception as e:
            log.error(f"Unexpected listener error: {e}. Reconnecting in {backoff}s...")
            time.sleep(backoff)
            backoff = min(backoff * 2, 60)
