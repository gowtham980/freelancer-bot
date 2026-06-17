---
name: freelancer-bot
version: "2.0.0"
description: "Automate Freelancer.com — smart project bidding with AI pre-bid analysis, tech contest discovery with auto-implementation, and website design contest tracking. Scores projects by AI/agentic keyword weight, detects red flags, generates tailored proposals."
argument-hint: 'freelancer-bot bid 3 | freelancer-bot contests 5 | freelancer-bot design 10 | freelancer-bot status'
allowed-tools: Bash
homepage: https://github.com/gowtham980/freelancer-bot
repository: https://github.com/gowtham980/freelancer-bot
author: gowthamkrishnateja
license: MIT
user-invocable: true
metadata:
  openclaw:
    emoji: "💼"
    requires:
      env:
        - FREELANCER_OAUTH_TOKEN
      optionalEnv:
        - EMAIL_PASSWORD
        - EMAIL_FROM
        - EMAIL_TO
        - EMAIL_SMTP_HOST
        - EMAIL_SMTP_PORT
        - LLM_API_KEY
        - LLM_BASE_URL
        - LLM_MODEL
      bins:
        - python3
    primaryEnv: FREELANCER_OAUTH_TOKEN
    install:
      - kind: brew
        formula: uv
        bins: [uv]
    tags:
      - freelancer
      - bidding
      - contests
      - freelance
      - automation
      - ai
      - gig-economy
      - projects
      - python
      - flutter
      - django
      - fastapi
      - agentic
      - llm
---

# Freelancer Bot v2

Unified Freelancer.com automation — smart project bidding, tech contest discovery, and website design tracking. Uses AI-powered pre-bid analysis to detect red flags, assess budget realism, and generate tailored proposals.

## Prerequisites

### 1. Python 3.10+ and uv

```bash
# Install uv (fast Python package manager)
brew install uv
```

### 2. Freelancer.com OAuth Token

You need a valid OAuth token from Freelancer.com:

