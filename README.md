# 🤖 Setup Agent

**AI-powered multi-language project scaffolder** — send a message from your phone or terminal, get a fully configured project on your laptop with a beautiful live dashboard.

<p align="center">
  <img src="https://img.shields.io/badge/python-3.12+-blue?logo=python&logoColor=white" alt="Python 3.12+">
  <img src="https://img.shields.io/badge/LangChain-agent-green?logo=chainlink&logoColor=white" alt="LangChain">
  <img src="https://img.shields.io/badge/Groq-LLM-orange?logo=lightning&logoColor=white" alt="Groq">
  <img src="https://img.shields.io/badge/13-templates-purple" alt="13 Templates">
  <img src="https://img.shields.io/badge/version-2.1.0-brightgreen" alt="Version 2.1.0">
</p>

---

## ✨ Features

### 🎨 Rich Terminal Dashboard
Beautiful live-updating terminal UI with status panels, progress tracking, and command history — powered by [Rich](https://github.com/Textualize/rich).

### 🌐 Web Dashboard
Local browser-based dashboard at `http://localhost:8745` with real-time stats, project history, health checks, and the ability to trigger new builds.

### 📱 Phone-to-Laptop Pipeline
Send a natural language message via [ntfy.sh](https://ntfy.sh) from your phone → agent scaffolds the project → sends you a completion notification.

### 🧠 Multi-Language AI Agent
Supports **13 project types** across 7 ecosystems — the LLM detects what you want and picks the right setup flow.

### 🔄 Auto-Rollback
If a setup fails midway, the agent automatically cleans up the incomplete project directory.

### 🏥 Health Checks
Verify created projects actually work — TypeScript compilation, package integrity, git initialization, and more.

### 📊 Project History
SQLite-backed history database tracks every project: timing, status, command logs, and aggregate statistics.

### 🖥️ Professional CLI
Full command-line interface with subcommands — no more remembering `python main.py` invocations.

### 🔒 Hardened Sandbox
Multi-layer security: command allowlisting, shell injection prevention, path sandboxing, input validation.

---

## 🚀 Supported Project Types

| Category | Templates | Package Manager |
|----------|-----------|-----------------|
| **Frontend** | React (Vite), Next.js, Svelte, Vanilla Vite | npm / npx |
| **Backend (JS)** | Express + TypeScript | npm |
| **Backend (Python)** | Flask, Django, FastAPI | uv |
| **Python** | Plain Python project | uv |
| **TypeScript** | Plain TypeScript | npm / tsc |
| **Systems** | Rust, Go | cargo / go |
| **Mobile** | Flutter | flutter |

---

## 🏗️ Architecture

```
📱 Phone (ntfy.sh)  ──→  main.py (listener + queue)
🖥️  Terminal (CLI)   ──→       │
🌐 Web Dashboard     ──→       │
                              ▼
                         agent.py (LangChain + Groq LLM)
                              │
                    ┌─────────┼─────────┐
                    ▼         ▼         ▼
              tools.py   templates.py  hooks.py
                    │
              ┌─────┼─────┐
              ▼     ▼     ▼
          sandbox  history  rollback
              │
              ▼
        subprocess (shell commands)
```

| Module | Purpose |
|--------|---------|
| `cli.py` | Click-based CLI with 7 subcommands |
| `main.py` | Request queue, input validation, lifecycle orchestration |
| `agent.py` | LangChain agent with multi-language system prompt |
| `tools.py` | Sandboxed tools the LLM can invoke |
| `templates.py` | 13 project template definitions |
| `dashboard.py` | Rich Live terminal dashboard |
| `web/server.py` | HTTP API for the web dashboard |
| `web/index.html` | Browser-based dashboard UI |
| `sandbox.py` | Security layer (command + path validation) |
| `history.py` | SQLite project history database |
| `rollback.py` | Auto-rollback on setup failure |
| `hooks.py` | Post-setup hooks (VS Code, start commands) |
| `healthcheck.py` | Per-language project verification |
| `config.py` | Centralized configuration from env vars |
| `logger.py` | Structured logging (console + file) |
| `notifier.py` | ntfy.sh communication with rate limiting |

---

## 📦 Setup

### Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) package manager
- [ntfy.sh](https://ntfy.sh) app on your phone
- A free [Groq API key](https://console.groq.com)

### Install

```bash
git clone https://github.com/yourusername/SetUp-Agent.git
cd SetUp-Agent
uv sync
```

### Configure

Create a `.env` file:

```env
# Required
GROQAPI=your_groq_api_key_here

# Notifications (ntfy.sh)
NTFY_INBOX_TOPIC=your-unique-inbox-topic
NTFY_UPDATE_TOPIC=your-unique-updates-topic

# Optional
LLM_MODEL=llama-3.3-70b-versatile
PROJECTS_DIR=/home/you/Desktop/Projects
HOOK_OPEN_VSCODE=true
WEB_PORT=8745
```

---

## 🖥️ Usage

### CLI Commands

```bash
# Listen for phone messages (with live dashboard + web UI)
setup-agent listen

# Listen without dashboards
setup-agent listen --no-dashboard --no-web

# Create a project directly from terminal
setup-agent create "react app with tailwind"

# Dry run — show matched template without executing
setup-agent create --dry-run "flask api for a blog"

# View project history
setup-agent history
setup-agent history --limit 5
setup-agent history --json-output

# Show aggregate statistics
setup-agent stats

# List available templates
setup-agent templates

# Run health check on a project
setup-agent check my-project-name

# Open web dashboard in browser
setup-agent dashboard
```

### Example Messages

```
"create a react app called dashboard"
"set up a python flask api for a blog"
"make a next.js app with tailwind"
"initialize a rust project called cli-tool"
"create an express typescript api with jwt and mongodb"
"set up a fastapi project"
"make a go project called web-scraper"
"create a django project for an e-commerce site"
```

---

## 🔒 Security

| Layer | Protection |
|-------|-----------|
| **Command Allowlist** | Only approved programs can run (npm, uv, git, cargo, etc.) |
| **Shell Injection** | `&&`, `;`, `\|`, `` ` ``, `$()` all blocked |
| **Destructive Commands** | rm, sudo, kill, shutdown blocked |
| **Path Sandboxing** | All operations confined to `PROJECTS_DIR` |
| **Path Traversal** | `../` blocked, paths resolved before checking |
| **Command Length** | 500 char limit prevents LLM hallucination exploits |
| **Input Validation** | Adversarial prompt injection patterns rejected |
| **Request Queue** | Max 5 queued requests prevents resource exhaustion |
| **Auto-Rollback** | Failed setups are automatically cleaned up |

---

## 📊 Web Dashboard

Access at `http://localhost:8745` when running `setup-agent listen` or `setup-agent dashboard`.

**Features:**
- Real-time project statistics
- Full project history table
- One-click health checks
- Create projects from browser
- Template browser with click-to-use
- Auto-refreshes every 10 seconds

---

## 📁 Project Structure

```
SetUp-Agent/
├── cli.py              # Click CLI entry point
├── main.py             # Listener, queue, lifecycle
├── agent.py            # LangChain agent
├── tools.py            # Sandboxed tool functions
├── templates.py        # 13 project templates
├── sandbox.py          # Security layer
├── config.py           # Centralized config
├── logger.py           # Structured logging
├── notifier.py         # ntfy.sh communication
├── dashboard.py        # Rich terminal UI
├── history.py          # SQLite history DB
├── rollback.py         # Auto-rollback system
├── hooks.py            # Post-setup hooks
├── healthcheck.py      # Project verification
├── web/
│   ├── server.py       # HTTP API server
│   └── index.html      # Web dashboard
├── pyproject.toml
├── .env                # Your config (git-ignored)
└── README.md
```

---

## 🛠️ Tech Stack

- **AI**: LangChain + Groq (Llama 3.3 70B)
- **Terminal UI**: Rich (live dashboard, tables, panels)
- **CLI**: Click
- **Web**: Vanilla HTML/JS + Tailwind CSS CDN
- **Database**: SQLite (stdlib)
- **Notifications**: ntfy.sh
- **Package Manager**: uv

---

## License

MIT
