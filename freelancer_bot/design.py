"""Website design contest discovery — 10 search categories, information only.

Discovers website design contests, scores them, sends email for manual review.
No auto-implementation — design work requires human review.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

import structlog
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from freelancer_bot.api import APIClient
from freelancer_bot.email import EmailSender
from freelancer_bot.scoring import score_design_contest
from freelancer_bot.state import StateManager

logger = structlog.get_logger(__name__)
console = Console()

# ── 10 Website Design Search Configs ────────────────────────────────────

DESIGN_SEARCH_CONFIGS: list[dict[str, Any]] = [
    {"name": "Website Design", "query": "website design", "limit": 50},
    {"name": "Web Design", "query": "web design", "limit": 50},
    {"name": "UI Design", "query": "ui design", "limit": 50},
    {"name": "Landing Page", "query": "landing page", "limit": 50},
    {"name": "Responsive", "query": "responsive design", "limit": 25},
    {"name": "Modern Website", "query": "modern website", "limit": 25},
    {"name": "Website Redesign", "query": "website redesign", "limit": 25},
    {"name": "Portfolio", "query": "portfolio website", "limit": 25},
    {"name": "Corporate", "query": "corporate website", "limit": 25},
    {"name": "E-commerce", "query": "ecommerce website", "limit": 25},
]


@dataclass
class DesignEngine:
    """Orchestrates website design contest discovery (information only)."""

    api: APIClient
    state: StateManager
    email: EmailSender
    max_matches: int = 15
    min_score: int = 40
    dry_run: bool = False

    async def run(self) -> dict[str, Any]:
        """Run the full design contest discovery pipeline.

        Returns summary dict with results.
        """
        console.print(Panel.fit(
            "[bold blue]Freelancer Bot v2 — Website Design Discovery[/bold blue]\n"
            f"Max matches: {self.max_matches} | Min score: {self.min_score} | "
            f"Mode: {'[yellow]DRY RUN[/yellow]' if self.dry_run else '[green]LIVE[/green]'}\n"
            "[dim]Information only — no auto-implementation. Results sent via email for manual review.[/dim]",
            border_style="blue",
        ))

        # Phase 1: Parallel search
        all_contests = await self._search_all()

        # Phase 2: Score and filter
        candidates = self._score_and_filter(all_contests)

        # Phase 3: Send report
        await self._send_report(candidates)

        # Update state
        self.state.touch_last_run("design")
        self.state.save_design()

        return {
            "discovered": len(candidates),
            "total_searched": len(all_contests),
            "candidates": [
                {
                    "id": c.get("id"),
                    "title": c.get("title"),
                    "score": c["_score"],
                    "prize": c.get("prize", 0),
                }
                for c in candidates
            ],
        }

    async def _search_all(self) -> list[dict[str, Any]]:
        """Run all 10 design searches in parallel."""
        console.print("\n[bold]🔍 Searching website design contests...[/bold]")

        seen_ids: set[int] = set()
        all_contests: list[dict[str, Any]] = []

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Searching...", total=len(DESIGN_SEARCH_CONFIGS))

            async def search_one(cfg: dict[str, Any]) -> list[dict[str, Any]]:
                try:
                    result = await self.api.search_contests(
                        query=cfg["query"],
                        limit=cfg["limit"],
                    )
                    contests = result.get("result", {}).get("contests", [])
                    progress.advance(task)
                    return contests
                except Exception as e:
                    logger.error("design_search_failed", config=cfg["name"], error=str(e)[:200])
                    progress.advance(task)
                    return []

            tasks_list = [search_one(cfg) for cfg in DESIGN_SEARCH_CONFIGS]
            results = await asyncio.gather(*tasks_list)

        for i, contests in enumerate(results):
            cfg = DESIGN_SEARCH_CONFIGS[i]
            new_count = 0
            for c in contests:
                cid = c.get("id")
                if cid and cid not in seen_ids:
                    seen_ids.add(cid)
                    c["_search_category"] = cfg["name"]
                    all_contests.append(c)
                    new_count += 1
            logger.info(
                "design_search_result",
                category=cfg["name"],
                total=len(contests),
                new=new_count,
            )

        console.print(f"[green]✓[/green] Found {len(all_contests)} unique contests across {len(DESIGN_SEARCH_CONFIGS)} searches")
        return all_contests

    def _score_and_filter(self, contests: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Score all design contests and filter to candidates above threshold."""
        console.print("\n[bold]📊 Scoring design contests...[/bold]")

        candidates: list[dict[str, Any]] = []
        skipped_seen = 0
        skipped_low_score = 0

        for contest in contests:
            cid = contest.get("id")

            # Skip already seen
            if self.state.is_design_seen(cid):
                skipped_seen += 1
                continue

            # Mark as seen
            self.state.mark_design_seen(cid)

            # Score
            scoring = score_design_contest(contest)

            if not scoring["should_report"]:
                skipped_low_score += 1
                continue

            contest["_score"] = scoring["score"]
            contest["_score_breakdown"] = scoring["breakdown"]
            contest["_matched_keywords"] = scoring["matched_keywords"]
            candidates.append(contest)

        # Sort by score descending
        candidates.sort(key=lambda c: c["_score"], reverse=True)

        console.print(f"[green]✓[/green] {len(candidates)} candidates above threshold (min {self.min_score})")
        console.print(f"  Skipped: {skipped_seen} seen, {skipped_low_score} low score")

        # Display top candidates
        if candidates:
            table = Table(title="Top Website Design Contests", show_header=True, header_style="bold cyan")
            table.add_column("#", style="dim", width=3)
            table.add_column("Contest", style="white", max_width=50)
            table.add_column("Score", style="green", justify="right")
            table.add_column("Prize", justify="right")
            table.add_column("Entries", justify="right")
            table.add_column("Category", style="dim")

            for i, c in enumerate(candidates[:15], 1):
                title = c.get("title", "Untitled")[:47]
                prize = c.get("prize", 0)
                if isinstance(prize, dict):
                    prize = prize.get("amount", 0)
                entry_count = c.get("entry_count", c.get("entries", 0))
                if isinstance(entry_count, dict):
                    entry_count = entry_count.get("count", 0)

                table.add_row(
                    str(i),
                    title,
                    str(c["_score"]),
                    f"${prize}",
                    str(entry_count),
                    c.get("_search_category", "—"),
                )

            console.print(table)

        return candidates

    async def _send_report(self, candidates: list[dict[str, Any]]) -> None:
        """Send email report with design contest discoveries."""
        if not candidates:
            console.print("[dim]No design contests to report — skipping email[/dim]")
            return

        # Limit to max_matches for the report
        report_candidates = candidates[:self.max_matches]

        subject = f"🎨 Freelancer Bot: {len(report_candidates)} Website Design Contests Found"

        total_prize = sum(
            c.get("prize", 0) if isinstance(c.get("prize"), (int, float))
            else c.get("prize", {}).get("amount", 0) if isinstance(c.get("prize"), dict)
            else 0
            for c in report_candidates
        )

        summary = (
            f"Website design contest discovery completed. "
            f"{len(report_candidates)} high-potential contests found "
            f"(total prize pool: ${total_prize:,.2f}). "
            f"These require manual review — no auto-implementation for design work."
        )

        details: list[dict[str, Any]] = []
        for c in report_candidates:
            prize = c.get("prize", 0)
            if isinstance(prize, dict):
                prize = prize.get("amount", 0)
            details.append({
                "title": c["title"],
                "link": f"https://www.freelancer.com/contest/{c.get('id', '')}",
                "score": str(c["_score"]),
                "bid": f"${prize}",
                "status": "discovered",
            })

        self.email.send_report(subject, summary, details, report_type="design", dry_run=self.dry_run)
        console.print(f"\n[green]✓[/green] Email report sent with {len(report_candidates)} design contests")
