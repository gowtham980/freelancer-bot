"""AI-powered proposal generation for Freelancer.com bids.

Generates truly tailored proposals that reference specific project details,
highlight relevant experience, include technical approach, and provide
timeline breakdowns. Not generic templates — each proposal is unique.
"""

from __future__ import annotations

import re
from typing import Any

import structlog

logger = structlog.get_logger(__name__)

# ── Skill detection patterns ────────────────────────────────────────────

SKILL_PATTERNS: dict[str, list[str]] = {
    "mobile": [
        r"\bmobile\b", r"\bios\b", r"\bandroid\b", r"\bflutter\b",
        r"\breact native\b", r"\bapp store\b", r"\bplay store\b",
        r"\bcross-platform\b", r"\biphone\b", r"\bipad\b",
    ],
    "web": [
        r"\bweb\b", r"\bwebsite\b", r"\bfrontend\b", r"\bfront-end\b",
        r"\breact\b", r"\bvue\b", r"\bangular\b", r"\bhtml\b", r"\bcss\b",
        r"\bjavascript\b", r"\btypescript\b", r"\bnext\.?js\b",
        r"\bresponsive\b", r"\bbrowser\b",
    ],
    "backend": [
        r"\bbackend\b", r"\bback-end\b", r"\bapi\b", r"\brest\b",
        r"\bgraphql\b", r"\bpython\b", r"\bdjango\b", r"\bflask\b",
        r"\bfastapi\b", r"\bnode\b", r"\bexpress\b", r"\bmicroservice",
        r"\bserver\b", r"\bdatabase\b", r"\bpostgres\b", r"\bmongodb\b",
        r"\bmysql\b", r"\bredis\b",
    ],
    "ai_ml": [
        r"\bai\b", r"\bartificial intelligence\b", r"\bmachine learning\b",
        r"\bml\b", r"\bllm\b", r"\blarge language model\b", r"\bopenai\b",
        r"\bgpt\b", r"\bchatgpt\b", r"\bclaude\b", r"\bgemini\b",
        r"\bdeep learning\b", r"\bneural network\b", r"\bnlp\b",
        r"\bcomputer vision\b", r"\btransformer\b", r"\bhugging face\b",
        r"\bagentic\b", r"\bagent\b", r"\bautonomous\b", r"\brag\b",
        r"\bvector database\b", r"\bembedding\b", r"\bfine-tuning\b",
        r"\bgoogle adk\b", r"\blangchain\b", r"\bllamaindex\b",
    ],
    "flutter": [
        r"\bflutter\b", r"\bdart\b", r"\bwidget\b", r"\bmaterial design\b",
        r"\bcupertino\b", r"\bfirebase\b", r"\bgoogle adk\b",
    ],
    "react": [
        r"\breact\b", r"\breact\.?js\b", r"\bnext\.?js\b", r"\bcomponent\b",
        r"\bjsx\b", r"\bredux\b", r"\bstate management\b", r"\bhook\b",
    ],
    "django": [
        r"\bdjango\b", r"\borm\b", r"\badmin panel\b", r"\bdjango rest\b",
        r"\bdrf\b", r"\bcelery\b", r"\bwsgi\b", r"\basgi\b",
    ],
    "fastapi": [
        r"\bfastapi\b", r"\bstarlette\b", r"\bpydantic\b", r"\basync\b",
        r"\bopenapi\b", r"\bswagger\b",
    ],
    "data": [
        r"\bdata\b", r"\bscraping\b", r"\bcrawl\b", r"\bautomation\b",
        r"\betl\b", r"\bpipeline\b", r"\bcsv\b", r"\bjson\b", r"\bexcel\b",
        r"\bparsing\b", r"\bextraction\b",
    ],
    "devops": [
        r"\bdocker\b", r"\bkubernetes\b", r"\bk8s\b", r"\bci/cd\b",
        r"\bdeployment\b", r"\baws\b", r"\bgcp\b", r"\bazure\b",
        r"\bcloud\b", r"\bterraform\b",
    ],
}


def detect_skills(text: str) -> dict[str, float]:
    """Detect relevant skills from project description.

    Returns dict of skill_category → confidence (0.0–1.0).
    """
    text_lower = text.lower()
    skills: dict[str, float] = {}

    for category, patterns in SKILL_PATTERNS.items():
        matches = 0
        for pattern in patterns:
            if re.search(pattern, text_lower):
                matches += 1
        if matches > 0:
            # Confidence based on match density
            confidence = min(matches / max(len(patterns) * 0.3, 1), 1.0)
            skills[category] = round(confidence, 2)

    return skills


# ── Experience blurbs per skill category ────────────────────────────────
# These are specific, credible, and reference real expertise — not generic fluff.

