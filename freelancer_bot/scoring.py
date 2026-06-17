"""Scoring algorithms for projects and contests.

All keyword weights and thresholds from the spec.
Enhanced with NLP-aware design filtering and quality scoring.
"""

from __future__ import annotations

import re
from typing import Any

# ── Keyword weights for project scoring ──────────────────────────────────

PROJECT_KEYWORD_WEIGHTS: dict[str, int] = {
    "flutter": 20,
    "python": 20,
    "fastapi": 25,
    "django": 25,
    "ai": 25,
    "ml": 25,
    "machine learning": 25,
    "agentic ai": 30,
    "google adk": 30,
    "react": 15,
}

# ── Keyword weights for tech contest scoring ────────────────────────────

CONTEST_FRAMEWORK_WEIGHTS: dict[str, int] = {
    "flutter": 70,
    "python": 60,
    "fastapi": 60,
    "django": 60,
    "ai": 60,
    "agentic ai": 70,
    "google adk": 70,
    "llm": 60,
    "openai": 50,
}

CONTEST_RELATED_WEIGHTS: dict[str, int] = {
    "mobile": 40,
    "web": 35,
    "api": 40,
    "backend": 40,
    "full stack": 40,
    "database": 30,
    "firebase": 30,
    "typescript": 25,
    "node": 25,
    "javascript": 25,
    "react": 35,
}

# ── Keyword weights for website design contest scoring ──────────────────

DESIGN_KEYWORD_WEIGHTS: dict[str, int] = {
    "website design": 50,
    "web design": 45,
    "ui design": 40,
    "landing page": 45,
    "responsive": 30,
    "modern website": 40,
    "website redesign": 35,
    "portfolio": 25,
    "corporate": 20,
    "e-commerce": 35,
    "ecommerce": 35,
    "saas": 30,
    "dashboard": 30,
    "admin panel": 25,
    "wordpress": 15,
    "shopify": 15,
}

# ── Excluded terms (ELT/Data Engineering) ────────────────────────────────

EXCLUDED_TERMS: list[str] = [
    "etl", "elt", "data pipeline", "airbyte", "dbt", "data warehouse",
    "data engineering", "apache airflow", "prefect", "dagster",
    "data extraction", "data transformation", "data loading",
]

# ── Design filter terms (60+ terms to exclude from tech contests) ────────

DESIGN_FILTER_TERMS: list[str] = [
    "logo", "need a logo", "design a logo", "need logo", "create a logo",
    "flyer", "brochure", "banner", "poster", "business card",
    "letterhead", "stationery", "branding identity", "packaging design",
    "label design", "t-shirt design", "merch design", "social media design",
    "instagram post", "facebook cover", "youtube banner", "thumbnail",
    "infographic", "illustration", "character design", "mascot",
    "photoshop", "illustrator design", "canva", "figma", "figma design only", "mockup", "wireframe",
    "graphic design", "ui design only", "ux design only", "web design only",
    "app design only", "icon design", "vector design", "redesign logo",
    "brand identity", "brand guidelines", "brand book", "style guide",
    "color palette", "typography", "font design", "motion graphics",
    "animation design", "3d design", "3d modeling", "product design",
    "industrial design", "interior design", "fashion design",
    "jewelry design", "print design", "magazine design", "book cover",
    "album cover", "podcast cover", "twitch overlay", "stream overlay",
    "discord banner", "twitter banner", "linkedin banner",
    "social media template", "email template", "newsletter design",
    "presentation design", "pitch deck", "resume design", "cv design",
    "artwork", "wordmark", "redesign", "website skin", "theme redesign",
    "skin redesign", "mousepad design", "medallion design",
]

# ── Tech terms for design-vs-tech context detection ──────────────────────

