# VPS deployment — salesdee.

End-to-end recipe to deploy salesdee on a single Linux VPS (Debian 12 / Ubuntu 24.04 LTS) with **Cloudflare in front + Nginx on the box + systemd for processes**. Targets the Phase-1/1.5 codebase as of this writing. One web process + one tasks worker + Postgres + Redis. No Docker (smallest moving parts; containerise later).

> Keep this file in sync with `config/settings/base.py` / `prod.py` and the systemd units below.

---

## 0. Topology

```
client ──HTTPS──▶ Cloudflare (edge: TLS, WAF, CDN, DDoS)
                       │
                       ▼ HTTPS (Full Strict, origin cert)
                  Nginx on the VPS (host routing, gzip, static/media, X-Forwarded-*)
                       │ Unix socket
                       ▼
                  gunicorn (config.wsgi)
                       │
                       ▼
                  Postgres 16 + Redis (localhost)
```

- Cloudflare is the public IP your DNS points at. The VPS origin is only reachable via Cloudflare (lock it down — see §10).
- Each tenant uses `<slug>.salesdee.app` (a wildcard you proxy through Cloudflare) **or** their own domain mapped via **Cloudflare for SaaS / Custom Hostnames** — that's the production-grade equivalent of on-demand TLS. The Django middleware (`apps/core/middleware.py::CurrentTenantMiddleware`) resolves the tenant from the `Host` header regardless of which it is.

```
# DNS at Cloudflare — proxied (orange-cloud):
salesdee.app.            A     <origin-ip>   ; proxied
*.salesdee.app.          A     <origin-ip>   ; proxied
```
Tenant custom domains: they add a `CNAME tenant.example.com → tenant.example.com.cdn.cloudflare.net.` (the exact target depends on your Cloudflare for SaaS config). Issuing the edge cert + validating ownership happens at Cloudflare; the origin doesn't care.

---

## 1. Pick a VPS