EXPERIENCE_BLURBS: dict[str, str] = {
    "mobile": (
        "I've built and shipped multiple cross-platform mobile apps using Flutter, "
        "including production apps with Firebase backend, push notifications, and "
        "in-app purchases. I follow clean architecture (BLoC/Riverpod) for maintainable, "
        "testable code."
    ),
    "web": (
        "I've delivered several production React/Next.js frontends with TypeScript, "
        "including dashboards, SaaS interfaces, and responsive consumer-facing sites. "
        "I focus on component-driven architecture, performance optimization, and "
        "accessibility best practices."
    ),
    "backend": (
        "I've designed and built production REST and GraphQL APIs serving thousands of "
        "users. My backend stack includes Python (FastAPI/Django), PostgreSQL, Redis, "
        "and Docker. I emphasize clean architecture, comprehensive testing, and "
        "proper error handling."
    ),
    "ai_ml": (
        "As an AI Tech Lead, I've built production LLM-powered applications including "
        "RAG systems, autonomous AI agents, and multi-model orchestration pipelines. "
        "I work extensively with OpenAI, Claude, Gemini APIs, LangChain, LlamaIndex, "
        "and Google ADK. I understand prompt engineering, embedding strategies, and "
        "production deployment of AI systems."
    ),
    "flutter": (
        "I'm a Flutter specialist with multiple production apps in the App Store and "
        "Play Store. I use clean architecture with BLoC/Riverpod, platform-specific "
        "optimizations, and seamless native feature integration."
    ),
    "react": (
        "I've built complex React applications with Next.js, TypeScript, and modern "
        "state management (Redux/Zustand). I focus on performance, SSR/SSG strategies, "
        "and clean component composition."
    ),
    "django": (
        "I have solid Django experience including Django REST Framework, ORM optimization, "
        "Celery for async task processing, and custom admin panels. I build secure, "
        "scalable backends with proper authentication and API documentation."
    ),
    "fastapi": (
        "I specialize in FastAPI for high-performance async APIs with Pydantic validation, "
        "auto-generated OpenAPI docs, and async database drivers. I've built production "
        "microservices handling thousands of requests per minute."
    ),
    "data": (
        "I've built robust web scrapers and data pipelines using Python, with anti-detection "
        "measures, automated scheduling, and error recovery. I handle data extraction, "
        "transformation, and delivery at scale."
    ),
    "devops": (
        "I handle deployment end-to-end: Docker containerization, CI/CD pipelines, "
        "cloud deployment on AWS/GCP, and monitoring setup. I ensure smooth production "
        "deployments with proper environment management."
    ),
}


def _extract_key_requirements(description: str) -> list[str]:
    """Extract key requirement phrases from project description.

    Looks for sentences/phrases that describe what needs to be built.
    """
    if not description:
        return []

    # Split into sentences
    sentences = re.split(r'[.!?]+', description)
    requirements: list[str] = []

    # Patterns that indicate requirements
    req_patterns = [
        r'\b(?:need|want|require|looking for|must have|should have)\b',
        r'\b(?:build|create|develop|implement|design|deliver)\b',
        r'\b(?:feature|functionality|capability|integration)\b',
    ]

    for sentence in sentences:
        sentence = sentence.strip()
        if len(sentence) < 15:  # skip very short fragments
            continue
        for pattern in req_patterns:
            if re.search(pattern, sentence.lower()):
                # Clean up and truncate
                cleaned = sentence.strip().rstrip(',;:')
                if len(cleaned) > 120:
                    cleaned = cleaned[:117] + "..."
                requirements.append(cleaned)
                break

    # Deduplicate and limit
    seen = set()
    unique = []
    for r in requirements:
        key = r.lower()[:40]
        if key not in seen:
            seen.add(key)
            unique.append(r)

    return unique[:4]  # top 4 unique requirements


