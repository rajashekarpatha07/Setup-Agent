"""
CLI interface for the Setup Agent.

Provides a professional command-line interface using Click:

    setup-agent listen      — Listen for phone messages (default)
    setup-agent create      — Create a project directly
    setup-agent history     — View project history
    setup-agent stats       — Show aggregate statistics
    setup-agent templates   — List available templates
    setup-agent check       — Health check a project
    setup-agent dashboard   — Open web dashboard
"""

import sys
import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich import box

console = Console()


# ── Banner ───────────────────────────────────────────────────────────────────

BANNER = """[bright_blue]
 ╔═╗╔═╗╔╦╗╦ ╦╔═╗  ╔═╗╔═╗╔═╗╔╗╔╔╦╗
 ╚═╗║╣  ║ ║ ║╠═╝  ╠═╣║ ╦║╣ ║║║ ║
 ╚═╝╚═╝ ╩ ╚═╝╩    ╩ ╩╚═╝╚═╝╝╚╝ ╩[/]
[dim]  AI-Powered Multi-Language Project Scaffolder[/]
"""


@click.group(invoke_without_command=True)
@click.pass_context
def cli(ctx):
    """🤖 Setup Agent — AI-powered multi-language project scaffolder.

    Send a message from your phone or terminal, and the agent will
    scaffold a complete project with all dependencies and configurations.
    """
    if ctx.invoked_subcommand is None:
        console.print(BANNER)
        console.print(ctx.get_help())


@cli.command()
@click.option("--no-dashboard", is_flag=True, help="Disable the rich terminal dashboard")
@click.option("--no-web", is_flag=True, help="Disable the web dashboard")
def listen(no_dashboard, no_web):
    """📡 Listen for incoming project setup requests via ntfy.sh."""
    console.print(BANNER)

    from main import main as start_listener
    start_listener(use_dashboard=not no_dashboard, use_web=not no_web)


@cli.command()
@click.argument("message")
@click.option("--dry-run", is_flag=True, help="Show what would happen without executing")
def create(message, dry_run):
    """🚀 Create a project directly from the terminal.

    MESSAGE is a natural language description like "create a flask api".
    """
    console.print(BANNER)

    from main import validate_input
    is_valid, reason = validate_input(message)

    if not is_valid:
        console.print(f"[red]❌ Invalid input: {reason}[/]")
        sys.exit(1)

    if dry_run:
        from templates import find_template
        console.print(f"[cyan]📋 Dry run for:[/] {message}\n")

        match = find_template(message)
        if match:
            console.print(f"[green]✅ Matched template:[/] [bold]{match['name']}[/]")
            console.print(f"[dim]   {match['description']}[/]\n")
            console.print("[cyan]Steps:[/]")
            for i, step in enumerate(match["steps"], 1):
                console.print(f"   {i}. [dim]{step}[/]")
        else:
            console.print("[yellow]⚠️  No template matched — agent will use general knowledge[/]")
        return

    from main import process_request
    process_request(message)


@cli.command()
@click.option("--limit", "-n", default=20, help="Number of records to show")
@click.option("--json-output", "json_out", is_flag=True, help="Output as JSON")
def history(limit, json_out):
    """📁 View project creation history."""
    from history import history_db
    import json

    projects = history_db.get_all(limit=limit)

    if json_out:
        click.echo(json.dumps(projects, indent=2, default=str))
        return

    if not projects:
        console.print(Panel("[dim]No projects created yet[/]", title="History", border_style="dim"))
        return

    table = Table(
        title="📁 Project History",
        box=box.ROUNDED,
        border_style="bright_blue",
        show_lines=False,
        padding=(0, 1),
    )
    table.add_column("#", style="dim", width=4)
    table.add_column("Project", style="cyan bold", min_width=20)
    table.add_column("Type", style="magenta", width=14)
    table.add_column("Status", width=12)
    table.add_column("Duration", style="dim", width=10)
    table.add_column("Date", style="dim", width=18)

    status_styles = {
        "success": "[green]✅ Success[/]",
        "failed": "[red]❌ Failed[/]",
        "rolled_back": "[yellow]🔄 Rolled Back[/]",
        "in_progress": "[blue]⏳ Working[/]",
    }

    for p in projects:
        status = status_styles.get(p.get("status", ""), p.get("status", ""))
        duration = f"{p['duration_seconds']:.0f}s" if p.get("duration_seconds", 0) > 0 else "-"
        date = p.get("started_at", "")[:16].replace("T", " ") if p.get("started_at") else "-"

        table.add_row(
            str(p.get("id", "")),
            p.get("name", "unknown"),
            p.get("project_type", "-"),
            status,
            duration,
            date,
        )

    console.print(table)


