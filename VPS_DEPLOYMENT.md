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
- Each tenant uses `<slug>.salesdee.com` (a wildcard you proxy through Cloudflare) **or** their own domain mapped via **Cloudflare for SaaS / Custom Hostnames** — that's the production-grade equivalent of on-demand TLS. The Django middleware (`apps/core/middleware.py::CurrentTenantMiddleware`) resolves the tenant from the `Host` header regardless of which it is.

```
# DNS at Cloudflare — proxied (orange-cloud):
salesdee.com.            A     <origin-ip>   ; proxied
*.salesdee.com.          A     <origin-ip>   ; proxied
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

(The `salesdee-cf-ips.timer` in §18 re-runs this weekly so the allow-list stays fresh — no cron.)

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
APP_DOMAIN=salesdee.com

# Postgres — APP role (not owner)
DATABASE_URL=postgres://salesdee_app:change-me-app@127.0.0.1:5432/salesdee
RLS_ENABLED=True

# Redis
# Redis — queue and cache on separate logical DB indexes so a cache flush never
# wipes queued/scheduled tasks. Pick free indexes via `redis-cli INFO keyspace`.
REDIS_URL=redis://127.0.0.1:6379/0          # generic fallback
Q_REDIS_URL=redis://127.0.0.1:6379/2        # django-q broker
CACHE_REDIS_URL=redis://127.0.0.1:6379/3    # Django cache + session

# Email — SMTP relay (Postmark / SES / Sendgrid / Mailgun)
EMAIL_URL=submission+tls://user:pass@smtp.example.com:587
DEFAULT_FROM_EMAIL=salesdee. <no-reply@salesdee.com>

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
# Media storage — Cloudflare R2 (S3-compatible, $0 egress, signed URLs)
USE_R2=True
R2_ENDPOINT_URL=https://<account>.r2.cloudflarestorage.com
R2_ACCESS_KEY_ID=<r2 access key>
R2_SECRET_ACCESS_KEY=<r2 secret>
R2_BUCKET=salesdee-media
R2_URL_TTL_SECONDS=3600
# Local fallback (only used if USE_R2=False):
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

### Tasks worker — `/etc/systemd/system/salesdee-qcluster.service`

Background queue + scheduler is **django-q2** (`Q_CLUSTER` setting; broker = Redis). One process drains the queue AND fires `Schedule` rows. In prod, `Q_CLUSTER["sync"]` is `False` (set in `config/settings/prod.py`), so `.enqueue()` actually queues and this worker picks it up.

```ini
[Unit]
Description=salesdee background queue + scheduler (django-q2 qcluster)
After=network.target postgresql.service redis-server.service salesdee-web.service
Wants=postgresql.service redis-server.service

[Service]
User=deploy
Group=deploy
WorkingDirectory=/home/deploy/salesdee
EnvironmentFile=/home/deploy/salesdee/.env
ExecStart=/home/deploy/.local/bin/uv run python manage.py qcluster
Restart=on-failure
RestartSec=3
NoNewPrivileges=yes
ProtectSystem=strict
ProtectHome=read-only
ReadWritePaths=/home/deploy/salesdee/media
PrivateTmp=yes

[Install]
WantedBy=multi-user.target
```

Enable both units + seed schedules once:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now salesdee-web salesdee-qcluster
# Idempotent — creates django_q Schedule rows (daily digest, AR reminders, expire quotations).
cd /home/deploy/salesdee && uv run python manage.py setup_q_schedules
systemctl status salesdee-web salesdee-qcluster
```

Schedules live in the **DB** (`django_q_schedule` table) — owners/admins can view, edit cron expressions, and trigger a run from Django admin without redeploying. No cron, no systemd timers.

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
    ssl_certificate     /etc/ssl/cloudflare/salesdee.com.pem;
    ssl_certificate_key /etc/ssl/cloudflare/salesdee.com.key;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;

    # Cloudflare → Nginx — trust the Real IP header
    set_real_ip_from 173.245.48.0/20;   # …or `include /etc/nginx/cloudflare.conf;` if you generate one
    # (Generate /etc/nginx/cloudflare.conf from https://www.cloudflare.com/ips-v4 and -v6;
    #  the systemd timer in §18 refreshes both ufw and this file weekly.)
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

