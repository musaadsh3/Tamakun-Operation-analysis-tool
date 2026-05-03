# Production deployment (systemd, no cPanel UI)

This folder contains the artifacts used to run the app under systemd on a CloudLinux/cPanel host **without** going through the cPanel Setup Python App wizard. The cPanel-managed nginx/Apache/AutoSSL stack is reused; only the Python app process and a single nginx vhost are added.

The original cPanel-flavored guide (`DEPLOY.md`) remains for shared-hosting accounts that don't have root.

## Architecture

```
Cloudflare (proxy) ──HTTPS──► nginx :443/:80 ──unix socket──► gunicorn (uvicorn workers) ──► FastAPI app
                                                                       │
                                                                       ├──► localhost Postgres 14 (primary, writable)
                                                                       └──► localhost Postgres 14 (ingest_tamakun, read-only)
```

- **OS user**: `tamakunsaas` — system account, shell `/sbin/nologin`, home `/opt/tamakun-saas`. No mail, no public_html, no cPanel account.
- **App dir**: `/opt/tamakun-saas` (code + venv + .env, owner `tamakunsaas:tamakunsaas`, mode `0750`).
- **Data dirs**: `/var/lib/tamakun-saas/{uploads,exports}` (mode `0750`), symlinked into the app dir so persistent data lives outside the deploy tree.
- **Process supervisor**: systemd unit `tamakun-saas.service` running gunicorn with three uvicorn workers, hardened (`ProtectSystem=strict`, `NoNewPrivileges`, `MemoryDenyWriteExecute`, etc.).
- **Reverse proxy**: nginx vhost (`00-operation-tamakun-saas.conf`) is loaded *before* the cPanel-generated `users/operationtamakun.conf` so it wins the `server_name operation.tamakun.sa` match.
- **TLS**: cPanel AutoSSL (Let's Encrypt) issues and renews `/var/cpanel/ssl/apache_tls/operation.tamakun.sa/combined`; the new vhost reads the same file. No separate certbot run is needed for `operation.tamakun.sa`.

## One-time bootstrap

These commands assume you have `sudo` on the host and Postgres 14 + nginx + cPanel are already running.

```bash
# 1. System user (no cPanel account, no shell)
sudo useradd --system --home-dir /opt/tamakun-saas --shell /sbin/nologin --user-group tamakunsaas
sudo install -d -o tamakunsaas -g tamakunsaas -m 0750 /opt/tamakun-saas
sudo install -d -o tamakunsaas -g tamakunsaas -m 0750 /var/lib/tamakun-saas/uploads /var/lib/tamakun-saas/exports

# 2. Primary Postgres database (run as `postgres`)
sudo -u postgres psql <<'SQL'
CREATE ROLE tamakunsaas LOGIN PASSWORD '<paste-strong-random-password>';
CREATE DATABASE tamakunsaas OWNER tamakunsaas ENCODING 'UTF8' TEMPLATE template0;
GRANT ALL PRIVILEGES ON DATABASE tamakunsaas TO tamakunsaas;
SQL

# 3. Code (rsync the repo, excluding venv / .git / uploads / exports / __pycache__)
sudo rsync -a --delete --exclude '.git' --exclude 'venv' --exclude '__pycache__' \
    --exclude 'uploads/*' --exclude 'exports/*' --exclude '.env' \
    ./ /opt/tamakun-saas/
sudo chown -R tamakunsaas:tamakunsaas /opt/tamakun-saas

# Symlink data dirs so writes go to /var/lib/tamakun-saas
sudo -u tamakunsaas ln -sfn /var/lib/tamakun-saas/uploads /opt/tamakun-saas/uploads
sudo -u tamakunsaas ln -sfn /var/lib/tamakun-saas/exports /opt/tamakun-saas/exports

# 4. Python venv (3.11)
sudo -u tamakunsaas python3.11 -m venv /opt/tamakun-saas/venv
sudo -u tamakunsaas /opt/tamakun-saas/venv/bin/pip install --upgrade pip wheel setuptools
sudo -u tamakunsaas /opt/tamakun-saas/venv/bin/pip install -r /opt/tamakun-saas/requirements-cpanel.txt 'gunicorn==23.0.0'

# 5. .env (mode 0640, owned by tamakunsaas)
sudo install -o tamakunsaas -g tamakunsaas -m 0640 /dev/stdin /opt/tamakun-saas/.env <<EOF
SECRET_KEY=$(python3 -c 'import secrets; print(secrets.token_urlsafe(64))')
DATABASE_URL=postgresql://tamakunsaas:<paste-db-password>@127.0.0.1:5432/tamakunsaas
EXTERNAL_DB_HOST=127.0.0.1
EXTERNAL_DB_PORT=5432
EXTERNAL_DB_USERNAME=ingest_readonly
EXTERNAL_DB_PASSWORD=<paste-ingest-password>
EXTERNAL_DB_NAME=ingest_tamakun
EXTERNAL_DB_TYPE=postgres
EXTERNAL_USE_SSL=false
EOF

# 6. Initialize schema + seeds (one-shot)
sudo -u tamakunsaas bash -c '
  cd /opt/tamakun-saas
  /opt/tamakun-saas/venv/bin/python -c "
from dotenv import load_dotenv; load_dotenv(\".env\")
from app.database import init_db, SessionLocal
from app.services.auth import seed_admin, seed_brands
init_db()
db = SessionLocal()
try: seed_admin(db); seed_brands(db)
finally: db.close()
print(\"OK\")
"'

# 7. systemd unit
sudo install -o root -g root -m 0644 deploy/systemd/tamakun-saas.service \
    /etc/systemd/system/tamakun-saas.service
sudo systemctl daemon-reload
sudo systemctl enable --now tamakun-saas.service

# 8. Let nginx (running as `nobody`) reach the unix socket
sudo usermod -a -G tamakunsaas nobody
sudo systemctl restart nginx

# 9. nginx vhost (filename prefix 00- so it wins server_name match against the cPanel-generated vhost)
sudo install -o root -g root -m 0644 deploy/nginx/00-operation-tamakun-saas.conf \
    /etc/nginx/conf.d/00-operation-tamakun-saas.conf
sudo nginx -t && sudo systemctl reload nginx
```

## Verification

```bash
bash deploy/smoke_test.sh
```

The smoke test exercises 27 checks: public landing pages, static assets, login/logout flow with both bad and good credentials, every authenticated admin page, every brand dashboard, and the external Salla DB integration (`/api/fetch-db`) for all three brands. Origin tests bypass Cloudflare via `--resolve`; the final block hits the real public DNS to confirm the CDN path works too.

## Day-2

- **Logs**: `journalctl -u tamakun-saas -f` and `/var/log/nginx/operation.tamakun.sa-{access,error}.log`.
- **Restart**: `sudo systemctl restart tamakun-saas` (graceful: 30s timeout for in-flight requests).
- **Re-deploy code**: rsync over the existing tree as `tamakunsaas`, then `sudo systemctl restart tamakun-saas`. The venv is preserved.
- **Schema changes**: there's no Alembic. New SQLAlchemy models are created on startup via `Base.metadata.create_all()`; column changes still need manual SQL or adding Alembic.
- **Rotating secrets**: edit `/opt/tamakun-saas/.env`, then `sudo systemctl restart tamakun-saas`. Mode stays at `0640`.
- **Default admin**: `m.alshathri@tamakun.sa` / `Tamakun@2024` (seeded on first start). Change at `/admin/password` after first login.

## Why nginx 00-* file instead of editing cPanel's vhost

cPanel regenerates `/etc/nginx/conf.d/users/operationtamakun.conf` whenever AutoSSL renews, the user adds a subdomain, or any whmapi runs that touches the account. Editing it directly means losing changes on the next regeneration. nginx walks `/etc/nginx/conf.d/*.conf` alphabetically and binds the first server block matching a given `server_name`, so a `00-` filename loads first and wins the match for `operation.tamakun.sa` while leaving the cPanel vhost intact for the service subdomains it owns (`mail.`, `webmail.`, `cpanel.`, etc.). nginx will print a "conflicting server name" warning at config-test time — that's expected and harmless.

## Notes for Cloudflare

- Origin DNS `operation.tamakun.sa` currently points at Cloudflare (188.114.96.x / AAAA 2a06:98c1:3120::3). The vhost serves the app on **both** :80 and :443 so Cloudflare in either Flexible or Full SSL mode works.
- For best practice, set Cloudflare SSL/TLS mode to **Full** (or **Full (strict)**, since AutoSSL provides a valid public cert at the origin). Flexible works but exposes origin traffic as plain HTTP between CF and the server.
- The `:80` block hard-codes `X-Forwarded-Proto: https` because Cloudflare always terminates TLS for clients regardless of the CF↔origin scheme; this lets the FastAPI app emit secure cookies and the right link schemes.
