# openclaw provisioning

The "openclaw" box is whatever dedicated Linux host owns the SQLite source of
truth and runs the daily tick. v1 assumes a single box; multi-box HA is a
future concern.

## Requirements
- Linux with systemd (Debian/Ubuntu/Arch all fine)
- Python **3.11+** available as `python3`
- `python3-venv`, `python3-pip` (Debian/Ubuntu split these out of the base package)
- `rsync`, `sudo`, `logrotate`, `tzdata`, `logger` (bsdutils), `journalctl` (systemd)
- Outbound HTTPS to `query1.finance.yahoo.com`, `query2.finance.yahoo.com`, and your Cloudflare Pages domain

`install.sh` runs a dependency precheck before touching anything and tells you
exactly which apt packages to install if any are missing. Suggested one-liner:

```bash
sudo apt update && sudo apt install -y python3 python3-venv python3-pip rsync sudo logrotate tzdata
```

## First-time setup

```bash
git clone <repo> ~/monkey-vs-machine
cd ~/monkey-vs-machine
sudo bash deploy/openclaw/install.sh    # precheck → user + venv + units + logrotate
sudo nano /etc/openclaw/secrets.env     # fill in PAGES_URL + MVM_INGEST_TOKEN
sudo -u mvm /opt/mvm/.venv/bin/python /opt/mvm/scripts/bootstrap_genesis.py --start-date $(date -u +%Y-%m-%d)
```

## Verify
```bash
systemctl status mvm-tick.timer
sudo journalctl -t mvm-alert -n 20
sudo tail -f /var/log/mvm/tick.log
```

## Run a tick manually
```bash
sudo -u mvm /opt/mvm/.venv/bin/python /opt/mvm/scripts/run_tick.py --date 2026-05-19
sudo -u mvm /opt/mvm/.venv/bin/python /opt/mvm/scripts/push_to_d1.py --date 2026-05-19
```

## Catch up after a multi-day outage
```bash
sudo -u mvm /opt/mvm/.venv/bin/python /opt/mvm/scripts/catchup.py --since 2026-05-12
```

## Rotate the D1 ingest token
```bash
sudo bash deploy/openclaw/rotate_d1_token.sh
```

## SQLite backup (recommended before going durable)

`install.sh` installs `mvm-backup.{service,timer}` but leaves the timer
**disabled** until you configure a backup target. The timer fires
daily at 03:00 (Australia/Sydney) and rsyncs `state.db` to wherever you
point it, keeping `state.db.<UTC-timestamp>` versioned copies plus a
`state.db.latest` pointer.

1. **Set the backup target** in `/etc/openclaw/backup.env`:

   ```bash
   sudo nano /etc/openclaw/backup.env
   # BACKUP_TARGET=/mnt/nas/mvm-backups     (local mount)
   # BACKUP_TARGET=backup-host:/srv/mvm     (SSH; ensure mvm@ has key auth)
   ```

2. **Enable the timer:**
   ```bash
   sudo systemctl enable --now mvm-backup.timer
   sudo systemctl list-timers mvm-backup.timer
   ```

3. **Verify:** wait a day, then check `/var/log/mvm/backup.log` and confirm
   `state.db.<timestamp>` files appear at the target.

Without this, a single-drive failure on openclaw permanently loses the
SQLite source of truth. The D1 publish surface omits the 100k×daily monkey
detail, so it can rebuild D1 from SQLite but not the reverse.

## Firewall

Inbound: nothing.
Outbound HTTPS (TCP/443) to:
- `query1.finance.yahoo.com`
- `query2.finance.yahoo.com`
- `*.pages.dev` (or your custom Pages domain)

Everything else can be denied.