TECH_CONTEXT_TERMS: list[str] = [
    "python", "javascript", "typescript", "react", "flutter", "django",
    "fastapi", "api", "script", "automate", "automation", "bot",
    "scraping", "scraper", "backend", "frontend", "full stack",
    "database", "node.js", "nodejs", "cli", "command line",
    "web app", "web application", "mobile app", "ai", "ml",
    "machine learning", "llm", "openai", "gpt", "google adk",
    "docker", "aws", "gcp", "azure", "kubernetes", "microservice",
    "rest api", "graphql", "websocket", "webhook", "cron job",
    "scheduler", "data processing", "csv", "json", "xml",
    "parsing", "extraction", "generate", "generator", "build",
    "develop", "code", "program", "implement", "deploy",
    "server", "hosting", "cloud function", "lambda",
    "firebase", "supabase", "sql", "nosql", "mongodb", "postgres",
    "redis", "celery", "rabbitmq", "kafka",
    "setup", "sms", "twilio", "reminder", "notification",
    "tech", "technology", "software", "saas",
    "component", "library", "module", "package",
]


def normalize_text(text: str) -> str:
    """Normalize text for keyword matching."""
    return text.lower().strip()


def count_keyword_matches(text: str, keywords: dict[str, int]) -> tuple[int, list[str]]:
    """Count weighted keyword matches in text.

    Returns (total_weight, matched_keywords_list).
    """
    text_lower = normalize_text(text)
    total = 0
    matched: list[str] = []

    for keyword, weight in keywords.items():
        # Use word boundary matching for short keywords, substring for phrases
        if " " in keyword:
            # Multi-word phrase — substring match
            if keyword in text_lower:
                total += weight
                matched.append(keyword)
        else:
            # Single word — word boundary match
            pattern = rf"\b{re.escape(keyword)}\b"
            if re.search(pattern, text_lower):
                total += weight
                matched.append(keyword)

    return total, matched


def contains_excluded_terms(text: str, excluded: list[str] | None = None) -> bool:
    """Check if text contains any excluded terms."""
    if excluded is None:
        excluded = EXCLUDED_TERMS
    text_lower = normalize_text(text)
    for term in excluded:
        if term in text_lower:
            return True
    return False


def contains_design_terms(text: str, design_terms: list[str] | None = None) -> bool:
    """Check if text contains design-related terms (for filtering tech contests)."""
    if design_terms is None:
        design_terms = DESIGN_FILTER_TERMS
    text_lower = normalize_text(text)
    for term in design_terms:
        if term in text_lower:
            return True
    return False


def contains_tech_terms(text: str, tech_terms: list[str] | None = None) -> bool:
    """Check if text contains tech-related terms."""
    if tech_terms is None:
        tech_terms = TECH_CONTEXT_TERMS
    text_lower = normalize_text(text)
    for term in tech_terms:
        if " " in term:
            if term in text_lower:
                return True
        else:
            pattern = rf"\b{re.escape(term)}\b"
            if re.search(pattern, text_lower):
                return True
    return False


def find_design_terms(text: str, design_terms: list[str] | None = None) -> list[str]:
    """Find which design terms are present in text."""
    if design_terms is None:
        design_terms = DESIGN_FILTER_TERMS
    text_lower = normalize_text(text)
    found: list[str] = []
    for term in design_terms:
        if term in text_lower:
            found.append(term)
    return found


def find_tech_terms(text: str, tech_terms: list[str] | None = None) -> list[str]:
    """Find which tech terms are present in text."""
    if tech_terms is None:
        tech_terms = TECH_CONTEXT_TERMS
    text_lower = normalize_text(text)
    found: list[str] = []
    for term in tech_terms:
        if " " in term:
            if term in text_lower:
                found.append(term)
        else:
            pattern = rf"\b{re.escape(term)}\b"
            if re.search(pattern, text_lower):
                found.append(term)
    return found