@cli.command()
def stats():
    """📊 Show aggregate project statistics."""
    from history import history_db

    data = history_db.get_stats()

    # Main stats panel
    stats_table = Table(show_header=False, box=None, padding=(0, 2))
    stats_table.add_column(style="bold cyan", min_width=18)
    stats_table.add_column(style="bold")

    stats_table.add_row("Total Projects", str(data["total"]))
    stats_table.add_row("Successful", f"[green]{data['success']}[/]")
    stats_table.add_row("Failed", f"[red]{data['failed']}[/]")
    stats_table.add_row("Rolled Back", f"[yellow]{data['rolled_back']}[/]")
    stats_table.add_row("Success Rate", f"[{'green' if data['success_rate'] >= 80 else 'yellow'}]{data['success_rate']}%[/]")
    stats_table.add_row("Avg Duration", f"[cyan]{data['avg_duration_seconds']}s[/]")

    console.print(Panel(stats_table, title="📊 Statistics", border_style="bright_blue", box=box.ROUNDED))

    # Projects by type
    if data.get("by_type"):
        type_table = Table(box=box.SIMPLE, border_style="dim")
        type_table.add_column("Type", style="magenta")
        type_table.add_column("Count", style="bold")
        type_table.add_column("Bar", min_width=20)

        max_count = max(data["by_type"].values()) if data["by_type"] else 1
        for t, count in sorted(data["by_type"].items(), key=lambda x: -x[1]):
            bar_len = int(count / max_count * 20)
            bar = f"[bright_blue]{'█' * bar_len}[/][dim]{'░' * (20 - bar_len)}[/]"
            type_table.add_row(t, str(count), bar)

        console.print(Panel(type_table, title="📊 By Type", border_style="dim", box=box.ROUNDED))


@cli.command()
def templates():
    """📋 List all available project templates."""
    from templates import TEMPLATES

    type_icons = {
        "react-vite": "⚛️", "nextjs": "▲ ", "express-ts": "🟢", "typescript": "🔷",
        "vite-vanilla": "⚡", "svelte": "🔥", "python-uv": "🐍", "flask": "🌶️",
        "django": "🎸", "fastapi": "⚡", "rust": "🦀", "go": "🐹", "flutter": "💙",
    }

    table = Table(
        title="📋 Available Templates",
        box=box.ROUNDED,
        border_style="bright_blue",
    )
    table.add_column("", width=3)
    table.add_column("Template", style="cyan bold", min_width=15)
    table.add_column("Description", style="dim")
    table.add_column("Keywords", style="magenta dim", max_width=30)

    for name, tmpl in TEMPLATES.items():
        icon = type_icons.get(name, "📦")
        keywords = ", ".join(tmpl["detect"][:3])
        table.add_row(icon, name, tmpl["description"], keywords)

    console.print(table)
    console.print(f"\n[dim]Use:[/] [cyan]setup-agent create \"<description>\"[/] [dim]to create a project[/]")


@cli.command()
@click.argument("project_name")
def check(project_name):
    """🏥 Run health checks on a created project.

    PROJECT_NAME is the name of the project directory.
    """
    from healthcheck import run_health_check
    from config import cfg

    project_path = cfg.projects_dir / project_name

    if not project_path.exists():
        console.print(f"[red]❌ Project not found: {project_path}[/]")
        sys.exit(1)

    console.print(f"\n[cyan]🏥 Running health check on[/] [bold]{project_name}[/]...\n")

    result = run_health_check(str(project_path))

    # Display checks
    for c in result.get("checks", []):
        icon = "✅" if c["passed"] else "❌"
        color = "green" if c["passed"] else "red"
        console.print(f"  {icon} [{color}]{c['check']}[/]")
        console.print(f"     [dim]{c['detail']}[/]")

    # Summary
    console.print()
    status = result.get("status", "unknown")
    if status == "healthy":
        console.print(Panel(
            f"[bold green]✅ HEALTHY[/] — {result['passed']}/{result['total']} checks passed",
            border_style="green",
        ))
    else:
        console.print(Panel(
            f"[bold red]⚠️ UNHEALTHY[/] — {result['passed']}/{result['total']} checks passed",
            border_style="red",
        ))


@cli.command()
@click.option("--port", "-p", default=8745, help="Port to run on")
def dashboard(port):
    """🌐 Open the web dashboard in your browser."""
    import webbrowser
    from web.server import start_web_server

    console.print(BANNER)
    url = f"http://localhost:{port}"
    console.print(f"[cyan]🌐 Starting web dashboard at[/] [bold underline]{url}[/]\n")

    webbrowser.open(url)
    start_web_server(port=port, background=False)


def main():
    """Entry point for the CLI."""
    cli()


if __name__ == "__main__":
    main()
