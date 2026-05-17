# Contributing to Setup Agent

Thanks for your interest in contributing! Here's how to get started.

## 🚀 Quick Start

```bash
# 1. Fork and clone the repo
git clone https://github.com/<your-username>/SetUp-Agent.git
cd SetUp-Agent

# 2. Install dependencies
uv sync

# 3. Set up your environment
cp .env.example .env
# Edit .env with your Groq API key and ntfy topics

# 4. Run the agent
uv run setup-agent --help
```

## 📁 Project Structure

```
src/setup_agent/         # Main package
├── agent.py             # LangChain agent (the brain)
├── cli.py               # Click CLI entry point
├── config.py            # Environment-based configuration
├── tools.py             # Sandboxed tool functions
├── templates.py         # Project template definitions
├── sandbox.py           # Security layer
├── main.py              # Listener + request queue
├── dashboard.py         # Rich terminal dashboard
├── history.py           # SQLite history database
├── rollback.py          # Auto-rollback system
├── hooks.py             # Post-setup automation
├── healthcheck.py       # Project verification
├── logger.py            # Structured logging
├── notifier.py          # ntfy.sh communication
└── web/                 # Web dashboard
    ├── server.py        # HTTP API server
    └── index.html       # Browser dashboard UI
```

## 🛠️ Development Workflow

1. **Create a branch** from `main`:
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes** — follow existing code style:
   - Use type hints
   - Add docstrings to public functions
   - Use `from .module import thing` (relative imports)

3. **Test your changes**:
   ```bash
   # Verify imports
   uv run python -c "from setup_agent.config import Config; print('✅')"

   # Verify CLI
   uv run setup-agent --help

   # Dry-run a template
   uv run setup-agent create --dry-run "create a flask api"
   ```

4. **Submit a pull request** with a clear description.

## 📋 Adding a New Template

1. Open `src/setup_agent/templates.py`
2. Add your template to the `TEMPLATES` dict:
   ```python
   "your-template": {
       "detect": ["keyword1", "keyword2"],
       "description": "Short description",
       "steps": ["command1", "command2"],
       "files": {"filename": "content"},
   }
   ```
3. Add health checks in `src/setup_agent/healthcheck.py` if needed.
4. Add getting-started commands in `src/setup_agent/hooks.py`.

## 🔒 Security

When adding new tools or commands:
- Only add programs to `ALLOWED_COMMANDS` in `sandbox.py` if they're safe
- Never allow `rm`, `sudo`, or destructive commands
- All paths must be validated through `is_path_safe()`

## 📝 Code Style

- **Python 3.12+** features are fine (type unions `X | Y`, etc.)
- **Rich** for terminal output — no bare `print()` calls
- **Relative imports** inside the package
- Keep functions focused — one function, one responsibility

## ❓ Questions?

Open an issue on GitHub — happy to help!