def _is_primary_design_output(text: str, design_terms: list[str]) -> bool:
    """Check if the contest is PRIMARILY about producing a design output.
    
    Uses multiple signals:
    1. Title contains design-output words (logo, brand identity, stationery, etc.)
    2. Explicit "need/want/design a [design-asset]" patterns
    3. Strong design terms present AND no code-output indicators
    
    e.g., "Logo Design for AapkaCash" → True (title says logo)
    "Python script that generates logos" → False (output is code)
    """
    text_lower = text.lower()
    
    # Signal 1: Title-first design detection
    # If the title (first ~150 chars) contains strong design-output words,
    # it's almost certainly a design contest regardless of description
    title_portion = text_lower[:150]

    # Quick check: does the TITLE indicate a design output?
    # "Midscore Credit Counseling Logo" → design (title ends with 'logo')
    # "Python Script for Logo Generation" → not design (title starts with code)
    # Strategy: check first ~80 chars for design-output words as standalone terms
    title_region = text_lower[:80]
    title_region_words = title_region.split()
    # Design-output words that indicate the deliverable IS a design asset
    primary_design_outputs = {
        'logo', 'flyer', 'brochure', 'banner', 'poster', 'illustration',
        'stationery', 'letterhead', 'mockup', 'wireframe', 'icon',
        'labels', 'artwork', 'medallion', 'wordmark',
    }
    # Code-output words that indicate the deliverable IS code
    code_outputs = {
        'script', 'app', 'api', 'backend', 'frontend', 'cli', 'tool',
        'bot', 'scraper', 'pipeline', 'microservice', 'generator',
        'builder', 'maker', 'creator', 'platform', 'website',
        'component', 'library', 'module', 'package', 'framework',
        'setup', 'configuration', 'deployment', 'integration',
        'automation', 'processing', 'extraction', 'conversion',
    }
    has_design_output = any(w.rstrip(',.:;!?') in primary_design_outputs for w in title_region_words)
    has_code_output = any(w.rstrip(',.:;!?') in code_outputs for w in title_region_words)
    
    if has_design_output and not has_code_output:
        return True

    strong_design_title_words = [
        'logo design', 'brand identity', 'stationery', 'business card',
        'letterhead', 'flyer design', 'brochure design', 'poster design',
        'banner design', 'packaging design', 'label design', 't-shirt design',
        'book cover', 'album cover', 'podcast cover', 'illustration',
        'vector design', 'icon design', 'mascot design', 'character design',
        'brand guidelines', 'brand book', 'style guide',
        'social media design', 'instagram post', 'facebook cover',
        'youtube banner', 'thumbnail design', 'twitch overlay',
        'stream overlay', 'discord banner', 'twitter banner',
        'presentation design', 'pitch deck', 'resume design', 'cv design',
        'infographic', 'motion graphics', 'animation design',
        'print design', 'magazine design', 'newsletter design',
        'email template', 'social media template', 'merch design',
        'clothing logo', 'brand identity kit', 'corporate stationery',
        'headstone medallion', 'pack designer', 'brand stationery',
    ]
    for phrase in strong_design_title_words:
        if phrase in title_portion:
            return True
    
    # Signal 2: Explicit "need/want/design/create a [design-asset]" patterns
    design_output_markers = [
        r'(?:need|want|design|create|make|get)(?:ing)?\s+a\s+(?:\w+\s+)?(?:logo|flyer|brochure|banner|poster|mockup|wireframe|figma|cover|illustration)',
        r'(?:need|want|design|create|make|get)(?:ing)?\s+(?:some|new|a|an|my)\s+(?:\w+\s+)?(?:logo|flyer|brochure|mockup|wireframe|cover|illustration)',
    ]
    for pattern in design_output_markers:
        if re.search(pattern, text_lower):
            return True
    
    # Signal 3: Strong design terms present AND no code-output indicators
    # If the text is about creating a design asset and doesn't mention
    # building/coding/programming as the primary action
    code_output_indicators = [
        r'(?:build|code|program|develop|implement|deploy)\s+(?:a|an|the)\s+',
        r'(?:script|app|application|api|backend|frontend|cli|tool|bot|scraper|pipeline|microservice)',
        r'(?:python|javascript|typescript|react|flutter|django|fastapi|node\.?js)\s+(?:script|app|code|project)',
    ]
    has_code_output = any(re.search(p, text_lower) for p in code_output_indicators)
    
    if not has_code_output and len(design_terms) >= 2:
        return True
    
    return False


