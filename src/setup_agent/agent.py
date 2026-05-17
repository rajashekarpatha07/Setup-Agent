"""
Agent — the brain of the Setup Agent.

Uses LangChain + Groq LLM to interpret user messages and execute
the right sequence of tools to scaffold any type of project.

The agent is multi-language — it detects the requested stack from
natural language and picks the appropriate setup flow using the
templates registry as a reference.
"""

import os
from langchain_core.tools import tool
from langchain_classic.agents import create_tool_calling_agent, AgentExecutor
from langchain_core.prompts import ChatPromptTemplate
from langchain_groq import ChatGroq
from .config import cfg
from .sandbox import ALLOWED_BASE
from .templates import get_template_summary, find_template, TEMPLATES
from .logger import get_logger
from . import tools as tool_functions

log = get_logger("agent")


# ── Structured Tools ─────────────────────────────────────────────────────────

@tool
def create_project_dir(project_name: str) -> str:
    """
    Creates a new project folder inside the allowed projects directory.
    Always call this FIRST before any other tool.
    Returns the full path to the created directory — save this path,
    you will use it as working_dir in all subsequent run_command calls.
    """
    return tool_functions.create_project_dir(project_name.strip())


@tool
def run_command(command: str, working_dir: str, timeout: int = 0) -> str:
    """
    Runs a shell command inside a specific directory.
    Use this for: npm init, npm install, npx, git init, tsc --init, mkdir,
    uv init, uv add, pip install, cargo init, go mod init, flutter create, etc.
    Always use the full absolute path for working_dir.
    Read the output carefully — it tells you if the command succeeded or failed.
    If a command fails, try to fix it based on the error output.
    Set timeout to a higher value (e.g., 300) for heavy commands like
    npx create-next-app or flutter create. Use 0 for auto-detection.
    IMPORTANT: Do NOT chain commands with && or ; — run them one at a time.
    """
    t = timeout if timeout > 0 else None
    return tool_functions.run_command(command.strip(), working_dir.strip(), timeout=t)


@tool
def create_file(filepath: str, content: str) -> str:
    """
    Creates a file with specific content.
    Use this for config files like tsconfig.json, .eslintrc, README.md,
    .env.example, pyproject.toml, Cargo.toml, go.mod, etc.
    The filepath must be an absolute path inside the project directory.
    The content is written exactly as-is, including newlines.
    """
    return tool_functions.create_file(filepath.strip(), content)


@tool
def append_to_file(filepath: str, content: str) -> str:
    """
    Appends content to an existing file.
    Use this to add lines to .gitignore, append to README, etc.
    If the file doesn't exist, it will be created.
    """
    return tool_functions.append_to_file(filepath.strip(), content)


@tool
def file_exists(filepath: str) -> str:
    """
    Checks if a file or directory exists at the given path.
    Returns EXISTS (with size info) or NOT_FOUND.
    Use this before creating files to avoid overwriting existing ones.
    """
    return tool_functions.file_exists(filepath.strip())


@tool
def read_directory(directory_path: str) -> str:
    """
    Lists all files and folders inside a directory.
    Use this to check what already exists before running setup commands.
    """
    return tool_functions.read_directory(directory_path.strip())


@tool
def list_templates() -> str:
    """
    Lists all available project templates with their descriptions and keywords.
    Call this if you're unsure what setup steps to use for a project type.
    """
    return get_template_summary()


@tool
def get_template_steps(template_name: str) -> str:
    """
    Gets the detailed setup steps for a specific template.
    Use the template name from list_templates (e.g., 'react-vite', 'flask', 'express-ts').
    Returns the setup steps and any starter files to create.
    """
    tmpl = TEMPLATES.get(template_name.strip())
    if not tmpl:
        return f"Template '{template_name}' not found. Call list_templates to see available templates."

    lines = [
        f"Template: {template_name}",
        f"Description: {tmpl['description']}",
        "",
        "Setup steps (run in order):",
    ]
    for i, step in enumerate(tmpl["steps"], 1):
        lines.append(f"  {i}. {step}")

    if tmpl.get("files"):
        lines.append("")
        lines.append("Files to create after setup:")
        for fpath, _content in tmpl["files"].items():
            lines.append(f"  • {fpath}")

    return "\n".join(lines)


TOOLS = [
    create_project_dir, run_command, create_file, append_to_file,
    file_exists, read_directory, list_templates, get_template_steps,
]


# ── System Prompt ────────────────────────────────────────────────────────────

SYSTEM_PROMPT = f"""You are a multi-language project setup agent running on a Linux laptop.

RULES — follow these strictly:
- You can ONLY create or modify files inside: {ALLOWED_BASE}
- Never use sudo or any system-level commands
- Never go outside the allowed directory
- NEVER chain commands with && or ; — run each command separately with run_command
- If a command fails, read the error output and try to fix it before giving up
- Do not install global packages — always use local/project installs

YOUR CAPABILITIES:
You can set up projects in many languages and frameworks:
- JavaScript/TypeScript: React (Vite), Next.js, Express, Svelte, vanilla Vite
- Python: uv projects, Flask, Django, FastAPI
- Systems: Rust (cargo), Go (go mod)
- Mobile: Flutter/Dart

WORKFLOW — for every request:
1. First call list_templates to see available templates
2. Call get_template_steps with the matching template name
3. Call create_project_dir with a sensible project name derived from the user's request
4. Use the returned path as working_dir for ALL subsequent commands
5. Follow the template steps, running each command one at a time
6. Create any starter files the template specifies
7. Install any EXTRA packages the user specifically mentioned
8. Run: git init (if not already done by the template)
9. Create a README.md summarizing what was set up

IMPORTANT NOTES:
- For Python projects, use 'uv' (not pip) for package management
- For TypeScript projects, always install type definitions (@types/*)
- For Next.js, always use: npx create-next-app@latest . --typescript --eslint --app --src-dir --tailwind --import-alias '@/*' --use-npm
- When a project template uses '.' as the path, the command runs in the project dir you created
- If the user asks for something not in the templates, use your knowledge to set it up correctly
- Always create a .gitignore appropriate for the project type

When you are done, provide a clear summary of:
- What project type was set up
- What packages were installed
- Where the project is located
- How to run it (e.g., npm run dev, uv run python app.py, cargo run, etc.)
"""


PROMPT = ChatPromptTemplate.from_messages([
    ("system", SYSTEM_PROMPT),
    ("human", "{input}"),
    ("placeholder", "{agent_scratchpad}"),
])


llm = ChatGroq(
    model=cfg.llm_model,
    groq_api_key=cfg.groq_api_key,
    temperature=0,
)

agent = create_tool_calling_agent(llm=llm, tools=TOOLS, prompt=PROMPT)

agent_executor = AgentExecutor(
    agent=agent, tools=TOOLS, verbose=True,
    max_iterations=cfg.max_iterations, handle_parsing_errors=True,
)


def run_agent(user_message: str) -> str:
    """
    The only function main.py needs to call.
    Passes the message into the agent loop and returns the final summary string.
    """
    log.info(f"Starting agent with message: {user_message}")
    try:
        result = agent_executor.invoke({"input": user_message})
        output = result.get("output", "Agent completed but returned no output")
        log.info("Agent finished successfully")
        return output
    except Exception as e:
        error_msg = f"An error occurred while running the agent: {str(e)}"
        log.error(error_msg)
        return error_msg
