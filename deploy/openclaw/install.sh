#!/usr/bin/env bash
# Provision an openclaw box for monkey-vs-machine.
#
# Run as root: `sudo bash deploy/openclaw/install.sh`
#
# Idempotent — re-running won't break an existing install.
set -euo pipefail

INSTALL_ROOT="/opt/mvm"
SECRETS_DIR="/etc/openclaw"
LOG_DIR="/var/log/mvm"
USER_NAME="mvm"
SYSTEMD_DIR="/etc/systemd/system"
REPO_DIR="$(cd "$(dirname "$0")/../.." && pwd)"

[ "$EUID" -ne 0 ] && { echo "ERROR: run as root"; exit 1; }

# === Dependency precheck =====================================================
# Fail loud BEFORE touching the filesystem or installing anything. Tells the
# operator exactly which apt package to install for the bits we need.

PYTHON_BIN="${PYTHON_BIN:-python3}"
MIN_PYTHON_MAJOR=3
MIN_PYTHON_MINOR=11

missing=()
hints=()

require_cmd() {
    local cmd="$1" pkg_hint="$2"
    if ! command -v "$cmd" >/dev/null 2>&1; then
        missing+=("$cmd")
        hints+=("$pkg_hint")
    fi
}

require_python_module() {
    local mod="$1" pkg_hint="$2"
    if ! "$PYTHON_BIN" -c "import $mod" >/dev/null 2>&1; then
        missing+=("python3:$mod")
        hints+=("$pkg_hint")
    fi
}

echo "Checking dependencies..."

require_cmd "$PYTHON_BIN" "python3 (>=${MIN_PYTHON_MAJOR}.${MIN_PYTHON_MINOR}) — apt install python3"
require_cmd rsync         "rsync — apt install rsync"
require_cmd systemctl     "systemctl — install systemd"
require_cmd journalctl    "journalctl — install systemd"
require_cmd logger        "logger — apt install bsdutils"
require_cmd useradd       "useradd — apt install passwd"
require_cmd install       "install — apt install coreutils"
require_cmd sudo          "sudo — apt install sudo"