def _has_specific_tech_terms(found_tech: list[str]) -> bool:
    """Check if found tech terms are specific (python, react) vs generic (generate, build)."""
    generic_tech_words: set[str] = {
        "generate", "generator", "build", "develop", "code", "program",
        "implement", "deploy", "server", "hosting",
    }
    return any(t not in generic_tech_words for t in found_tech)


def classify_design_vs_tech(text: str) -> dict[str, Any]:
    """Smart classification: is this design-only, tech-only, or mixed?

    Uses multiple heuristics:
    1. If it has design terms only → design_only
    2. If it has specific tech terms only → tech_only
    3. If both, check: is the PRIMARY output a design asset?
       - "I need a logo for my Python consulting" → design (output is logo)
       - "Python script that generates SVGs" → tech (output is code)
    4. If generic tech + design → design (e.g., "Generate a podcast cover")
    """
    design_terms_found = find_design_terms(text)
    tech_terms_found = find_tech_terms(text)

    # ── Primary design output check (runs BEFORE term matching) ─────
    # Some contests are clearly design but don't match DESIGN_FILTER_TERMS
    # e.g., "Medieval Mousepad Artwork Design" or "Website Skin Redesign"
    if _is_primary_design_output(text, design_terms_found):
        return {
            "category": "design_only",
            "confidence": 0.8,
            "reasoning": "Primary output is a design asset — treating as design contest",
            "design_terms_found": design_terms_found,
            "tech_terms_found": tech_terms_found,
            "is_design_only": True,
            "is_tech": False,
        }

    if tech_terms_found and design_terms_found:
        # Has both — determine if the PRIMARY output is a design asset
        is_primary_design = _is_primary_design_output(text, design_terms_found)
        has_specific_tech = _has_specific_tech_terms(tech_terms_found)

        if is_primary_design and not has_specific_tech:
            # "Generate a logo for..." → design
            return {
                "category": "design_only",
                "confidence": 0.75,
                "reasoning": f"Primary output is a design asset ({', '.join(design_terms_found[:3])}) — treating as design",
                "design_terms_found": design_terms_found,
                "tech_terms_found": tech_terms_found,
                "is_design_only": True,
                "is_tech": False,
            }
        elif is_primary_design and has_specific_tech:
            # "I need a logo for my Python consulting biz" → still design
            # The tech term is about the business context, not the deliverable
            return {
                "category": "design_only",
                "confidence": 0.7,
                "reasoning": f"Primary output is a design asset ({', '.join(design_terms_found[:3])}); tech terms are contextual — treating as design",
                "design_terms_found": design_terms_found,
                "tech_terms_found": tech_terms_found,
                "is_design_only": True,
                "is_tech": False,
            }
        elif not has_specific_tech:
            # Only generic tech + design, not primary design → still design
            return {
                "category": "design_only",
                "confidence": 0.75,
                "reasoning": f"Design terms found ({', '.join(design_terms_found[:3])}) but only generic tech terms — treating as design",
                "design_terms_found": design_terms_found,
                "tech_terms_found": tech_terms_found,
                "is_design_only": True,
                "is_tech": False,
            }

        # Specific tech + design, NOT primary design output → tech contest
        # (e.g., "Python script that generates logos", "AI model for logo design")
        return {
            "category": "mixed_design_tech",
            "confidence": 0.7,
            "reasoning": f"Contains both tech ({', '.join(tech_terms_found[:3])}) and design ({', '.join(design_terms_found[:3])}) terms — treating as tech contest",
            "design_terms_found": design_terms_found,
            "tech_terms_found": tech_terms_found,
            "is_design_only": False,
            "is_tech": True,
        }
    elif tech_terms_found:
        # Only tech terms — check if they're specific or generic
        has_specific_tech = _has_specific_tech_terms(tech_terms_found)
        if not has_specific_tech:
            return {
                "category": "unclear",
                "confidence": 0.4,
                "reasoning": f"Only generic terms found ({', '.join(tech_terms_found[:3])}) — unclear if tech",
                "design_terms_found": design_terms_found,
                "tech_terms_found": tech_terms_found,
                "is_design_only": False,
                "is_tech": False,
            }
        return {
            "category": "tech_only",
            "confidence": 0.8,
            "reasoning": f"Contains tech terms: {', '.join(tech_terms_found[:3])}",
            "design_terms_found": design_terms_found,
            "tech_terms_found": tech_terms_found,
            "is_design_only": False,
            "is_tech": True,
        }
    elif design_terms_found:
        return {
            "category": "design_only",
            "confidence": 0.7,
            "reasoning": f"Contains design terms: {', '.join(design_terms_found[:3])}",
            "design_terms_found": design_terms_found,
            "tech_terms_found": tech_terms_found,
            "is_design_only": True,
            "is_tech": False,
        }
    else:
        return {
            "category": "unclear",
            "confidence": 0.3,
            "reasoning": "No clear tech or design terms found",
            "design_terms_found": [],
            "tech_terms_found": [],
            "is_design_only": False,
            "is_tech": False,
        }
