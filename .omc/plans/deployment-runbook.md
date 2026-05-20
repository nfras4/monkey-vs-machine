# Deployment runbook

Three milestones, each independently useful. Stop at whichever level matches how much you want to invest.

## Milestone 1 — Daily tick running locally (Windows) [30 min]

The shipped code already works on your Windows machine. Just schedule it.

1. **Real bootstrap** (replace the smoke-test 1k monkeys / 10 tickers):
   ```powershell
   cd D:\claudecode\monkey-vs-machine
   python scripts/bootstrap_genesis.py --start-date 2026-05-20 --force
   ```
   Defaults: 100k monkeys, 50 tickers from the fallback S&P list, 180d warmup.

2. **Run today's tick manually once to confirm scale**:
   ```powershell
   python scripts/run_tick.py --date 2026-05-20
   ```
   Watch `ticks.duration_seconds`. At 100k × 50 tickers expect 20–60s on your machine. Record it in `deploy/openclaw/PERF.md` as your baseline.

3. **Schedule with Windows Task Scheduler** (UI-driven, takes 5 min):
   - Action: Start a program — `python.exe`
   - Arguments: `D:\claudecode\monkey-vs-machine\scripts\run_tick.py`
   - Start in: `D:\claudecode\monkey-vs-machine`
   - Trigger: Daily at 06:00 (your local time, after US close)

You now have a perpetual simulation running on your laptop. No public dashboard yet — query SQLite directly:
```powershell
sqlite3 data\state.db "SELECT date, equity FROM ai_portfolio_equity ORDER BY date"
sqlite3 data\state.db "SELECT date, monkey_median, monkey_best FROM daily_aggregates ORDER BY date"
```

**Caveat:** ticks only run when your laptop is on. Misses become catchup work — `python scripts/catchup.py --since 2026-05-19` fixes gaps.

---

## Milestone 2 — Public dashboard, still compute on Windows [2-3 hours]

Adds Cloudflare D1 + SvelteKit Pages so anyone can see the race chart. Compute still local.

1. **Create the D1 database** (one-time, from any machine with wrangler installed):
   ```powershell
   cd D:\claudecode\monkey-vs-machine\dashboard
   npm install -g wrangler   # or use bunx if you prefer
   wrangler login            # browser auth to your Cloudflare account
   wrangler d1 create mvm-prod
   ```
   Wrangler prints a `database_id`. Paste it into `wrangler.toml` replacing `REPLACE_WITH_REAL_ID_AFTER_wrangler_d1_create`.

2. **Apply the schema**:
   ```powershell
   wrangler d1 execute mvm-prod --file=migrations/0001_init.sql --remote
   ```

3. **Generate a strong ingest token** + set it on Pages + on Windows:
   ```powershell
   # Generate (any 32-char hex string works)
   python -c "import secrets; print(secrets.token_hex(32))"
   # Copy the output. You'll use it in two places.
   ```

4. **First Pages deploy**:
   ```powershell
   cd dashboard
   bun install      # or npm install
   bun run build
   wrangler pages deploy .svelte-kit/cloudflare --project-name mvm-dashboard
   # wrangler prints e.g. https://abc123.mvm-dashboard.pages.dev — capture the production URL
   wrangler pages secret put MVM_INGEST_TOKEN --project-name mvm-dashboard
   # paste your token when prompted
   ```

5. **Configure the Windows side** to push after each tick. Two options:
   - **Option A** (simplest): wrap the scheduled task in a `.bat`:
     ```bat
     @echo off
     set PAGES_URL=https://mvm-dashboard.pages.dev
     set MVM_INGEST_TOKEN=<your token from step 3>
     python D:\claudecode\monkey-vs-machine\scripts\run_tick.py
     python D:\claudecode\monkey-vs-machine\scripts\push_to_d1.py
     ```
     Point Task Scheduler at the `.bat` instead of `python.exe`.
   - **Option B**: set the env vars persistently in Windows (`setx PAGES_URL ...` + `setx MVM_INGEST_TOKEN ...`), then your existing scheduled task picks them up.

6. **Backfill any existing ticks to D1**:
   ```powershell
   python scripts\rebuild_d1.py --since 2026-05-20
   ```