- **2 vCPU · 4 GB RAM · 40 GB SSD** floor (Postgres + Redis + gunicorn + WeasyPrint + one anchor tenant's LINE traffic). Bangkok region (Vultr / DigitalOcean / Linode SGP / AIS / TRUE IDC) for Thai-side latency.
- Public IPv4 + IPv6. Cloudflare reaches your IPv4 only by default — that's fine.

---

## 2. Server prep

```bash
# Fresh root login → make a deploy user, lock root SSH.
adduser deploy
usermod -aG sudo deploy
rsync --archive --chown=deploy:deploy ~/.ssh /home/deploy
# /etc/ssh/sshd_config: PermitRootLogin no, PasswordAuthentication no
systemctl reload ssh

# Basics
apt update && apt -y upgrade
apt -y install build-essential git ufw curl ca-certificates \
                pkg-config libssl-dev zlib1g-dev libffi-dev \
                postgresql postgresql-contrib redis-server \
                nginx \
                # WeasyPrint runtime
                libpango-1.0-0 libpangoft2-1.0-0 libcairo2 libgdk-pixbuf-2.0-0 \
                shared-mime-info \
                # Thai fonts (also bundled in static/fonts/ — Sarabun)
                fonts-thai-tlwg

# uv (Python toolchain) — install as the deploy user
sudo -u deploy bash -c 'curl -LsSf https://astral.sh/uv/install.sh | sh'
```

### Firewall — only Cloudflare IPs may hit 443/80

```bash
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp                       # SSH (or restrict to your office IP)
# Cloudflare IPv4 + IPv6 ranges (refresh quarterly):
#   https://www.cloudflare.com/ips-v4
#   https://www.cloudflare.com/ips-v6
for net in $(curl -fsSL https://www.cloudflare.com/ips-v4); do ufw allow from "$net" to any port 443 proto tcp; done
for net in $(curl -fsSL https://www.cloudflare.com/ips-v6); do ufw allow from "$net" to any port 443 proto tcp; done
ufw --force enable
```

(Keep a small cron job to refresh those rules. Or use `nft` sets — same idea.)

---

## 3. Postgres — owner role and a separate app role

salesdee uses Row-Level Security as a tenant-isolation backstop (CLAUDE.md §5). **RLS is bypassed by the table owner and superusers** — the app must connect as a *non-owner, non-superuser* role.

```bash
sudo -u postgres psql <<'SQL'
CREATE ROLE salesdee_owner LOGIN PASSWORD 'change-me-owner';
CREATE ROLE salesdee_app   LOGIN PASSWORD 'change-me-app';
CREATE DATABASE salesdee OWNER salesdee_owner ENCODING 'UTF8' LC_COLLATE 'th_TH.UTF-8' LC_CTYPE 'th_TH.UTF-8' TEMPLATE template0;

GRANT CONNECT ON DATABASE salesdee TO salesdee_app;
\c salesdee
GRANT USAGE ON SCHEMA public TO salesdee_app;
ALTER DEFAULT PRIVILEGES FOR ROLE salesdee_owner IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO salesdee_app;
ALTER DEFAULT PRIVILEGES FOR ROLE salesdee_owner IN SCHEMA public
  GRANT USAGE, SELECT ON SEQUENCES TO salesdee_app;
SQL
```

(`apt -y install language-pack-th && locale-gen th_TH.UTF-8` first if the locale isn't built.)

Migrations run as `salesdee_owner`. The app runs as `salesdee_app`.

---

## 4. Redis

Default install. Bind to `127.0.0.1` (already does). `/etc/redis/redis.conf`:
```
maxmemory 128mb
maxmemory-policy allkeys-lru
```
`systemctl restart redis-server`.

---

## 5. Clone

```bash
sudo -iu deploy
git clone <YOUR_REMOTE> ~/salesdee
cd ~/salesdee
git checkout main           # or a vetted tag
uv sync --frozen
```

---

## 6. `.env` (production) — `/home/deploy/salesdee/.env`, mode 600

```dotenv
DJANGO_SETTINGS_MODULE=config.settings.prod

SECRET_KEY=__paste 64 random bytes from secrets.token_urlsafe(64)__
DEBUG=False
ALLOWED_HOSTS=*              # see "host gating" below
APP_DOMAIN=salesdee.app

# Postgres — APP role (not owner)
DATABASE_URL=postgres://salesdee_app:change-me-app@127.0.0.1:5432/salesdee
RLS_ENABLED=True

# Redis
REDIS_URL=redis://127.0.0.1:6379/0

# Email — SMTP relay (Postmark / SES / Sendgrid / Mailgun)
EMAIL_URL=submission+tls://user:pass@smtp.example.com:587
DEFAULT_FROM_EMAIL=salesdee. <no-reply@salesdee.app>

# Optional AI
ANTHROPIC_API_KEY=
ANTHROPIC_MODEL=claude-sonnet-4-6

# Sentry (optional)
SENTRY_DSN=

# Behind Cloudflare + Nginx: trust X-Forwarded-Proto so request.is_secure() is correct.
# Django reads SECURE_PROXY_SSL_HEADER from settings; the prod settings should already
# set ("HTTP_X_FORWARDED_PROTO", "https").
USE_X_FORWARDED_HOST=True

# Local media for now; swap to S3/R2 via django-storages later
MEDIA_ROOT=/home/deploy/salesdee/media
```

**Host gating.** `config/settings/prod.py` requires `SECRET_KEY` + `ALLOWED_HOSTS`. With custom tenant domains a fixed `ALLOWED_HOSTS` doesn't scale — set `ALLOWED_HOSTS=*` and rely on `CurrentTenantMiddleware` to 403 hosts that aren't a known platform host or a verified `TenantDomain` (CLAUDE.md §5). That's the explicit, supported route.

---

## 7. First-time deploy

```bash
cd ~/salesdee
set -a; source .env; set +a

# Migrate AS THE OWNER (owner-only DDL).
DATABASE_URL=postgres://salesdee_owner:change-me-owner@127.0.0.1:5432/salesdee \
  uv run python manage.py migrate

uv run python manage.py collectstatic --noinput
uv run python manage.py createsuperuser
uv run python manage.py check --deploy
```

`check --deploy` should be quiet once Nginx is in front (only HSTS preload nags are acceptable until you commit to preloading the domain).

---

## 8. systemd

### Web — `/etc/systemd/system/salesdee-web.service`

```ini
[Unit]
Description=salesdee web (gunicorn)
After=network.target postgresql.service redis-server.service
Wants=postgresql.service redis-server.service

[Service]
User=deploy
Group=www-data
WorkingDirectory=/home/deploy/salesdee
EnvironmentFile=/home/deploy/salesdee/.env
ExecStart=/home/deploy/.local/bin/uv run gunicorn \
            --workers 3 --threads 2 --timeout 60 \
            --bind unix:/run/salesdee/web.sock --umask 007 \
            --access-logfile - --error-logfile - \
            --forwarded-allow-ips=127.0.0.1 \
            config.wsgi:application
RuntimeDirectory=salesdee
RuntimeDirectoryMode=0755
Restart=on-failure
RestartSec=3
NoNewPrivileges=yes
ProtectSystem=strict
ProtectHome=read-only
ReadWritePaths=/home/deploy/salesdee/media /home/deploy/salesdee/staticfiles /run/salesdee
PrivateTmp=yes

[Install]
WantedBy=multi-user.target
```

Group is `www-data` and umask `007` so Nginx (running as `www-data`) can read the socket.

### Tasks worker — `/etc/systemd/system/salesdee-tasks.service`

`TASKS` currently uses the **ImmediateBackend** (`config/settings/base.py`): every `.enqueue()` runs inline in the request. There is no separate worker yet — this unit is the slot for when you swap a real backend in (django-tasks PyPI's DatabaseBackend → `manage.py db_worker`, or Celery+Redis). Install it then; for now you can leave the file masked.

```ini
[Unit]
Description=salesdee background tasks worker
After=network.target postgresql.service redis-server.service salesdee-web.service
Wants=postgresql.service redis-server.service

[Service]
User=deploy
Group=www-data
WorkingDirectory=/home/deploy/salesdee
EnvironmentFile=/home/deploy/salesdee/.env
# Replace once a real backend is chosen:
#   uv run python manage.py db_worker            # django-tasks PyPI DatabaseBackend
#   uv run celery -A config worker -l info       # Celery
ExecStart=/home/deploy/.local/bin/uv run python manage.py db_worker
Restart=on-failure
RestartSec=3
NoNewPrivileges=yes
ProtectSystem=strict
ProtectHome=read-only
PrivateTmp=yes

[Install]
WantedBy=multi-user.target
```

Enable:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now salesdee-web
# sudo systemctl enable --now salesdee-tasks    # when a real backend is wired
systemctl status salesdee-web
```

---

## 9. Nginx — `/etc/nginx/sites-available/salesdee`

```nginx
upstream salesdee_web {
    server unix:/run/salesdee/web.sock fail_timeout=0;
}

# A tiny shared map: only allow the Host header onto the app if it's a platform host
# or a custom domain Django will recognise. The "Allow" decision is delegated to Django
# via an internal endpoint (see §10) — Nginx just passes everything through and Django
# rejects unknown hosts with 403 via CurrentTenantMiddleware.

server {
    listen 80 default_server;
    listen [::]:80 default_server;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name _;

    # Origin certificate from Cloudflare (15-year, only valid behind Cloudflare):
    ssl_certificate     /etc/ssl/cloudflare/salesdee.app.pem;
    ssl_certificate_key /etc/ssl/cloudflare/salesdee.app.key;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;

    # Cloudflare → Nginx — trust the Real IP header
    set_real_ip_from 173.245.48.0/20;   # …or `include /etc/nginx/cloudflare.conf;` if you generate one
    # (Generate /etc/nginx/cloudflare.conf from https://www.cloudflare.com/ips-v4 and -v6;
    #  refresh it with a cron job.)
    real_ip_header CF-Connecting-IP;
    real_ip_recursive on;

    client_max_body_size 25M;
    keepalive_timeout 65;

    gzip on;
    gzip_types text/plain text/css application/javascript application/json image/svg+xml;
    gzip_min_length 1024;

    # static + media — Nginx serves files directly, no gunicorn hop.
    location /static/ {
        alias /home/deploy/salesdee/staticfiles/;
        access_log off;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
    location /media/ {
        alias /home/deploy/salesdee/media/;
        access_log off;
        expires 7d;
    }

    # everything else → Django
    location / {
        proxy_pass http://salesdee_web;
        proxy_http_version 1.1;
        proxy_set_header Host                $host;
        proxy_set_header X-Real-IP           $remote_addr;
        proxy_set_header X-Forwarded-For     $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto   $scheme;
        proxy_set_header X-Forwarded-Host    $host;
        proxy_redirect off;
        proxy_read_timeout 60s;
        proxy_send_timeout 60s;
    }

    # LINE webhook — needs the raw body untouched (signature is HMAC-SHA256 over it).
    location /integrations/line/ {
        proxy_pass http://salesdee_web;
        proxy_http_version 1.1;
        proxy_request_buffering on;
        proxy_set_header Host                $host;
        proxy_set_header X-Real-IP           $remote_addr;
        proxy_set_header X-Forwarded-For     $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto   $scheme;
        proxy_set_header X-Line-Signature    $http_x_line_signature;
        client_max_body_size 5M;
    }

    # Healthcheck — Cloudflare and your uptime monitor hit this. Add a /healthz/ view that
    # does a single DB ping and returns 200.
    location = /healthz/ {
        proxy_pass http://salesdee_web;
        access_log off;
    }
}
```

Enable + reload:
```bash
sudo ln -s /etc/nginx/sites-available/salesdee /etc/nginx/sites-enabled/salesdee
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl reload nginx
```

**Cloudflare Origin Cert.** Cloudflare → SSL/TLS → Origin Server → Create Certificate (RSA, 15-year). Save `.pem` to `/etc/ssl/cloudflare/salesdee.app.pem` and `.key` to `/etc/ssl/cloudflare/salesdee.app.key` (mode 600 root:root). Set Cloudflare SSL/TLS mode to **Full (strict)** so Cloudflare verifies the origin cert.

---

## 10. Cloudflare — settings that matter

- **SSL/TLS**: `Full (strict)`. Force HTTPS (Edge Certificates → Always Use HTTPS). Min TLS 1.2.
- **DNS**: A/AAAA records proxied (orange cloud) — apex + wildcard.
- **HSTS**: enable once you're sure (max-age 31536000, includeSubdomains, preload). Then submit to https://hstspreload.org.
- **WAF managed rules**: Free tier is fine to start. Add a rate-limit rule on the LINE webhook path (`/integrations/line/*`) — though LINE's traffic is bursty, a 100 req/min from any single IP is plenty.
- **Cloudflare for SaaS / Custom Hostnames** (paid feature, but cheap): when a tenant wants `shop.example.com`, they `CNAME` it at Cloudflare; Cloudflare validates ownership + provisions the edge cert. The origin is unchanged — your `CurrentTenantMiddleware` resolves the host via `TenantDomain`.
- **Lock down the origin**: in Cloudflare → Authenticated Origin Pulls, enable; on Nginx, require the Cloudflare-issued client cert. Or simpler: the `ufw` rules in §2 already only allow Cloudflare IPs.
- **No Cloudflare caching for dynamic routes** (default behaviour). For `/static/*` you can turn on aggressive caching (Cache Everything rule + Edge Cache TTL 1 month) — files in `staticfiles/` are hashed by `ManifestStaticFilesStorage` if you enable it in `prod.py`.

(If you'd rather not pay for Custom Hostnames: skip it; tenants get a `*.salesdee.app` subdomain only. Add custom-domain support later.)

---

## 11. Deploy script — commit at `scripts/deploy.sh`

```bash
#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
set -a; source .env; set +a

git fetch --tags
git checkout "${1:-main}"
git pull --ff-only

uv sync --frozen

# Migrate as owner (separate DSN; app role can't ALTER tables).
DATABASE_URL=postgres://salesdee_owner:${PG_OWNER_PASSWORD}@127.0.0.1:5432/salesdee \
  uv run python manage.py migrate

uv run python manage.py collectstatic --noinput

sudo systemctl restart salesdee-web
# sudo systemctl restart salesdee-tasks    # once a real backend is wired

uv run python manage.py check --deploy
echo "deployed $(git rev-parse --short HEAD)"
```

`./scripts/deploy.sh` (main) or `./scripts/deploy.sh v1.2.0`. gunicorn workers cycle within seconds on `systemctl restart`; in-flight requests queue at Nginx briefly.

---

## 12. LINE webhook URL

Each tenant gets its own webhook URL (see `apps/integrations/urls.py`):

```
https://<slug>.salesdee.app/integrations/line/webhook/<slug>/
```

Set it in the LINE Developers console with the tenant's `channel_secret` + `channel_access_token`, which you saved in `settings → การเชื่อม LINE OA`. The signature is verified server-side (HMAC-SHA256 over the raw body); a bad signature returns 403. Nginx must NOT rewrite/buffer-then-rewrite the body for this path — the config in §9 already passes it untouched.

(Custom tenant domain via Cloudflare for SaaS works identically — just use the verified hostname in the LINE URL.)

---

## 13. Media storage

Local `MEDIA_ROOT` is fine for the anchor tenant. When usage grows: `uv add 'django-storages[s3]'`, point `DEFAULT_FILE_STORAGE` at Cloudflare R2 (S3-compatible, cheapest egress), private bucket served via signed URLs, copy existing media over with `aws s3 sync`.

---

## 14. Backups

```bash
sudo install -d -o postgres /var/backups/salesdee
sudo tee /etc/cron.d/salesdee-backup >/dev/null <<'CRON'
30 2 * * * postgres pg_dump -Fc salesdee | gzip > /var/backups/salesdee/$(date +\%F).dump.gz; find /var/backups/salesdee -name '*.dump.gz' -mtime +14 -delete
CRON
```

Push the dump off-box (`rclone copy /var/backups/salesdee r2:salesdee-pgbackups` nightly). Restore drill quarterly: dump → scratch DB → render a tenant's latest invoice in a staging app to verify.

For media: `rclone sync /home/deploy/salesdee/media r2:salesdee-media-backup` nightly.

---

## 15. Monitoring + logs

- **Sentry** — `SENTRY_DSN` in `.env`; init in `config/settings/prod.py` (`sentry-sdk[django]`).
- **App logs**: `journalctl -u salesdee-web -f`.
- **Nginx**: `tail -f /var/log/nginx/access.log /var/log/nginx/error.log`.
- **Postgres**: `tail -f /var/log/postgresql/postgresql-*.log`.
- **Healthcheck**: `GET /healthz/` (add a tiny view that does `connection.ensure_connection()` and returns 200). Wire it into a Cloudflare Health Check or Better Stack / UptimeRobot.
- **Cloudflare Analytics** for traffic / 4xx / 5xx baselines without instrumenting the app.

---

## 16. Security checklist (must pass before first paying tenant)

- [ ] SSH password auth off; key-only; root login disabled.
- [ ] `ufw status` shows 443/80 limited to Cloudflare IPs; 22 limited to known IPs ideally.
- [ ] Cloudflare SSL/TLS = **Full (strict)** with an Origin Certificate installed in Nginx; origin only reachable via Cloudflare (`ufw` rules).
- [ ] App role is **not** the table owner and **not** a superuser; `RLS_ENABLED=true`.
- [ ] `manage.py check --deploy` passes (HSTS preload INFO is acceptable until you preload).
- [ ] `SECRET_KEY` is 64+ random bytes from `python -c 'import secrets; print(secrets.token_urlsafe(64))'`. Stored only in `.env` and a password manager.
- [ ] HSTS enabled at Cloudflare; `SECURE_HSTS_SECONDS≥31536000`, `SECURE_HSTS_PRELOAD=True` in Django.
- [ ] Django CSP middleware on (Django 6 built-in `django.middleware.csp.ContentSecurityPolicyMiddleware`) — review `SECURE_CSP` in `config/settings/base.py`.
- [ ] **Tenant-leakage tests** green in the deployed branch: `uv run pytest -q apps/*/tests/test_tenant_isolation*.py`.
- [ ] LINE channel-access-token + Anthropic key live in `.env` only (and a password manager), never in git.
- [ ] Backups verified by an actual restore drill.
- [ ] PDPA: privacy policy live, data-export/delete endpoints reachable.

---

## 17. Day-2 cheat-sheet

```bash
sudo journalctl -u salesdee-web -f
sudo tail -f /var/log/nginx/error.log

cd ~/salesdee && uv run python manage.py shell

# Scheduled jobs (cron these once the tasks worker is real; for now they run inline):
uv run python manage.py send_daily_digests
uv run python manage.py send_ar_reminders
uv run python manage.py expire_quotations

sudo nginx -t && sudo systemctl reload nginx

./scripts/deploy.sh v1.2.0

# Cloudflare cache purge after a static asset rev:
curl -sS -X POST "https://api.cloudflare.com/client/v4/zones/<ZONE_ID>/purge_cache" \
     -H "Authorization: Bearer $CF_API_TOKEN" -H "Content-Type: application/json" \
     --data '{"purge_everything":true}'
```

`make worker` in the repo Makefile is the **local dev** shorthand; production uses systemd as above.

---

## 18. Cron / scheduled jobs

Add a cron job for the daily digest + AR reminders + quotation expiry. Pre-async-worker, these commands run sync inside the cron invocation:

```bash
sudo tee /etc/cron.d/salesdee >/dev/null <<'CRON'
0  7  * * * deploy cd /home/deploy/salesdee && /home/deploy/.local/bin/uv run python manage.py send_daily_digests > /dev/null 2>&1
30 8  * * * deploy cd /home/deploy/salesdee && /home/deploy/.local/bin/uv run python manage.py send_ar_reminders   > /dev/null 2>&1
0  2  * * * deploy cd /home/deploy/salesdee && /home/deploy/.local/bin/uv run python manage.py expire_quotations    > /dev/null 2>&1
CRON
```

(`expire_quotations` walks tenants internally; the digests do too.)

---

## 19. What's deliberately not here (yet)

- **Dockerfile / compose** — single-VPS systemd is simpler at this size. Containerise when you need >1 host or want CI/CD-driven blue-green.
- **K8s** — overkill at the first ~30 tenants. Revisit at Phase-2 traffic.
- **Async worker** — `TASKS` is ImmediateBackend; swap in `django-tasks` PyPI's `DatabaseBackend` (writes to `django_tasks_*` tables, polled by `manage.py db_worker`) or Celery+Redis when fire-and-forget actually matters. `apps/*/tasks.py` call sites won't change.
- **Multi-region** — ditto.
- **Real-time notifications** (WebSockets / SSE) — htmx-poll is fine for inbox unread counts at current scale.
- **Cloudflare Tunnel (cloudflared)** instead of a public IP — viable, swap §2's `ufw` for a tunnel service. The Nginx config below stays identical.

Update this doc when any of the above lands.
