"""Grok/LLM integration for AI-powered contest analysis and code generation.

Uses Ollama (local) or OpenAI-compatible API for:
- Contest feasibility analysis (can AI implement this? is it worth it?)
- Code generation for implementable contests
- Smart design-vs-tech classification
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import structlog

logger = structlog.get_logger(__name__)

# ── Default LLM config ──────────────────────────────────────────────────

DEFAULT_LLM_CONFIG: dict[str, Any] = {
    "provider": "ollama",  # "ollama" or "openai"
    "model": "deepseek-v4-pro",
    "base_url": "http://localhost:11434",  # Ollama default
    "api_key": "",  # Only needed for OpenAI
    "temperature": 0.3,
    "max_tokens": 4096,
    "timeout": 120.0,
}


@dataclass
class GrokClient:
    """LLM client for contest analysis and code generation.

    Supports Ollama (local) and OpenAI-compatible APIs.
    """

    provider: str = "ollama"
    model: str = "deepseek-v4-pro"
    base_url: str = "http://localhost:11434"
    api_key: str = ""
    temperature: float = 0.3
    max_tokens: int = 4096
    timeout: float = 120.0

    @classmethod
    def from_config(cls, config: dict[str, Any] | None = None) -> "GrokClient":
        """Create client from config dict or env vars."""
        if config is None:
            config = {}
        return cls(
            provider=config.get("provider", os.environ.get("LLM_PROVIDER", "ollama")),
            model=config.get("model", os.environ.get("LLM_MODEL", "deepseek-v4-pro")),
            base_url=config.get("base_url", os.environ.get("LLM_BASE_URL", "http://localhost:11434")),
            api_key=config.get("api_key", os.environ.get("LLM_API_KEY", "")),
            temperature=config.get("temperature", 0.3),
            max_tokens=config.get("max_tokens", 4096),
            timeout=config.get("timeout", 120.0),
        )

    async def chat(self, messages: list[dict[str, str]]) -> str:
        """Send a chat completion request and return the response text."""
        import httpx

        if self.provider == "ollama":
            return await self._chat_ollama(messages)
        else:
            return await self._chat_openai(messages)

    async def _chat_ollama(self, messages: list[dict[str, str]]) -> str:
        """Send chat request to Ollama API."""
        import httpx

        url = f"{self.base_url}/api/chat"
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": self.temperature,
                "num_predict": self.max_tokens,
            },
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                data = response.json()
                return data.get("message", {}).get("content", "")
            except httpx.HTTPError as e:
                logger.error("ollama_chat_error", error=str(e)[:300])
                raise GrokError(f"Ollama chat failed: {e}") from e

    async def _chat_openai(self, messages: list[dict[str, str]]) -> str:
        """Send chat request to OpenAI-compatible API."""
        import httpx

        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(url, json=payload, headers=headers)
                response.raise_for_status()
                data = response.json()
                return data.get("choices", [{}])[0].get("message", {}).get("content", "")
            except httpx.HTTPError as e:
                logger.error("openai_chat_error", error=str(e)[:300])
                raise GrokError(f"OpenAI chat failed: {e}") from e

    async def analyze_contest_feasibility(
        self, contest: dict[str, Any]
    ) -> ContestFeasibility:
        """Analyze whether AI can implement this contest and if it's worth it.

        Fetches full contest description and performs deep analysis.
        """
        title = contest.get("title", "Untitled")
        description = contest.get("description", "") or contest.get("preview_description", "")
        prize = contest.get("prize", 0)
        if isinstance(prize, dict):
            prize = prize.get("amount", 0)
        skills = contest.get("skills", [])
        if isinstance(skills, list):
            skills_str = ", ".join(str(s) for s in skills)
        else:
            skills_str = str(skills)

        prompt = f"""Analyze this Freelancer.com contest for AI implementation feasibility.

CONTEST DETAILS:
Title: {title}
Prize: ${prize}
Skills Required: {skills_str}
Description:
{description[:3000]}

