"""
Main entry point for the Setup Agent.

Handles:
  - Listening for incoming requests from your phone via ntfy.sh
  - Input validation (length, content)
  - Request queuing (one agent run at a time, rest queued)
  - Graceful shutdown on SIGINT/SIGTERM
  - History tracking + auto-rollback on failure
  - Post-setup hooks (VS Code, getting-started commands)
  - Rich terminal dashboard + web dashboard
  - CLI mode for local testing
"""

import sys
import signal
import threading
import queue
from config import cfg
from logger import get_logger

log = get_logger("main")

# ── Request Queue ────────────────────────────────────────────────────────────
_request_queue: queue.Queue = queue.Queue(maxsize=5)
_shutdown_event = threading.Event()

# Dashboard reference (set in main() if enabled)
_dashboard = None


# ── Input Validation ─────────────────────────────────────────────────────────

def validate_input(message: str) -> tuple[bool, str]:
    """
    Validates incoming messages before passing to the agent.
    Catches: empty messages, too short, too long, suspicious content.
    """
    if not message or not message.strip():
        return False, "Empty message"

    stripped = message.strip()

    if len(stripped) < cfg.min_message_length:
        return False, f"Message too short (min {cfg.min_message_length} chars)"

    if len(stripped) > cfg.max_message_length:
        return False, f"Message too long (max {cfg.max_message_length} chars)"

    adversarial_patterns = [
        "ignore previous", "ignore all", "forget your instructions",
        "you are now", "pretend you are", "act as root",
        "delete everything", "format disk", "rm -rf",
    ]
    lower = stripped.lower()
    for pattern in adversarial_patterns:
        if pattern in lower:
            return False, f"Message contains blocked pattern: '{pattern}'"

    return True, "ok"


# ── Process Request ──────────────────────────────────────────────────────────

def process_request(message: str):
    """
    Run the full agent pipeline for a single request.

    Handles: history recording, rollback tracking, agent execution,
    post-setup hooks, dashboard updates, and error recovery.
    """
    from agent import run_agent
    from notifier import send
    from history import history_db
    from rollback import start_tracking, stop_tracking
    from hooks import run_post_setup_hooks, format_start_commands
    from templates import find_template

    # Detect project type from message
    template_match = find_template(message)
    project_type = template_match["name"] if template_match else "unknown"

    # Generate a project name for tracking (agent will create the real one)
    import re
    words = re.sub(r'[^a-zA-Z0-9\s]', '', message).lower().split()
    tracking_name = "-".join(words[:4]) or "project"

    # Start tracking
    history_db.record_start(tracking_name, project_type=project_type, user_message=message)
    tracker = start_tracking(tracking_name)

    # Update dashboard
    if _dashboard:
        _dashboard.set_task(tracking_name, message)

    log.info(f"Processing request: {message[:80]}")
    send(f"🔄 Working on: '{message[:100]}'", title="Agent Started ⏳", level="progress")

    try:
        result = run_agent(message)
        log.info("Agent finished successfully")

        # Determine the actual project path from the tracker
        project_path = str(tracker.project_dir) if tracker.project_dir else ""

        # Update history with success
        history_db.update_project_info(tracking_name, project_type=project_type, path=project_path)
        history_db.record_complete(tracking_name, status="success")

        # Run post-setup hooks
        hook_results = {}
        if project_path and project_type != "unknown":
            hook_results = run_post_setup_hooks(tracking_name, project_type, project_path)

        # Build final notification message
        final_message = result
        if hook_results.get("start_commands"):
            start_cmds = format_start_commands(project_type, project_path)
            if start_cmds:
                final_message += start_cmds

        send(final_message, title="Setup Complete ✅", level="success", force=True)

    except Exception as e:
        error_msg = f"Agent crashed: {str(e)}"
        log.error(error_msg)

        # Auto-rollback
        if tracker and tracker.project_dir and tracker.project_dir.exists():
            log.info("Auto-rolling back failed project...")
            rolled_back = tracker.rollback()
            status = "rolled_back" if rolled_back else "failed"
            history_db.record_complete(tracking_name, status=status, error_message=str(e))
            if rolled_back:
                error_msg += "\n\n🔄 The incomplete project has been automatically cleaned up."
        else:
            history_db.record_complete(tracking_name, status="failed", error_message=str(e))

        send(error_msg, title="Agent Error ❌", level="error", force=True)

        if _dashboard:
            _dashboard.set_error(str(e))

    finally:
        stop_tracking()
        if _dashboard:
            _dashboard.set_idle()


# ── Worker Thread ────────────────────────────────────────────────────────────

def _worker():
    """Background worker that processes requests from the queue one at a time."""
    log.info("Worker thread started — waiting for requests")

    while not _shutdown_event.is_set():
        try:
            message = _request_queue.get(timeout=1.0)
        except queue.Empty:
            continue

        if _dashboard:
            _dashboard.set_queue_size(_request_queue.qsize())

        process_request(message)
        _request_queue.task_done()

    log.info("Worker thread shutting down")


