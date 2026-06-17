"""Unified state management for Freelancer Bot v2.

Migrates from three separate JSON files to a single state directory:
~/.local/share/freelancer-bot/

State files:
- bidding.json   — project bidding state
- contests.json  — tech contest state
- design.json    — website design state
- analytics.json — tracking data (bids, wins, revenue)
"""

from __future__ import annotations

import json
import os
import shutil
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import structlog

logger = structlog.get_logger(__name__)

DEFAULT_STATE_DIR = Path.home() / ".local" / "share" / "freelancer-bot"


@dataclass
class BiddingState:
    """State for project bidding bot."""

    bid_project_ids: set[int] = field(default_factory=set)
    attempted_bids: set[int] = field(default_factory=set)
    skills_mismatch: set[int] = field(default_factory=set)
    last_run: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "bid_project_ids": sorted(self.bid_project_ids),
            "attempted_bids": sorted(self.attempted_bids),
            "skills_mismatch": sorted(self.skills_mismatch),
            "last_run": self.last_run,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BiddingState":
        return cls(
            bid_project_ids=set(data.get("bid_project_ids", [])),
            attempted_bids=set(data.get("attempted_bids", [])),
            skills_mismatch=set(data.get("skills_mismatch", [])),
            last_run=data.get("last_run"),
        )


@dataclass
class ContestsState:
    """State for tech contest bot."""

    seen_contest_ids: set[int] = field(default_factory=set)
    implemented_contest_ids: set[int] = field(default_factory=set)
    entered_contest_ids: set[int] = field(default_factory=set)
    attempted_entries: set[int] = field(default_factory=set)
    skills_mismatch: set[int] = field(default_factory=set)
    wins: list[int] = field(default_factory=list)
    entries_by_contest: dict[str, Any] = field(default_factory=dict)
    last_run: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "seen_contest_ids": sorted(self.seen_contest_ids),
            "implemented_contest_ids": sorted(self.implemented_contest_ids),
            "entered_contest_ids": sorted(self.entered_contest_ids),
            "attempted_entries": sorted(self.attempted_entries),
            "skills_mismatch": sorted(self.skills_mismatch),
            "wins": self.wins,
            "entries_by_contest": self.entries_by_contest,
            "last_run": self.last_run,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ContestsState":
        return cls(
            seen_contest_ids=set(data.get("seen_contest_ids", [])),
            implemented_contest_ids=set(data.get("implemented_contest_ids", [])),
            entered_contest_ids=set(data.get("entered_contest_ids", [])),
            attempted_entries=set(data.get("attempted_entries", [])),
            skills_mismatch=set(data.get("skills_mismatch", [])),
            wins=data.get("wins", []),
            entries_by_contest=data.get("entries_by_contest", {}),
            last_run=data.get("last_run"),
        )


@dataclass
class DesignState:
    """State for website design discovery bot."""

    seen_contest_ids: set[int] = field(default_factory=set)
    last_run: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "seen_contest_ids": sorted(self.seen_contest_ids),
            "last_run": self.last_run,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DesignState":
        return cls(
            seen_contest_ids=set(data.get("seen_contest_ids", [])),
            last_run=data.get("last_run"),
        )