# Python module checks (only meaningful if python3 itself is present)
if command -v "$PYTHON_BIN" >/dev/null 2>&1; then
    # `venv` is its own apt package on Debian/Ubuntu
    require_python_module venv     "python3-venv — apt install python3-venv"
    # `ensurepip` proves pip will work inside the venv
    require_python_module ensurepip "python3-pip — apt install python3-pip python3-venv"

    PY_VER=$("$PYTHON_BIN" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
    PY_OK=$("$PYTHON_BIN" -c "import sys; print(1 if sys.version_info >= (${MIN_PYTHON_MAJOR},${MIN_PYTHON_MINOR}) else 0)")
    if [ "$PY_OK" != "1" ]; then
        missing+=("python3>=${MIN_PYTHON_MAJOR}.${MIN_PYTHON_MINOR} (found ${PY_VER})")
        hints+=("Upgrade Python (e.g. via deadsnakes PPA or distro python3.11)")
    fi
fi

# tzdata is needed by both Python's zoneinfo (US/Eastern lookup in run_tick)
# and systemd timer's Timezone=Australia/Sydney.
if [ ! -d /usr/share/zoneinfo ] || [ ! -f /usr/share/zoneinfo/Australia/Sydney ]; then
    missing+=("tzdata")
    hints+=("tzdata — apt install tzdata")
fi

# logrotate is wired up by install.sh below; without it the rotate config is silently ignored.
require_cmd logrotate "logrotate — apt install logrotate"

if [ ${#missing[@]} -gt 0 ]; then
    echo ""
    echo "ERROR: missing dependencies. Install the packages below and re-run install.sh."
    for i in "${!missing[@]}"; do
        printf "  - %-40s  %s\n" "${missing[$i]}" "${hints[$i]}"
    done
    echo ""
    echo "Common one-liner (Debian/Ubuntu):"
    echo "  sudo apt update && sudo apt install -y python3 python3-venv python3-pip rsync sudo logrotate tzdata"
    exit 2
fi

echo "  all dependencies present (python ${PY_VER:-?})"
echo ""

if ! id "${USER_NAME}" &>/dev/null; then
  useradd --system --home-dir "${INSTALL_ROOT}" --shell /usr/sbin/nologin "${USER_NAME}"
fi

mkdir -p "${INSTALL_ROOT}" "${SECRETS_DIR}" "${LOG_DIR}"
chown -R "${USER_NAME}:${USER_NAME}" "${INSTALL_ROOT}" "${LOG_DIR}"
chmod 0700 "${SECRETS_DIR}"

# rsync code into place (skip data + venv)
rsync -a --delete \
  --exclude "data/" \
  --exclude ".venv/" \
  --exclude "__pycache__/" \
  --exclude ".pytest_cache/" \
  --exclude "dashboard/node_modules/" \
  --exclude ".omc/" \
  "${REPO_DIR}/" "${INSTALL_ROOT}/"
chown -R "${USER_NAME}:${USER_NAME}" "${INSTALL_ROOT}"

# Python venv
if [ ! -d "${INSTALL_ROOT}/.venv" ]; then
  sudo -u "${USER_NAME}" python3 -m venv "${INSTALL_ROOT}/.venv"
fi
sudo -u "${USER_NAME}" "${INSTALL_ROOT}/.venv/bin/pip" install --upgrade pip
sudo -u "${USER_NAME}" "${INSTALL_ROOT}/.venv/bin/pip" install -r "${INSTALL_ROOT}/requirements.txt"

# Secrets
if [ ! -f "${SECRETS_DIR}/secrets.env" ]; then
  echo "Creating ${SECRETS_DIR}/secrets.env — fill in PAGES_URL + MVM_INGEST_TOKEN."
  cat > "${SECRETS_DIR}/secrets.env" <<EOF
# /etc/openclaw/secrets.env — keep mode 0600
PAGES_URL=https://mvm-dashboard.pages.dev
MVM_INGEST_TOKEN=REPLACE_ME
EOF
  chmod 0600 "${SECRETS_DIR}/secrets.env"
  chown root:"${USER_NAME}" "${SECRETS_DIR}/secrets.env"
fi

# systemd
install -m 0644 "${REPO_DIR}/deploy/openclaw/mvm-tick.service" "${SYSTEMD_DIR}/mvm-tick.service"
install -m 0644 "${REPO_DIR}/deploy/openclaw/mvm-tick.timer" "${SYSTEMD_DIR}/mvm-tick.timer"
install -m 0644 "${REPO_DIR}/deploy/openclaw/mvm-tick-alert.service" "${SYSTEMD_DIR}/mvm-tick-alert.service"
install -m 0644 "${REPO_DIR}/deploy/openclaw/mvm-backup.service" "${SYSTEMD_DIR}/mvm-backup.service"
install -m 0644 "${REPO_DIR}/deploy/openclaw/mvm-backup.timer" "${SYSTEMD_DIR}/mvm-backup.timer"
systemctl daemon-reload
systemctl enable --now mvm-tick.timer

# Backup env file stub. The backup timer stays disabled until BACKUP_TARGET is filled in.
if [ ! -f "${SECRETS_DIR}/backup.env" ]; then
  cat > "${SECRETS_DIR}/backup.env" <<'EOF'
# /etc/openclaw/backup.env — mode 0600
# Set BACKUP_TARGET to a writable rsync target (local NAS mount or SSH path)
# then enable the backup timer:
#   sudo systemctl enable --now mvm-backup.timer
# Examples:
#   BACKUP_TARGET=/mnt/nas/mvm-backups
#   BACKUP_TARGET=backup-host:/srv/mvm-backups
BACKUP_TARGET=
EOF
  chmod 0600 "${SECRETS_DIR}/backup.env"
  chown root:"${USER_NAME}" "${SECRETS_DIR}/backup.env"
fi

# Log rotation
cat > /etc/logrotate.d/mvm <<'EOF'
/var/log/mvm/*.log {
    weekly
    rotate 12
    compress
    delaycompress
    missingok
    notifempty
    copytruncate
}
EOF

echo ""
echo "Install complete."
echo "  - State db will live at ${INSTALL_ROOT}/data/state.db (run bootstrap_genesis.py once)"
echo "  - Edit ${SECRETS_DIR}/secrets.env to fill in the real D1 ingest token"
echo "  - Timer status: systemctl status mvm-tick.timer"