def score_description_quality(text: str) -> tuple[int, dict[str, Any]]:
    """Score contest description quality — longer/detailed = more serious client.

    Returns (quality_score, breakdown).
    """
    text = text.strip()
    word_count = len(text.split())
    has_bullets = bool(re.search(r'[-*•]\s|\d+\.\s', text))
    has_sections = bool(re.search(r'(?i)(requirements|deliverables|scope|timeline|budget)', text))
    has_specifics = bool(re.search(r'(?i)(must|should|required|need to|specifically|exactly)', text))

    score = 0
    breakdown = {}

    # Length scoring
    if word_count >= 200:
        score += 15
        breakdown["length"] = 15
    elif word_count >= 100:
        score += 10
        breakdown["length"] = 10
    elif word_count >= 50:
        score += 5
        breakdown["length"] = 5
    else:
        breakdown["length"] = 0

    # Structure scoring
    if has_bullets:
        score += 5
        breakdown["has_bullets"] = 5
    else:
        breakdown["has_bullets"] = 0

    if has_sections:
        score += 5
        breakdown["has_sections"] = 5
    else:
        breakdown["has_sections"] = 0

    if has_specifics:
        score += 5
        breakdown["has_specifics"] = 5
    else:
        breakdown["has_specifics"] = 0

    return score, breakdown


def score_prize_to_scope(prize: float, description: str) -> tuple[int, dict[str, Any]]:
    """Score prize-to-scope ratio. Higher prize for simpler work = better.

    Returns (ratio_score, breakdown).
    """
    word_count = len(description.split())
    # Rough scope estimate from description length
    if word_count >= 300:
        estimated_scope = "large"
    elif word_count >= 150:
        estimated_scope = "medium"
    elif word_count >= 50:
        estimated_scope = "small"
    else:
        estimated_scope = "tiny"

    score = 0
    breakdown = {"prize": prize, "estimated_scope": estimated_scope}

    if estimated_scope == "tiny" and prize >= 50:
        score = 15
        breakdown["ratio"] = "excellent"
    elif estimated_scope == "small" and prize >= 100:
        score = 12
        breakdown["ratio"] = "great"
    elif estimated_scope == "small" and prize >= 50:
        score = 8
        breakdown["ratio"] = "good"
    elif estimated_scope == "medium" and prize >= 200:
        score = 10
        breakdown["ratio"] = "great"
    elif estimated_scope == "medium" and prize >= 100:
        score = 6
        breakdown["ratio"] = "good"
    elif estimated_scope == "large" and prize >= 500:
        score = 8
        breakdown["ratio"] = "good"
    elif estimated_scope == "large" and prize >= 200:
        score = 4
        breakdown["ratio"] = "ok"
    else:
        score = 0
        breakdown["ratio"] = "poor"

    return score, breakdown