def _build_technical_approach(
    skills: dict[str, float],
    requirements: list[str],
    project_type: str,
) -> str:
    """Build a specific technical approach section based on detected skills.

    This is the core of the tailored proposal — it shows the client you've
    actually thought about their project, not just pasted a template.
    """
    top_skills = sorted(skills.items(), key=lambda x: x[1], reverse=True)
    approach_lines: list[str] = []

    # Determine primary tech stack from skills
    primary_skills = [s for s, c in top_skills if c >= 0.3]

    if "ai_ml" in primary_skills:
        approach_lines.append(
            "1. **AI Architecture Design** — I'll design the agent/LLM pipeline "
            "architecture, including model selection, prompt strategy, and RAG setup "
            "if needed. This ensures the AI component is robust and production-ready "
            "from day one."
        )
        if "backend" in primary_skills or "fastapi" in primary_skills:
            approach_lines.append(
                "2. **API Layer** — I'll build a FastAPI backend to serve the AI "
                "capabilities, with proper async handling, rate limiting, and "
                "error recovery for LLM API calls."
            )
        else:
            approach_lines.append(
                "2. **Core Implementation** — I'll implement the AI logic with "
                "proper error handling, fallback strategies, and monitoring so "
                "the system is reliable in production."
            )
        if "web" in primary_skills or "react" in primary_skills:
            approach_lines.append(
                "3. **Frontend Integration** — I'll build the user-facing interface "
                "with React/Next.js, connecting to the AI backend with real-time "
                "updates and a polished UX."
            )
        if "flutter" in primary_skills or "mobile" in primary_skills:
            approach_lines.append(
                "3. **Mobile Integration** — I'll build the Flutter mobile app "
                "connecting to the AI backend, with offline support and native "
                "performance."
            )
    elif "backend" in primary_skills or "fastapi" in primary_skills or "django" in primary_skills:
        approach_lines.append(
            "1. **API Design** — I'll design the REST/GraphQL API with proper "
            "resource modeling, authentication, and comprehensive error handling."
        )
        approach_lines.append(
            "2. **Database Architecture** — I'll set up the database schema with "
            "proper indexing, migrations, and query optimization for performance."
        )
        approach_lines.append(
            "3. **Core Business Logic** — I'll implement the business logic layer "
            "with clean separation of concerns, making it testable and maintainable."
        )
        if "web" in primary_skills or "react" in primary_skills:
            approach_lines.append(
                "4. **Frontend Integration** — I'll build the React/Next.js frontend "
                "with API integration, state management, and responsive design."
            )
    elif "flutter" in primary_skills or "mobile" in primary_skills:
        approach_lines.append(
            "1. **App Architecture** — I'll set up clean Flutter architecture with "
            "BLoC/Riverpod for state management and proper separation of concerns."
        )
        approach_lines.append(
            "2. **UI Implementation** — I'll build all screens with Material Design "
            "guidelines, responsive layouts, and smooth animations."
        )
        approach_lines.append(
            "3. **Backend Integration** — I'll connect to APIs with proper error "
            "handling, caching, and offline support."
        )
    elif "web" in primary_skills or "react" in primary_skills:
        approach_lines.append(
            "1. **Component Architecture** — I'll design the component tree with "
            "reusable, composable components and clear data flow."
        )
        approach_lines.append(
            "2. **State Management** — I'll implement efficient state management "
            "with Redux/Zustand and React Query for server state."
        )
        approach_lines.append(
            "3. **Performance & UX** — I'll optimize for Core Web Vitals, implement "
            "responsive design, and ensure accessibility compliance."
        )
    else:
        # Generic but still structured approach
        approach_lines.append(
            "1. **Requirements Review** — I'll thoroughly analyze all requirements "
            "and clarify any ambiguities before starting."
        )
        approach_lines.append(
            "2. **Architecture Planning** — I'll design the technical architecture "
            "with clean separation of concerns."
        )
        approach_lines.append(
            "3. **Implementation** — I'll build the solution iteratively with "
            "regular progress updates and milestone deliveries."
        )

    # Add testing/delivery step
    approach_lines.append(
        f"{len(approach_lines) + 1}. **Testing & Delivery** — I'll include "
        "comprehensive testing (unit, integration, and E2E where applicable) "
        "and provide clear documentation for handover."
    )

    return "\n".join(approach_lines)


def _build_timeline_breakdown(bid_period: int, bid_amount: float, skills: dict[str, float]) -> str:
    """Build a clear timeline breakdown based on bid period and project scope."""
    days = bid_period

    if days <= 3:
        return (
            f"**Timeline: {days} days**\n"
            f"- Day 1: Requirements analysis, architecture setup, initial implementation\n"
            f"- Day 2: Core functionality complete, testing begins\n"
            f"- Day 3: Final testing, polish, documentation, delivery"
        )
    elif days <= 7:
        return (
            f"**Timeline: {days} days**\n"
            f"- Days 1-2: Requirements deep-dive, architecture design, environment setup\n"
            f"- Days 3-5: Core implementation with daily progress updates\n"
            f"- Days 6-7: Testing, bug fixes, polish, documentation, final delivery"
        )
    elif days <= 14:
        return (
            f"**Timeline: {days} days (2 weeks)**\n"
            f"- Week 1: Architecture & design, core feature implementation\n"
            f"- Week 2: Remaining features, integration testing, polish, delivery\n"
            f"- Milestone check-ins at days 5 and 10 for feedback and adjustments"
        )
    else:
        weeks = days // 7
        return (
            f"**Timeline: {days} days (~{weeks} weeks)**\n"
            f"- Phase 1 (first {weeks // 3 + 1} weeks): Architecture, core features\n"
            f"- Phase 2 (middle {weeks // 3 + 1} weeks): Remaining features, integration\n"
            f"- Phase 3 (final {weeks // 3 + 1} weeks): Testing, polish, documentation\n"
            f"- Weekly progress updates and milestone reviews throughout"
        )


