# Council transcript — Daily tick runner architecture

**Date:** 2026-05-20
**Question:** How should monkey-vs-machine run its daily tick now that the openclaw box is dead and Nick doesn't want his laptop as a 24/7 dependency?

**Candidate options:**
1. On-laptop PowerShell verb (`update.ps1`) — catchup → push, one command
2. GitHub Actions cron + R2 — daily workflow + `workflow_dispatch`, SQLite state in R2
3. GH Actions + commit DB to a state branch — binary-in-git, ugly
4. Refactor: D1 as source-of-truth — multi-day refactor, breaks DETERMINISM.md contract
5. Cloudflare Cron Worker — infeasible (sklearn doesn't run in V8)

---

## Advisor responses

### The Contrarian (Response C — strongest per all 3 reviewers)
Option 2 has a fatal flaw being glossed over: GH Actions cron is not a scheduler, it's a suggestion. GitHub explicitly documents that scheduled workflows are deprioritized during high load — delayed 30+ minutes or skipped entirely. For a "perpetual sim" where one missed tick corrupts the lineage timeline forever, this is a silent data-integrity bomb.

Ranked sleeper risks:
1. yfinance from GH runner IPs is already broken intermittently — Azure ranges get 429'd by Yahoo. Known unfixed issue.
2. Determinism is dead the moment you cross OS. HistGradientBoosting + numpy + OpenMP threads on Ubuntu will not produce bit-identical splits to Windows. Pin `OMP_NUM_THREADS=1`, pin every wheel, accept the lineage forks. Document it or the "fair contest" claim dies.
3. `mvm.db` on R2 with no locking = race. `workflow_dispatch` + scheduled run overlap → last-write-wins. Need both a lockfile object and `concurrency:` group on the workflow.
4. R2 cold-start from a 500MB db in two years = 6-min job becomes 25.

Ship Option 1 this week. Add "last tick" timestamp to the dashboard so missed days are visible, not invisible. Migrate to Option 2 only after proving determinism on Ubuntu via Docker locally.

### The First Principles Thinker (Response A)
The framing is wrong. Nick is asking "where do I run cron?" The actual problem: a portfolio piece is generating recurring operational anxiety, and the simulation's design is forcing infrastructure decisions it shouldn't need.

Why does this tick run daily at all? Because markets close daily. But the dashboard's purpose is to demonstrate AI-vs-random-baseline storytelling to recruiters, not to be a real-time prediction service. A 36-hour latency between market close and dashboard update changes literally nothing about the portfolio value.

Two reframes:
1. Batch weekly. One GH Actions run on Saturday processes all 5 trading days at once. Same determinism contract, 5x fewer failure surfaces.
2. Freeze the sim at N days and shift the narrative. A frozen, reproducible 365-day run is a *stronger* portfolio artefact than a fragile live one — recruiters can actually evaluate it.

The assumption baked into all 5 candidates is "daily ticks are non-negotiable." They're not. If Nick still wants live ticks: Option 2. But answer the prior question first.

### The Outsider (Response B)
Why does this need to run every trading day with zero gaps? It's a simulation against random monkeys. If Nick misses a Tuesday, do the monkeys care? Does the visitor at 3am care? The whole framing assumes daily continuity is sacred, but nobody has justified that.

"Perpetual" is doing heavy lifting. A portfolio piece has a job: get looked at once, impress, move on. "Runs forever unattended" is an engineering flex, not a portfolio requirement.

Nick is choosing between two different projects, not four options:
- Option 1 = "I have a cool simulation I run sometimes"
- Option 2 = "I built a self-sustaining cloud system"

He's not over-thinking. He's under-naming the decision. It's not "how do I run the tick," it's "is this a finished portfolio artefact or an ongoing hobby?"

### The Executor (Response D)
Option 1. Ship the PowerShell verb today. Monday morning: open terminal, `./update.ps1`, close laptop. The script is `python scripts/catchup.py; if ($?) { python scripts/push_to_d1.py }`. 15 lines. Twenty minutes end-to-end.

"Laptop not 24/7" is a fake constraint. Nick said "come home in the afternoon and run it." That IS Option 1. He's not asking for unattended automation — he's asking for one command instead of three.

Time-sinks hiding in Option 2:
- R2 bucket + IAM + GH secrets: 30 min good day, 2 hrs when the secret name is wrong
- Seeding initial `mvm.db` into R2: one-off upload script
- sklearn version pinning in runner vs laptop: silent model drift
- Four network hops + race condition vs existing local `.bat`
- `run_daily_tick.bat` Task Scheduler becomes a second cron source of truth

Option 3 is worse: binary SQLite in git is a footgun. Option 4 is a refactor masquerading as a decision. Do Option 1 Monday. Revisit only if Nick actually goes on holiday.

### The Expansionist (Response E — biggest blind spot per all 3 reviewers)
Option 2, and it's not close. The real play: your tick log becomes the artefact. 365 green checkmarks a year on a public repo is a recruiter signal nothing else matches. A Strava streak for engineering discipline.

Second-order upside:
1. The dataset is the moat. Years of (ai_pred, monkey_distribution, actual_return) on real SPX is novel. R2 makes nightly Parquet snapshots cheap. HuggingFace dataset, Kaggle seed, paper hook.
2. GH Actions = free model swaps. Swapping HistGBM for an LLM trader becomes a 50-line PR. "MVM Arena" — submit your model via PR. HN front page.
3. On-laptop forecloses everything. If you go viral on a Tuesday and your laptop is closed, the streak dies.
4. R2 + Workers Analytics Engine = real-time leaderboard.

Pick 2. Publish nightly Parquet. The infra is the smaller half of the bet.

---

## Peer review

All three reviewers independently picked **C (Contrarian)** as strongest — the only response engaging with concrete failure modes (GH Actions cron deprioritization, yfinance/Azure 429s, OpenMP non-determinism across OS, R2 race conditions) rather than narrative.

All three independently flagged **E (Expansionist)** as biggest blind spot — "fantasy second-order outcomes" (HN front page, MVM Arena contributors, dataset moat) that assume inbound demand which doesn't exist for a 90-second-recruiter-skim portfolio piece, and that get killed by C's first-order infra problems anyway.

**New blind spots collectively surfaced:**
- Reviewer 1: Does the existing lineage already have gaps? If yes, the "perpetual integrity" constraint driving the whole debate is already violated and the decision collapses to D trivially.
- Reviewer 2: Nobody costed the **recovery path**. Observability + idempotent backfill is the load-bearing decision, not where cron runs.
- Reviewer 3: Nobody asked what happens **after Nick lands a job**. Option 1's real virtue isn't simplicity, it's *disposability*.

---

## Chairman verdict

### Where the council agrees
- Options 3 (binary in git) and 4 (D1 refactor) are noise — dismiss.
- The dashboard is a portfolio artefact, not a real-time prediction service.
- "Daily ticks are non-negotiable" is the unexamined load-bearing assumption.

### Where the council clashes
- Option 1 (ship the verb today) vs Option 2 (set-and-forget cloud).
  - Contrarian + Executor + First Principles (provisional): Option 1 now, maybe migrate later.
  - Expansionist: Option 2, full send.
- The real disagreement is whether MVM is a finished artefact or a developing platform.

### Blind spots the peer review caught
1. **Existing lineage may already have gaps.** If yes, integrity is already broken — Option 1 wins trivially. Worth auditing before deciding.
2. **No advisor specified the alert/repair loop.** Whichever option ships, the dashboard needs to *visibly* show last-tick freshness so failures are loud, not silent.
3. **Disposability matters more than scalability.** Post-job, Nick wants to stop thinking about this. Option 1 lets him stop. Option 2 commits him to maintenance during the highest-leverage career window.

### The recommendation
**Ship Option 1.** With two riders:
1. Make tick freshness *visible* on the dashboard — pull `lastTick.date` into the hero status pill prominently, with a "stale" colour state if the latest tick is >36h old. This is the alert/repair loop the council missed.
2. Combine with the First Principles reframe: **batch on demand, not by calendar.** Reframe the project narrative away from "perpetual sim" toward "I run a batch when I open my laptop; catchup handles the gap." That eliminates the daily-continuity anxiety entirely.

Reject the Expansionist romance. There is no MVM Arena. There is no HN front page. There is a recruiter who will skim the dashboard for 90 seconds.

### The one thing to do first
**Audit the existing lineage for gaps.** Run a single SQL query against `data/mvm.db` and the prod D1 to see whether the supposed daily-continuity invariant is *already* violated. If yes → Option 1 is the only sane answer. If no → Nick decides consciously whether he wants to defend that property, and the decision is no longer being made by inertia.
