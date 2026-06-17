"""Analytics tracking and reporting for Freelancer Bot v2.

Tracks bids placed, contests entered, success rates, and revenue over time.
Provides summary reports and trend analysis.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import structlog
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from freelancer_bot.state import AnalyticsState, StateManager

logger = structlog.get_logger(__name__)
console = Console()


@dataclass
class AnalyticsReporter:
    """Generate analytics reports from state data."""

    state: StateManager

    def show_summary(self) -> None:
        """Display a rich analytics summary in the terminal."""
        a = self.state.analytics
        summary = self.state.get_summary()

        # Main stats panel
        stats_text = (
            f"[bold cyan]Bidding[/bold cyan]\n"
            f"  Bids Placed: {a.total_bids_placed}\n"
            f"  Bids Won: [green]{a.total_bids_won}[/green]\n"
            f"  Success Rate: [bold]{a.bid_success_rate:.1f}%[/bold]\n"
            f"\n"
            f"[bold cyan]Contests[/bold cyan]\n"
            f"  Contests Entered: {a.total_contests_entered}\n"
            f"  Contests Won: [green]{a.total_contests_won}[/green]\n"
            f"  Success Rate: [bold]{a.contest_success_rate:.1f}%[/bold]\n"
            f"\n"
            f"[bold cyan]Revenue[/bold cyan]\n"
            f"  Total Revenue: [green bold]${a.total_revenue:,.2f}[/green bold]\n"
            f"\n"
            f"[bold cyan]State[/bold cyan]\n"
            f"  Successful Bids: {summary['bidding']['successful_bids']}\n"
            f"  Attempted Bids: {summary['bidding']['attempted_bids']}\n"
            f"  Contests Seen: {summary['contests']['seen']}\n"
            f"  Contests Implemented: {summary['contests']['implemented']}\n"
            f"  Design Contests Seen: {summary['design']['seen']}"
        )

        console.print(Panel.fit(stats_text, title="📊 Analytics Summary", border_style="cyan"))

        # Daily stats table
        if a.daily_stats:
            self._show_daily_table(a)

        # Recent bid history
        if a.bid_history:
            self._show_recent_bids(a)

        # Recent contest history
        if a.contest_history:
            self._show_recent_contests(a)

    def _show_daily_table(self, a: AnalyticsState) -> None:
        """Show daily activity table."""
        table = Table(title="📅 Daily Activity", show_header=True, header_style="bold cyan")
        table.add_column("Date", style="dim")
        table.add_column("Bids", justify="right")
        table.add_column("Won", justify="right", style="green")
        table.add_column("Contests", justify="right")
        table.add_column("Won", justify="right", style="green")

        # Show last 14 days
        sorted_days = sorted(a.daily_stats.keys(), reverse=True)[:14]
        for day in sorted_days:
            stats = a.daily_stats[day]
            table.add_row(
                day,
                str(stats.get("bids_placed", 0)),
                str(stats.get("bids_won", 0)),
                str(stats.get("contests_entered", 0)),
                str(stats.get("contests_won", 0)),
            )

        console.print(table)

    def _show_recent_bids(self, a: AnalyticsState) -> None:
        """Show recent bid history."""
        table = Table(title="💰 Recent Bids", show_header=True, header_style="bold cyan")
        table.add_column("Date", style="dim")
        table.add_column("Project ID", justify="right")
        table.add_column("Amount", justify="right")
        table.add_column("Status")

        recent = a.bid_history[-10:]
        for bid in reversed(recent):
            ts = bid.get("timestamp", "")
            if ts:
                try:
                    dt = datetime.fromisoformat(ts)
                    ts = dt.strftime("%Y-%m-%d %H:%M")
                except (ValueError, TypeError):
                    pass

            status = bid.get("status", "placed")
            status_style = {
                "placed": "yellow",
                "won": "green",
                "lost": "red",
            }.get(status, "white")

            table.add_row(
                ts,
                str(bid.get("project_id", "—")),
                f"${bid.get('amount', 0):,.2f}",
                f"[{status_style}]{status}[/{status_style}]",
            )

        console.print(table)

    def _show_recent_contests(self, a: AnalyticsState) -> None:
        """Show recent contest history."""
        table = Table(title="🏆 Recent Contests", show_header=True, header_style="bold cyan")
        table.add_column("Date", style="dim")
        table.add_column("Contest ID", justify="right")
        table.add_column("Prize", justify="right")
        table.add_column("Status")

        recent = a.contest_history[-10:]
        for entry in reversed(recent):
            ts = entry.get("timestamp", "")
            if ts:
                try:
                    dt = datetime.fromisoformat(ts)
                    ts = dt.strftime("%Y-%m-%d %H:%M")
                except (ValueError, TypeError):
                    pass

            status = entry.get("status", "entered")
            status_style = {
                "entered": "yellow",
                "won": "green",
                "lost": "red",
            }.get(status, "white")

            table.add_row(
                ts,
                str(entry.get("contest_id", "—")),
                f"${entry.get('prize', 0):,.2f}",
                f"[{status_style}]{status}[/{status_style}]",
            )

        console.print(table)

    def export_json(self) -> dict[str, Any]:
        """Export analytics as JSON-serializable dict."""
        a = self.state.analytics
        return {
            "summary": {
                "total_bids_placed": a.total_bids_placed,
                "total_bids_won": a.total_bids_won,
                "bid_success_rate": round(a.bid_success_rate, 1),
                "total_contests_entered": a.total_contests_entered,
                "total_contests_won": a.total_contests_won,
                "contest_success_rate": round(a.contest_success_rate, 1),
                "total_revenue": a.total_revenue,
            },
            "daily_stats": a.daily_stats,
            "recent_bids": a.bid_history[-20:],
            "recent_contests": a.contest_history[-20:],
            "state_snapshot": self.state.get_summary(),
        }