Analyze and respond in JSON format with these fields:
1. "can_implement": true/false — Can an AI coding agent actually build this?
2. "confidence": 0.0-1.0 — How confident are you in the assessment?
3. "scope": "small"/"medium"/"large"/"xlarge" — Actual scope of work
4. "estimated_hours": number — Estimated hours to implement
5. "worth_it": true/false — Is the prize worth the effort? (prize/hours >= $15/hr is good)
6. "worth_it_reason": string — Brief explanation of worth assessment
7. "implementation_type": string — e.g., "python_script", "fastapi_backend", "flutter_app", "react_frontend", "cli_tool", "discord_bot", "telegram_bot", "data_processing", "llm_integration", "general_python"
8. "technical_plan": string — 3-5 sentence technical implementation plan
9. "key_requirements": list of strings — Extracted key requirements
10. "risks": list of strings — Potential challenges or gotchas
11. "is_design_heavy": true/false — Is this primarily a design contest?
12. "design_tech_mix": true/false — Does it mix design AND tech (e.g., "Python script that generates logos")?

Rules:
- If the contest requires native iOS/Android, 3D modeling, video editing, hardware, blockchain, Kubernetes, security audits, or production deployment → can_implement=false
- If it's purely design (logo, flyer, brochure, UI mockup only) → can_implement=false, is_design_heavy=true
- If it mixes design with tech (e.g., "build a Python script that generates logos" or "create a web app with a nice UI") → can_implement=true, design_tech_mix=true
- Simple scripts, APIs, bots, web apps, data processing → usually can_implement=true
- Prize < $30 for > 5 hours work → worth_it=false
- Be realistic about scope — some "simple script" contests are actually complex

