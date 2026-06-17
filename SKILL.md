---
name: freelancer-bot
version: "2.0.0"
description: "Automate Freelancer.com — smart project bidding with AI pre-bid analysis, tech contest discovery with auto-implementation, and website design contest tracking. Scores projects by AI/agentic keyword weight, detects red flags, generates tailored proposals."
argument-hint: 'freelancer-bot bid 3 | freelancer-bot contests 5 | freelancer-bot design 10 | freelancer-bot status'
allowed-tools: Bash, Read, Write, AskUserQuestion
homepage: https://github.com/gowthamkrishnateja/freelancer-bot
repository: https://github.com/gowthamkrishnateja/freelancer-bot
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
      bins:
        - python3
    primaryEnv: FREELANCER_OAUTH_TOKEN
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

## Quick Start

```bash
cd freelancer_bot_v2

# Preview projects without bidding
python3 -m freelancer_bot.cli bid --dry-run 5

# Interactive review — see full analysis, approve/reject each
python3 -m freelancer_bot.cli bid --review 3

# Auto-bid on top 2 projects
python3 -m freelancer_bot.cli bid 2

# Discover tech contests
python3 -m freelancer_bot.cli contests --dry-run 10

# Check status
python3 -m freelancer_bot.cli status
```

## Environment Setup

Required:
```bash
export FREELANCER_OAUTH_TOKEN="your_token_here"
```

Optional (for email reports):
```bash
export EMAIL_PASSWORD="your_app_password_here"
export EMAIL_FROM="sender@gmail.com"
export EMAIL_TO="recipient@gmail.com"
```

## Commands

### `bid` — Smart Project Bidding
Searches 12 categories (Flutter, Python, FastAPI, Django, AI Agents, LLM, etc.), scores projects with AI/agentic keywords weighted highest, and generates tailored proposals.

```bash
python3 -m freelancer_bot.cli bid [MAX_BIDS]
python3 -m freelancer_bot.cli bid --dry-run 5       # Preview only
python3 -m freelancer_bot.cli bid --review 3         # Interactive approve/reject
python3 -m freelancer_bot.cli bid --min-score 60 2   # Higher threshold
python3 -m freelancer_bot.cli bid --min-rate 35 2    # Set minimum hourly rate
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
└── cli.py           # Typer CLI with all subcommands
```

## Configuration

Config file: `~/.config/freelancer-bot/config.yaml`
State files: `~/.local/share/freelancer-bot/`

## Key Features Over Manual Bidding

| Feature | Manual | Freelancer Bot |
|---------|--------|----------------|
| Pre-bid analysis | None | Red flags, skill match, budget check, client signals |
| Proposals | Generic template | Tailored with project details + technical approach |
| Design filtering | Keyword only | Smart NLP — "Python script that generates logos" passes |
| Contest implementation | Manual | Generates actual code with README |
| Scoring | Basic keywords | AI/agentic weighted highest, quality signals |
| Review mode | None | Interactive approve/reject with full analysis |

## Typical Workflow

**Morning check (5 min):**
```bash
cd freelancer_bot_v2
python3 -m freelancer_bot.cli bid --dry-run 5
python3 -m freelancer_bot.cli contests --dry-run 10
python3 -m freelancer_bot.cli bid --review 3
python3 -m freelancer_bot.cli status
```

## Cron Automation

Install crontab manually (macOS blocks automated crontab):
```bash
crontab /tmp/new_crontab
```

Runs bidding 3x daily (6AM, 12PM, 6PM) and contests 3x daily (4:30AM, 10AM, 3:30PM).

## Notes

- The bot tracks state so it never re-bids the same project
- AI/agentic keywords are weighted highest in scoring (your specialty)
- ELT/data engineering projects are excluded (13 filter terms)
- Default is discovery-only for contests — `--implement` must be explicitly passed
- Requires a valid Freelancer.com OAuth token (get from Freelancer API settings)