def score_project(project: dict[str, Any]) -> dict[str, Any]:
    """Score a project for bidding suitability.

    Returns dict with score, matched_keywords, and breakdown.
    """
    title = project.get("title", "")
    description = project.get("description", "") or project.get("preview_description", "")
    full_text = f"{title} {description}"

    # Check excluded terms first
    if contains_excluded_terms(full_text):
        return {
            "score": 0,
            "matched_keywords": [],
            "breakdown": {"excluded": True},
            "should_bid": False,
        }

    # Keyword scoring
    kw_score, matched = count_keyword_matches(full_text, PROJECT_KEYWORD_WEIGHTS)

    # Budget scoring
    budget = project.get("budget", {})
    budget_score = 0
    budget_min = budget.get("minimum", 0) if isinstance(budget, dict) else 0
    budget_max = budget.get("maximum", 0) if isinstance(budget, dict) else 0
    project_type = project.get("type", "fixed")

    if project_type == "fixed":
        if budget_min >= 1000 or budget_max >= 1000:
            budget_score = 15
        elif budget_min >= 500 or budget_max >= 500:
            budget_score = 10
    elif project_type == "hourly":
        # Check hourly rate from budget or description
        hourly_rate = 0
        if isinstance(budget, dict):
            hourly_rate = budget.get("minimum", 0)
        if hourly_rate >= 50:
            budget_score = 15

    # Competition scoring
    bid_count = project.get("bid_count", project.get("bids", 0))
    if isinstance(bid_count, dict):
        bid_count = bid_count.get("count", 0)
    competition_score = 0
    if bid_count < 10:
        competition_score = 15
    elif bid_count < 30:
        competition_score = 10

    total_score = kw_score + budget_score + competition_score

    return {
        "score": total_score,
        "matched_keywords": matched,
        "breakdown": {
            "keywords": kw_score,
            "budget": budget_score,
            "competition": competition_score,
            "excluded": False,
        },
        "should_bid": total_score >= 40,
    }


def score_tech_contest(contest: dict[str, Any]) -> dict[str, Any]:
    """Score a tech contest for implementation suitability.

    Enhanced with:
    - NLP-aware design filtering (design terms + tech terms = tech contest)
    - Description quality scoring
    - Prize-to-scope ratio scoring

    Returns dict with score, matched_keywords, breakdown, and design_filter flag.
    """
    title = contest.get("title", "")
    description = contest.get("description", "") or contest.get("preview_description", "")
    full_text = f"{title} {description}"

    # ── Smart design filtering ───────────────────────────────────────
    # Instead of blindly excluding anything with design terms,
    # check if tech terms are ALSO present. If so, it's a tech contest.
    classification = classify_design_vs_tech(full_text)

    if classification["is_design_only"]:
        return {
            "score": 0,
            "matched_keywords": [],
            "breakdown": {
                "design_filtered": True,
                "classification": classification,
            },
            "should_enter": False,
            "is_design": True,
        }

    # ── Framework keyword scoring ────────────────────────────────────
    fw_score, fw_matched = count_keyword_matches(full_text, CONTEST_FRAMEWORK_WEIGHTS)

    # ── Related tech scoring ─────────────────────────────────────────
    rel_score, rel_matched = count_keyword_matches(full_text, CONTEST_RELATED_WEIGHTS)

    # ── Prize scoring ────────────────────────────────────────────────
    prize = contest.get("prize", 0)
    if isinstance(prize, dict):
        prize = prize.get("amount", 0)
    prize_score = 0
    if prize >= 500:
        prize_score = 10
    elif prize >= 200:
        prize_score = 7
    elif prize >= 100:
        prize_score = 5

    # ── Competition scoring ──────────────────────────────────────────
    entry_count = contest.get("entry_count", contest.get("entries", 0))
    if isinstance(entry_count, dict):
        entry_count = entry_count.get("count", 0)
    competition_score = 0
    if entry_count < 10:
        competition_score = 15
    elif entry_count < 25:
        competition_score = 10
    elif entry_count < 50:
        competition_score = 5

    # ── Quality scoring (NEW) ────────────────────────────────────────
    quality_score, quality_breakdown = score_description_quality(description)

    # ── Prize-to-scope scoring (NEW) ─────────────────────────────────
    ratio_score, ratio_breakdown = score_prize_to_scope(prize, description)

    # ── Design-tech mix bonus (NEW) ──────────────────────────────────
    # If it's mixed design+tech, give a small bonus for being a tech contest
    # that the old filter would have wrongly excluded
    mix_bonus = 5 if classification["category"] == "mixed_design_tech" else 0

    total_score = (
        fw_score + rel_score + prize_score + competition_score +
        quality_score + ratio_score + mix_bonus
    )

    return {
        "score": total_score,
        "matched_keywords": fw_matched + rel_matched,
        "breakdown": {
            "framework_keywords": fw_score,
            "related_tech": rel_score,
            "prize": prize_score,
            "competition": competition_score,
            "quality": quality_score,
            "quality_detail": quality_breakdown,
            "prize_to_scope": ratio_score,
            "prize_to_scope_detail": ratio_breakdown,
            "design_tech_mix_bonus": mix_bonus,
            "design_filtered": False,
            "classification": classification,
        },
        "should_enter": total_score >= 50,
        "is_design": False,
    }