@dataclass
class AnalyticsState:
    """Tracking data for analytics."""

    total_bids_placed: int = 0
    total_bids_won: int = 0
    total_contests_entered: int = 0
    total_contests_won: int = 0
    total_revenue: float = 0.0
    bid_history: list[dict[str, Any]] = field(default_factory=list)
    contest_history: list[dict[str, Any]] = field(default_factory=list)
    daily_stats: dict[str, dict[str, int]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_bids_placed": self.total_bids_placed,
            "total_bids_won": self.total_bids_won,
            "total_contests_entered": self.total_contests_entered,
            "total_contests_won": self.total_contests_won,
            "total_revenue": self.total_revenue,
            "bid_history": self.bid_history[-1000:],  # keep last 1000
            "contest_history": self.contest_history[-1000:],
            "daily_stats": self.daily_stats,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AnalyticsState":
        return cls(
            total_bids_placed=data.get("total_bids_placed", 0),
            total_bids_won=data.get("total_bids_won", 0),
            total_contests_entered=data.get("total_contests_entered", 0),
            total_contests_won=data.get("total_contests_won", 0),
            total_revenue=data.get("total_revenue", 0.0),
            bid_history=data.get("bid_history", []),
            contest_history=data.get("contest_history", []),
            daily_stats=data.get("daily_stats", {}),
        )

    def record_bid(self, project_id: int, amount: float, status: str = "placed") -> None:
        """Record a bid in history."""
        now = datetime.now(timezone.utc).isoformat()
        self.bid_history.append({
            "project_id": project_id,
            "amount": amount,
            "status": status,
            "timestamp": now,
        })
        self.total_bids_placed += 1
        self._update_daily("bids_placed")

    def record_bid_won(self, project_id: int, amount: float) -> None:
        """Record a won bid."""
        self.total_bids_won += 1
        self.total_revenue += amount
        self._update_daily("bids_won")
        # Update the bid history entry
        for entry in reversed(self.bid_history):
            if entry["project_id"] == project_id:
                entry["status"] = "won"
                break

    def record_contest_entry(self, contest_id: int, prize: float = 0.0) -> None:
        """Record a contest entry."""
        now = datetime.now(timezone.utc).isoformat()
        self.contest_history.append({
            "contest_id": contest_id,
            "prize": prize,
            "status": "entered",
            "timestamp": now,
        })
        self.total_contests_entered += 1
        self._update_daily("contests_entered")

    def record_contest_win(self, contest_id: int, prize: float) -> None:
        """Record a won contest."""
        self.total_contests_won += 1
        self.total_revenue += prize
        self._update_daily("contests_won")
        for entry in reversed(self.contest_history):
            if entry["contest_id"] == contest_id:
                entry["status"] = "won"
                entry["prize"] = prize
                break

    def _update_daily(self, key: str) -> None:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if today not in self.daily_stats:
            self.daily_stats[today] = {}
        self.daily_stats[today][key] = self.daily_stats[today].get(key, 0) + 1

    @property
    def bid_success_rate(self) -> float:
        """Percentage of bids won."""
        if self.total_bids_placed == 0:
            return 0.0
        return (self.total_bids_won / self.total_bids_placed) * 100

    @property
    def contest_success_rate(self) -> float:
        """Percentage of contests won."""
        if self.total_contests_entered == 0:
            return 0.0
        return (self.total_contests_won / self.total_contests_entered) * 100


class StateManager:
    """Unified state manager — load, save, migrate from legacy JSON files."""

    def __init__(self, state_dir: Path | str | None = None):
        self.state_dir = Path(state_dir) if state_dir else DEFAULT_STATE_DIR
        self.bidding = BiddingState()
        self.contests = ContestsState()
        self.design = DesignState()
        self.analytics = AnalyticsState()

    # ── File paths ───────────────────────────────────────────────────────

    @property
    def bidding_path(self) -> Path:
        return self.state_dir / "bidding.json"

    @property
    def contests_path(self) -> Path:
        return self.state_dir / "contests.json"

    @property
    def design_path(self) -> Path:
        return self.state_dir / "design.json"

    @property
    def analytics_path(self) -> Path:
        return self.state_dir / "analytics.json"

    # ── Load / Save ──────────────────────────────────────────────────────

    def _ensure_dir(self) -> None:
        self.state_dir.mkdir(parents=True, exist_ok=True)

    def _load_json(self, path: Path) -> dict[str, Any]:
        if path.exists():
            try:
                return json.loads(path.read_text())
            except json.JSONDecodeError:
                logger.warning("state_corrupt", path=str(path))
                # Backup corrupt file
                backup = path.with_suffix(".json.bak")
                shutil.copy2(path, backup)
                return {}
        return {}

    def _save_json(self, path: Path, data: dict[str, Any]) -> None:
        self._ensure_dir()
        # Atomic write: write to temp, then rename
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(data, indent=2, default=str))
        tmp.replace(path)

    def load(self) -> None:
        """Load all state from disk."""
        self._ensure_dir()
        self.bidding = BiddingState.from_dict(self._load_json(self.bidding_path))
        self.contests = ContestsState.from_dict(self._load_json(self.contests_path))
        self.design = DesignState.from_dict(self._load_json(self.design_path))
        self.analytics = AnalyticsState.from_dict(self._load_json(self.analytics_path))
        logger.info(
            "state_loaded",
            bidding_bids=len(self.bidding.bid_project_ids),
            contests_seen=len(self.contests.seen_contest_ids),
            design_seen=len(self.design.seen_contest_ids),
        )

    def save(self) -> None:
        """Save all state to disk."""
        self._save_json(self.bidding_path, self.bidding.to_dict())
        self._save_json(self.contests_path, self.contests.to_dict())
        self._save_json(self.design_path, self.design.to_dict())
        self._save_json(self.analytics_path, self.analytics.to_dict())
        logger.debug("state_saved")

    def save_bidding(self) -> None:
        """Save only bidding state."""
        self._save_json(self.bidding_path, self.bidding.to_dict())

    def save_contests(self) -> None:
        """Save only contests state."""
        self._save_json(self.contests_path, self.contests.to_dict())

    def save_design(self) -> None:
        """Save only design state."""
        self._save_json(self.design_path, self.design.to_dict())

    def save_analytics(self) -> None:
        """Save only analytics state."""
        self._save_json(self.analytics_path, self.analytics.to_dict())

    # ── Migration from legacy JSON files ─────────────────────────────────

    def migrate_from_legacy(
        self,
        bidding_path: str | Path | None = None,
        contests_path: str | Path | None = None,
        design_path: str | Path | None = None,
    ) -> dict[str, int]:
        """Migrate state from legacy JSON files in workspace root.

        Returns counts of migrated records.
        """
        counts: dict[str, int] = {}

        # Migrate bidding state
        if bidding_path is None:
            bidding_path = Path.home() / ".openclaw" / "workspace" / "freelancer_bot_state.json"
        bidding_path = Path(bidding_path)
        if bidding_path.exists():
            data = self._load_json(bidding_path)
            self.bidding = BiddingState.from_dict(data)
            counts["bidding_bids"] = len(self.bidding.bid_project_ids)
            counts["bidding_attempted"] = len(self.bidding.attempted_bids)
            counts["bidding_mismatch"] = len(self.bidding.skills_mismatch)
            logger.info("migrated_bidding_state", **counts)

        # Migrate contests state
        if contests_path is None:
            contests_path = Path.home() / ".openclaw" / "workspace" / "freelancer_contest_state.json"
        contests_path = Path(contests_path)
        if contests_path.exists():
            data = self._load_json(contests_path)
            self.contests = ContestsState.from_dict(data)
            counts["contests_seen"] = len(self.contests.seen_contest_ids)
            counts["contests_implemented"] = len(self.contests.implemented_contest_ids)
            logger.info("migrated_contests_state", **counts)

        # Migrate design state
        if design_path is None:
            design_path = Path.home() / ".openclaw" / "workspace" / "freelancer_website_design_state.json"
        design_path = Path(design_path)
        if design_path.exists():
            data = self._load_json(design_path)
            self.design = DesignState.from_dict(data)
            counts["design_seen"] = len(self.design.seen_contest_ids)
            logger.info("migrated_design_state", **counts)

        # Save migrated state
        self.save()
        return counts

    # ── Convenience methods ──────────────────────────────────────────────

    def is_project_bid(self, project_id: int) -> bool:
        """Check if project was already successfully bid."""
        return project_id in self.bidding.bid_project_ids

    def is_project_attempted(self, project_id: int) -> bool:
        """Check if project bid was attempted (failed/retryable)."""
        return project_id in self.bidding.attempted_bids

    def is_project_skipped(self, project_id: int) -> bool:
        """Check if project was permanently skipped (skills mismatch)."""
        return project_id in self.bidding.skills_mismatch

    def is_project_known(self, project_id: int) -> bool:
        """Check if project is known in any capacity."""
        return (
            self.is_project_bid(project_id)
            or self.is_project_attempted(project_id)
            or self.is_project_skipped(project_id)
        )

    def mark_bid_success(self, project_id: int) -> None:
        """Mark a project as successfully bid."""
        self.bidding.bid_project_ids.add(project_id)
        self.bidding.attempted_bids.discard(project_id)

    def mark_bid_attempted(self, project_id: int) -> None:
        """Mark a project bid as attempted (failed but retryable)."""
        self.bidding.attempted_bids.add(project_id)

    def mark_skills_mismatch(self, project_id: int) -> None:
        """Mark a project as permanently skipped."""
        self.bidding.skills_mismatch.add(project_id)

    def is_contest_seen(self, contest_id: int) -> bool:
        """Check if contest was already seen."""
        return contest_id in self.contests.seen_contest_ids

    def is_contest_implemented(self, contest_id: int) -> bool:
        """Check if contest was already implemented."""
        return contest_id in self.contests.implemented_contest_ids

    def mark_contest_seen(self, contest_id: int) -> None:
        """Mark contest as seen."""
        self.contests.seen_contest_ids.add(contest_id)

    def mark_contest_implemented(self, contest_id: int) -> None:
        """Mark contest as implemented."""
        self.contests.implemented_contest_ids.add(contest_id)

    def is_design_seen(self, contest_id: int) -> bool:
        """Check if design contest was already seen."""
        return contest_id in self.design.seen_contest_ids

    def mark_design_seen(self, contest_id: int) -> None:
        """Mark design contest as seen."""
        self.design.seen_contest_ids.add(contest_id)

    def touch_last_run(self, bot: str = "bidding") -> None:
        """Update last_run timestamp for a bot."""
        now = datetime.now(timezone.utc).isoformat()
        if bot == "bidding":
            self.bidding.last_run = now
        elif bot == "contests":
            self.contests.last_run = now
        elif bot == "design":
            self.design.last_run = now

    def get_summary(self) -> dict[str, Any]:
        """Get a summary of all state for status display."""
        return {
            "bidding": {
                "successful_bids": len(self.bidding.bid_project_ids),
                "attempted_bids": len(self.bidding.attempted_bids),
                "skills_mismatch": len(self.bidding.skills_mismatch),
                "last_run": self.bidding.last_run,
            },
            "contests": {
                "seen": len(self.contests.seen_contest_ids),
                "implemented": len(self.contests.implemented_contest_ids),
                "entered": len(self.contests.entered_contest_ids),
                "wins": len(self.contests.wins),
                "last_run": self.contests.last_run,
            },
            "design": {
                "seen": len(self.design.seen_contest_ids),
                "last_run": self.design.last_run,
            },
            "analytics": {
                "bids_placed": self.analytics.total_bids_placed,
                "bids_won": self.analytics.total_bids_won,
                "bid_success_rate": f"{self.analytics.bid_success_rate:.1f}%",
                "contests_entered": self.analytics.total_contests_entered,
                "contests_won": self.analytics.total_contests_won,
                "contest_success_rate": f"{self.analytics.contest_success_rate:.1f}%",
                "total_revenue": f"${self.analytics.total_revenue:,.2f}",
            },
        }
