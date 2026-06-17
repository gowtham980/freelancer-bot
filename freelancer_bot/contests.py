"""Tech contest discovery + implementation — 18 search categories, AI-powered analysis.

Enhanced with:
- AI contest feasibility analysis via Grok/LLM
- Auto-implementation with code generation
- NLP-aware design filtering (design+tech = tech contest)
- Contest quality scoring (description detail, prize-to-scope ratio)
- --implement flag for actual code generation vs discovery-only
"""

from __future__ import annotations

import asyncio
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import structlog
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from freelancer_bot.api import APIClient
from freelancer_bot.email import EmailSender
from freelancer_bot.grok import (
    ContestFeasibility,
    DesignTechClassification,
    GrokClient,
    GrokError,
    ImplementationResult,
)
from freelancer_bot.proposals import generate_contest_proposal
from freelancer_bot.scoring import score_tech_contest
from freelancer_bot.state import StateManager

logger = structlog.get_logger(__name__)
console = Console()

# ── 18 Tech Contest Search Configs ──────────────────────────────────────

CONTEST_SEARCH_CONFIGS: list[dict[str, Any]] = [
    {"name": "Python", "query": "python", "limit": 50},
    {"name": "Flutter", "query": "flutter", "limit": 50},
    {"name": "Django", "query": "django", "limit": 50},
    {"name": "FastAPI", "query": "fastapi", "limit": 50},
    {"name": "React", "query": "react", "limit": 50},
    {"name": "Full Stack", "query": "full stack", "limit": 50},
    {"name": "AI/ML", "query": "ai ml", "limit": 50},
    {"name": "Artificial Intelligence", "query": "artificial intelligence", "limit": 50},
    {"name": "Mobile App Dev", "query": "mobile app development", "limit": 50},
    {"name": "Web App", "query": "web application", "limit": 50},
    {"name": "API Development", "query": "api development", "limit": 50},
    {"name": "Backend", "query": "backend", "limit": 50},
    {"name": "Node.js", "query": "node.js", "limit": 50},
    {"name": "JavaScript", "query": "javascript", "limit": 50},
    {"name": "TypeScript", "query": "typescript", "limit": 50},
    {"name": "Google ADK", "query": "google adk", "limit": 25},
    {"name": "LLM", "query": "llm", "limit": 25},
    {"name": "OpenAI", "query": "openai", "limit": 25},
    {"name": "LangChain", "query": "langchain", "limit": 25},
    {"name": "AI Agent", "query": "ai agent", "limit": 25},
    {"name": "RAG", "query": "rag", "limit": 25},
    {"name": "Web Scraping", "query": "web scraping", "limit": 25},
    {"name": "Automation", "query": "automation", "limit": 25},
    {"name": "Bot Dev", "query": "bot", "limit": 25},
]

# ── AI Implementation Capabilities (fallback when LLM unavailable) ──────

AI_CAN_IMPLEMENT: list[str] = [
    "python scripts", "apis", "web scraping", "automation", "data processing",
    "cli tools", "telegram bots", "discord bots", "fastapi apps", "flask apps",
    "simple django", "database scripts", "csv processing", "json processing",
    "file conversion", "text processing", "basic image processing",
    "api integrations", "webhooks", "scheduled tasks", "flutter apps",
]

AI_CANNOT_IMPLEMENT: list[str] = [
    "ios native", "android native", "react native", "ui/ux design",
    "3d", "animation", "video editing", "audio processing", "hardware",
    "desktop apps", "game development", "ml model training", "blockchain",
    "kubernetes", "security audits", "production deployment",
    "wordpress themes", "shopify themes",
]

IMPLEMENTATIONS_DIR = Path.home() / ".local" / "share" / "freelancer-bot" / "contest_implementations"