**Cloudflare Origin Cert.** Cloudflare → SSL/TLS → Origin Server → Create Certificate (RSA, 15-year). Save `.pem` to `/etc/ssl/cloudflare/salesdee.com.pem` and `.key` to `/etc/ssl/cloudflare/salesdee.com.key` (mode 600 root:root). Set Cloudflare SSL/TLS mode to **Full (strict)** so Cloudflare verifies the origin cert.

---

## 10. Cloudflare — settings that matter

- **SSL/TLS**: `Full (strict)`. Force HTTPS (Edge Certificates → Always Use HTTPS). Min TLS 1.2.
- **DNS**: A/AAAA records proxied (orange cloud) — apex + wildcard.
- **HSTS**: enable once you're sure (max-age 31536000, includeSubdomains, preload). Then submit to https://hstspreload.org.
- **WAF managed rules**: Free tier is fine to start. Add a rate-limit rule on the LINE webhook path (`/integrations/line/*`) — though LINE's traffic is bursty, a 100 req/min from any single IP is plenty.
- **Cloudflare for SaaS / Custom Hostnames** (paid feature, but cheap): when a tenant wants `shop.example.com`, they `CNAME` it at Cloudflare; Cloudflare validates ownership + provisions the edge cert. The origin is unchanged — your `CurrentTenantMiddleware` resolves the host via `TenantDomain`.
- **Lock down the origin**: in Cloudflare → Authenticated Origin Pulls, enable; on Nginx, require the Cloudflare-issued client cert. Or simpler: the `ufw` rules in §2 already only allow Cloudflare IPs.
- **No Cloudflare caching for dynamic routes** (default behaviour). For `/static/*` you can turn on aggressive caching (Cache Everything rule + Edge Cache TTL 1 month) — files in `staticfiles/` are hashed by `ManifestStaticFilesStorage` if you enable it in `prod.py`.

