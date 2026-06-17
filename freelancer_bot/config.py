"""YAML config management for Freelancer Bot v2 — with LLM/LLM config.

Config file: ~/.config/freelancer-bot/config.yaml
All secrets from environment variables (never hardcoded).
"""

from __future__ import annotations

import copy
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import structlog
import yaml

logger = structlog.get_logger(__name__)

DEFAULT_CONFIG_DIR = Path.home() / ".config" / "freelancer-bot"
DEFAULT_CONFIG_PATH = DEFAULT_CONFIG_DIR / "config.yaml"

# ── Default configuration ───────────────────────────────────────────────

DEFAULT_CONFIG: dict[str, Any] = {
    "freelancer": {
        "token": "${FREELANCER_OAUTH_TOKEN}",
        "user_id": 0  # Set your Freelancer user ID,
    },
    "email": {
        "from": "your_email@gmail.com",
        "to": "your_email@gmail.com",
        "password": "${EMAIL_PASSWORD}",
        "smtp_host": "smtp.gmail.com",
        "smtp_port": 587,
    },
    "bidding": {
        "max_bids_per_run": 2,
        "min_score": 40,
        "excluded_terms": [
            "etl", "elt", "data pipeline", "airbyte", "dbt", "data warehouse",
            "data engineering", "apache airflow", "prefect", "dagster",
            "data extraction", "data transformation", "data loading",
        ],
        "search_configs": [
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
        ],
    },
    "llm": {
        "provider": "ollama",
        "model": "deepseek-v4-pro",
        "base_url": "http://localhost:11434",
        "api_key": "${LLM_API_KEY}",
        "temperature": 0.3,
        "max_tokens": 4096,
        "timeout": 120,
        "enabled": True,
    },
    "contests": {
        "max_matches": 10,
        "min_score": 50,
        "auto_implement": True,
        "design_filter_terms": [
            "logo", "flyer", "brochure", "banner", "poster", "business card",
            "letterhead", "stationery", "branding identity", "packaging design",
            "label design", "t-shirt design", "merch design", "social media design",
            "instagram post", "facebook cover", "youtube banner", "thumbnail",
            "infographic", "illustration", "character design", "mascot",
            "photoshop", "illustrator design", "canva", "figma design only",
            "graphic design", "ui design only", "ux design only", "web design only",
            "app design only", "icon design", "vector design", "redesign logo",
        ],
        "search_configs": [
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
        ],
    },
    "design": {
        "max_matches": 15,
        "min_score": 40,
        "search_configs": [
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
        ],
    },
    "schedule": {
        "bidding": "0 6,12,18 * * *",
        "contests": "30 4,10,15 * * *",
        "design": "0 7,13,19 * * *",
    },
    "notifications": {
        "discord_webhook": None,
    },
}


@dataclass
class ConfigManager:
    """Manage YAML configuration with env var resolution."""

    config_path: Path = field(default=DEFAULT_CONFIG_PATH)
    _data: dict[str, Any] = field(default_factory=dict, init=False, repr=False)

    def __post_init__(self) -> None:
        self._data = {}

    @property
    def data(self) -> dict[str, Any]:
        if not self._data:
            self.load()
        return self._data

    def load(self) -> dict[str, Any]:
        """Load config from file, falling back to defaults."""
        self.config_path.parent.mkdir(parents=True, exist_ok=True)

        if self.config_path.exists():
            try:
                with open(self.config_path) as f:
                    self._data = yaml.safe_load(f) or {}
                logger.info("config_loaded", path=str(self.config_path))
            except yaml.YAMLError as e:
                logger.error("config_parse_error", error=str(e))
                self._data = {}
        else:
            logger.info("config_not_found", path=str(self.config_path))
            self._data = {}

        # Merge with defaults for missing sections
        self._data = self._deep_merge(DEFAULT_CONFIG, self._data)

        # Resolve env vars
        self._data = self._resolve_env_vars(self._data)

        return self._data

    def save(self) -> None:
        """Save current config to file."""
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        # Strip env var values before saving (they're secrets)
        save_data = self._mask_secrets(self._data)
        with open(self.config_path, "w") as f:
            yaml.safe_dump(save_data, f, default_flow_style=False, sort_keys=False)
        logger.info("config_saved", path=str(self.config_path))

    def init_default(self) -> None:
        """Initialize config file with defaults if it doesn't exist."""
        if not self.config_path.exists():
            self._data = dict(DEFAULT_CONFIG)  # deep copy
            self.save()
            logger.info("config_initialized", path=str(self.config_path))

    def get(self, *keys: str, default: Any = None) -> Any:
        """Get a nested config value by key path.

        Example: config.get("bidding", "max_bids_per_run")
        """
        value: Any = self.data
        for key in keys:
            if isinstance(value, dict):
                value = value.get(key)
            else:
                return default
            if value is None:
                return default
        return value

    def set(self, *keys: str, value: Any) -> None:
        """Set a nested config value and save.

        Example: config.set("bidding", "max_bids_per_run", value=5)
        """
        data = self.data
        for key in keys[:-1]:
            if key not in data:
                data[key] = {}
            data = data[key]
        data[keys[-1]] = value
        self.save()

    def show(self) -> str:
        """Return YAML representation of config (with secrets masked)."""
        return yaml.safe_dump(self._mask_secrets(self.data), default_flow_style=False, sort_keys=False)

    # ── Helpers ──────────────────────────────────────────────────────────

    @staticmethod
    def _resolve_env_vars(data: Any) -> Any:
        """Recursively resolve ${ENV_VAR} placeholders in config values."""
        if isinstance(data, dict):
            return {k: ConfigManager._resolve_env_vars(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [ConfigManager._resolve_env_vars(v) for v in data]
        elif isinstance(data, str) and data.startswith("${") and data.endswith("}"):
            env_var = data[2:-1]
            return os.environ.get(env_var, "")
        return data

    @staticmethod
    def _mask_secrets(data: Any) -> Any:
        """Mask secret values for safe display/saving."""
        if isinstance(data, dict):
            result = {}
            for k, v in data.items():
                if k in ("token", "password", "discord_webhook", "api_key"):
                    if v and isinstance(v, str) and len(v) > 4:
                        result[k] = v[:4] + "****"
                    else:
                        result[k] = "****"
                else:
                    result[k] = ConfigManager._mask_secrets(v)
            return result
        elif isinstance(data, list):
            return [ConfigManager._mask_secrets(v) for v in data]
        return data

    @staticmethod
    def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
        """Deep merge two dicts, with override taking precedence."""
        result = copy.deepcopy(base)
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = ConfigManager._deep_merge(result[key], value)
            else:
                result[key] = value
        return result