1. Go to **Freelancer.com → Settings → API** (or visit https://www.freelancer.com/users/api)
2. Create an application or use an existing token
3. Copy the OAuth token — it looks like a long random string
4. Tokens expire periodically; you'll need to refresh when bids start failing with 401 errors

```bash
export FREELANCER_OAUTH_TOKEN="your_token_here"
```

### 3. LLM for AI Features (Optional but Recommended)

The pre-bid analysis, contest feasibility checks, and auto-implementation use an LLM via Ollama or any OpenAI-compatible API. Without this, the bot falls back to keyword-based scoring (less accurate).

**Option A: Local Ollama (free, private)**
```bash
# Install Ollama and pull a model
brew install ollama
ollama pull llama3.2:3b
# Bot auto-detects Ollama at http://localhost:11434
```

**Option B: Any OpenAI-compatible API (Groq, XAI, OpenRouter, etc.)**
```bash
export LLM_API_KEY="your_api_key"
export LLM_BASE_URL="https://api.groq.com/openai/v1"   # optional, defaults to Ollama
export LLM_MODEL="llama-3.1-8b-instant"                 # optional
```

### 4. Email Reports (Optional)

For email summaries after bidding/contest runs:

```bash
export EMAIL_PASSWORD="your_gmail_app_password"
export EMAIL_FROM="sender@gmail.com"
export EMAIL_TO="recipient@gmail.com"
# Optional overrides:
export EMAIL_SMTP_HOST="smtp.gmail.com"   # default
export EMAIL_SMTP_PORT="587"             # default
```

## Installation

```bash
# Navigate to the skill folder
cd skills/freelancer-bot

# Install dependencies with uv
uv pip install httpx typer rich pyyaml structlog croniter python-dateutil

# Or install the package in development mode
uv pip install -e .
```

After install, the CLI is available as `freelancer-bot` or via `python3 -m freelancer_bot.cli`.

## Quick Start

```bash
# Always start with dry-runs to preview without committing
python3 -m freelancer_bot.cli bid --dry-run 5
python3 -m freelancer_bot.cli contests --dry-run 10

# Interactive review — see full analysis, approve/reject each
python3 -m freelancer_bot.cli bid --review 3

# Auto-bid on top 2 projects (when you're comfortable)
python3 -m freelancer_bot.cli bid 2

# Check status
python3 -m freelancer_bot.cli status
```

## Commands

### `bid` — Smart Project Bidding
Searches 12 categories (Flutter, Python, FastAPI, Django, AI Agents, LLM, etc.), scores projects with AI/agentic keywords weighted highest, and generates tailored proposals.

```bash
python3 -m freelancer_bot.cli bid [MAX_BIDS]
python3 -m freelancer_bot.cli bid --dry-run 5       # Preview only, no bids placed
python3 -m freelancer_bot.cli bid --review 3         # Interactive approve/reject each
python3 -m freelancer_bot.cli bid --min-score 60 2   # Only high-quality matches
python3 -m freelancer_bot.cli bid --min-rate 35 2    # Minimum hourly rate filter
python3 -m freelancer_bot.cli bid --no-ai 2          # Skip AI analysis, faster
```

**Pre-bid analysis checks:**
- Red flags: clones, deferred payment, unlimited revisions, vague scope
- Skill match: verifies project matches Python/Flutter/AI stack
- Budget realism: flags unrealistic budgets for scope
- Client quality: milestone payments, verified payment, clear requirements

### `contests` — Tech Contest Discovery
Searches 18 tech categories, uses AI to assess feasibility, estimates hours, judges prize-to-effort ratio. Can auto-implement with `--implement`.

```bash
python3 -m freelancer_bot.cli contests [MAX_MATCHES]
python3 -m freelancer_bot.cli contests --dry-run 10  # Preview only
python3 -m freelancer_bot.cli contests --implement 3  # Generate code via AI
python3 -m freelancer_bot.cli contests --no-ai 5     # Skip AI, faster
python3 -m freelancer_bot.cli contests --min-score 60 5  # Higher threshold
```

### `design` — Website Design Contests
Discovers website design contests across 10 categories. Information-only (no bidding).

```bash
python3 -m freelancer_bot.cli design [MAX_MATCHES]
python3 -m freelancer_bot.cli design --dry-run 10
```

### `status` — Analytics & State
```bash
python3 -m freelancer_bot.cli status
python3 -m freelancer_bot.cli status --json
```

### `config` — Configuration Management
```bash
python3 -m freelancer_bot.cli config show
python3 -m freelancer_bot.cli config set bidding.max_bids_per_run 5
python3 -m freelancer_bot.cli config set llm.model llama3.2:3b
```

### `schedule` — Cron Schedule
```bash
python3 -m freelancer_bot.cli schedule show
python3 -m freelancer_bot.cli schedule generate
```

## Architecture

```
freelancer_bot/
├── api.py           # httpx async API client with retry/backoff
├── email.py         # SMTP email sender (HTML + plain text)
├── state.py         # Unified state management + migration
├── scoring.py       # Scoring algorithms for projects & contests
├── proposals.py     # AI-powered dynamic proposal generation
├── bidding.py       # Project bidding engine (12 search categories)
├── contests.py      # Tech contest discovery + implementation (18 categories)
├── design.py        # Website design contest discovery (10 categories)
├── config.py        # YAML config management
├── analytics.py     # Tracking and reporting
├── llm.py          # LLM client (Ollama + OpenAI-compatible APIs)
└── cli.py           # Typer CLI with all subcommands
```

## Configuration

Config file: `~/.config/freelancer-bot/config.yaml`
State files: `~/.local/share/freelancer-bot/`

## Key Features

| Feature | Manual Bidding | Freelancer Bot |
|---------|---------------|----------------|
| Pre-bid analysis | None | Red flags, skill match, budget check, client signals |
| Proposals | Generic template | Tailored with project details + technical approach |
| Design filtering | Keyword only | Smart NLP — "Python script that generates logos" passes |
| Contest implementation | Manual | Generates actual code with README |
| Scoring | Basic keywords | AI/agentic weighted highest, quality signals |
| Review mode | None | Interactive approve/reject with full analysis |

## Typical Workflow

**Morning check (5 min):**
```bash
cd skills/freelancer-bot
python3 -m freelancer_bot.cli bid --dry-run 5
python3 -m freelancer_bot.cli contests --dry-run 10
python3 -m freelancer_bot.cli bid --review 3
python3 -m freelancer_bot.cli status
```

## Cron Automation

Generate a crontab file, then install it manually (macOS blocks automated crontab install):

```bash
python3 -m freelancer_bot.cli schedule generate
crontab /tmp/new_crontab
```

Default schedule: bidding 3x daily (6AM, 12PM, 6PM) and contests 3x daily (4:30AM, 10AM, 3:30PM).

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `ModuleNotFoundError: httpx` | Run `uv pip install httpx typer rich pyyaml structlog croniter python-dateutil` |
| `401 Authentication failed` | Your Freelancer OAuth token expired — get a new one from freelancer.com/users/api |
| `No AI analysis` | Install Ollama (`brew install ollama`) or set `LLM_API_KEY` |
| `uv: command not found` | Run `brew install uv` |
| Config not saving | Check `~/.config/freelancer-bot/` exists and is writable |

## Notes

- The bot tracks state so it never re-bids the same project
- AI/agentic keywords are weighted highest in scoring
- ELT/data engineering projects are excluded (13 filter terms)
- Default is discovery-only for contests — `--implement` must be explicitly passed
- Always use `--dry-run` first to preview before placing real bids