Respond ONLY with valid JSON, no markdown or explanation."""

        try:
            response = await self.chat([
                {"role": "system", "content": "You are a technical contest analyzer. Respond only with valid JSON."},
                {"role": "user", "content": prompt},
            ])

            # Extract JSON from response (handle markdown wrapping)
            json_match = re.search(r'\{[\s\S]*\}', response)
            if json_match:
                data = json.loads(json_match.group())
            else:
                data = json.loads(response)

            return ContestFeasibility(
                can_implement=data.get("can_implement", False),
                confidence=data.get("confidence", 0.5),
                scope=data.get("scope", "medium"),
                estimated_hours=data.get("estimated_hours", 0),
                worth_it=data.get("worth_it", False),
                worth_it_reason=data.get("worth_it_reason", ""),
                implementation_type=data.get("implementation_type", "general_python"),
                technical_plan=data.get("technical_plan", ""),
                key_requirements=data.get("key_requirements", []),
                risks=data.get("risks", []),
                is_design_heavy=data.get("is_design_heavy", False),
                design_tech_mix=data.get("design_tech_mix", False),
            )

        except (json.JSONDecodeError, KeyError) as e:
            logger.error("feasibility_parse_error", error=str(e)[:200], title=title)
            # Fallback to keyword-based analysis
            return self._fallback_feasibility(contest)
        except GrokError as e:
            logger.error("feasibility_grok_error", error=str(e)[:200], title=title)
            return self._fallback_feasibility(contest)

    def _fallback_feasibility(self, contest: dict[str, Any]) -> ContestFeasibility:
        """Keyword-based fallback when LLM is unavailable."""
        title = (contest.get("title", "") or "").lower()
        description = (contest.get("description", "") or "").lower()
        skills = contest.get("skills", [])
        if isinstance(skills, list):
            skills_text = " ".join(str(s) for s in skills)
        else:
            skills_text = str(skills) if skills else ""
        full_text = f"{title} {description} {skills_text}"
        prize = contest.get("prize", 0)
        if isinstance(prize, dict):
            prize = prize.get("amount", 0)

        # Cannot-implement patterns
        cannot_patterns = [
            "ios native", "android native", "react native", "ui/ux design",
            "3d", "animation", "video editing", "audio processing", "hardware",
            "desktop apps", "game development", "ml model training", "blockchain",
            "kubernetes", "security audits", "production deployment",
            "wordpress themes", "shopify themes",
        ]
        for term in cannot_patterns:
            if term in full_text:
                return ContestFeasibility(
                    can_implement=False,
                    confidence=0.8,
                    scope="large",
                    estimated_hours=0,
                    worth_it=False,
                    worth_it_reason=f"requires {term}",
                    implementation_type="general_python",
                    technical_plan="",
                    key_requirements=[],
                    risks=[f"Requires {term} which AI cannot reliably implement"],
                    is_design_heavy=False,
                    design_tech_mix=False,
                )

        # Can-implement patterns (individual keywords)
        can_keywords = [
            ("python", "python code"), ("script", "automation script"),
            ("api", "api development"), ("fastapi", "fastapi app"),
            ("flask", "flask app"), ("django", "django app"),
            ("flutter", "flutter app"), ("react", "react app"),
            ("cli", "cli tool"), ("telegram", "telegram bot"),
            ("discord", "discord bot"), ("csv", "csv processing"),
            ("json", "json processing"), ("web scraping", "web scraping"),
            ("automation", "automation"), ("data", "data processing"),
            ("database", "database work"), ("webhooks", "webhooks"),
            ("backend", "backend development"), ("bot", "bot development"),
            ("tool", "tool development"), ("conversion", "file conversion"),
            ("text processing", "text processing"),
        ]
        for keyword, desc in can_keywords:
            if keyword in full_text:
                hours = 2 if ("script" in full_text or "cli" in full_text or "bot" in full_text) else 4
                return ContestFeasibility(
                    can_implement=True,
                    confidence=0.6,
                    scope="small",
                    estimated_hours=hours,
                    worth_it=prize >= 20,
                    worth_it_reason=f"Prize ${prize} for ~{hours}h work" if prize < 20 else "Good prize-to-effort ratio",
                    implementation_type=self._detect_type_fallback(full_text),
                    technical_plan=f"Implement {term} solution with proper error handling and documentation",
                    key_requirements=[f"Build {term}"],
                    risks=["Requirements may be underspecified"],
                    is_design_heavy=False,
                    design_tech_mix=False,
                )

        # Default: unclear
        return ContestFeasibility(
            can_implement=False,
            confidence=0.3,
            scope="medium",
            estimated_hours=0,
            worth_it=False,
            worth_it_reason="unclear requirements",
            implementation_type="general_python",
            technical_plan="",
            key_requirements=[],
            risks=["Requirements too vague to assess"],
            is_design_heavy=False,
            design_tech_mix=False,
        )

    def _detect_type_fallback(self, text: str) -> str:
        """Detect implementation type from text (fallback)."""
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
            if any(kw in text for kw in keywords):
                return impl_type
        return "general_python"

    async def generate_implementation(
        self,
        contest: dict[str, Any],
        feasibility: ContestFeasibility,
    ) -> ImplementationResult:
        """Generate implementation code for a contest deemed feasible.

        Returns structured result with code files and README.
        """
        title = contest.get("title", "Untitled")
        description = contest.get("description", "") or contest.get("preview_description", "")
        prize = contest.get("prize", 0)
        if isinstance(prize, dict):
            prize = prize.get("amount", 0)

        prompt = f"""Generate a complete, working implementation for this Freelancer.com contest.

CONTEST:
Title: {title}
Prize: ${prize}
Type: {feasibility.implementation_type}
Scope: {feasibility.scope} (~{feasibility.estimated_hours}h)

Technical Plan:
{feasibility.technical_plan}

Key Requirements:
{chr(10).join(f'- {r}' for r in feasibility.key_requirements)}

Full Description:
{description[:3000]}

Generate the implementation. Respond in this JSON format:
{{
  "files": [
    {{
      "path": "relative/path/to/file.py",
      "content": "full file content here",
      "description": "what this file does"
    }}
  ],
  "readme": "Full README.md content with setup instructions, usage, and requirements",
  "entry_point": "main file to run (e.g., main.py)",
  "dependencies": ["list", "of", "pip/package", "dependencies"],
  "summary": "One-paragraph summary of what was implemented"
}}