# ── Message Handler ──────────────────────────────────────────────────────────

def handle_new_request(message: str):
    """
    Callback fired by notifier.listen() every time a push notification arrives.
    Also called by the web dashboard's /api/create endpoint.
    """
    from notifier import send

    is_valid, reason = validate_input(message)
    if not is_valid:
        log.warning(f"Message rejected: {reason}")
        send(f"⚠️ Message rejected: {reason}", title="Invalid Request", level="error", force=True)
        return

    try:
        _request_queue.put_nowait(message)
        queue_size = _request_queue.qsize()

        if _dashboard:
            _dashboard.set_queue_size(queue_size)

        if queue_size > 1:
            send(
                f"📋 Your request is queued (position {queue_size}). "
                f"I'll work on it after the current task finishes.",
                title="Request Queued 📋",
                level="info",
                force=True,
            )
            log.info(f"Request queued (position {queue_size}): {message[:60]}")
        else:
            log.info(f"Request accepted: {message[:60]}")

    except queue.Full:
        log.warning("Request queue is full — rejecting request")
        send(
            "🚫 I'm too busy right now — 5 tasks are already queued. "
            "Please try again later.",
            title="Queue Full 🚫",
            level="error",
            force=True,
        )


# ── Graceful Shutdown ────────────────────────────────────────────────────────

def _signal_handler(signum, frame):
    sig_name = signal.Signals(signum).name
    log.info(f"Received {sig_name} — shutting down gracefully...")
    _shutdown_event.set()
    if _dashboard:
        _dashboard.stop()


# ── Main ─────────────────────────────────────────────────────────────────────

def main(use_dashboard: bool = True, use_web: bool = True):
    """Start the agent in listener mode with optional dashboard and web server."""
    global _dashboard

    from notifier import listen

    # Validate configuration
    warnings = cfg.validate()
    if warnings:
        for w in warnings:
            log.warning(f"Config warning: {w}")

    # Register signal handlers
    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    # Start Rich terminal dashboard
    if use_dashboard:
        try:
            from dashboard import Dashboard
            _dashboard = Dashboard()
            _dashboard.start()

            # Provide dashboard reference to tools
            from tools import set_dashboard
            set_dashboard(_dashboard)
        except Exception as e:
            log.warning(f"Failed to start terminal dashboard: {e}")
            use_dashboard = False

    if not use_dashboard:
        # Print banner to console if dashboard is disabled
        log.info("═" * 55)
        log.info("🤖 Setup Agent v2.1 — Multi-Language Project Scaffolder")
        log.info("═" * 55)
        log.info(f"  LLM Model:    {cfg.llm_model}")
        log.info(f"  Projects Dir: {cfg.projects_dir}")
        log.info(f"  Inbox Topic:  {cfg.ntfy_inbox_topic}")
        log.info(f"  Max Queue:    5 concurrent requests")
        log.info("═" * 55)

    # Start web dashboard
    if use_web:
        try:
            from web.server import start_web_server
            start_web_server(port=cfg.web_port, background=True)
            log.info(f"Web dashboard: http://localhost:{cfg.web_port}")
        except Exception as e:
            log.warning(f"Failed to start web dashboard: {e}")

    # Start worker thread
    worker_thread = threading.Thread(target=_worker, daemon=True)
    worker_thread.start()

    # Start listener (blocks until shutdown)
    try:
        listen(handle_new_request)
    except Exception as e:
        log.error(f"Listener crashed: {e}")
    finally:
        _shutdown_event.set()
        if _dashboard:
            _dashboard.stop()
        worker_thread.join(timeout=5)
        log.info("Agent shut down cleanly")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        if sys.argv[1] == "--dry-run" and len(sys.argv) > 2:
            test_msg = " ".join(sys.argv[2:])
            log.info(f"[DRY RUN] Would process: {test_msg}")
            is_valid, reason = validate_input(test_msg)
            if is_valid:
                log.info("[DRY RUN] Input validation: PASSED ✅")
                from templates import find_template
                match = find_template(test_msg)
                if match:
                    log.info(f"[DRY RUN] Matched template: {match['name']} — {match['description']}")
                else:
                    log.info("[DRY RUN] No template matched — agent will use general knowledge")
            else:
                log.info(f"[DRY RUN] Input validation: FAILED ❌ ({reason})")
        else:
            test_msg = " ".join(sys.argv[1:])
            is_valid, reason = validate_input(test_msg)
            if not is_valid:
                log.error(f"Invalid input: {reason}")
                sys.exit(1)

            log.info(f"CLI mode — processing: {test_msg}")
            process_request(test_msg)
    else:
        main()