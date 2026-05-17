"""
Health check system for the Setup Agent.

Verifies that created projects are properly configured and functional.
Runs language-specific checks:
  - Node.js: package.json, node_modules, tsconfig, TypeScript compilation
  - Python: pyproject.toml, .venv or dependencies
  - Rust: Cargo.toml, cargo check
  - Go: go.mod, go build

Usage:
    from .healthcheck import run_health_check
    result = run_health_check("/path/to/project")
    print(result["status"])   # "healthy" or "unhealthy"
    print(result["checks"])   # list of check results
"""

import subprocess
import json
from pathlib import Path
from .logger import get_logger

log = get_logger("healthcheck")


def _check_file_exists(project_path: Path, filename: str) -> dict:
    """Check if a file exists in the project."""
    path = project_path / filename
    exists = path.exists()
    return {
        "check": f"{filename} exists",
        "passed": exists,
        "detail": f"Found at {path}" if exists else f"Not found: {path}",
    }


def _check_dir_exists(project_path: Path, dirname: str) -> dict:
    """Check if a directory exists and has content."""
    path = project_path / dirname
    if not path.exists():
        return {"check": f"{dirname}/ exists", "passed": False, "detail": f"Not found: {path}"}
    items = list(path.iterdir())
    return {"check": f"{dirname}/ exists", "passed": True, "detail": f"Found with {len(items)} items"}


def _run_check_command(project_path: Path, command: str, description: str) -> dict:
    """Run a command as a health check."""
    try:
        result = subprocess.run(
            command, shell=True, capture_output=True, text=True, timeout=60, cwd=str(project_path),
        )
        passed = result.returncode == 0
        detail = "Passed" if passed else (result.stderr.strip()[:200] or result.stdout.strip()[:200])
        return {"check": description, "passed": passed, "detail": detail}
    except subprocess.TimeoutExpired:
        return {"check": description, "passed": False, "detail": "Timed out after 60s"}
    except Exception as e:
        return {"check": description, "passed": False, "detail": str(e)}


def _detect_project_type(project_path: Path) -> str:
    """Detect the project type from files present."""
    if (project_path / "Cargo.toml").exists():
        return "rust"
    if (project_path / "go.mod").exists():
        return "go"
    if (project_path / "pubspec.yaml").exists():
        return "flutter"
    if (project_path / "manage.py").exists():
        return "django"
    if (project_path / "pyproject.toml").exists():
        return "python"
    if (project_path / "package.json").exists():
        try:
            pkg = json.loads((project_path / "package.json").read_text())
            deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
            if "next" in deps:
                return "nextjs"
            if "react" in deps:
                return "react"
            if "svelte" in deps or "@sveltejs/kit" in deps:
                return "svelte"
            if "express" in deps:
                return "express"
            if "typescript" in deps:
                return "typescript"
        except Exception:
            pass
        return "nodejs"
    return "unknown"


def _check_nodejs(project_path: Path, project_type: str) -> list[dict]:
    """Health checks for Node.js projects."""
    checks = [
        _check_file_exists(project_path, "package.json"),
        _check_dir_exists(project_path, "node_modules"),
    ]
    if (project_path / "tsconfig.json").exists():
        checks.append(_check_file_exists(project_path, "tsconfig.json"))
        checks.append(_run_check_command(project_path, "npx tsc --noEmit 2>&1", "TypeScript compiles cleanly"))
    try:
        pkg = json.loads((project_path / "package.json").read_text())
        dep_count = len(pkg.get("dependencies", {})) + len(pkg.get("devDependencies", {}))
        checks.append({"check": "package.json is valid", "passed": True, "detail": f"Valid JSON with {dep_count} dependencies"})
    except Exception as e:
        checks.append({"check": "package.json is valid", "passed": False, "detail": f"Invalid JSON: {e}"})
    checks.append(_check_dir_exists(project_path, ".git"))
    return checks


def _check_python(project_path: Path, project_type: str) -> list[dict]:
    """Health checks for Python projects."""
    checks = [_check_file_exists(project_path, "pyproject.toml")]
    if (project_path / ".venv").exists():
        checks.append(_check_dir_exists(project_path, ".venv"))
    else:
        checks.append({"check": ".venv/ exists", "passed": False, "detail": "No virtual environment found (run 'uv sync')"})
    if project_type == "django":
        checks.append(_check_file_exists(project_path, "manage.py"))
    checks.append(_check_dir_exists(project_path, ".git"))
    return checks


def _check_rust(project_path: Path) -> list[dict]:
    return [
        _check_file_exists(project_path, "Cargo.toml"),
        _check_file_exists(project_path, "src/main.rs"),
        _run_check_command(project_path, "cargo check 2>&1", "cargo check passes"),
        _check_dir_exists(project_path, ".git"),
    ]


def _check_go(project_path: Path) -> list[dict]:
    return [
        _check_file_exists(project_path, "go.mod"),
        _run_check_command(project_path, "go build ./... 2>&1", "go build passes"),
        _check_dir_exists(project_path, ".git"),
    ]


def _check_flutter(project_path: Path) -> list[dict]:
    return [
        _check_file_exists(project_path, "pubspec.yaml"),
        _check_file_exists(project_path, "lib/main.dart"),
        _run_check_command(project_path, "flutter analyze 2>&1", "flutter analyze passes"),
        _check_dir_exists(project_path, ".git"),
    ]


def run_health_check(project_path: str) -> dict:
    """
    Run all health checks for a project.
    Returns: {"project_path", "project_type", "status", "checks", "passed", "failed", "total"}
    """
    path = Path(project_path).resolve()

    if not path.exists():
        return {
            "project_path": str(path), "project_type": "unknown", "status": "not_found",
            "checks": [], "passed": 0, "failed": 0, "total": 0,
            "error": f"Directory not found: {path}",
        }

    project_type = _detect_project_type(path)
    log.info(f"Running health check for {path.name} (type: {project_type})")

    if project_type in ("react", "nextjs", "express", "typescript", "svelte", "nodejs"):
        checks = _check_nodejs(path, project_type)
    elif project_type in ("python", "flask", "django", "fastapi"):
        checks = _check_python(path, project_type)
    elif project_type == "rust":
        checks = _check_rust(path)
    elif project_type == "go":
        checks = _check_go(path)
    elif project_type == "flutter":
        checks = _check_flutter(path)
    else:
        checks = [
            _check_dir_exists(path, ".git"),
            {"check": "Project type detection", "passed": False, "detail": f"Unknown type: {project_type}"},
        ]

    passed = sum(1 for c in checks if c["passed"])
    failed = len(checks) - passed
    status = "healthy" if failed == 0 else "unhealthy"
    log.info(f"Health check result: {status} ({passed}/{len(checks)} passed)")

    return {
        "project_path": str(path), "project_type": project_type, "status": status,
        "checks": checks, "passed": passed, "failed": failed, "total": len(checks),
    }
