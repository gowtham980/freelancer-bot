# Freelancer Bot v2 — What It Does & How To Use It

## The Two Bots That Matter

### 1. `bid` — Smart Project Bidding 🚀

**What it does:**
- Searches 12 categories in parallel (Flutter, Python, FastAPI, Django, AI Agents, LLM, etc.)
- Scores projects with AI/agentic keywords weighted HIGHEST (your specialty)
- **Pre-bid analysis** — detects red flags (clones, deferred payment, unlimited revisions, vague scope)
- **Skill match check** — verifies project actually matches your Python/Flutter/AI stack
- **Budget realism** — flags "build Uber clone for $500" nonsense
- **Client quality signals** — milestone payments, clear requirements, verified payment
- Generates truly tailored proposals (references project title, extracts requirements, includes technical approach)
- Filters out ELT/data engineering projects (13 excluded terms)
- Tracks state so it never re-bids the same project

**How to use:**
```bash
cd freelancer_bot_v2

# Quick preview (always do this first)
python3 -m freelancer_bot.cli bid --dry-run 5

# Interactive review — see full analysis, approve/reject each
python3 -m freelancer_bot.cli bid --review 3

# Auto-bid on top 2 (after you're comfortable)
python3 -m freelancer_bot.cli bid 2

# Higher threshold — only excellent matches
python3 -m freelancer_bot.cli bid --min-score 60 2

# Set your minimum rate
python3 -m freelancer_bot.cli bid --min-rate 35 2
```

**What the review mode shows you:**
- Red flags: "Deferred payment", "Clone request", "Unlimited revisions" → verdict: SKIP
- Skill match: "Strong match — skills align: python, ai_agentic, backend" → verdict: GO
- Budget assessment: Is the budget realistic for the scope?
- Client signals: Milestone payments, verified payment, clear requirements

---

### 2. `contests` — Smart Tech Contest Discovery 🏆

**What it does:**
- Searches 18 tech categories in parallel
- **Smart design filtering** — "Python script that generates logos" now PASSES (old filter blocked it)
- **AI feasibility analysis** — checks if AI can actually implement, estimates hours, judges prize-to-effort
- **Quality scoring** — description detail, clear deliverables, prize-to-scope ratio
- **Auto-implementation** — when `--implement` is set, generates actual code with README
- Default is discovery-only (safe) — `--implement` must be explicitly passed

**How to use:**
```bash
# Discovery only (safe default) — find contests, save requests
python3 -m freelancer_bot.cli contests 5

# Dry run — preview without saving anything
python3 -m freelancer_bot.cli contests --dry-run 10

# Actually generate code via AI
python3 -m freelancer_bot.cli contests --implement 3

# Skip AI analysis, use keyword fallback (faster)
python3 -m freelancer_bot.cli contests --no-ai 5

# Higher threshold
python3 -m freelancer_bot.cli contests --min-score 60 5
```

**What AI can implement:**
Python scripts, APIs, web scraping, automation, CLI tools, bots (Telegram/Discord),
FastAPI/Flask apps, simple Django, database scripts, CSV/JSON processing,
file conversion, text processing, API integrations, webhooks, Flutter apps

**What AI CANNOT implement (won't attempt):**
iOS/Android native, React Native, UI/UX design, 3D, animation, video/audio,
hardware, desktop apps, game dev, ML model training, blockchain, Kubernetes

---

## Typical Workflow

### Morning (5 min):
```bash
cd freelancer_bot_v2

# 1. See what's available
python3 -m freelancer_bot.cli bid --dry-run 5
python3 -m freelancer_bot.cli contests --dry-run 10

# 2. Review and bid on good projects
python3 -m freelancer_bot.cli bid --review 3

# 3. Check status
python3 -m freelancer_bot.cli status
```

### Automated (via cron — needs manual install):
```bash
crontab /tmp/new_crontab
```
This runs bidding 3x daily (6AM, 12PM, 6PM) and contests 3x daily (4:30AM, 10AM, 3:30PM).

---

## Key Improvements Over v1

| Feature | v1 (old scripts) | v2 (now) |
|---------|-----------------|----------|
| Pre-bid analysis | None | Red flags, skill match, budget check, client signals |
| Proposals | Generic template | Tailored with project details + technical approach |
| Design filtering | Keyword only | Smart NLP — "Python script that generates logos" passes |
| Contest implementation | JSON file only | Generates actual code with README |
| Scoring | Basic keywords | AI/agentic weighted highest, quality signals, prize-to-scope |
| Review mode | None | Interactive approve/reject with full analysis |
| CLI | 3 separate scripts | One unified CLI with 6 commands |

---

## Environment Variables (already set)
```bash
FREELANCER_OAUTH_TOKEN  # Your Freelancer API token
EMAIL_PASSWORD          # Gmail app password for reports
```
