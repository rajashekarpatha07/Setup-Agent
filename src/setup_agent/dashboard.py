"""
Rich terminal dashboard for the Setup Agent.

Renders a beautiful live TUI with:
  - Status panel (listening/working, model, uptime)
  - Current task panel (steps, progress bar)
  - Recent history panel
  - Live-updating via Rich's Live renderer

Usage:
    from .dashboard import Dashboard
    dash = Dashboard()
    dash.start()
    dash.set_task("flask api", "Setup a flask api")
    dash.add_step("npm init -y", "success")
    dash.set_idle()
    dash.stop()
"""

import time
import threading
from datetime import datetime, timedelta
from rich.live import Live
from rich.table import Table
from rich.panel import Panel
from rich.layout import Layout
from rich.text import Text
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskID
from rich.console import Console, Group
from rich.align import Align
from rich import box
from .history import history_db
from .logger import get_logger

log = get_logger("dashboard")

STATUS_DISPLAY = {
    "listening": ("🟢", "Listening", "green"),
    "working": ("🔵", "Working", "blue"),
    "error": ("🔴", "Error", "red"),
    "shutdown": ("⚫", "Shutting Down", "dim"),
}


class Dashboard:
    """Rich Live terminal dashboard."""

    def __init__(self, console: Console | None = None):
        self.console = console or Console()
        self._live: Live | None = None
        self._lock = threading.Lock()
        self._status = "listening"
        self._start_time = time.time()
        self._current_task: str | None = None
        self._current_message: str | None = None
        self._task_start_time: float | None = None
        self._steps: list[dict] = []
        self._queue_size: int = 0

    def start(self):
        """Start the live dashboard rendering."""
        self._live = Live(self._render(), console=self.console, refresh_per_second=2, screen=False)
        self._live.start()
        log.debug("Dashboard started")

    def stop(self):
        """Stop the live dashboard."""
        if self._live:
            self._live.stop()
            self._live = None
            log.debug("Dashboard stopped")

    def _refresh(self):
        if self._live:
            try:
                self._live.update(self._render())
            except Exception:
                pass

    def set_task(self, project_name: str, user_message: str):
        with self._lock:
            self._status = "working"
            self._current_task = project_name
            self._current_message = user_message
            self._task_start_time = time.time()
            self._steps = []
        self._refresh()

    def add_step(self, command: str, status: str = "running", duration: float = 0.0):
        with self._lock:
            for step in self._steps:
                if step["command"] == command and step["status"] == "running":
                    step["status"] = status
                    step["duration"] = duration
                    self._refresh()
                    return
            self._steps.append({"command": command, "status": status, "duration": duration})
        self._refresh()

    def set_idle(self):
        with self._lock:
            self._status = "listening"
            self._current_task = None
            self._current_message = None
            self._task_start_time = None
            self._steps = []
        self._refresh()

    def set_queue_size(self, size: int):
        with self._lock:
            self._queue_size = size
        self._refresh()

    def set_error(self, message: str = ""):
        with self._lock:
            self._status = "error"
        self._refresh()

    def _render(self) -> Layout:
        layout = Layout()
        layout.split_column(
            Layout(name="header", size=6),
            Layout(name="body"),
            Layout(name="footer", size=3),
        )
        layout["body"].split_column(
            Layout(name="task", size=None),
            Layout(name="history", size=10),
        )
        layout["header"].update(self._render_header())
        layout["task"].update(self._render_task())
        layout["history"].update(self._render_history())
        layout["footer"].update(self._render_footer())
        return layout

    def _render_header(self) -> Panel:
        emoji, status_text, color = STATUS_DISPLAY.get(self._status, STATUS_DISPLAY["listening"])
        uptime = timedelta(seconds=int(time.time() - self._start_time))
        from .config import cfg
        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column(style="bold cyan", min_width=12)
        table.add_column()
        table.add_row("Status", f"{emoji}  [{color}]{status_text}[/]")
        table.add_row("Model", f"[dim]{cfg.llm_model}[/]")
        table.add_row("Uptime", f"[dim]{uptime}[/]")
        if self._queue_size > 0:
            table.add_row("Queue", f"[yellow]{self._queue_size} pending[/]")
        return Panel(table, title="[bold bright_white]🤖 Setup Agent[/]", border_style="bright_blue", box=box.DOUBLE)

    def _render_task(self) -> Panel:
        if self._status != "working" or not self._current_task:
            waiting_text = Text("Waiting for requests...", style="dim italic")
            return Panel(Align.center(waiting_text, vertical="middle"), title="[bold]Current Task[/]", border_style="dim", box=box.ROUNDED)

        elapsed = time.time() - (self._task_start_time or time.time())
        lines = []
        msg = self._current_message or ""
        if len(msg) > 80:
            msg = msg[:77] + "..."
        lines.append(Text(f'📨 "{msg}"', style="bold"))
        lines.append(Text(f"⏱  Started {elapsed:.0f}s ago", style="dim"))
        lines.append(Text(""))

        completed = sum(1 for s in self._steps if s["status"] in ("success", "SUCCESS"))
        total = max(len(self._steps), 1)
        progress_text = f"Step {completed}/{total}"
        lines.append(Text(f"{'━' * completed}{'╸' if self._steps else ''}{'━' * max(0, total - completed - 1)}  {progress_text}", style="bright_blue"))
        lines.append(Text(""))

        for step in self._steps[-10:]:
            cmd = step["command"]
            if len(cmd) > 60:
                cmd = cmd[:57] + "..."
            if step["status"] in ("success", "SUCCESS"):
                icon, style = "✅", "green"
            elif step["status"] in ("failed", "FAILED"):
                icon, style = "❌", "red"
            elif step["status"] == "running":
                icon, style = "⏳", "yellow"
            else:
                icon, style = "○", "dim"
            duration_str = f" ({step['duration']:.1f}s)" if step['duration'] > 0 else ""
            lines.append(Text(f"  {icon} {cmd}{duration_str}", style=style))

        content = Group(*lines)
        return Panel(content, title=f"[bold]Current Task — [cyan]{self._current_task}[/][/]", border_style="bright_blue", box=box.ROUNDED)

    def _render_history(self) -> Panel:
        try:
            recent = history_db.get_recent(5)
        except Exception:
            recent = []
        if not recent:
            return Panel(Align.center(Text("No projects yet", style="dim italic"), vertical="middle"), title="[bold]Recent History[/]", border_style="dim", box=box.ROUNDED)

        table = Table(box=box.SIMPLE_HEAVY, show_edge=False, padding=(0, 1))
        table.add_column("#", style="dim", width=4)
        table.add_column("Project", style="cyan", min_width=25)
        table.add_column("Type", style="magenta", width=15)
        table.add_column("Status", width=8)
        table.add_column("Duration", style="dim", width=10)

        for i, project in enumerate(recent):
            status = project.get("status", "unknown")
            if status == "success":
                status_display = "[green]✅[/]"
            elif status == "failed":
                status_display = "[red]❌[/]"
            elif status == "rolled_back":
                status_display = "[yellow]🔄[/]"
            else:
                status_display = "[blue]⏳[/]"
            duration = project.get("duration_seconds", 0)
            duration_str = f"{duration:.0f}s" if duration > 0 else "-"
            table.add_row(
                f"#{project.get('id', i+1)}",
                project.get("name", "unknown"),
                project.get("project_type", "-"),
                status_display,
                duration_str,
            )
        return Panel(table, title="[bold]Recent History[/]", border_style="dim", box=box.ROUNDED)

    def _render_footer(self) -> Panel:
        now = datetime.now().strftime("%H:%M:%S")
        footer = Text(f" 📡 ntfy.sh  │  🕐 {now}  │  Ctrl+C to quit ", style="dim")
        return Panel(footer, box=box.SIMPLE, style="dim")
