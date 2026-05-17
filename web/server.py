"""
Web dashboard server for the Setup Agent.

Serves a local web UI at http://localhost:8745 with:
  - JSON API endpoints for history, stats, health checks
  - Static file serving for the dashboard HTML
  - Trigger new project setups from the browser

Built with Python stdlib (http.server) — no Flask/Django needed.
"""

import json
import threading
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from logger import get_logger
from config import cfg

log = get_logger("web")

WEB_DIR = Path(__file__).parent
STATIC_DIR = WEB_DIR
PORT = 8745


class DashboardHandler(SimpleHTTPRequestHandler):
    """HTTP request handler for the web dashboard."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(STATIC_DIR), **kwargs)

    def log_message(self, format, *args):
        """Suppress default access logs — we use our own logger."""
        pass

    def do_GET(self):
        """Handle GET requests."""
        parsed = urlparse(self.path)
        path = parsed.path

        # API routes
        if path == "/api/status":
            return self._json_response(self._get_status())
        elif path == "/api/history":
            return self._json_response(self._get_history())
        elif path == "/api/stats":
            return self._json_response(self._get_stats())
        elif path == "/api/templates":
            return self._json_response(self._get_templates())
        elif path.startswith("/api/health/"):
            project_name = path.split("/api/health/", 1)[1]
            return self._json_response(self._get_health(project_name))
        elif path == "/" or path == "/index.html":
            return self._serve_dashboard()
        else:
            super().do_GET()

    def do_POST(self):
        """Handle POST requests."""
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/api/create":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode("utf-8")
            try:
                data = json.loads(body)
                return self._json_response(self._trigger_create(data))
            except json.JSONDecodeError:
                return self._json_response({"error": "Invalid JSON"}, status=400)
        else:
            self.send_error(404)

    def _json_response(self, data: dict, status: int = 200):
        """Send a JSON response."""
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data, default=str).encode("utf-8"))

    def _serve_dashboard(self):
        """Serve the main dashboard HTML."""
        html_path = STATIC_DIR / "index.html"
        if html_path.exists():
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(html_path.read_bytes())
        else:
            self.send_error(404, "Dashboard not found")

    # ── API Handlers ─────────────────────────────────────────────────────

    def _get_status(self) -> dict:
        """Get current agent status."""
        import time
        return {
            "status": "running",
            "model": cfg.llm_model,
            "projects_dir": str(cfg.projects_dir),
            "timestamp": time.time(),
        }

    def _get_history(self) -> dict:
        """Get project history."""
        from history import history_db
        try:
            projects = history_db.get_all(limit=100)
            return {"projects": projects}
        except Exception as e:
            return {"projects": [], "error": str(e)}

    def _get_stats(self) -> dict:
        """Get aggregate stats."""
        from history import history_db
        try:
            return history_db.get_stats()
        except Exception as e:
            return {"error": str(e)}

    def _get_templates(self) -> dict:
        """Get available templates."""
        from templates import TEMPLATES
        templates = []
        for name, tmpl in TEMPLATES.items():
            templates.append({
                "name": name,
                "description": tmpl["description"],
                "keywords": tmpl["detect"],
                "steps": tmpl["steps"],
            })
        return {"templates": templates}

    def _get_health(self, project_name: str) -> dict:
        """Run health check on a project."""
        from healthcheck import run_health_check
        project_path = cfg.projects_dir / project_name
        return run_health_check(str(project_path))

    def _trigger_create(self, data: dict) -> dict:
        """Trigger a new project creation."""
        message = data.get("message", "").strip()
        if not message:
            return {"error": "No message provided"}

        # Import here to avoid circular imports
        from main import handle_new_request
        try:
            handle_new_request(message)
            return {"status": "queued", "message": message}
        except Exception as e:
            return {"error": str(e)}


def start_web_server(port: int = PORT, background: bool = True):
    """Start the web dashboard server."""
    server = HTTPServer(("0.0.0.0", port), DashboardHandler)
    log.info(f"Web dashboard starting at http://localhost:{port}")

    if background:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        return server
    else:
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            server.shutdown()
            log.info("Web server stopped")
