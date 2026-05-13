#!/usr/bin/env bash
# salesdee — pull, migrate, collectstatic, refresh schedules, restart systemd, Slack ping.
#
# Runs on the prod box (driven by .github/workflows/deploy.yml over SSH, or by hand).
#
# Env (set in /home/deploy/salesdee/.env):
#   SECRET_KEY, DATABASE_URL, RLS_ENABLED, ALLOWED_HOSTS, REDIS_URL, EMAIL_URL, etc.
#   DATABASE_URL_OWNER         postgres://salesdee_owner:…@…/salesdee — used for `migrate`
#                              (the runtime DATABASE_URL is the app role, which can't ALTER tables)
#   SLACK_DEPLOY_WEBHOOK_URL   optional — silent if unset
#   PROD_URL                   default https://salesdee.com — base for the post-deploy probe
#
# Tunables (override on the command line):
#   WEB_SERVICE                default: salesdee-web
#   QCLUSTER_SERVICE           default: salesdee-qcluster
#   UV_BIN                     default: $HOME/.local/bin/uv
#   SLACK_USERNAME             default: salesdee-deploy
#
# Exit codes: 0 success; non-zero phase-tagged failure (the trap notifies Slack with the phase).

set -euo pipefail

WEB_SERVICE="${WEB_SERVICE:-salesdee-web}"
QCLUSTER_SERVICE="${QCLUSTER_SERVICE:-salesdee-qcluster}"
SLACK_USERNAME="${SLACK_USERNAME:-salesdee-deploy}"
UV_BIN="${UV_BIN:-$HOME/.local/bin/uv}"
PROD_URL="${PROD_URL:-https://salesdee.com}"
START_TS="$(date +%s)"
PHASE="setup"

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_ROOT"

# Pull SLACK_DEPLOY_WEBHOOK_URL + DATABASE_URL_OWNER out of .env if not already set.
# Tolerates `export ` prefix and quoted values.
load_env_var() {
  local name="$1"
  if [ -z "${!name:-}" ] && [ -f .env ]; then
    local v
    v=$(grep -E "^(export[[:space:]]+)?${name}=" .env | head -1 \
        | sed -E "s/^(export[[:space:]]+)?${name}=//" | tr -d '"' | tr -d "'")
    [ -n "$v" ] && export "$name=$v"
  fi
}
load_env_var SLACK_DEPLOY_WEBHOOK_URL
load_env_var DATABASE_URL_OWNER

if [ -n "${SLACK_DEPLOY_WEBHOOK_URL:-}" ]; then
  echo "[deploy] Slack notify: enabled"
else
  echo "[deploy] Slack notify: disabled (set SLACK_DEPLOY_WEBHOOK_URL in .env)"
fi

# ─── Slack helper ────────────────────────────────────────────────────────
post_slack() {
  local emoji="$1" text="$2"
  [ -z "${SLACK_DEPLOY_WEBHOOK_URL:-}" ] && return 0
  local payload
  payload=$(python3 -c '
import json, sys
print(json.dumps({"username": sys.argv[1], "icon_emoji": sys.argv[2], "text": sys.argv[3]}))' \
    "$SLACK_USERNAME" "$emoji" "$text")
  curl -fsS -X POST -H 'Content-Type: application/json' \
    --data "$payload" "$SLACK_DEPLOY_WEBHOOK_URL" > /dev/null || true
}

on_error() {
  local code=$?
  local elapsed=$(( $(date +%s) - START_TS ))
  local sha
  sha=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")
  post_slack ":x:" "❌ Deploy failed at *${PHASE}* (exit ${code}) · \`${sha}\` · ${elapsed}s"
  exit "$code"
}
trap on_error ERR

echo "Deploying in $PROJECT_ROOT..."

# ─── Phases ──────────────────────────────────────────────────────────────
PHASE="git pull"
git pull --ff-only

PHASE="uv sync"
"$UV_BIN" sync --frozen

PHASE="migrate"
# Migrations run as the Postgres OWNER role (only role with DDL on the schema).
# The runtime app connects as a non-owner role so RLS isn't bypassed.
if [ -z "${DATABASE_URL_OWNER:-}" ]; then
  echo "DATABASE_URL_OWNER not set (need it for migrations — owner role)." >&2
  exit 1
fi
DATABASE_URL="$DATABASE_URL_OWNER" "$UV_BIN" run python manage.py migrate --noinput

PHASE="collectstatic"
"$UV_BIN" run python manage.py collectstatic --noinput

PHASE="setup_q_schedules"
# Idempotent — keeps django_q.Schedule rows in sync with code (see apps/core/management/commands/setup_q_schedules.py).
"$UV_BIN" run python manage.py setup_q_schedules

PHASE="systemctl restart ${WEB_SERVICE}"
sudo systemctl restart "${WEB_SERVICE}"

# Restart the qcluster too — it loads task code at startup, so without this restart it keeps
# running the previous deploy's code. Skip silently when the unit isn't installed yet.
if systemctl list-unit-files | grep -q "^${QCLUSTER_SERVICE}\.service"; then
  PHASE="systemctl restart ${QCLUSTER_SERVICE}"
  sudo systemctl restart "${QCLUSTER_SERVICE}"
else
  echo "[deploy] ${QCLUSTER_SERVICE}.service not installed — skipping worker restart"
fi

PHASE="check --deploy"
"$UV_BIN" run python manage.py check --deploy

# ─── Verify the live process is up ───────────────────────────────────────
# /healthz/ should return 200 OK (add a view if it doesn't exist yet — see VPS_DEPLOYMENT.md §15).
# If salesdee gains a /version endpoint later, swap this for a SHA comparison like the original.
SHA=$(git rev-parse --short HEAD)
SUBJECT=$(git log -1 --pretty=%s)

LIVE_OK="no"
for _ in {1..10}; do
  if curl -fsS --max-time 2 "${PROD_URL}/healthz/" > /dev/null 2>&1; then
    LIVE_OK="yes"; break
  fi
  sleep 1
done

ELAPSED=$(( $(date +%s) - START_TS ))
if [ "$LIVE_OK" = "yes" ]; then
  echo "✅ Deployed ${SHA} (${ELAPSED}s) — /healthz/ 200"
  post_slack ":white_check_mark:" "✅ Deployed \`${SHA}\` · ${SUBJECT} · ${ELAPSED}s"
else
  echo "⚠️  Deployed ${SHA} but /healthz/ never returned 200 (${ELAPSED}s)"
  post_slack ":warning:" "⚠️ Deployed \`${SHA}\` · ${SUBJECT} · ${ELAPSED}s · /healthz/ not responding"
fi