def generate_proposal(
    project: dict[str, Any],
    bid_amount: float,
    bid_period: int,
    *,
    intro_index: int | None = None,
    outro_index: int | None = None,
) -> str:
    """Generate a truly tailored proposal based on project analysis.

    Unlike the old template-based approach, this:
    1. References specific details from the project description
    2. Highlights relevant past experience based on detected tech stack
    3. Includes a specific technical approach for THIS project
    4. Has a clear timeline breakdown
    5. Is concise but compelling — no generic template fluff

    Args:
        project: Project dict from API (should include full description)
        bid_amount: Calculated bid amount
        bid_period: Bid period in days
        intro_index: Optional specific intro to use (for deterministic testing)
        outro_index: Optional specific outro to use (for deterministic testing)

    Returns:
        Full proposal text ready for submission
    """
    title = project.get("title", "")
    description = project.get("description", "") or project.get("preview_description", "")
    project_type = project.get("type", "fixed")
    full_text = f"{title}\n{description}"

    # Detect relevant skills
    skills = detect_skills(full_text)

    # Sort by confidence, take top 3
    top_skills = sorted(skills.items(), key=lambda x: x[1], reverse=True)[:3]

    # Extract key requirements from description
    requirements = _extract_key_requirements(description)

    # ── Build proposal sections ────────────────────────────────────────

    sections: list[str] = []

    # ── 1. Personalized intro referencing the project ──────────────────

    # Craft intro that references the actual project title/type
    title_short = title[:60].rstrip()
    if title_short:
        intro = (
            f"Hi! I've carefully reviewed your project \"{title_short}\" and "
            f"I'm confident I can deliver exactly what you need. "
            f"Here's my tailored approach:"
        )
    else:
        intro = (
            "Hi! I've thoroughly reviewed your project requirements and "
            "I'm confident I can deliver high-quality results. "
            "Here's my tailored approach:"
        )
    sections.append(intro)
    sections.append("")

    # ── 2. Understanding of requirements (shows you actually read it) ──

    if requirements:
        sections.append("**What I Understand You Need:**")
        sections.append("")
        for req in requirements:
            sections.append(f"- {req}")
        sections.append("")

    # ── 3. Relevant experience (specific, not generic) ──────────────────

    if top_skills:
        sections.append("**My Relevant Experience:**")
        sections.append("")
        for skill, confidence in top_skills:
            if skill in EXPERIENCE_BLURBS:
                sections.append(f"- {EXPERIENCE_BLURBS[skill]}")
        sections.append("")

    # ── 4. Technical approach (specific to this project) ────────────────

    sections.append("**My Technical Approach:**")
    sections.append("")
    approach = _build_technical_approach(skills, requirements, project_type)
    sections.append(approach)
    sections.append("")

    # ── 5. Timeline breakdown ───────────────────────────────────────────

    sections.append("**Timeline & Budget:**")
    sections.append("")
    timeline = _build_timeline_breakdown(bid_period, bid_amount, skills)
    sections.append(timeline)
    sections.append("")
    sections.append(
        f"Budget: **${bid_amount:,.2f}** — I'm flexible on scope and "
        f"happy to discuss adjustments to fit your needs."
    )
    sections.append("")

    # ── 6. Outro ────────────────────────────────────────────────────────

    outro = (
        "I'm available to start immediately and can commit to this timeline. "
        "I prioritize clear communication and regular updates throughout the "
        "project. Feel free to check my profile for past work — let's build "
        "something great together!"
    )
    sections.append(outro)

    return "\n".join(sections)


def generate_contest_proposal(
    contest: dict[str, Any],
    implementation_plan: str,
) -> str:
    """Generate a contest entry description based on implementation plan.

    Args:
        contest: Contest dict from API
        implementation_plan: Description of what was implemented

    Returns:
        Contest entry description text
    """
    title = contest.get("title", "")
    prize = contest.get("prize", 0)
    if isinstance(prize, dict):
        prize = prize.get("amount", 0)

    sections = [
        f"Here is my implementation for the contest: **{title}**",
        "",
        "**What I Built:**",
        implementation_plan,
        "",
        "**Technical Details:**",
        "- Clean, well-documented code following best practices",
        "- Proper error handling and edge case coverage",
        "- Ready to use / deploy with minimal setup",
        "",
        "I've thoroughly tested the implementation and it meets all the requirements "
        "specified in the contest brief. Happy to make any adjustments if needed!",
    ]

    return "\n".join(sections)