(If you'd rather not pay for Custom Hostnames: skip it; tenants get a `*.salesdee.com` subdomain only. Add custom-domain support later.)

---

## 11. Deploy script — `scripts/deploy.sh` (lives in the repo)

The script (already committed at `scripts/deploy.sh`) does, in order: `git pull` → `uv sync --frozen` → `manage.py migrate` (using `DATABASE_URL_OWNER`) → `collectstatic` → `setup_q_schedules` → `systemctl restart salesdee-web` → `systemctl restart salesdee-qcluster` (if installed) → `manage.py check --deploy` → poll `/healthz/` until 200 → Slack notify with the commit SHA + elapsed time.

Required `.env` additions on the box (alongside the rest):
```dotenv
# Used by scripts/deploy.sh for migrations — the *owner* role, NOT the runtime app role.
DATABASE_URL_OWNER=postgres://salesdee_owner:OWNER_PASS@127.0.0.1:5432/salesdee

# Optional — deploy script Slack notification
SLACK_DEPLOY_WEBHOOK_URL=https://hooks.slack.com/services/...
PROD_URL=https://salesdee.com
```

Run by hand: `bash scripts/deploy.sh`. Or trigger from GitHub: the workflow at `.github/workflows/deploy.yml` SSHs in and runs it on every push to `main` (secrets `DEPLOY_HOST`, `DEPLOY_USER`, `DEPLOY_SSH_KEY`, `DEPLOY_PATH`). gunicorn workers cycle within seconds on `systemctl restart`; in-flight requests queue at Nginx briefly. The qcluster restart picks up new task code from the same deploy.

---

## 12. LINE webhook URL

Each tenant gets its own webhook URL (see `apps/integrations/urls.py`):

```
https://<slug>.salesdee.com/integrations/line/webhook/<slug>/
```

Set it in the LINE Developers console with the tenant's `channel_secret` + `channel_access_token`, which you saved in `settings → การเชื่อม LINE OA`. The signature is verified server-side (HMAC-SHA256 over the raw body); a bad signature returns 403. Nginx must NOT rewrite/buffer-then-rewrite the body for this path — the config in §9 already passes it untouched.

(Custom tenant domain via Cloudflare for SaaS works identically — just use the verified hostname in the LINE URL.)

---

## 13. Media storage

**Cloudflare R2 (default in prod).** `django-storages[s3]` is wired; `USE_R2=True` swaps `STORAGES["default"]` to a private R2 bucket. Every `ImageField` / `FileField` URL is presigned (`querystring_auth=True`) with a TTL from `R2_URL_TTL_SECONDS` so leaked URLs auto-expire. Static files stay on disk (Nginx serves them, Cloudflare caches at the edge — no point hosting on R2).

Setup once at Cloudflare:
1. Dashboard → R2 → **Create bucket** `salesdee-media` (region: APAC). Keep it private (default).
2. R2 → **Manage R2 API Tokens** → Create API Token → permission **Object Read & Write**, scope to this bucket. Copy `accessKeyId`, `secretAccessKey`, `endpoint URL`.
3. Paste into `.env` as `R2_*` vars above + set `USE_R2=True` + `systemctl restart salesdee-web salesdee-qcluster`.
4. (If migrating from local) sync existing files with rclone:
   ```bash
   rclone sync /home/deploy/salesdee/media r2:salesdee-media --progress
   ```

Set `USE_R2=False` to stay on local disk (dev/tests do this — no live R2 calls during pytest).

---

## 14. Backups (systemd timer — no cron)

The whole box uses systemd timers, never cron — `journalctl` gives one place to look for both run history and stderr; `systemctl list-timers` shows next-fire at a glance; `OnCalendar` is timezone-aware and `Persistent=true` catches up after a reboot.

`/etc/systemd/system/salesdee-backup.service`:
```ini
[Unit]
Description=salesdee Postgres + media backup
After=postgresql.service

[Service]
Type=oneshot
User=postgres
StateDirectory=salesdee-backups
ExecStart=/bin/bash -c 'pg_dump -Fc salesdee | gzip > /var/lib/salesdee-backups/$(date +%%F).dump.gz'
ExecStartPost=/usr/bin/find /var/lib/salesdee-backups -name "*.dump.gz" -mtime +14 -delete
# off-box copy (optional — uses /home/deploy/.config/rclone)
# ExecStartPost=/usr/bin/rclone copy /var/lib/salesdee-backups r2:salesdee-pgbackups
```

`/etc/systemd/system/salesdee-backup.timer`:
```ini
[Unit]
Description=salesdee nightly backup

[Timer]
OnCalendar=*-*-* 02:30:00 Asia/Bangkok
Persistent=true
RandomizedDelaySec=10m

[Install]
WantedBy=timers.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now salesdee-backup.timer
systemctl list-timers --all | grep salesdee
```

For media: a second timer pair `salesdee-media-sync.{service,timer}` running `rclone sync /home/deploy/salesdee/media r2:salesdee-media-backup` daily.

Restore drill quarterly: dump → scratch DB → render a tenant's latest invoice in a staging app to verify.

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

# Scheduled jobs live in django-q (see §18); the qcluster worker fires them.
sudo systemctl status salesdee-qcluster
sudo journalctl -u salesdee-qcluster -f
# Trigger one-off (still goes through the queue):
uv run python manage.py shell -c "from django_q.tasks import async_task; async_task('django.core.management.call_command','send_daily_digests')"

sudo nginx -t && sudo systemctl reload nginx

bash scripts/deploy.sh                     # roll the current main forward

# Cloudflare cache purge after a static asset rev:
curl -sS -X POST "https://api.cloudflare.com/client/v4/zones/<ZONE_ID>/purge_cache" \
     -H "Authorization: Bearer $CF_API_TOKEN" -H "Content-Type: application/json" \
     --data '{"purge_everything":true}'
```

`make worker` in the repo Makefile is the **local dev** shorthand; production uses systemd as above.

---

## 18. Scheduled jobs — django-q2 `Schedule` rows (no cron, no systemd timers)

App-level recurring jobs (daily digest, AR reminders, quotation expiry) live in the **`django_q_schedule`** table and are fired by the `qcluster` worker (§8). Seed them once with the management command — idempotent, safe to re-run on every deploy:

```bash
cd /home/deploy/salesdee && uv run python manage.py setup_q_schedules
```

That creates / updates three `Schedule` rows (Asia/Bangkok, `Schedule.CRON`):

| Name | Cron | Calls |
|---|---|---|
| `salesdee.send_daily_digests` | `0 7 * * *` | `manage.py send_daily_digests` |
| `salesdee.send_ar_reminders` | `30 8 * * *` | `manage.py send_ar_reminders` |
| `salesdee.expire_quotations` | `0 2 * * *` | `manage.py expire_quotations` |

To **edit a schedule without redeploying**: Django admin → Django Q → Scheduled tasks → edit the cron field. The change takes effect at the next cluster tick (a few seconds). Failed runs land in admin → Failed tasks.

To trigger one on demand from the box:

```bash
cd /home/deploy/salesdee
uv run python manage.py shell -c "from django_q.tasks import async_task; async_task('django.core.management.call_command','send_daily_digests')"
```

### Cloudflare-IP allow-list refresh — `/etc/systemd/system/salesdee-cf-ips.{service,timer}`

This one is **not** a Django task (it edits `ufw`, needs root), so it stays a systemd timer.

```ini
# /etc/systemd/system/salesdee-cf-ips.service
[Unit]
Description=Refresh Cloudflare IP allow-list in ufw

[Service]
Type=oneshot
ExecStart=/usr/local/sbin/refresh-cf-ips.sh
```
`/usr/local/sbin/refresh-cf-ips.sh` (chmod 0755 root:root):
```bash
#!/usr/bin/env bash
set -euo pipefail
# wipe previous CF rules (any "ALLOW IN" rule with comment "cf"), then re-add.
ufw status numbered | awk '/cf]/ {print $1}' | tr -d '[]' | sort -rn | while read -r n; do yes | ufw delete "$n"; done
for n in $(curl -fsSL https://www.cloudflare.com/ips-v4); do ufw allow proto tcp from "$n" to any port 443 comment 'cf'; done
for n in $(curl -fsSL https://www.cloudflare.com/ips-v6); do ufw allow proto tcp from "$n" to any port 443 comment 'cf'; done
```
```ini
# /etc/systemd/system/salesdee-cf-ips.timer
[Unit]
Description=Refresh CF IPs weekly

[Timer]
OnCalendar=Sun *-*-* 03:00:00 Asia/Bangkok
Persistent=true

[Install]
WantedBy=timers.target
```
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now salesdee-backup.timer salesdee-cf-ips.timer
systemctl list-timers --all | grep salesdee
```

> The Postgres-backup timer in §14 also stays systemd (`pg_dump` runs as the `postgres` system user, not the Django app).

---

## 19. What's deliberately not here (yet)

- **Dockerfile / compose** — single-VPS systemd is simpler at this size. Containerise when you need >1 host or want CI/CD-driven blue-green.
- **K8s** — overkill at the first ~30 tenants. Revisit at Phase-2 traffic.
- **Heavier task backend** — django-q2 + Redis covers the workload at current scale. Swap to Celery+Redis if/when fire-and-forget volume justifies it; the `@task` decorator in `apps/core/tasks.py` is a shim that makes the swap a settings change, not a code change.
- **Multi-region** — ditto.
- **Real-time notifications** (WebSockets / SSE) — htmx-poll is fine for inbox unread counts at current scale.
- **Cloudflare Tunnel (cloudflared)** instead of a public IP — viable, swap §2's `ufw` for a tunnel service. The Nginx config below stays identical.

Update this doc when any of the above lands.