Rules:
- Write COMPLETE, WORKING code — not stubs or placeholders
- Include proper error handling, docstrings, and comments
- Use standard libraries where possible, popular packages otherwise
- For Python: include requirements.txt dependencies
- For Flutter: include pubspec.yaml dependencies
- For web: include package.json if needed
- Make it production-ready quality
- Include setup/run instructions in README
- Keep it focused — implement the core requirements, not extras

Respond ONLY with valid JSON, no markdown wrapping or explanation."""

        try:
            response = await self.chat([
                {"role": "system", "content": "You are an expert software engineer. Generate complete, working code. Respond only with valid JSON."},
                {"role": "user", "content": prompt},
            ])

            # Extract JSON
            json_match = re.search(r'\{[\s\S]*\}', response)
            if json_match:
                data = json.loads(json_match.group())
            else:
                data = json.loads(response)

            files = data.get("files", [])
            readme = data.get("readme", "")
            entry_point = data.get("entry_point", "main.py")
            dependencies = data.get("dependencies", [])
            summary = data.get("summary", "")

            return ImplementationResult(
                files=files,
                readme=readme,
                entry_point=entry_point,
                dependencies=dependencies,
                summary=summary,
            )

        except (json.JSONDecodeError, KeyError) as e:
            logger.error("implementation_parse_error", error=str(e)[:200], title=title)
            raise GrokError(f"Failed to parse implementation response: {e}") from e
        except GrokError:
            raise

    async def classify_design_vs_tech(
        self, contest: dict[str, Any]
    ) -> DesignTechClassification:
        """Smart classification: is this design-only, tech-only, or mixed?

        Handles edge cases like "Python script that generates logos"
        which current keyword filter would wrongly exclude.
        """
        title = contest.get("title", "Untitled")
        description = contest.get("description", "") or contest.get("preview_description", "")

        prompt = f"""Classify this Freelancer.com contest as design-only, tech-only, or mixed.

Title: {title}
Description:
{description[:2000]}

Respond in JSON:
{{
  "category": "design_only" | "tech_only" | "mixed_design_tech" | "unclear",
  "confidence": 0.0-1.0,
  "reasoning": "Brief explanation",
  "design_terms_found": ["list", "of", "design", "terms"],
  "tech_terms_found": ["list", "of", "tech", "terms"]
}}

Key distinction:
- "I need a logo" → design_only
- "I need a Python script that generates logos" → mixed_design_tech (tech contest!)
- "Build a web app with nice UI" → mixed_design_tech (tech contest!)
- "Create a REST API" → tech_only
- "Design a website mockup in Figma" → design_only

