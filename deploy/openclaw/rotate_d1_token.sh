#!/usr/bin/env bash
# Rotate the D1 ingest token. Updates /etc/openclaw/secrets.env in place,
# restarts the timer, and sends one test ingest with the new token.
set -euo pipefail

SECRETS="/etc/openclaw/secrets.env"
[ "$EUID" -ne 0 ] && { echo "ERROR: run as root"; exit 1; }
[ ! -f "$SECRETS" ] && { echo "ERROR: $SECRETS missing — run install.sh first"; exit 1; }

read -rsp "New MVM_INGEST_TOKEN (input hidden): " new_token
echo
[ -z "$new_token" ] && { echo "ERROR: empty token"; exit 1; }

cp "$SECRETS" "$SECRETS.bak.$(date -u +%s)"
sed -i.bak "s|^MVM_INGEST_TOKEN=.*|MVM_INGEST_TOKEN=${new_token}|" "$SECRETS"

systemctl restart mvm-tick.timer

echo "Sending a test ingest..."
sudo -u mvm /opt/mvm/.venv/bin/python /opt/mvm/scripts/push_to_d1.py \
    --date "$(date -u +%Y-%m-%d)" || {
  echo "Test ingest failed — token may be wrong. Backup is at ${SECRETS}.bak.*"
  exit 1
}

echo "Token rotation OK."
