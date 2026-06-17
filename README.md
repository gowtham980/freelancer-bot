# Freelancer Bot v2

Unified Freelancer.com automation bot — project bidding, tech contests, website design discovery.

## Installation

```bash
cd freelancer_bot_v2
pip install -e .
```

## Environment Variables

All secrets must be set as environment variables:

```bash
export FREELANCER_OAUTH_TOKEN="your_token_here"
export EMAIL_PASSWORD="your_app_password_here"
```

Optional overrides:
```bash
export EMAIL_FROM="sender@gmail.com"
export EMAIL_TO="recipient@gmail.com"
export EMAIL_SMTP_HOST="smtp.gmail.com"
export EMAIL_SMTP_PORT="587"
```

## Commands

```bash
# Project bidding — search, score, auto-bid
freelancer-bot bid [MAX_BIDS] --dry-run
freelancer-bot bid 3 --min-score 45

# Tech contest discovery — find & implement
freelancer-bot contests [MAX_MATCHES] --dry-run
freelancer-bot contests 5 --no-implement

# Website design discovery — information only
freelancer-bot design [MAX_MATCHES] --dry-run

# View analytics & state
freelancer-bot status
freelancer-bot status --json

# Manage configuration
freelancer-bot config show
freelancer-bot config init
freelancer-bot config set bidding.max_bids_per_run 5
freelancer-bot config migrate  # migrate from legacy JSON state files

# View/generate cron schedules
freelancer-bot schedule show
freelancer-bot schedule generate
```

## Configuration

Config file: `~/.config/freelancer-bot/config.yaml`

State files: `~/.local/share/freelancer-bot/`

## Architecture

```
freelancer_bot/
├── __init__.py      # Package metadata
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