Respond ONLY with valid JSON."""

        try:
            response = await self.chat([
                {"role": "system", "content": "You are a contest classifier. Respond only with valid JSON."},
                {"role": "user", "content": prompt},
            ])

            json_match = re.search(r'\{[\s\S]*\}', response)
            if json_match:
                data = json.loads(json_match.group())
            else:
                data = json.loads(response)

            return DesignTechClassification(
                category=data.get("category", "unclear"),
                confidence=data.get("confidence", 0.5),
                reasoning=data.get("reasoning", ""),
                design_terms_found=data.get("design_terms_found", []),
                tech_terms_found=data.get("tech_terms_found", []),
            )

        except (json.JSONDecodeError, KeyError) as e:
            logger.error("classify_parse_error", error=str(e)[:200], title=title)
            return self._fallback_classify(contest)
        except GrokError as e:
            logger.error("classify_grok_error", error=str(e)[:200], title=title)
            return self._fallback_classify(contest)

    def _fallback_classify(self, contest: dict[str, Any]) -> DesignTechClassification:
        """Keyword-based fallback classification."""
        title = (contest.get("title", "") or "").lower()
        description = (contest.get("description", "") or "").lower()
        skills = contest.get("skills", [])
        if isinstance(skills, list):
            skills_text = " ".join(str(s) for s in skills)
        else:
            skills_text = str(skills) if skills else ""
        full_text = f"{title} {description} {skills_text}"

        # Design terms
        design_terms = [
            "logo", "flyer", "brochure", "banner", "poster", "business card",
            "letterhead", "branding", "packaging design", "t-shirt design",
            "illustration", "graphic design", "ui design", "ux design",
            "icon design", "vector", "motion graphics", "3d design",
            "photoshop", "illustrator", "canva", "figma",
        ]
        # Tech terms
        tech_terms = [
            "python", "javascript", "typescript", "react", "flutter", "django",
            "fastapi", "api", "script", "automate", "bot", "scraping",
            "backend", "frontend", "full stack", "database", "node.js",
            "cli", "command line", "web app", "mobile app", "ai", "ml",
            "llm", "openai", "google adk", "docker", "aws", "gcp",
        ]

        found_design = [t for t in design_terms if t in full_text]
        found_tech = [t for t in tech_terms if t in full_text]

        if found_tech and found_design:
            return DesignTechClassification(
                category="mixed_design_tech",
                confidence=0.7,
                reasoning=f"Contains both tech ({', '.join(found_tech[:3])}) and design ({', '.join(found_design[:3])}) terms",
                design_terms_found=found_design,
                tech_terms_found=found_tech,
            )
        elif found_tech:
            return DesignTechClassification(
                category="tech_only",
                confidence=0.8,
                reasoning=f"Contains tech terms: {', '.join(found_tech[:3])}",
                design_terms_found=found_design,
                tech_terms_found=found_tech,
            )
        elif found_design:
            return DesignTechClassification(
                category="design_only",
                confidence=0.7,
                reasoning=f"Contains design terms: {', '.join(found_design[:3])}",
                design_terms_found=found_design,
                tech_terms_found=found_tech,
            )
        else:
            return DesignTechClassification(
                category="unclear",
                confidence=0.3,
                reasoning="No clear tech or design terms found",
                design_terms_found=[],
                tech_terms_found=[],
            )


# ── Data classes for structured results ──────────────────────────────────

@dataclass
class ContestFeasibility:
    """Result of AI contest feasibility analysis."""
    can_implement: bool = False
    confidence: float = 0.0
    scope: str = "medium"  # small, medium, large, xlarge
    estimated_hours: int = 0
    worth_it: bool = False
    worth_it_reason: str = ""
    implementation_type: str = "general_python"
    technical_plan: str = ""
    key_requirements: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    is_design_heavy: bool = False
    design_tech_mix: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "can_implement": self.can_implement,
            "confidence": self.confidence,
            "scope": self.scope,
            "estimated_hours": self.estimated_hours,
            "worth_it": self.worth_it,
            "worth_it_reason": self.worth_it_reason,
            "implementation_type": self.implementation_type,
            "technical_plan": self.technical_plan,
            "key_requirements": self.key_requirements,
            "risks": self.risks,
            "is_design_heavy": self.is_design_heavy,
            "design_tech_mix": self.design_tech_mix,
        }


@dataclass
class ImplementationResult:
    """Result of AI code generation for a contest."""
    files: list[dict[str, str]] = field(default_factory=list)
    readme: str = ""
    entry_point: str = "main.py"
    dependencies: list[str] = field(default_factory=list)
    summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "files": self.files,
            "readme": self.readme,
            "entry_point": self.entry_point,
            "dependencies": self.dependencies,
            "summary": self.summary,
        }


@dataclass
class DesignTechClassification:
    """Result of design-vs-tech classification."""
    category: str = "unclear"  # design_only, tech_only, mixed_design_tech, unclear
    confidence: float = 0.0
    reasoning: str = ""
    design_terms_found: list[str] = field(default_factory=list)
    tech_terms_found: list[str] = field(default_factory=list)

    @property
    def is_design_only(self) -> bool:
        return self.category == "design_only"

    @property
    def is_tech(self) -> bool:
        return self.category in ("tech_only", "mixed_design_tech")

    def to_dict(self) -> dict[str, Any]:
        return {
            "category": self.category,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
            "design_terms_found": self.design_terms_found,
            "tech_terms_found": self.tech_terms_found,
        }


class GrokError(Exception):
    """Error from Grok/LLM operations."""