def score_design_contest(contest: dict[str, Any]) -> dict[str, Any]:
    """Score a website design contest for discovery/reporting.

    Returns dict with score, matched_keywords, and breakdown.
    """
    title = contest.get("title", "")
    description = contest.get("description", "") or contest.get("preview_description", "")
    full_text = f"{title} {description}"

    # Keyword scoring
    kw_score, matched = count_keyword_matches(full_text, DESIGN_KEYWORD_WEIGHTS)

    # Prize scoring
    prize = contest.get("prize", 0)
    if isinstance(prize, dict):
        prize = prize.get("amount", 0)
    prize_score = 0
    if prize >= 500:
        prize_score = 20
    elif prize >= 200:
        prize_score = 15
    elif prize >= 100:
        prize_score = 10

    # Competition scoring
    entry_count = contest.get("entry_count", contest.get("entries", 0))
    if isinstance(entry_count, dict):
        entry_count = entry_count.get("count", 0)
    competition_score = 0
    if entry_count < 10:
        competition_score = 20
    elif entry_count < 25:
        competition_score = 15
    elif entry_count < 50:
        competition_score = 10

    total_score = kw_score + prize_score + competition_score

    return {
        "score": total_score,
        "matched_keywords": matched,
        "breakdown": {
            "keywords": kw_score,
            "prize": prize_score,
            "competition": competition_score,
        },
        "should_report": total_score >= 40,
    }


def calculate_bid_amount(
    project: dict[str, Any],
    bid_avg: float | None = None,
) -> float:
    """Calculate suggested bid amount.

    Strategy: bid_avg × 0.85, or midpoint of budget range if no bid_avg.
    """
    budget = project.get("budget", {})
    if not isinstance(budget, dict):
        budget = {}

    budget_min = budget.get("minimum", 0)
    budget_max = budget.get("maximum", 0)

    if bid_avg and bid_avg > 0:
        return round(bid_avg * 0.85, 2)

    if budget_min > 0 and budget_max > 0:
        return round((budget_min + budget_max) / 2, 2)

    if budget_min > 0:
        return round(float(budget_min), 2)

    if budget_max > 0:
        return round(float(budget_max) * 0.85, 2)

    return 100.0  # fallback


def calculate_bid_period(bid_amount: float) -> int:
    """Calculate suggested bid period in days based on amount.

    <$500 → 3 days, <$1500 → 7 days, <$5000 → 14 days, else 30 days.
    """
    if bid_amount < 500:
        return 3
    elif bid_amount < 1500:
        return 7
    elif bid_amount < 5000:
        return 14
    else:
        return 30
