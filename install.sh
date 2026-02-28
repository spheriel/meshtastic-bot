#!/usr/bin/env bash
set -euo pipefail

# Meshtastic Channel Utility Bot installer (user-level systemd service)
# - Creates a Python venv inside the repo
# - Installs dependencies
# - Creates a systemd *user* service for the current user
# - Enables + starts the service

RED="\033[0;31m"
GRN="\033[0;32m"
YLW="\033[0;33m"
NC="\033[0m"

info()  { echo -e "${GRN}[INFO]${NC} $*"; }
warn()  { echo -e "${YLW}[WARN]${NC} $*"; }
error() { echo -e "${RED}[ERR ]${NC} $*"; }

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || { error "Missing required command: $1"; exit 1; }
}

need_cmd python3
need_cmd systemctl

# Resolve repo root (works both when executed from anywhere and when called via path)
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$SCRIPT_DIR"

# If inside a git repo, prefer the top-level
if command -v git >/dev/null 2>&1; then
  if git -C "$SCRIPT_DIR" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    REPO_ROOT="$(git -C "$SCRIPT_DIR" rev-parse --show-toplevel)"
  fi
fi

BOT_PY="$REPO_ROOT/meshtastic_bot.py"
CFG_TOML="$REPO_ROOT/config.toml"
VENV_DIR="$REPO_ROOT/venv"
PY="$VENV_DIR/bin/python"
PIP="$VENV_DIR/bin/pip"

if [[ ! -f "$BOT_PY" ]]; then
  error "Cannot find $BOT_PY"
  exit 1
fi

if [[ ! -f "$CFG_TOML" ]]; then
  error "Cannot find $CFG_TOML"
  exit 1
fi

# Ensure systemd user session is available
if ! systemctl --user show-environment >/dev/null 2>&1; then
  warn "systemd user instance is not available in this shell/session."
  warn "If you're running over SSH, try enabling lingering or logging in with a full user session."
  warn "Continuing anyway; service creation will still happen."
fi

info "Repository root: $REPO_ROOT"
info "Creating/using venv: $VENV_DIR"

if [[ ! -d "$VENV_DIR" ]]; then
  python3 -m venv "$VENV_DIR"
fi

# Upgrade pip & install deps
info "Installing Python dependencies..."
"$PY" -m pip install --upgrade pip >/dev/null
# Minimal dependency set for this bot
"$PIP" install --upgrade meshtastic requests PyPubSub >/dev/null

# Create systemd user service
SERVICE_DIR="$HOME/.config/systemd/user"
SERVICE_NAME="meshtastic-bot.service"
SERVICE_PATH="$SERVICE_DIR/$SERVICE_NAME"

mkdir -p "$SERVICE_DIR"

info "Writing systemd user service: $SERVICE_PATH"

cat > "$SERVICE_PATH" <<EOF
[Unit]
Description=Meshtastic utility bot (user service)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=$REPO_ROOT
ExecStart=$PY $BOT_PY -c $CFG_TOML
Restart=always
RestartSec=5

# Optional hardening (safe defaults for a bot)
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=default.target
EOF

# Reload systemd user config, enable and start
info "Reloading systemd user daemon..."
systemctl --user daemon-reload

info "Enabling service for autostart..."
systemctl --user enable "$SERVICE_NAME" >/dev/null

info "Starting service..."
systemctl --user restart "$SERVICE_NAME"

info "Service status:"
systemctl --user --no-pager status "$SERVICE_NAME" || true

echo
info "Done!"
echo "To view logs:"
echo "  journalctl --user -u $SERVICE_NAME -f"
echo
echo "To stop/disable:"
echo "  systemctl --user stop $SERVICE_NAME"
echo "  systemctl --user disable $SERVICE_NAME"
echo
echo "Boot autostart notes:"
echo "- User services start at boot only if your user session is started."
echo "- For true 'start at boot even when not logged in', enable lingering:"
echo "    sudo loginctl enable-linger $USER"
sudo loginctl enable-linger $USER
echo "lingering enabled"
