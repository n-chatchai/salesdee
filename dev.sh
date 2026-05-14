#!/usr/bin/env bash
# Local dev runner: Django runserver (auto-reload) + django-q2 qcluster + caddy TLS proxy.
# Stops everything on Ctrl-C.
#
# Pre-reqs (one-time):
#   /etc/hosts:   127.0.0.1 salesdee.local wandeedee.salesdee.local
#   mkcert -install
#   mkdir -p certs && (cd certs && mkcert salesdee.local '*.salesdee.local')
#   brew install caddy
#
# Then:  ./dev.sh

set -euo pipefail
cd "$(dirname "$0")"

# ── pre-flight ──────────────────────────────────────────────────────────────
command -v uv >/dev/null || { echo "uv not found"; exit 1; }
command -v caddy >/dev/null || { echo "caddy not found — brew install caddy"; exit 1; }
[ -f certs/salesdee.local+1.pem ] || {
	echo "TLS cert missing — generate it:"
	echo "  mkcert -install"
	echo "  mkdir -p certs && (cd certs && mkcert salesdee.local '*.salesdee.local')"
	exit 1
}
grep -q '^127\.0\.0\.1[[:space:]].*salesdee\.local' /etc/hosts || {
	echo "/etc/hosts entry missing — run:"
	echo "  sudo sh -c 'printf \"\\n127.0.0.1 salesdee.local wandeedee.salesdee.local\\n\" >> /etc/hosts'"
	exit 1
}

# ── cleanup ─────────────────────────────────────────────────────────────────
pids=()
cleanup() {
	echo
	echo "→ stopping (${pids[*]})"
	for pid in "${pids[@]}"; do
		kill "$pid" 2>/dev/null || true
	done
	wait 2>/dev/null || true
	exit 0
}
trap cleanup INT TERM

# ── run ─────────────────────────────────────────────────────────────────────
mkdir -p .dev-logs

echo "→ Django runserver  http://127.0.0.1:8000     log: .dev-logs/web.log"
uv run python manage.py runserver 127.0.0.1:8000 >.dev-logs/web.log 2>&1 &
pids+=($!)

echo "→ django-q2 qcluster                          log: .dev-logs/worker.log"
uv run python manage.py qcluster >.dev-logs/worker.log 2>&1 &
pids+=($!)

echo "→ caddy TLS proxy   https://salesdee.local    log: .dev-logs/caddy.log"
caddy run --config Caddyfile >.dev-logs/caddy.log 2>&1 &
pids+=($!)

echo
echo "──────────────────────────────────────────────────────"
echo "  https://salesdee.local              (platform host)"
echo "  https://wandeedee.salesdee.local    (tenant)"
echo "  login: admin@salesdee.local / salesdee-dev"
echo "──────────────────────────────────────────────────────"
echo "  Ctrl-C to stop everything"
echo

# follow logs interleaved
tail -F .dev-logs/web.log .dev-logs/worker.log .dev-logs/caddy.log
