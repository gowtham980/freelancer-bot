"""Project bidding logic — 12 search categories, scoring, auto-bid with proposals.

Runs parallel searches, scores projects, performs pre-bid analysis,
and places bids with AI-tailored proposals. Supports interactive review mode.
"""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass, field
from typing import Any

import structlog
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table
from rich.text import Text

from freelancer_bot.api import APIClient
from freelancer_bot.email import EmailSender
from freelancer_bot.proposals import generate_proposal
from freelancer_bot.scoring import (
    calculate_bid_amount,
    calculate_bid_period,
    score_project,
)
from freelancer_bot.state import StateManager

logger = structlog.get_logger(__name__)
console = Console()

# ── 12 Search Configs from spec ─────────────────────────────────────────

SEARCH_CONFIGS: list[dict[str, Any]] = [
    {"name": "Flutter", "query": "flutter", "types": ["fixed", "hourly"], "min_price": None, "limit": 20},
    {"name": "Flutter Mobile", "query": "flutter mobile app", "types": ["fixed"], "min_price": 300, "limit": 15},
    {"name": "Python", "query": "python", "types": ["fixed", "hourly"], "min_price": None, "limit": 20},
    {"name": "Python Backend", "query": "python backend api", "types": ["fixed", "hourly"], "min_price": None, "limit": 15},
    {"name": "FastAPI", "query": "fastapi", "types": ["fixed", "hourly"], "min_price": None, "limit": 15},
    {"name": "Django", "query": "django", "types": ["fixed"], "min_price": 300, "limit": 15},
    {"name": "Agentic AI", "query": "agentic ai", "types": ["fixed", "hourly"], "min_price": None, "limit": 15},
    {"name": "AI Agents", "query": "ai agents autonomous", "types": ["fixed"], "min_price": 500, "limit": 15},
    {"name": "LLM Integration", "query": "llm integration openai", "types": ["fixed"], "min_price": 500, "limit": 15},
    {"name": "Google ADK", "query": "google adk", "types": ["fixed", "hourly"], "min_price": None, "limit": 15},
    {"name": "React", "query": "react frontend", "types": ["fixed"], "min_price": 300, "limit": 15},
    {"name": "Full Stack Python", "query": "python react full stack", "types": ["fixed"], "min_price": 500, "limit": 15},
]

# ── Red flag patterns for pre-bid analysis ──────────────────────────────

RED_FLAG_PATTERNS: list[tuple[str, str, str]] = [
    # (pattern, severity, description)
    (r"urgent.*(?:yesterday|asap|immediately|today)", "high",
     "Unrealistic urgency — client wants it 'yesterday'"),
    (r"(?:we.?ll pay|will pay).*(?:later|after|once|when)", "high",
     "Deferred payment — 'we'll pay later/after launch'"),
    (r"(?:no budget|budget.*tight|budget.*low|cheap|lowest price)", "medium",
     "Budget concerns — client signals low budget expectations"),
    (r"(?:just|only|simple|easy|quick).*(?:need|want|looking)", "medium",
     "Scope minimization — 'just a simple/quick/easy' (often scope creep)"),
    (r"(?:copy|clone|exactly like|same as).*(?:uber|airbnb|amazon|netflix|facebook|twitter|tinder)", "high",
     "Clone request — 'make an app exactly like Uber/Airbnb' (massive scope)"),
    (r"(?:no clear|vague|not sure|figure out|you decide)", "medium",
     "Vague requirements — client doesn't know what they want"),
    (r"(?:need.*yesterday|deadline.*tomorrow|due.*today)", "high",
     "Impossible deadline — due today/tomorrow"),
    (r"(?:long.?term|ongoing|full.?time).*(?:but|however).*(?:low|cheap|budget)", "medium",
     "Long-term commitment at low budget"),
    (r"(?:unpaid|free|exposure|portfolio|experience.*instead|no pay)", "high",
     "Unpaid work — 'for exposure/portfolio/experience'"),
    (r"(?:nda.*before|sign.*nda.*first|nda.*required)", "low",
     "NDA before seeing project details"),
    (r"(?:multiple.*revision|unlimited.*revision|revision.*until)", "medium",
     "Unlimited revisions — scope creep risk"),
    (r"(?:must.*have|required).*(?:5\+|10\+|many).*(?:years|experience)", "low",
     "Excessive experience requirements"),
]