7. **Verify** by visiting your `mvm-dashboard.pages.dev` URL. Race / aggregates / monkeys / AI tabs should show real rows.

You now have the public dashboard live, fed by your laptop. Same caveat: laptop must be on at 06:00 daily.

---

## Milestone 3 — Move compute to a dedicated openclaw box [half-day]

Eliminates the laptop dependency. The `deploy/openclaw/` files do most of the work.

1. **Pick a box.** Options:
   - **Cheapest free**: Oracle Cloud Free Tier ARM Ampere (4 vCPU / 24 GB, $0/mo permanently). Sign-up has a hold but no charge.
   - **Cheap paid**: Hetzner CX22 (€4.51/mo, plenty for this workload).
   - **Home hardware**: any always-on Linux box / Raspberry Pi 4+ / NUC.

2. **Provision** (Debian/Ubuntu assumed):
   ```bash
   sudo apt update && sudo apt install -y python3-venv python3-pip git rsync
   git clone <your repo> ~/monkey-vs-machine
   cd ~/monkey-vs-machine
   sudo bash deploy/openclaw/install.sh
   ```
   `install.sh` creates the `mvm` user, sets up the venv, installs systemd units, and prompts for the D1 ingest token.

3. **Fill in secrets**:
   ```bash
   sudo nano /etc/openclaw/secrets.env
   # Set PAGES_URL=https://mvm-dashboard.pages.dev
   # Set MVM_INGEST_TOKEN=<same token from M2 step 3>
   ```

4. **Genesis on openclaw**:
   ```bash
   sudo -u mvm /opt/mvm/.venv/bin/python /opt/mvm/scripts/bootstrap_genesis.py --start-date 2026-05-20
   ```
   *or* if you want to import Windows state: `scp data/state.db user@openclaw:/opt/mvm/data/state.db` and `chown mvm:mvm` it.

5. **Verify**:
   ```bash
   systemctl status mvm-tick.timer
   sudo -u mvm /opt/mvm/.venv/bin/python /opt/mvm/scripts/run_tick.py --date $(date +%Y-%m-%d)
   sudo journalctl -u mvm-tick.service -n 50
   ```

6. **Disable the Windows task** (so you don't double-push). Open Task Scheduler → disable the mvm task.

7. **(Recommended) Add backup** — without this, openclaw drive failure permanently loses SQLite:
   ```bash
   sudo nano /etc/systemd/system/mvm-backup.{service,timer}
   ```
   Templates are in `deploy/openclaw/README.md`. Aim a daily rsync at any second box, NAS, or even a free B2 bucket.

8. **(Optional) Custom domain**: in Cloudflare dashboard, add `monkeys.nickwfraser.dev` (or whatever) → mvm-dashboard project.

---

## Order-of-effort cheatsheet

| Goal | Time | Cost | Risk |
|---|---|---|---|
| **M1** Daily run on your laptop | 30 min | $0 | Laptop must be on |
| **M2** Public dashboard, laptop computes | +2-3h | $0 (CF free tier) | Same |
| **M3** Move compute to openclaw | +half-day | $0-5/mo | Drive failure if no backup |
| **M3b** Add daily backup | +30 min | $0 | None |

## Shortcuts / gotchas

- **You can run M1 today** — everything works on Windows already. M2/M3 are optional polish.
- **D1 free tier** (5 GB storage, 5 M reads/day) handles years of this workload. Won't hit limits at 1 push/day.
- **wrangler login** on Windows opens a browser tab; if your browser blocks it, the CLI prints a URL — open manually.
- **First Pages deploy** may need a custom build command if SvelteKit complains — try `bun run build && wrangler pages deploy .svelte-kit/cloudflare --project-name mvm-dashboard --commit-dirty=true`.
- If wrangler complains about `pages_build_output_dir`, comment it out in `wrangler.toml` and pass the path on the CLI instead (CF Pages keeps changing this surface).

## Done condition for "shipped publicly"

- ✅ `https://mvm-dashboard.pages.dev/` shows AI vs monkey aggregates
- ✅ `https://mvm-dashboard.pages.dev/monkeys/alice` shows a continuous trade history for one of the genesis personalities
- ✅ The latest row is no more than 24h stale (visible in the header)
- ✅ `tick_log` in D1 has a fresh `ok` row every morning
