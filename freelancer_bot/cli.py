"""Typer CLI for Freelancer Bot v2 — unified entry point.

Commands:
    freelancer-bot bid       — Search & auto-bid on projects
    freelancer-bot contests  — Discover & implement tech contests
    freelancer-bot design    — Discover website design contests
    freelancer-bot status    — Show analytics & state summary
    freelancer-bot config    — Manage configuration
    freelancer-bot schedule  — Show/manage cron schedules
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from typing import Annotated, Optional

import structlog
import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from freelancer_bot import __version__
from freelancer_bot.analytics import AnalyticsReporter
from freelancer_bot.api import APIClient
from freelancer_bot.bidding import BiddingEngine
from freelancer_bot.config import ConfigManager
from freelancer_bot.contests import ContestsEngine
from freelancer_bot.design import DesignEngine
from freelancer_bot.email import EmailSender
from freelancer_bot.state import StateManager

# ── Logging setup ───────────────────────────────────────────────────────

import logging
logging.basicConfig(level=logging.WARNING, format="%(message)s")

structlog.configure(
    processors=[
        structlog.dev.set_exc_info,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(logging.WARNING),
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger(__name__)
console = Console()

app = typer.Typer(
    name="freelancer-bot",
    help="Unified Freelancer.com automation bot — bidding, contests, design discovery",
    add_completion=False,
    no_args_is_help=True,
)


def version_callback(value: bool) -> None:
    if value:
        console.print(f"Freelancer Bot v{__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: Annotated[
        Optional[bool],
        typer.Option("--version", "-V", callback=version_callback, is_eager=True, help="Show version"),
    ] = None,
    verbose: Annotated[
        bool,
        typer.Option("--verbose", "-v", help="Enable verbose/debug logging"),
    ] = False,
) -> None:
    """Freelancer Bot v2 — automate your Freelancer.com workflow."""
    if verbose:
        structlog.configure(
            processors=[
                structlog.dev.set_exc_info,
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.dev.ConsoleRenderer(),
            ],
            wrapper_class=structlog.make_filtering_bound_logger(logging.DEBUG),
            context_class=dict,
            logger_factory=structlog.PrintLoggerFactory(),
            cache_logger_on_first_use=True,
        )


# ── Shared dependencies ─────────────────────────────────────────────────

def get_config() -> ConfigManager:
    """Get config manager instance."""
    return ConfigManager()


def get_state() -> StateManager:
    """Get state manager with loaded state."""
    state = StateManager()
    state.load()
    return state


def get_api(config: ConfigManager | None = None) -> APIClient:
    """Get API client from config/env."""
    if config is None:
        config = get_config()
    token = config.get("freelancer", "token") or os.environ.get("FREELANCER_OAUTH_TOKEN", "")
    user_id = config.get("freelancer", "user_id", default=32666915)
    return APIClient(token=token, user_id=user_id)


def get_email(config: ConfigManager | None = None) -> EmailSender:
    """Get email sender from config/env."""
    if config is None:
        config = get_config()
    from_addr = config.get("email", "from") or os.environ.get("EMAIL_FROM", "your_email@gmail.com")
    to_addr = config.get("email", "to") or os.environ.get("EMAIL_TO", "your_email@gmail.com")
    password = config.get("email", "password") or os.environ.get("EMAIL_PASSWORD", "")
    smtp_host = config.get("email", "smtp_host") or os.environ.get("EMAIL_SMTP_HOST", "smtp.gmail.com")
    smtp_port = config.get("email", "smtp_port") or int(os.environ.get("EMAIL_SMTP_PORT", "587"))

    from freelancer_bot.email import EmailConfig
    email_config = EmailConfig(
        smtp_host=smtp_host,
        smtp_port=smtp_port,
        username=from_addr,
        password=password,
        from_addr=from_addr,
        to_addr=to_addr,
    )
    return EmailSender(config=email_config)


# ── bid command ─────────────────────────────────────────────────────────

@app.command()
def bid(
    max_bids: Annotated[
        int,
        typer.Argument(help="Maximum number of bids to place"),
    ] = 2,
    min_score: Annotated[
        int,
        typer.Option("--min-score", "-s", help="Minimum score threshold for bidding"),
    ] = 40,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", "-n", help="Preview without actually bidding"),
    ] = False,
    review: Annotated[
        bool,
        typer.Option(
            "--review", "-r",
            help="Interactive review mode: show full analysis and approve/reject each candidate before bidding",
        ),
    ] = False,
    no_email: Annotated[
        bool,
        typer.Option("--no-email", help="Skip sending email report"),
    ] = False,
    min_rate: Annotated[
        float,
        typer.Option(
            "--min-rate",
            help="Minimum acceptable hourly rate for bid calculations (default: $25)",
        ),
    ] = 25.0,
) -> None:
    """Search projects, score them, and auto-bid with tailored proposals.

    In normal mode, the bot automatically bids on the top-scoring candidates.
    Use --review for interactive mode where you approve/reject each candidate
    after seeing full analysis (red flags, skill match, budget assessment).

    Examples:
        freelancer-bot bid              # Auto-bid on top 2 projects
        freelancer-bot bid 5            # Auto-bid on top 5 projects
        freelancer-bot bid --review     # Interactive review before bidding
        freelancer-bot bid -n           # Dry run (preview only)
        freelancer-bot bid -r -n        # Review mode + dry run
    """
    console.print(Panel.fit(
        "[bold blue]🚀 Freelancer Bot v2 — Project Bidding[/bold blue]",
        border_style="blue",
    ))

    config = get_config()
    state = get_state()
    email = get_email(config) if not no_email else None

    async def _run() -> None:
        async with get_api(config) as api:
            engine = BiddingEngine(
                api=api,
                state=state,
                email=email or EmailSender(),  # dummy if no_email
                max_bids=max_bids,
                min_score=min_score,
                dry_run=dry_run,
                review_mode=review,
                min_rate=min_rate,
            )
            results = await engine.run()

            if dry_run:
                console.print("\n[yellow]⚠ DRY RUN — no actual bids were placed[/yellow]")

    asyncio.run(_run())


# ── contests command ────────────────────────────────────────────────────

@app.command()
def contests(
    max_matches: Annotated[
        int,
        typer.Argument(help="Maximum number of contests to implement"),
    ] = 10,
    min_score: Annotated[
        int,
        typer.Option("--min-score", "-s", help="Minimum score threshold"),
    ] = 50,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", "-n", help="Preview without implementing"),
    ] = False,
    no_implement: Annotated[
        bool,
        typer.Option("--no-implement", help="Discover only, don't prepare implementations"),
    ] = False,
    implement: Annotated[
        bool,
        typer.Option("--implement", help="Actually generate implementation code via AI (default: discovery-only)"),
    ] = False,
    no_ai: Annotated[
        bool,
        typer.Option("--no-ai", help="Disable AI-powered feasibility analysis (use keyword-based fallback)"),
    ] = False,
    no_email: Annotated[
        bool,
        typer.Option("--no-email", help="Skip sending email report"),
    ] = False,
) -> None:
    """Discover tech contests, filter out design, and prepare implementations.

    Default mode is discovery-only: finds contests, scores them, and saves
    implementation requests. Use --implement to actually generate code via AI.

    Examples:
        freelancer-bot contests              # Discover & prepare (safe default)
        freelancer-bot contests --implement  # Discover & generate code via AI
        freelancer-bot contests --no-ai      # Skip AI analysis, use keywords
        freelancer-bot contests -n           # Dry run (preview only)
        freelancer-bot contests 5 -s 60     # Max 5 matches, min score 60
    """
    console.print(Panel.fit(
        "[bold blue]🏆 Freelancer Bot v2 — Tech Contest Discovery[/bold blue]",
        border_style="blue",
    ))

    config = get_config()
    state = get_state()
    email = get_email(config) if not no_email else None

    async def _run() -> None:
        async with get_api(config) as api:
            engine = ContestsEngine(
                api=api,
                state=state,
                email=email or EmailSender(),
                max_matches=max_matches,
                min_score=min_score,
                auto_implement=not no_implement,
                implement=implement,
                use_ai_analysis=not no_ai,
                dry_run=dry_run,
            )
            results = await engine.run()

            if dry_run:
                console.print("\n[yellow]⚠ DRY RUN — no implementations were prepared[/yellow]")

    asyncio.run(_run())


# ── design command ──────────────────────────────────────────────────────

@app.command()
def design(
    max_matches: Annotated[
        int,
        typer.Argument(help="Maximum number of design contests to report"),
    ] = 15,
    min_score: Annotated[
        int,
        typer.Option("--min-score", "-s", help="Minimum score threshold"),
    ] = 40,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", "-n", help="Preview without sending email"),
    ] = False,
    no_email: Annotated[
        bool,
        typer.Option("--no-email", help="Skip sending email report"),
    ] = False,
) -> None:
    """Discover website design contests for manual review (information only)."""
    console.print(Panel.fit(
        "[bold blue]🎨 Freelancer Bot v2 — Website Design Discovery[/bold blue]",
        border_style="blue",
    ))

    config = get_config()
    state = get_state()
    email = get_email(config) if not no_email else None

    async def _run() -> None:
        async with get_api(config) as api:
            engine = DesignEngine(
                api=api,
                state=state,
                email=email or EmailSender(),
                max_matches=max_matches,
                min_score=min_score,
                dry_run=dry_run,
            )
            results = await engine.run()

            if dry_run:
                console.print("\n[yellow]⚠ DRY RUN — no email was sent[/yellow]")

    asyncio.run(_run())


# ── status command ─────────────────────────────────────────────────────

@app.command()
def status(
    json_output: Annotated[
        bool,
        typer.Option("--json", "-j", help="Output as JSON"),
    ] = False,
) -> None:
    """Show analytics, state summary, and recent activity."""
    state = get_state()
    reporter = AnalyticsReporter(state)

    if json_output:
        import json
        console.print_json(json.dumps(reporter.export_json(), indent=2, default=str))
    else:
        reporter.show_summary()

        # Last run timestamps
        summary = state.get_summary()
        console.print("\n[bold]⏱ Last Runs:[/bold]")
        for bot_name, key in [("Bidding", "bidding"), ("Contests", "contests"), ("Design", "design")]:
            last = summary[key].get("last_run")
            if last:
                console.print(f"  {bot_name}: [dim]{last}[/dim]")
            else:
                console.print(f"  {bot_name}: [dim]never[/dim]")


# ── config command ──────────────────────────────────────────────────────

config_app = typer.Typer(help="Manage configuration")
app.add_typer(config_app, name="config")


@config_app.command("show")
def config_show() -> None:
    """Show current configuration (secrets masked)."""
    config = get_config()
    console.print(Panel(config.show(), title="📋 Configuration", border_style="cyan"))


@config_app.command("init")
def config_init() -> None:
    """Initialize default configuration file."""
    config = get_config()
    config.init_default()
    console.print(f"[green]✓[/green] Config initialized at {config.config_path}")


@config_app.command("set")
def config_set(
    key: Annotated[str, typer.Argument(help="Dot-separated key path, e.g. 'bidding.max_bids_per_run'")],
    value: Annotated[str, typer.Argument(help="New value")],
) -> None:
    """Set a configuration value."""
    config = get_config()
    keys = key.split(".")

    # Try to parse value as int/float/bool
    parsed: Any = value
    if value.lower() == "true":
        parsed = True
    elif value.lower() == "false":
        parsed = False
    else:
        try:
            parsed = int(value)
        except ValueError:
            try:
                parsed = float(value)
            except ValueError:
                parsed = value

    config.set(*keys, value=parsed)
    console.print(f"[green]✓[/green] Set {key} = {parsed}")


@config_app.command("migrate")
def config_migrate(
    bidding_path: Annotated[
        Optional[str],
        typer.Option("--bidding", help="Path to legacy bidding state JSON"),
    ] = None,
    contests_path: Annotated[
        Optional[str],
        typer.Option("--contests", help="Path to legacy contests state JSON"),
    ] = None,
    design_path: Annotated[
        Optional[str],
        typer.Option("--design", help="Path to legacy design state JSON"),
    ] = None,
) -> None:
    """Migrate state from legacy JSON files to new format."""
    state = get_state()
    counts = state.migrate_from_legacy(
        bidding_path=bidding_path,
        contests_path=contests_path,
        design_path=design_path,
    )

    console.print("[green]✓[/green] Migration complete!")
    table = Table(title="Migrated Records")
    table.add_column("Category", style="cyan")
    table.add_column("Count", justify="right", style="green")
    for key, count in counts.items():
        table.add_row(key.replace("_", " ").title(), str(count))
    console.print(table)


# ── schedule command ───────────────────────────────────────────────────

schedule_app = typer.Typer(help="Manage cron schedules")
app.add_typer(schedule_app, name="schedule")


@schedule_app.command("show")
def schedule_show() -> None:
    """Show configured cron schedules."""
    config = get_config()
    schedule = config.get("schedule", default={})

    table = Table(title="⏰ Cron Schedules", show_header=True, header_style="bold cyan")
    table.add_column("Bot", style="cyan")
    table.add_column("Cron Expression", style="white")
    table.add_column("Description")

    descriptions = {
        "bidding": "Project bidding — 3x daily",
        "contests": "Tech contest discovery — 3x daily",
        "design": "Website design discovery — 3x daily",
    }

    for bot, cron_expr in schedule.items():
        desc = descriptions.get(bot, "")
        table.add_row(bot.title(), cron_expr, desc)

    console.print(table)
    console.print("\n[dim]Use 'crontab -e' to add these schedules to your system crontab.[/dim]")


@schedule_app.command("generate")
def schedule_generate() -> None:
    """Generate crontab entries for all bots."""
    config = get_config()
    schedule = config.get("schedule", default={})

    console.print("[bold]📋 Crontab Entries:[/bold]\n")

    for bot, cron_expr in schedule.items():
        # Build the command
        cmd = f"/opt/homebrew/bin/python3 -m freelancer_bot.cli {bot}"
        console.print(f"# {bot.title()} Bot")
        console.print(f"{cron_expr} {cmd}")
        console.print()

    console.print("[dim]Add these lines to your crontab with: crontab -e[/dim]")


# ── Entry point ─────────────────────────────────────────────────────────

def main_cli() -> None:
    """Entry point for console_scripts."""
    app()


if __name__ == "__main__":
    main_cli()