# ── Client quality signal patterns ──────────────────────────────────────

CLIENT_QUALITY_PATTERNS: list[tuple[str, str, str]] = [
    # (pattern, signal_type, description)
    (r"(?:verified|payment verified)", "positive", "Verified payment method"),
    (r"(?:clear|detailed|specific).*(?:requirement|spec|brief)", "positive",
     "Clear, detailed requirements"),
    (r"(?:milestone|phase|stage).*(?:payment|delivery)", "positive",
     "Milestone-based payment structure"),
    (r"(?:previous|past|existing).*(?:developer|code|app|project)", "positive",
     "Has existing codebase — not starting from scratch"),
    (r"(?:long.?term|ongoing|regular|multiple).*(?:work|project|job)", "positive",
     "Potential for ongoing work"),
    (r"(?:responsive|communicative|available).*(?:chat|call|discuss)", "positive",
     "Client values communication"),
]


@dataclass
class ProjectAnalysis:
    """Result of pre-bid project analysis."""

    project_id: int
    title: str
    red_flags: list[dict[str, str]] = field(default_factory=list)
    client_signals: list[dict[str, str]] = field(default_factory=list)
    skill_match: dict[str, Any] = field(default_factory=dict)
    budget_assessment: dict[str, Any] = field(default_factory=dict)
    overall_verdict: str = "neutral"  # "go", "caution", "skip"
    verdict_reason: str = ""


