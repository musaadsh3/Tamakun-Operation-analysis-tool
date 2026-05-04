#!/bin/bash
# Pull the latest origin/main into /opt/tamakun-saas and restart the
# systemd service. Idempotent: safe to run repeatedly. Exits non-zero
# if any step fails so it can be wrapped in CI later.
#
# Usage (run as root or via sudo on the deploy host):
#   sudo bash /opt/tamakun-saas/deploy/pull-and-restart.sh
#
# Or, since cron etc. may not have a TTY:
#   sudo /opt/tamakun-saas/deploy/pull-and-restart.sh

set -euo pipefail

APP_DIR="/opt/tamakun-saas"
APP_USER="tamakunsaas"
SERVICE="tamakun-saas.service"
DOMAIN="operation.tamakun.sa"
ORIGIN_IP="${ORIGIN_IP:-37.27.130.230}"

if [ "$(id -u)" -ne 0 ]; then
    echo "ERROR: must run as root (use sudo)" >&2
    exit 1
fi

echo "==> Fetching from origin"
sudo -u "$APP_USER" git -C "$APP_DIR" fetch --quiet origin main

LOCAL=$(sudo -u "$APP_USER" git -C "$APP_DIR" rev-parse HEAD)
REMOTE=$(sudo -u "$APP_USER" git -C "$APP_DIR" rev-parse origin/main)

if [ "$LOCAL" = "$REMOTE" ]; then
    echo "==> Already at $REMOTE — nothing to deploy."
    systemctl is-active "$SERVICE" >/dev/null && echo "==> Service active." || systemctl restart "$SERVICE"
    exit 0
fi

echo "==> Local  : $LOCAL"
echo "==> Remote : $REMOTE"
echo "==> Incoming commits:"
sudo -u "$APP_USER" git -C "$APP_DIR" log --oneline "${LOCAL}..${REMOTE}" | sed 's/^/      /'

echo "==> Checking out origin/main"
sudo -u "$APP_USER" git -C "$APP_DIR" reset --hard origin/main

# If requirements changed, refresh the venv.
if sudo -u "$APP_USER" git -C "$APP_DIR" diff --name-only "${LOCAL}" "${REMOTE}" \
        | grep -qE '^requirements(-cpanel)?\.txt$'; then
    echo "==> requirements changed; reinstalling deps"
    sudo -u "$APP_USER" "$APP_DIR/venv/bin/pip" install --quiet --upgrade pip wheel
    sudo -u "$APP_USER" "$APP_DIR/venv/bin/pip" install --quiet -r "$APP_DIR/requirements-cpanel.txt" 'gunicorn==23.0.0'
fi

# Run init_db so any new SQLAlchemy tables are created. create_all() is
# idempotent for existing tables but DOES NOT alter columns — schema
# changes beyond add-table still need manual SQL or Alembic.
echo "==> Running init_db (idempotent)"
sudo -u "$APP_USER" bash -c "
  cd '$APP_DIR'
  '$APP_DIR/venv/bin/python' -c '
from dotenv import load_dotenv; load_dotenv(\"$APP_DIR/.env\")
from app.database import init_db
init_db()
print(\"  init_db OK\")
'
"

echo "==> Restarting $SERVICE"
systemctl restart "$SERVICE"
sleep 3

if ! systemctl is-active --quiet "$SERVICE"; then
    echo "ERROR: $SERVICE did not become active" >&2
    journalctl -u "$SERVICE" -n 50 --no-pager >&2
    exit 1
fi

echo "==> Smoke test"
HTTP=$(curl -sk --max-time 10 --resolve "$DOMAIN:443:$ORIGIN_IP" "https://$DOMAIN/" -o /dev/null -w "%{http_code}")
if [ "$HTTP" != "200" ]; then
    echo "ERROR: smoke test failed: GET / returned $HTTP" >&2
    journalctl -u "$SERVICE" -n 30 --no-pager >&2
    exit 1
fi

echo "==> OK. Now at $(sudo -u "$APP_USER" git -C "$APP_DIR" rev-parse --short HEAD)"