@dataclass
class ContestsEngine:
    """Orchestrates tech contest discovery, scoring, and implementation.

    Enhanced with AI-powered feasibility analysis and code generation.
    """

    api: APIClient
    state: StateManager
    email: EmailSender
    max_matches: int = 10
    min_score: int = 50
    auto_implement: bool = True
    dry_run: bool = False
    # ── New fields ──────────────────────────────────────────────────
    implement: bool = False  # --implement flag: actually generate code
    grok: GrokClient | None = None  # LLM client for AI analysis
    use_ai_analysis: bool = True  # Enable AI-powered feasibility analysis

    async def run(self) -> dict[str, Any]:
        """Run the full contest discovery pipeline.

        Returns summary dict with results.
        """
        console.print(Panel.fit(
            "[bold blue]Freelancer Bot v2 — Tech Contest Discovery[/bold blue]\n"
            f"Max matches: {self.max_matches} | Min score: {self.min_score} | "
            f"Auto-implement: {'[green]ON[/green]' if self.auto_implement else '[yellow]OFF[/yellow]'} | "
            f"AI Analysis: {'[green]ON[/green]' if self.use_ai_analysis else '[yellow]OFF[/yellow]'} | "
            f"Code Gen: {'[green]ON[/green]' if self.implement else '[yellow]OFF[/yellow]'} | "
            f"Mode: {'[yellow]DRY RUN[/yellow]' if self.dry_run else '[green]LIVE[/green]'}",
            border_style="blue",
        ))

        # Initialize Grok client if AI analysis is enabled
        if self.use_ai_analysis and self.grok is None:
            self.grok = GrokClient.from_config()

        # Phase 1: Parallel search
        all_contests = await self._search_all()

        # Phase 2: Score and filter (with smart design filtering)
        candidates = self._score_and_filter(all_contests)

        # Phase 3: AI feasibility analysis (NEW)
        if self.use_ai_analysis and candidates:
            candidates = await self._analyze_feasibility(candidates)

        # Phase 4: Implement top matches
        results = await self._implement_contests(candidates)

        # Phase 5: Send report
        await self._send_report(results)

        # Update state
        self.state.touch_last_run("contests")
        self.state.save_contests()

        return results

    async def _search_all(self) -> list[dict[str, Any]]:
        """Run all 18 contest searches in parallel."""
        console.print("\n[bold]🔍 Searching tech contests...[/bold]")

        seen_ids: set[int] = set()
        all_contests: list[dict[str, Any]] = []

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Searching...", total=len(CONTEST_SEARCH_CONFIGS))

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
                    logger.error("contest_search_failed", config=cfg["name"], error=str(e)[:200])
                    progress.advance(task)
                    return []

            tasks_list = [search_one(cfg) for cfg in CONTEST_SEARCH_CONFIGS]
            results = await asyncio.gather(*tasks_list)

        for i, contests in enumerate(results):
            cfg = CONTEST_SEARCH_CONFIGS[i]
            new_count = 0
            for c in contests:
                cid = c.get("id")
                if cid and cid not in seen_ids:
                    seen_ids.add(cid)
                    c["_search_category"] = cfg["name"]
                    all_contests.append(c)
                    new_count += 1
            logger.info(
                "contest_search_result",
                category=cfg["name"],
                total=len(contests),
                new=new_count,
            )

        console.print(f"[green]✓[/green] Found {len(all_contests)} unique contests across {len(CONTEST_SEARCH_CONFIGS)} searches")
        return all_contests

    def _score_and_filter(self, contests: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Score all contests and filter to candidates above threshold.

        Uses enhanced scoring with NLP-aware design filtering,
        quality scoring, and prize-to-scope ratio.
        """
        console.print("\n[bold]📊 Scoring contests...[/bold]")

        candidates: list[dict[str, Any]] = []
        skipped_seen = 0
        skipped_design = 0
        skipped_low_score = 0
        design_tech_mix_saved = 0  # NEW: track contests saved by smart filtering

        for contest in contests:
            cid = contest.get("id")

            # Skip already seen
            if self.state.is_contest_seen(cid):
                skipped_seen += 1
                continue

            # Mark as seen
            self.state.mark_contest_seen(cid)

            # Score (enhanced with smart design filtering)
            scoring = score_tech_contest(contest)

            if scoring.get("is_design"):
                skipped_design += 1
                continue

            # Track design-tech mix saves
            classification = scoring.get("breakdown", {}).get("classification", {})
            if classification.get("category") == "mixed_design_tech":
                design_tech_mix_saved += 1

            if not scoring["should_enter"]:
                skipped_low_score += 1
                continue

            contest["_score"] = scoring["score"]
            contest["_score_breakdown"] = scoring["breakdown"]
            contest["_matched_keywords"] = scoring["matched_keywords"]
            contest["_classification"] = classification
            candidates.append(contest)

        # Sort by score descending
        candidates.sort(key=lambda c: c["_score"], reverse=True)

        console.print(f"[green]✓[/green] {len(candidates)} candidates above threshold (min {self.min_score})")
        console.print(f"  Skipped: {skipped_seen} seen, {skipped_design} design-filtered, {skipped_low_score} low score")
        if design_tech_mix_saved > 0:
            console.print(f"  [bold cyan]💡 Smart filter saved {design_tech_mix_saved} design+tech mixed contests[/bold cyan]")

        # Display top candidates
        if candidates:
            table = Table(title="Top Tech Contests", show_header=True, header_style="bold cyan")
            table.add_column("#", style="dim", width=3)
            table.add_column("Contest", style="white", max_width=50)
            table.add_column("Score", style="green", justify="right")
            table.add_column("Prize", justify="right")
            table.add_column("Entries", justify="right")
            table.add_column("Category", style="dim")
            table.add_column("Quality", style="yellow", justify="right")  # NEW

            for i, c in enumerate(candidates[:15], 1):
                title = c.get("title", "Untitled")[:47]
                prize = c.get("prize", 0)
                if isinstance(prize, dict):
                    prize = prize.get("amount", 0)
                entry_count = c.get("entry_count", c.get("entries", 0))
                if isinstance(entry_count, dict):
                    entry_count = entry_count.get("count", 0)

                # Quality indicator
                breakdown = c.get("_score_breakdown", {})
                quality = breakdown.get("quality", 0)
                ratio = breakdown.get("prize_to_scope", 0)
                quality_str = f"Q{quality}/R{ratio}"

                # Mark mixed contests
                classification = c.get("_classification", {})
                cat_str = c.get("_search_category", "—")
                if classification.get("category") == "mixed_design_tech":
                    cat_str = f"{cat_str} 🔀"

                table.add_row(
                    str(i),
                    title,
                    str(c["_score"]),
                    f"${prize}",
                    str(entry_count),
                    cat_str,
                    quality_str,
                )

            console.print(table)

        return candidates

    async def _analyze_feasibility(self, candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Run AI-powered feasibility analysis on top candidates.

        Fetches full contest descriptions and analyzes:
        - Can AI actually implement this?
        - What's the actual scope?
        - Is the prize worth the effort?
        - What would the implementation approach be?

        Filters out contests that AI determines are not feasible.
        """
        if not self.grok:
            return candidates

        console.print(f"\n[bold]🤖 AI Feasibility Analysis (top {min(len(candidates), 15)})...[/bold]")

        analyzed: list[dict[str, Any]] = []
        skipped_not_feasible = 0
        skipped_not_worth = 0
        skipped_ai_error = 0

        # Only analyze top candidates to save API calls
        to_analyze = candidates[:15]

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Analyzing with AI...", total=len(to_analyze))

            for contest in to_analyze:
                cid = contest.get("id")
                title = contest.get("title", "Untitled")

                try:
                    # Fetch full contest description for better analysis
                    full_contest = contest
                    try:
                        full_contest = await self.api.get_contest(cid)
                        # Merge search metadata back
                        full_contest["_search_category"] = contest.get("_search_category")
                        full_contest["_score"] = contest.get("_score")
                        full_contest["_score_breakdown"] = contest.get("_score_breakdown")
                        full_contest["_matched_keywords"] = contest.get("_matched_keywords")
                        full_contest["_classification"] = contest.get("_classification")
                    except Exception as e:
                        logger.warning("full_contest_fetch_failed", contest_id=cid, error=str(e)[:200])
                        # Use the search result as-is

                    # Run AI feasibility analysis
                    feasibility = await self.grok.analyze_contest_feasibility(full_contest)

                    # Store analysis results
                    full_contest["_feasibility"] = feasibility.to_dict()

                    if not feasibility.can_implement:
                        console.print(
                            f"  [yellow]⊘[/yellow] AI says NO to [bold]{title}[/bold]: "
                            f"{feasibility.worth_it_reason or 'cannot implement'}"
                        )
                        skipped_not_feasible += 1
                        progress.advance(task)
                        continue

                    if not feasibility.worth_it:
                        console.print(
                            f"  [yellow]💰[/yellow] Not worth it [bold]{title}[/bold]: "
                            f"${full_contest.get('prize', 0)} for ~{feasibility.estimated_hours}h — "
                            f"{feasibility.worth_it_reason}"
                        )
                        skipped_not_worth += 1
                        progress.advance(task)
                        continue

                    console.print(
                        f"  [green]✓[/green] Feasible [bold]{title}[/bold]: "
                        f"{feasibility.scope} scope, ~{feasibility.estimated_hours}h, "
                        f"type: {feasibility.implementation_type}"
                    )
                    analyzed.append(full_contest)

                except GrokError as e:
                    logger.error("feasibility_analysis_error", contest_id=cid, error=str(e)[:200])
                    console.print(f"  [red]✗[/red] AI error for [bold]{title}[/bold] — keeping in candidates")
                    skipped_ai_error += 1
                    analyzed.append(contest)  # Keep in candidates despite error

                progress.advance(task)

        console.print(
            f"[green]✓[/green] {len(analyzed)} contests passed AI feasibility check "
            f"({skipped_not_feasible} not feasible, {skipped_not_worth} not worth it, "
            f"{skipped_ai_error} AI errors kept)"
        )

        return analyzed

    async def _implement_contests(self, candidates: list[dict[str, Any]]) -> dict[str, Any]:
        """Implement top contest matches up to max_matches.

        When --implement flag is set, actually generates code via AI.
        Otherwise, prepares implementation directories (discovery-only).
        """
        mode_str = "Generating code" if self.implement else "Preparing"
        console.print(f"\n[bold]🛠️ {mode_str} contests (max {self.max_matches})...[/bold]")

        results: dict[str, Any] = {
            "implemented": [],
            "skipped": [],
            "failed": [],
            "total_candidates": len(candidates),
        }

        implemented_count = 0

        for contest in candidates:
            if implemented_count >= self.max_matches:
                results["skipped"].append({
                    "id": contest.get("id"),
                    "title": contest.get("title"),
                    "score": contest["_score"],
                    "reason": "max_matches_reached",
                })
                continue

            cid = contest.get("id")
            title = contest.get("title", "Untitled")
            score = contest["_score"]

            # Check if already implemented
            if self.state.is_contest_implemented(cid):
                results["skipped"].append({
                    "id": cid,
                    "title": title,
                    "score": score,
                    "reason": "already_implemented",
                })
                continue

            # Check implementability — use AI analysis if available, fallback to keyword
            feasibility = contest.get("_feasibility")
            if feasibility:
                can_implement = feasibility.get("can_implement", False)
                reason = feasibility.get("worth_it_reason", "")
            else:
                can_implement, reason = self._check_implementable(contest)

            if not can_implement:
                console.print(f"  [yellow]⊘[/yellow] Cannot implement [bold]{title}[/bold]: {reason}")
                results["skipped"].append({
                    "id": cid,
                    "title": title,
                    "score": score,
                    "reason": f"cannot_implement: {reason}",
                })
                continue

            if self.dry_run:
                console.print(
                    f"  [yellow]DRY RUN[/yellow] Would implement [bold]{title}[/bold] "
                    f"(Score: {score}, Prize: ${contest.get('prize', 0)})"
                )
                results["implemented"].append({
                    "id": cid,
                    "title": title,
                    "score": score,
                    "dry_run": True,
                })
                implemented_count += 1
                continue

            # ── Implementation ───────────────────────────────────────
            try:
                impl_dir = IMPLEMENTATIONS_DIR / f"contest_{cid}"
                impl_dir.mkdir(parents=True, exist_ok=True)

                # Save contest info
                prize = contest.get("prize", 0)
                if isinstance(prize, dict):
                    prize = prize.get("amount", 0)

                contest_info = {
                    "id": cid,
                    "title": title,
                    "description": contest.get("description", ""),
                    "prize": prize,
                    "skills_required": contest.get("skills", []),
                    "matched_keywords": contest["_matched_keywords"],
                    "score": score,
                    "score_breakdown": contest.get("_score_breakdown", {}),
                }

                # Add AI analysis if available
                if feasibility:
                    contest_info["ai_analysis"] = feasibility

                (impl_dir / "contest_info.json").write_text(json.dumps(contest_info, indent=2))

                # ── Code generation (NEW: --implement flag) ──────────
                if self.implement and self.grok:
                    console.print(f"  [bold cyan]🤖[/bold cyan] Generating code for [bold]{title}[/bold]...")

                    try:
                        # Build feasibility object from stored data or create one
                        if feasibility:
                            fe_obj = ContestFeasibility(
                                can_implement=feasibility.get("can_implement", True),
                                confidence=feasibility.get("confidence", 0.7),
                                scope=feasibility.get("scope", "medium"),
                                estimated_hours=feasibility.get("estimated_hours", 4),
                                worth_it=feasibility.get("worth_it", True),
                                worth_it_reason=feasibility.get("worth_it_reason", ""),
                                implementation_type=feasibility.get("implementation_type", "general_python"),
                                technical_plan=feasibility.get("technical_plan", ""),
                                key_requirements=feasibility.get("key_requirements", []),
                                risks=feasibility.get("risks", []),
                                is_design_heavy=feasibility.get("is_design_heavy", False),
                                design_tech_mix=feasibility.get("design_tech_mix", False),
                            )
                        else:
                            # Create basic feasibility for code gen
                            impl_type = self._detect_implementation_type(contest)
                            fe_obj = ContestFeasibility(
                                can_implement=True,
                                confidence=0.6,
                                scope="small",
                                estimated_hours=3,
                                worth_it=True,
                                worth_it_reason="",
                                implementation_type=impl_type,
                                technical_plan=f"Implement {impl_type} solution",
                                key_requirements=self._extract_requirements(contest),
                                risks=[],
                            )

                        impl_result = await self.grok.generate_implementation(contest, fe_obj)

                        # Save generated files
                        code_dir = impl_dir / "code"
                        code_dir.mkdir(exist_ok=True)

                        for file_info in impl_result.files:
                            file_path = code_dir / file_info["path"]
                            file_path.parent.mkdir(parents=True, exist_ok=True)
                            file_path.write_text(file_info["content"])
                            logger.info("code_file_saved", contest_id=cid, path=str(file_path))

                        # Save README
                        (code_dir / "README.md").write_text(impl_result.readme)

                        # Save requirements/dependencies
                        if impl_result.dependencies:
                            if impl_result.implementation_type == "flutter_app":
                                # Flutter uses pubspec.yaml — dependencies are saved in files
                                pass
                            else:
                                reqs = "\n".join(impl_result.dependencies)
                                (code_dir / "requirements.txt").write_text(reqs)

                        # Save implementation metadata
                        impl_meta = {
                            "contest_id": cid,
                            "title": title,
                            "implementation_type": impl_result.implementation_type if hasattr(impl_result, 'implementation_type') else fe_obj.implementation_type,
                            "entry_point": impl_result.entry_point,
                            "dependencies": impl_result.dependencies,
                            "summary": impl_result.summary,
                            "files": [f["path"] for f in impl_result.files],
                            "generated_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
                        }
                        (impl_dir / "implementation_meta.json").write_text(json.dumps(impl_meta, indent=2))

                        console.print(
                            f"  [green]✓[/green] Code generated for [bold]{title}[/bold]: "
                            f"{len(impl_result.files)} files → {code_dir}"
                        )

                    except GrokError as e:
                        logger.error("code_generation_error", contest_id=cid, error=str(e)[:200])
                        console.print(f"  [red]✗[/red] Code gen failed for [bold]{title}[/bold]: {str(e)[:100]}")
                        # Still save the contest info even if code gen fails
                        results["failed"].append({
                            "id": cid,
                            "title": title,
                            "score": score,
                            "error": f"code_generation: {str(e)[:200]}",
                        })
                        continue

                else:
                    # Discovery-only mode: save implementation request
                    impl_request = {
                        "contest_id": cid,
                        "title": title,
                        "description": contest.get("description", ""),
                        "requirements": self._extract_requirements(contest),
                        "implementation_type": self._detect_implementation_type(contest),
                    }
                    if feasibility:
                        impl_request["ai_analysis"] = feasibility

                    (impl_dir / "implementation_request.json").write_text(
                        json.dumps(impl_request, indent=2)
                    )

                    console.print(
                        f"  [green]✓[/green] Prepared implementation for [bold]{title}[/bold] "
                        f"(Score: {score}) → {impl_dir}"
                    )

                self.state.mark_contest_implemented(cid)
                self.state.analytics.record_contest_entry(cid)
                results["implemented"].append({
                    "id": cid,
                    "title": title,
                    "score": score,
                    "dir": str(impl_dir),
                    "code_generated": self.implement,
                })
                implemented_count += 1

            except Exception as e:
                logger.error("implementation_error", contest_id=cid, error=str(e)[:200])
                console.print(f"  [red]✗[/red] Error processing [bold]{title}[/bold]: {str(e)[:100]}")
                results["failed"].append({
                    "id": cid,
                    "title": title,
                    "score": score,
                    "error": str(e)[:200],
                })

        console.print(f"\n[bold]📋 Contest Summary:[/bold]")
        console.print(f"  [green]✓ Implemented:[/green] {len(results['implemented'])}")
        console.print(f"  [yellow]⊘ Skipped:[/yellow] {len(results['skipped'])}")
        console.print(f"  [red]✗ Failed:[/red] {len(results['failed'])}")

        return results

    def _check_implementable(self, contest: dict[str, Any]) -> tuple[bool, str]:
        """Check if AI can implement this contest (keyword-based fallback).

        Returns (can_implement, reason_if_not).
        """
        title = (contest.get("title", "") or "").lower()
        description = (contest.get("description", "") or "").lower()
        full_text = f"{title} {description}"

        # Check cannot-implement patterns
        for term in AI_CANNOT_IMPLEMENT:
            if term in full_text:
                return False, f"requires {term}"

        # Check can-implement patterns
        for term in AI_CAN_IMPLEMENT:
            if term in full_text:
                return True, ""

        # Default: can implement if it has tech keywords
        if contest.get("_score", 0) >= 50:
            return True, ""

        return False, "unclear requirements"

    def _extract_requirements(self, contest: dict[str, Any]) -> list[str]:
        """Extract key requirements from contest description."""
        description = contest.get("description", "") or ""
        requirements: list[str] = []

        # Look for bullet points, numbered lists, or requirement keywords
        lines = description.split("\n")
        for line in lines:
            line = line.strip()
            if line.startswith(("-", "*", "•", "1.", "2.", "3.", "4.", "5.")):
                requirements.append(line.lstrip("-*• 1234567890.").strip())
            elif any(kw in line.lower() for kw in ["must", "should", "required", "need to"]):
                requirements.append(line)

        if not requirements:
            # Fallback: use the whole description
            requirements.append(description[:500])

        return requirements[:10]  # cap at 10

    def _detect_implementation_type(self, contest: dict[str, Any]) -> str:
        """Detect the type of implementation needed."""
        title = (contest.get("title", "") or "").lower()
        description = (contest.get("description", "") or "").lower()
        full_text = f"{title} {description}"

        type_checks = [
            ("flutter_app", ["flutter", "dart", "mobile app"]),
            ("fastapi_backend", ["fastapi", "api", "backend"]),
            ("django_app", ["django", "web app"]),
            ("python_script", ["python script", "automation", "scraping"]),
            ("discord_bot", ["discord", "bot"]),
            ("telegram_bot", ["telegram", "bot"]),
            ("react_frontend", ["react", "frontend", "ui"]),
            ("cli_tool", ["cli", "command line", "terminal"]),
            ("data_processing", ["data", "csv", "json", "processing"]),
            ("llm_integration", ["llm", "openai", "gpt", "ai"]),
        ]

        for impl_type, keywords in type_checks:
            if any(kw in full_text for kw in keywords):
                return impl_type

        return "general_python"

    async def _send_report(self, results: dict[str, Any]) -> None:
        """Send email report with contest results."""
        implemented = results["implemented"]
        skipped = results["skipped"]
        failed = results["failed"]

        if not implemented and not failed:
            console.print("[dim]No contest implementations to report — skipping email[/dim]")
            return

        code_gen_str = "Code Generated" if self.implement else "Prepared"
        subject = f"🏆 Freelancer Bot: {len(implemented)} Tech Contests {code_gen_str}"

        summary = (
            f"Tech contest run completed. {len(implemented)} contests {code_gen_str.lower()}, "
            f"{len(skipped)} skipped, {len(failed)} failed. "
            f"Total candidates found: {results['total_candidates']}."
        )

        details: list[dict[str, Any]] = []
        for c in implemented:
            details.append({
                "title": c["title"],
                "link": f"https://www.freelancer.com/contest/{c.get('id', '')}",
                "score": str(c["score"]),
                "bid": "—",
                "status": "code_generated" if c.get("code_generated") else "entered",
            })
        for c in failed:
            details.append({
                "title": c["title"],
                "link": f"https://www.freelancer.com/contest/{c.get('id', '')}",
                "score": str(c["score"]),
                "bid": "—",
                "status": "failed",
            })

        self.email.send_report(subject, summary, details, report_type="contests", dry_run=self.dry_run)