@dataclass
class BiddingEngine:
    """Orchestrates project search, scoring, and bidding.

    Supports interactive review mode (--review flag) where top candidates
    are shown with full analysis and the user approves/rejects each one.
    """

    api: APIClient
    state: StateManager
    email: EmailSender
    max_bids: int = 2
    min_score: int = 40
    dry_run: bool = False
    review_mode: bool = False
    min_rate: float = 25.0  # Gowtham's minimum acceptable hourly rate

    async def run(self) -> dict[str, Any]:
        """Run the full bidding pipeline.

        Returns summary dict with results.
        """
        console.print(Panel.fit(
            "[bold blue]Freelancer Bot v2 — Project Bidding[/bold blue]\n"
            f"Max bids: {self.max_bids} | Min score: {self.min_score} | "
            f"Mode: {'[yellow]DRY RUN[/yellow]' if self.dry_run else '[green]LIVE[/green]'} | "
            f"Review: {'[cyan]ON[/cyan]' if self.review_mode else '[dim]OFF[/dim]'}",
            border_style="blue",
        ))

        # Phase 1: Parallel search
        all_projects = await self._search_all()

        # Phase 2: Score and filter
        candidates = self._score_and_filter(all_projects)

        # Phase 3: Pre-bid analysis (fetch full details + analyze)
        if candidates:
            candidates = await self._analyze_candidates(candidates)

        # Phase 4: Review mode (interactive approval)
        if self.review_mode and candidates:
            candidates = await self._interactive_review(candidates)

        # Phase 5: Bid on top candidates
        results = await self._place_bids(candidates)

        # Phase 6: Send report
        await self._send_report(results)

        # Update state
        self.state.touch_last_run("bidding")
        self.state.save_bidding()

        return results

    async def _search_all(self) -> list[dict[str, Any]]:
        """Run all 12 searches in parallel."""
        console.print("\n[bold]🔍 Searching projects...[/bold]")

        seen_ids: set[int] = set()
        all_projects: list[dict[str, Any]] = []

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Searching...", total=len(SEARCH_CONFIGS))

            async def search_one(cfg: dict[str, Any]) -> list[dict[str, Any]]:
                try:
                    result = await self.api.search_projects(
                        query=cfg["query"],
                        project_types=cfg["types"],
                        limit=cfg["limit"],
                    )
                    projects = result.get("result", {}).get("projects", [])
                    progress.advance(task)
                    return projects
                except Exception as e:
                    logger.error("search_failed", config=cfg["name"], error=str(e)[:200])
                    progress.advance(task)
                    return []

            # Run all searches concurrently
            tasks_list = [search_one(cfg) for cfg in SEARCH_CONFIGS]
            results = await asyncio.gather(*tasks_list)

        for i, projects in enumerate(results):
            cfg = SEARCH_CONFIGS[i]
            new_count = 0
            for p in projects:
                pid = p.get("id")
                if pid and pid not in seen_ids:
                    seen_ids.add(pid)
                    p["_search_category"] = cfg["name"]
                    all_projects.append(p)
                    new_count += 1
            logger.info(
                "search_result",
                category=cfg["name"],
                total=len(projects),
                new=new_count,
            )

        console.print(f"[green]✓[/green] Found {len(all_projects)} unique projects across {len(SEARCH_CONFIGS)} searches")
        return all_projects

    def _score_and_filter(self, projects: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Score all projects and filter to candidates above threshold."""
        console.print("\n[bold]📊 Scoring projects...[/bold]")

        candidates: list[dict[str, Any]] = []
        skipped_known = 0
        skipped_excluded = 0
        skipped_low_score = 0

        for project in projects:
            pid = project.get("id")

            # Skip known projects
            if self.state.is_project_known(pid):
                skipped_known += 1
                continue

            # Score
            scoring = score_project(project)

            if scoring["breakdown"].get("excluded"):
                skipped_excluded += 1
                continue

            if not scoring["should_bid"]:
                skipped_low_score += 1
                continue

            project["_score"] = scoring["score"]
            project["_score_breakdown"] = scoring["breakdown"]
            project["_matched_keywords"] = scoring["matched_keywords"]
            candidates.append(project)

        # Sort by score descending
        candidates.sort(key=lambda p: p["_score"], reverse=True)

        console.print(f"[green]✓[/green] {len(candidates)} candidates above threshold (min {self.min_score})")
        console.print(f"  Skipped: {skipped_known} known, {skipped_excluded} excluded, {skipped_low_score} low score")

        # Display top candidates
        if candidates:
            table = Table(title="Top Candidates", show_header=True, header_style="bold cyan")
            table.add_column("#", style="dim", width=3)
            table.add_column("Project", style="white", max_width=50)
            table.add_column("Score", style="green", justify="right")
            table.add_column("Bids", justify="right")
            table.add_column("Budget", justify="right")
            table.add_column("Category", style="dim")

            for i, p in enumerate(candidates[:10], 1):
                title = p.get("title", "Untitled")[:47]
                budget = p.get("budget", {})
                if isinstance(budget, dict):
                    bmin = budget.get("minimum", 0)
                    bmax = budget.get("maximum", 0)
                    budget_str = f"${bmin}-${bmax}" if bmax else f"${bmin}"
                else:
                    budget_str = "—"
                bid_count = p.get("bid_count", p.get("bids", 0))
                if isinstance(bid_count, dict):
                    bid_count = bid_count.get("count", 0)

                table.add_row(
                    str(i),
                    title,
                    str(p["_score"]),
                    str(bid_count),
                    budget_str,
                    p.get("_search_category", "—"),
                )

            console.print(table)

        return candidates

    # ── Pre-bid analysis ─────────────────────────────────────────────────

    async def _analyze_candidates(
        self, candidates: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Fetch full project details and run pre-bid analysis on top candidates.

        For each candidate (up to max_bids * 3 to have enough to choose from):
        1. Fetch full project description via api.get_project()
        2. Run red flag detection
        3. Assess skill match quality
        4. Evaluate budget realism
        5. Check client quality signals
        6. Attach analysis to project dict
        """
        analyze_count = min(len(candidates), self.max_bids * 3)
        to_analyze = candidates[:analyze_count]

        if not to_analyze:
            return candidates

        console.print(f"\n[bold]🔬 Pre-bid analysis on top {len(to_analyze)} candidates...[/bold]")

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Analyzing...", total=len(to_analyze))

            async def analyze_one(project: dict[str, Any]) -> dict[str, Any]:
                pid = project.get("id")
                try:
                    # Fetch full project details
                    full = await self.api.get_project(pid)
                    result_data = full.get("result", {})
                    # Merge full description into project
                    full_desc = result_data.get("description", "")
                    if full_desc:
                        project["description"] = full_desc
                    # Merge any additional fields
                    for key in ("bid_stats", "bid_avg", "bid_count", "type", "budget",
                                "currency", "status", "time_submitted", "time_updated",
                                "seo_url", "upgrades", "files"):
                        if key in result_data and key not in project:
                            project[key] = result_data[key]

                    # Run analysis
                    analysis = analyze_project(project)
                    project["_analysis"] = analysis
                    progress.advance(task)
                    return project
                except Exception as e:
                    logger.warning("analysis_failed", project_id=pid, error=str(e)[:200])
                    # Still run analysis with whatever data we have
                    analysis = analyze_project(project)
                    project["_analysis"] = analysis
                    progress.advance(task)
                    return project

            analyzed = await asyncio.gather(*[analyze_one(p) for p in to_analyze])

        # Re-sort: push "skip" verdict projects to the bottom
        go_projects = [p for p in analyzed if p.get("_analysis") and p["_analysis"].overall_verdict != "skip"]
        caution_projects = [p for p in analyzed if p.get("_analysis") and p["_analysis"].overall_verdict == "caution"]
        skip_projects = [p for p in analyzed if p.get("_analysis") and p["_analysis"].overall_verdict == "skip"]

        # Order: go first, then caution, then skip (but keep within score order)
        reordered = go_projects + caution_projects + skip_projects

        # Add back unanalyzed candidates
        reordered.extend(candidates[analyze_count:])

        # Show analysis summary
        go_count = len(go_projects)
        caution_count = len(caution_projects)
        skip_count = len(skip_projects)
        console.print(
            f"[green]✓[/green] Analysis complete: "
            f"[green]{go_count} go[/green], "
            f"[yellow]{caution_count} caution[/yellow], "
            f"[red]{skip_count} skip[/red]"
        )

        return reordered

    # ── Interactive review mode ──────────────────────────────────────────

    async def _interactive_review(
        self, candidates: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Interactive review: show full analysis and let user approve/reject.

        Displays each candidate with:
        - Full project details
        - Score breakdown
        - Red flags and client signals
        - Skill match assessment
        - Budget analysis
        - Generated proposal preview
        - Bid amount and period

        User can: approve (y), reject (n), skip to next (s), or quit (q).
        """
        console.print("\n[bold cyan]🔍 Interactive Review Mode[/bold cyan]")
        console.print("[dim]Review each candidate and approve/reject before bidding.[/dim]")
        console.print("[dim]Commands: [green]y[/green]=approve, [red]n[/red]=reject, [cyan]s[/cyan]=skip, [yellow]q[/yellow]=quit[/dim]\n")

        approved: list[dict[str, Any]] = []
        rejected: list[dict[str, Any]] = []

        for i, project in enumerate(candidates, 1):
            if len(approved) >= self.max_bids:
                break

            pid = project.get("id")
            title = project.get("title", "Untitled")
            score = project.get("_score", 0)
            analysis = project.get("_analysis")

            # ── Display project details ────────────────────────────────

            console.print(Panel.fit(
                f"[bold white]#{i}: {title}[/bold white]\n"
                f"ID: {pid} | Score: {score} | "
                f"Category: {project.get('_search_category', '—')}",
                border_style="cyan",
            ))

            # Description preview
            desc = project.get("description", "") or project.get("preview_description", "")
            if desc:
                desc_preview = desc[:300].replace("\n", " ")
                if len(desc) > 300:
                    desc_preview += "..."
                console.print(f"[dim]Description:[/dim] {desc_preview}")

            # Budget info
            budget = project.get("budget", {})
            if isinstance(budget, dict):
                bmin = budget.get("minimum", 0)
                bmax = budget.get("maximum", 0)
                ptype = project.get("type", "fixed")
                console.print(f"[dim]Budget:[/dim] ${bmin}-${bmax} ({ptype})")

            # Score breakdown
            breakdown = project.get("_score_breakdown", {})
            keywords = project.get("_matched_keywords", [])
            console.print(
                f"[dim]Score breakdown:[/dim] "
                f"Keywords({breakdown.get('keywords', 0)}) + "
                f"Budget({breakdown.get('budget', 0)}) + "
                f"Competition({breakdown.get('competition', 0)})"
            )
            if keywords:
                console.print(f"[dim]Matched:[/dim] {', '.join(keywords)}")

            # ── Analysis results ───────────────────────────────────────

            if analysis:
                # Verdict
                verdict_color = {"go": "green", "caution": "yellow", "skip": "red"}
                vcolor = verdict_color.get(analysis.overall_verdict, "white")
                console.print(f"\n[bold {vcolor}]Verdict: {analysis.overall_verdict.upper()}[/bold {vcolor}]")
                if analysis.verdict_reason:
                    console.print(f"[{vcolor}]{analysis.verdict_reason}[/{vcolor}]")

                # Red flags
                if analysis.red_flags:
                    console.print("\n[bold red]⚠ Red Flags:[/bold red]")
                    for rf in analysis.red_flags:
                        sev_color = {"high": "red", "medium": "yellow", "low": "dim"}
                        sc = sev_color.get(rf["severity"], "white")
                        console.print(f"  [{sc}]● [{rf['severity']}] {rf['description']}[/{sc}]")

                # Client signals
                if analysis.client_signals:
                    console.print("\n[bold green]✓ Positive Signals:[/bold green]")
                    for cs in analysis.client_signals:
                        console.print(f"  [green]● {cs['description']}[/green]")

                # Skill match
                sm = analysis.skill_match
                if sm:
                    match_color = "green" if sm.get("is_match", False) else "yellow"
                    console.print(f"\n[bold]Skill Match:[/bold] [{match_color}]{sm.get('assessment', '')}[/{match_color}]")
                    if sm.get("matched_skills"):
                        console.print(f"  [dim]Skills: {', '.join(sm['matched_skills'])}[/dim]")

                # Budget assessment
                ba = analysis.budget_assessment
                if ba:
                    realism_color = "green" if ba.get("is_realistic", False) else "yellow"
                    console.print(f"[bold]Budget:[/bold] [{realism_color}]{ba.get('assessment', '')}[/{realism_color}]")

            # ── Bid preview ─────────────────────────────────────────────

            bid_avg = project.get("bid_avg", None)
            if isinstance(bid_avg, dict):
                bid_avg = bid_avg.get("avg")
            bid_amount = calculate_bid_amount(project, bid_avg)
            bid_period = calculate_bid_period(bid_amount)

            console.print(f"\n[bold]Proposed Bid:[/bold] [green]${bid_amount:,.2f}[/green] — [cyan]{bid_period} days[/cyan]")

            # Proposal preview (first 200 chars)
            proposal = generate_proposal(project, bid_amount, bid_period)
            proposal_preview = proposal[:200].replace("\n", " ")
            console.print(f"[dim]Proposal preview:[/dim] {proposal_preview}...")

            # ── Get user decision ───────────────────────────────────────

            console.print()
            decision = console.input(
                f"[bold]Approve bid?[/bold] "
                f"[[green]y[/green]/[red]n[/red]/[cyan]s[/cyan]kip/[yellow]q[/yellow]uit]: "
            ).strip().lower()

            if decision == "q":
                console.print("[yellow]Quitting review mode.[/yellow]")
                break
            elif decision == "y":
                project["_approved"] = True
                project["_bid_amount"] = bid_amount
                project["_bid_period"] = bid_period
                project["_proposal"] = proposal
                approved.append(project)
                console.print(f"[green]✓ Approved #{i}: {title[:60]}[/green]\n")
            elif decision == "n":
                project["_approved"] = False
                rejected.append(project)
                console.print(f"[red]✗ Rejected #{i}: {title[:60]}[/red]\n")
            else:  # 's' or anything else = skip
                console.print(f"[cyan]⊘ Skipped #{i} (will not bid)[/cyan]\n")

        console.print(
            f"\n[bold]Review Summary:[/bold] "
            f"[green]{len(approved)} approved[/green], "
            f"[red]{len(rejected)} rejected[/red]"
        )

        return approved

    # ── Place bids ───────────────────────────────────────────────────────

    async def _place_bids(self, candidates: list[dict[str, Any]]) -> dict[str, Any]:
        """Place bids on top candidates up to max_bids."""
        console.print(f"\n[bold]💰 Placing bids (max {self.max_bids})...[/bold]")

        results: dict[str, Any] = {
            "bids_placed": [],
            "bids_failed": [],
            "bids_skipped": [],
            "total_candidates": len(candidates),
        }

        bids_placed = 0

        for project in candidates:
            if bids_placed >= self.max_bids:
                results["bids_skipped"].append({
                    "id": project.get("id"),
                    "title": project.get("title"),
                    "score": project["_score"],
                    "reason": "max_bids_reached",
                })
                continue

            pid = project.get("id")
            title = project.get("title", "Untitled")
            score = project["_score"]

            # Skip projects with "skip" verdict (unless in review mode where user approved)
            analysis = project.get("_analysis")
            if analysis and analysis.overall_verdict == "skip" and not project.get("_approved"):
                results["bids_skipped"].append({
                    "id": pid,
                    "title": title,
                    "score": score,
                    "reason": f"analysis_skip: {analysis.verdict_reason}",
                })
                continue

            # Use pre-computed bid/proposal from review mode, or calculate now
            if project.get("_approved") and project.get("_bid_amount"):
                bid_amount = project["_bid_amount"]
                bid_period = project["_bid_period"]
                proposal = project.get("_proposal", "")
            else:
                bid_avg = project.get("bid_avg", None)
                if isinstance(bid_avg, dict):
                    bid_avg = bid_avg.get("avg")
                bid_amount = calculate_bid_amount(project, bid_avg)
                bid_period = calculate_bid_period(bid_amount)
                proposal = generate_proposal(project, bid_amount, bid_period)

            if self.dry_run:
                console.print(
                    f"  [yellow]DRY RUN[/yellow] Would bid ${bid_amount:,.2f} "
                    f"({bid_period}d) on [bold]{title}[/bold] (Score: {score})"
                )
                results["bids_placed"].append({
                    "id": pid,
                    "title": title,
                    "score": score,
                    "amount": bid_amount,
                    "period": bid_period,
                    "dry_run": True,
                })
                bids_placed += 1
                continue

            try:
                console.print(
                    f"  [bold cyan]Bidding[/bold cyan] ${bid_amount:,.2f} "
                    f"({bid_period}d) on [bold]{title}[/bold] (Score: {score})..."
                )

                response = await self.api.place_bid(
                    project_id=pid,
                    amount=bid_amount,
                    period=bid_period,
                    description=proposal,
                )

                if response.get("status") == "success" or "id" in response.get("result", {}):
                    console.print(f"    [green]✓ Bid placed successfully![/green]")
                    self.state.mark_bid_success(pid)
                    self.state.analytics.record_bid(pid, bid_amount, "placed")
                    results["bids_placed"].append({
                        "id": pid,
                        "title": title,
                        "score": score,
                        "amount": bid_amount,
                        "period": bid_period,
                    })
                    bids_placed += 1
                else:
                    console.print(f"    [red]✗ Bid failed[/red]")
                    self.state.mark_bid_attempted(pid)
                    results["bids_failed"].append({
                        "id": pid,
                        "title": title,
                        "score": score,
                        "error": str(response)[:200],
                    })

            except Exception as e:
                logger.error("bid_error", project_id=pid, error=str(e)[:200])
                console.print(f"    [red]✗ Error: {str(e)[:100]}[/red]")
                self.state.mark_bid_attempted(pid)
                results["bids_failed"].append({
                    "id": pid,
                    "title": title,
                    "score": score,
                    "error": str(e)[:200],
                })

        # Summary
        console.print(f"\n[bold]📋 Bid Summary:[/bold]")
        console.print(f"  [green]✓ Placed:[/green] {len(results['bids_placed'])}")
        console.print(f"  [red]✗ Failed:[/red] {len(results['bids_failed'])}")
        console.print(f"  [yellow]⊘ Skipped:[/yellow] {len(results['bids_skipped'])}")

        return results

    async def _send_report(self, results: dict[str, Any]) -> None:
        """Send email report with bidding results."""
        placed = results["bids_placed"]
        failed = results["bids_failed"]
        skipped = results["bids_skipped"]

        if not placed and not failed:
            console.print("[dim]No bids to report — skipping email[/dim]")
            return

        subject = f"🤖 Freelancer Bot: {len(placed)} Bids Placed — {len(failed)} Failed"

        summary_parts = [
            f"Bidding run completed. {len(placed)} bids placed, {len(failed)} failed, "
            f"{len(skipped)} skipped (max bids reached)."
        ]
        if placed:
            total_bid = sum(b.get("amount", 0) for b in placed)
            summary_parts.append(f"Total bid value: ${total_bid:,.2f}")

        summary = " ".join(summary_parts)

        details: list[dict[str, Any]] = []
        for b in placed:
            details.append({
                "title": b["title"],
                "link": f"https://www.freelancer.com/projects/{b.get('id', '')}",
                "score": str(b["score"]),
                "bid": f"${b['amount']:,.2f} ({b['period']}d)",
                "status": "bid",
            })
        for b in failed:
            details.append({
                "title": b["title"],
                "link": f"https://www.freelancer.com/projects/{b.get('id', '')}",
                "score": str(b["score"]),
                "bid": "—",
                "status": "failed",
            })

        self.email.send_report(subject, summary, details, report_type="bidding", dry_run=self.dry_run)


# ── Standalone analysis function (usable outside the engine) ────────────

def analyze_project(project: dict[str, Any]) -> ProjectAnalysis:
    """Analyze a project for red flags, skill match, budget realism, and client quality.

    This is the core pre-bid intelligence. It examines the full project description
    and metadata to determine whether this project is worth bidding on.

    Args:
        project: Project dict with full description (from api.get_project())

    Returns:
        ProjectAnalysis with red flags, signals, skill match, budget assessment, and verdict
    """
    pid = project.get("id", 0)
    title = project.get("title", "")
    description = project.get("description", "") or project.get("preview_description", "")
    full_text = f"{title} {description}".lower()

    analysis = ProjectAnalysis(project_id=pid, title=title)

    # ── 1. Red flag detection ──────────────────────────────────────────

    for pattern, severity, desc in RED_FLAG_PATTERNS:
        if re.search(pattern, full_text):
            analysis.red_flags.append({
                "pattern": pattern,
                "severity": severity,
                "description": desc,
            })

    # ── 2. Client quality signals ──────────────────────────────────────

    for pattern, signal_type, desc in CLIENT_QUALITY_PATTERNS:
        if re.search(pattern, full_text):
            analysis.client_signals.append({
                "pattern": pattern,
                "type": signal_type,
                "description": desc,
            })

    # ── 3. Skill match assessment ──────────────────────────────────────

    # Gowtham's core skills
    core_skills = {
        "python": ["python", "fastapi", "django", "flask", "pydantic"],
        "flutter": ["flutter", "dart", "mobile app", "ios", "android"],
        "ai_agentic": ["ai", "agentic", "llm", "langchain", "llamaindex", "rag",
                       "openai", "claude", "gemini", "google adk", "autonomous agent"],
        "react": ["react", "next.js", "nextjs", "typescript", "frontend"],
        "backend": ["api", "rest", "graphql", "postgresql", "redis", "docker", "microservice"],
    }

    matched_skills: list[str] = []
    missing_core: list[str] = []

    for skill_area, keywords in core_skills.items():
        area_match = False
        for kw in keywords:
            if kw in full_text:
                area_match = True
                break
        if area_match:
            matched_skills.append(skill_area)
        else:
            # Only flag as missing if the project seems to need it
            # (we don't flag missing flutter if project is pure backend)
            pass

    # Check for skills Gowtham does NOT have
    foreign_skills = {
        "wordpress": ["wordpress", "wp", "woocommerce"],
        "php": ["php", "laravel", "symfony", "codeigniter"],
        "ruby": ["ruby", "rails", "ruby on rails"],
        "java": ["java", "spring boot", "hibernate", "kotlin"],
        "csharp": ["c#", ".net", "asp.net", "blazor"],
        "go": ["golang", "go lang"],
        "rust": ["rust", "cargo"],
        "blockchain": ["solidity", "web3", "smart contract", "blockchain", "nft"],
        "devops_only": ["kubernetes", "terraform", "jenkins", "ansible", "helm"],
    }

    foreign_matches: list[str] = []
    for area, keywords in foreign_skills.items():
        for kw in keywords:
            if kw in full_text:
                foreign_matches.append(area)
                break

    if matched_skills:
        analysis.skill_match = {
            "is_match": len(matched_skills) >= 1 and len(foreign_matches) == 0,
            "matched_skills": matched_skills,
            "foreign_skills": foreign_matches,
            "assessment": (
                f"Strong match — skills align: {', '.join(matched_skills)}"
                if len(matched_skills) >= 2 and not foreign_matches
                else f"Partial match — has {', '.join(matched_skills)}"
                if matched_skills and not foreign_matches
                else f"Partial match but has foreign requirements: {', '.join(foreign_matches)}"
                if matched_skills and foreign_matches
                else f"Poor match — requires: {', '.join(foreign_matches)}"
            ),
        }
    else:
        analysis.skill_match = {
            "is_match": False,
            "matched_skills": [],
            "foreign_skills": foreign_matches,
            "assessment": "No core skill match detected — review carefully",
        }

    # ── 4. Budget realism assessment ───────────────────────────────────

    budget = project.get("budget", {})
    if isinstance(budget, dict):
        budget_min = budget.get("minimum", 0)
        budget_max = budget.get("maximum", 0)
    else:
        budget_min = 0
        budget_max = 0

    project_type = project.get("type", "fixed")

    # Heuristic: estimate scope from description length and complexity keywords
    desc_length = len(description) if description else 0
    complexity_keywords = [
        "complex", "advanced", "enterprise", "scalable", "real-time", "realtime",
        "machine learning", "ai", "agent", "microservice", "multi-platform",
        "cross-platform", "full stack", "end-to-end", "production",
    ]
    complexity_score = sum(1 for kw in complexity_keywords if kw in full_text)

    # Rough scope estimate
    if desc_length > 1000 and complexity_score >= 3:
        estimated_scope = "large"
        reasonable_min = 2000
    elif desc_length > 500 or complexity_score >= 2:
        estimated_scope = "medium"
        reasonable_min = 500
    elif desc_length > 200:
        estimated_scope = "small"
        reasonable_min = 150
    else:
        estimated_scope = "tiny"
        reasonable_min = 50

    is_realistic = (budget_max >= reasonable_min) if budget_max > 0 else (budget_min >= reasonable_min)

    analysis.budget_assessment = {
        "estimated_scope": estimated_scope,
        "reasonable_minimum": reasonable_min,
        "budget_min": budget_min,
        "budget_max": budget_max,
        "project_type": project_type,
        "is_realistic": is_realistic,
        "assessment": (
            f"Budget (${budget_min}-${budget_max}) is realistic for {estimated_scope} scope"
            if is_realistic
            else f"Budget (${budget_min}-${budget_max}) seems low for {estimated_scope} scope "
                 f"(reasonable min: ~${reasonable_min})"
        ),
    }

    # ── 5. Overall verdict ─────────────────────────────────────────────

    high_flags = [rf for rf in analysis.red_flags if rf["severity"] == "high"]
    medium_flags = [rf for rf in analysis.red_flags if rf["severity"] == "medium"]

    if high_flags:
        analysis.overall_verdict = "skip"
        analysis.verdict_reason = f"{len(high_flags)} high-severity red flag(s): {high_flags[0]['description']}"
    elif not analysis.skill_match.get("is_match", False) and analysis.skill_match.get("foreign_skills"):
        analysis.overall_verdict = "skip"
        analysis.verdict_reason = f"Requires skills outside Gowtham's stack: {', '.join(analysis.skill_match['foreign_skills'])}"
    elif medium_flags and not analysis.budget_assessment.get("is_realistic", True):
        analysis.overall_verdict = "skip"
        analysis.verdict_reason = f"Multiple concerns: {len(medium_flags)} red flags + unrealistic budget"
    elif medium_flags:
        analysis.overall_verdict = "caution"
        analysis.verdict_reason = f"{len(medium_flags)} medium-severity concern(s) — review before bidding"
    elif not analysis.budget_assessment.get("is_realistic", True):
        analysis.overall_verdict = "caution"
        analysis.verdict_reason = "Budget may be below reasonable minimum for scope"
    elif analysis.skill_match.get("is_match", False) and not analysis.red_flags:
        analysis.overall_verdict = "go"
        analysis.verdict_reason = "Good match — no red flags, skills align, budget reasonable"
    else:
        analysis.overall_verdict = "go"
        analysis.verdict_reason = "Acceptable — proceed with standard bid"

    return analysis
