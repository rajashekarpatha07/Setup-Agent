"""
Project template registry for the Setup Agent.

Each template defines:
  - detect:      keywords the agent uses to match user intent
  - description: human-readable explanation
  - steps:       ordered setup instructions the agent should follow
  - files:       config files to create after setup

The agent doesn't blindly execute these — it uses them as a reference
to know the RIGHT commands for each ecosystem. The LLM still adapts
based on the specific user request.
"""

TEMPLATES = {
    # ── JavaScript / TypeScript ──────────────────────────────────────────

    "react-vite": {
        "detect": ["react", "react app", "vite react", "frontend react"],
        "description": "React app scaffolded with Vite + TypeScript",
        "steps": [
            "npm create vite@latest . -- --template react-ts",
            "npm install",
            "git init",
        ],
        "files": {
            ".gitignore": "node_modules/\ndist/\n.env\n",
        },
    },

    "nextjs": {
        "detect": ["next", "next.js", "nextjs", "next app"],
        "description": "Next.js app with TypeScript and App Router",
        "steps": [
            "npx create-next-app@latest . --typescript --eslint --app --src-dir --tailwind --import-alias '@/*' --use-npm",
            "git init",
        ],
        "files": {},
    },

    "express-ts": {
        "detect": ["express", "express api", "node api", "backend node", "rest api node"],
        "description": "Express.js REST API with TypeScript",
        "steps": [
            "npm init -y",
            "npm install express cors dotenv",
            "npm install -D typescript @types/express @types/cors @types/node ts-node nodemon",
            "npx tsc --init",
            "mkdir -p src",
            "git init",
        ],
        "files": {
            "src/index.ts": (
                'import express from "express";\n'
                'import cors from "cors";\n'
                'import dotenv from "dotenv";\n\n'
                "dotenv.config();\n\n"
                "const app = express();\n"
                "const PORT = process.env.PORT || 3000;\n\n"
                "app.use(cors());\n"
                "app.use(express.json());\n\n"
                'app.get("/", (_req, res) => {\n'
                '  res.json({ message: "API is running" });\n'
                "});\n\n"
                "app.listen(PORT, () => {\n"
                '  console.log(`Server running on port ${PORT}`);\n'
                "});\n"
            ),
            ".env.example": "PORT=3000\n",
            ".gitignore": "node_modules/\ndist/\n.env\n",
        },
    },

    "typescript": {
        "detect": ["typescript", "ts project", "plain ts", "ts"],
        "description": "Plain TypeScript project with ts-node",
        "steps": [
            "npm init -y",
            "npm install -D typescript ts-node @types/node",
            "npx tsc --init",
            "mkdir -p src",
            "git init",
        ],
        "files": {
            "src/index.ts": 'console.log("Hello, TypeScript!");\n',
            ".gitignore": "node_modules/\ndist/\n",
        },
    },

    "vite-vanilla": {
        "detect": ["vite", "vanilla vite", "html css js", "static site"],
        "description": "Vanilla Vite project (HTML/CSS/JS or TS)",
        "steps": [
            "npm create vite@latest . -- --template vanilla-ts",
            "npm install",
            "git init",
        ],
        "files": {},
    },

    "svelte": {
        "detect": ["svelte", "sveltekit", "svelte app"],
        "description": "SvelteKit application with TypeScript",
        "steps": [
            "npx sv create . --template minimal --types ts",
            "npm install",
            "git init",
        ],
        "files": {},
    },

    # ── Python ───────────────────────────────────────────────────────────

    "python-uv": {
        "detect": ["python", "py project", "python project", "uv project", "python script"],
        "description": "Python project initialized with uv",
        "steps": [
            "uv init .",
            "git init",
        ],
        "files": {
            ".gitignore": (
                "__pycache__/\n*.py[oc]\n"
                ".venv/\n.env\n"
                "dist/\nbuild/\n*.egg-info/\n"
            ),
        },
    },

    "flask": {
        "detect": ["flask", "flask api", "python api", "python web", "python rest"],
        "description": "Flask REST API with uv",
        "steps": [
            "uv init .",
            "uv add flask flask-cors python-dotenv",
            "mkdir -p app",
            "git init",
        ],
        "files": {
            "app/__init__.py": "",
            "app/main.py": (
                "from flask import Flask\n"
                "from flask_cors import CORS\n\n"
                "def create_app():\n"
                '    app = Flask(__name__)\n'
                "    CORS(app)\n\n"
                '    @app.route("/")\n'
                "    def index():\n"
                '        return {"message": "API is running"}\n\n'
                "    return app\n\n\n"
                'if __name__ == "__main__":\n'
                "    app = create_app()\n"
                "    app.run(debug=True)\n"
            ),
            ".env.example": "FLASK_ENV=development\nFLASK_PORT=5000\n",
            ".gitignore": (
                "__pycache__/\n*.py[oc]\n"
                ".venv/\n.env\n"
                "dist/\nbuild/\n*.egg-info/\n"
            ),
        },
    },

    "django": {
        "detect": ["django", "django project", "django app"],
        "description": "Django project with uv",
        "steps": [
            "uv init .",
            "uv add django",
            "uv run django-admin startproject config .",
            "git init",
        ],
        "files": {
            ".gitignore": (
                "__pycache__/\n*.py[oc]\n"
                ".venv/\n.env\ndb.sqlite3\n"
                "staticfiles/\nmedia/\n"
            ),
        },
    },

    "fastapi": {
        "detect": ["fastapi", "fast api", "python async api"],
        "description": "FastAPI project with uvicorn and uv",
        "steps": [
            "uv init .",
            "uv add fastapi uvicorn[standard] python-dotenv",
            "mkdir -p app",
            "git init",
        ],
        "files": {
            "app/__init__.py": "",
            "app/main.py": (
                "from fastapi import FastAPI\n\n"
                "app = FastAPI()\n\n\n"
                '@app.get("/")\n'
                "async def root():\n"
                '    return {"message": "API is running"}\n'
            ),
            ".env.example": "PORT=8000\n",
            ".gitignore": (
                "__pycache__/\n*.py[oc]\n"
                ".venv/\n.env\n"
                "dist/\nbuild/\n*.egg-info/\n"
            ),
        },
    },

    # ── Systems Languages ────────────────────────────────────────────────

    "rust": {
        "detect": ["rust", "cargo", "rust project"],
        "description": "Rust project initialized with Cargo",
        "steps": [
            "cargo init .",
            "git init",
        ],
        "files": {},
    },

    "go": {
        "detect": ["go", "golang", "go project"],
        "description": "Go module project",
        "steps": [
            # Agent will fill in the module name from the project name
            "go mod init {project_name}",
            "mkdir -p cmd pkg internal",
            "git init",
        ],
        "files": {
            "cmd/main.go": (
                "package main\n\n"
                'import "fmt"\n\n'
                "func main() {\n"
                '\tfmt.Println("Hello, Go!")\n'
                "}\n"
            ),
            ".gitignore": "bin/\n*.exe\n",
        },
    },

    # ── Mobile ───────────────────────────────────────────────────────────

    "flutter": {
        "detect": ["flutter", "dart", "flutter app", "mobile app"],
        "description": "Flutter application",
        "steps": [
            "flutter create .",
            "git init",
        ],
        "files": {},
    },
}


def get_template_names() -> list[str]:
    """Return all available template names."""
    return list(TEMPLATES.keys())


def get_template_summary() -> str:
    """Human-readable summary of all templates for the agent."""
    lines = []
    for name, tmpl in TEMPLATES.items():
        keywords = ", ".join(tmpl["detect"])
        lines.append(f"• {name}: {tmpl['description']}  (keywords: {keywords})")
    return "\n".join(lines)


def find_template(query: str) -> dict | None:
    """
    Try to match a user query to a template by checking keywords.
    Returns the template dict or None.
    """
    query_lower = query.lower()
    for name, tmpl in TEMPLATES.items():
        for keyword in tmpl["detect"]:
            if keyword in query_lower:
                return {"name": name, **tmpl}
    return None
