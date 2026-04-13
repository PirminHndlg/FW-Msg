#!/usr/bin/env bash
# FWMsg — Proxmox LXC Install Script
#
# Run on the Proxmox HOST — it will create the CT, clone the repo inside it,
# and provision everything automatically.
#
# Usage (on Proxmox host):
#   bash <(curl -fsSL https://raw.githubusercontent.com/PirminHndlg/FW-Msg/main/install.sh)
#   # — or —
#   ./install.sh
#
# The script is dual-mode:
#   HOST mode  (default)      — creates the LXC CT, clones repo, triggers install inside CT
#   CT mode    (--inside-ct)  — provisions the app (called automatically by host mode)

set -euo pipefail

# ==============================================================================
# SHARED CONSTANTS
# ==============================================================================

INSTALL_DIR="/opt/fwmsg"
VENV_DIR="${INSTALL_DIR}/venv"
APP_DIR="${INSTALL_DIR}/FWMsg"
SETTINGS_FILE="${APP_DIR}/FWMsg/settings.py"
SECRETS_FILE="${APP_DIR}/FWMsg/.secrets.json"
SECRETS_EXAMPLE="${APP_DIR}/FWMsg/.example-secrets.json"
DB_NAME="fwmsg"
DB_USER="fwmsg"
DAPHNE_HOST="127.0.0.1"
DAPHNE_PORT="8001"
DOMAIN_HOST="volunteer.solutions"

REPO_URL="https://github.com/PirminHndlg/FW-Msg"

# Colours
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m'

msg_info()  { echo -e "${BLUE}[INFO]${NC}  $*"; }
msg_ok()    { echo -e "${GREEN}[OK]${NC}    $*"; }
msg_warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
msg_error() { echo -e "${RED}[ERROR]${NC} $*" >&2; }
msg_step()  { echo -e "\n${BOLD}${BLUE}━━━ $* ${NC}"; }

# ==============================================================================
# MODE DISPATCH  (functions defined below, dispatch at bottom)
# ==============================================================================

# ==============================================================================
# HOST MODE — runs on the Proxmox VE node
# ==============================================================================

host_setup() {
    echo ""
    echo -e "${BOLD}================================================================${NC}"
    echo -e "${BOLD}  FWMsg — Proxmox LXC Installer${NC}"
    echo -e "${BOLD}================================================================${NC}"
    echo ""

    # ── Pre-flight: must run on a Proxmox host ────────────────────────────────
    if ! command -v pct &>/dev/null; then
        msg_error "pct not found. This script must be run on a Proxmox VE host."
        exit 1
    fi
    if ! command -v pvesh &>/dev/null; then
        msg_error "pvesh not found. Are you on a Proxmox VE node?"
        exit 1
    fi

    # ── Collect required inputs ───────────────────────────────────────────────

    # ORG_NAME — required
    if [[ -z "${ORG_NAME:-}" ]]; then
        read -rp "  ORG_NAME (domain/hostname, e.g. fwmsg.local): " ORG_NAME
    fi
    if [[ -z "${ORG_NAME:-}" ]]; then
        msg_error "ORG_NAME is required. Aborting."
        exit 1
    fi

    # Check if REPO_URL is reachable
    if ! curl -f -s -o /dev/null "${REPO_URL}"; then
        msg_error "REPO_URL is not reachable. Aborting."
        exit 1
    fi

    # CT resources — optional with sensible defaults
    CT_ID="${CT_ID:-$(pvesh get /cluster/nextid 2>/dev/null || echo 200)}"
    CT_HOSTNAME="${CT_HOSTNAME:-fwmsg}"
    CT_RAM="${CT_RAM:-2048}"
    CT_CORES="${CT_CORES:-2}"
    CT_DISK="${CT_DISK:-8}"
    CT_BRIDGE="${CT_BRIDGE:-vmbr0}"

    echo ""
    msg_info "Configuration:"
    echo "    ORG_NAME   : ${ORG_NAME}"
    echo "    REPO_URL   : ${REPO_URL}"
    echo "    CT ID      : ${CT_ID}"
    echo "    Hostname   : ${CT_HOSTNAME}"
    echo "    RAM        : ${CT_RAM} MB"
    echo "    Cores      : ${CT_CORES}"
    echo "    Disk       : ${CT_DISK} GB"
    echo "    Bridge     : ${CT_BRIDGE}"
    echo ""
    read -rp "  Proceed? [y/N] " CONFIRM
    [[ "${CONFIRM,,}" =~ ^y ]] || { msg_warn "Aborted."; exit 0; }

    # ── Detect storage ────────────────────────────────────────────────────────
    msg_step "Detecting Proxmox storage"

    # Show all available storages so the user can see what exists
    msg_info "Available storages on this node:"
    pvesm status 2>/dev/null | column -t || true
    echo ""

    # Auto-detect via pvesh API (more reliable than pvesm --content filter)
    _detect_storage() {
        local content_type="$1"
        pvesh get /storage --output-format json 2>/dev/null \
            | python3 -c "
import json, sys
try:
    for s in json.load(sys.stdin):
        if '${content_type}' in s.get('content', '').split(','):
            print(s['storage'])
            break
except Exception:
    pass
" 2>/dev/null || true
    }

    # CT rootfs disk storage — default: local-lvm
    if [[ -z "${ROOTFS_STORAGE:-}" ]]; then
        ROOTFS_STORAGE="$(_detect_storage rootdir)"
        ROOTFS_STORAGE="${ROOTFS_STORAGE:-local-lvm}"
    fi

    # Template storage — default: local
    if [[ -z "${TEMPLATE_STORAGE:-}" ]]; then
        TEMPLATE_STORAGE="$(_detect_storage vztmpl)"
        TEMPLATE_STORAGE="${TEMPLATE_STORAGE:-local}"
    fi

    # Let user confirm or override
    read -rp "  Storage for CT disk    [${ROOTFS_STORAGE}]: " _input
    ROOTFS_STORAGE="${_input:-${ROOTFS_STORAGE}}"

    read -rp "  Storage for templates  [${TEMPLATE_STORAGE}]: " _input
    TEMPLATE_STORAGE="${_input:-${TEMPLATE_STORAGE}}"

    msg_ok "Rootfs storage : ${ROOTFS_STORAGE}"
    msg_ok "Template storage: ${TEMPLATE_STORAGE}"

    # ── Find or download Debian 12 template ──────────────────────────────────
    msg_step "Preparing Debian 12 template"

    TEMPLATE=$(pveam list "${TEMPLATE_STORAGE}" 2>/dev/null \
        | awk '/debian-12-standard/ {print $1}' | sort -V | tail -1)

    if [[ -z "${TEMPLATE}" ]]; then
        msg_info "Template not found locally. Fetching available list..."
        pveam update &>/dev/null || true

        AVAIL=$(pveam available --section system 2>/dev/null \
            | awk '/debian-12-standard/ {print $2}' | sort -V | tail -1)

        if [[ -z "${AVAIL}" ]]; then
            msg_error "No Debian 12 standard template found. Check internet access on the Proxmox node."
            exit 1
        fi

        read -rp "  Download template '${AVAIL}' to '${TEMPLATE_STORAGE}'? [Y/n] " DL_CONFIRM
        if [[ "${DL_CONFIRM,,}" =~ ^n ]]; then
            msg_warn "Template download skipped. Aborting."
            exit 0
        fi

        msg_info "Downloading ${AVAIL} ..."
        pveam download "${TEMPLATE_STORAGE}" "${AVAIL}"
        TEMPLATE="${TEMPLATE_STORAGE}:vztmpl/${AVAIL}"
        msg_ok "Template downloaded: ${TEMPLATE}"
    else
        msg_ok "Using existing template: ${TEMPLATE}"
    fi

    # ── Create the LXC container ──────────────────────────────────────────────
    msg_step "Creating LXC container (CT ${CT_ID})"

    # Generate a random root password for the CT
    CT_ROOT_PW="$(tr -dc 'A-Za-z0-9!@#%^&*' </dev/urandom | head -c 20)"

    pct create "${CT_ID}" "${TEMPLATE}" \
        --hostname   "${CT_HOSTNAME}" \
        --memory     "${CT_RAM}" \
        --cores      "${CT_CORES}" \
        --rootfs     "${ROOTFS_STORAGE}:${CT_DISK}" \
        --net0       "name=eth0,bridge=${CT_BRIDGE},ip=dhcp" \
        --unprivileged 1 \
        --features   "nesting=1" \
        --password   "${CT_ROOT_PW}" \
        --ostype     "debian" \
        --start      0

    msg_ok "CT ${CT_ID} created."

    # ── Start the CT and wait for network ────────────────────────────────────
    msg_step "Starting CT ${CT_ID}"
    pct start "${CT_ID}"

    msg_info "Waiting for CT to become ready..."
    for i in $(seq 1 40); do
        if pct exec "${CT_ID}" -- hostname &>/dev/null 2>&1; then
            break
        fi
        if [[ ${i} -eq 40 ]]; then
            msg_error "CT did not become ready in time. Check: pct status ${CT_ID}"
            exit 1
        fi
        sleep 3
    done

    # Give systemd another moment to finish booting
    sleep 5
    msg_ok "CT ${CT_ID} is up."

    # ── Install git inside the CT ─────────────────────────────────────────────
    msg_step "Bootstrapping CT (git)"

    pct exec "${CT_ID}" -- bash -c "
        export DEBIAN_FRONTEND=noninteractive
        apt-get update -qq
        apt-get install -y -qq git
    "
    msg_ok "git installed in CT."

    # ── Clone the repo ────────────────────────────────────────────────────────
    msg_step "Cloning repo into CT"

    pct exec "${CT_ID}" -- git clone "${REPO_URL}" "${INSTALL_DIR}"
    msg_ok "Repo cloned to ${INSTALL_DIR} inside CT."

    # ── Run the app installer inside the CT ──────────────────────────────────
    msg_step "Running app installer inside CT"
    msg_info "This will take several minutes (packages + pip install)..."
    echo ""

    pct exec "${CT_ID}" -- bash -c \
        "export ORG_NAME='${ORG_NAME}'; bash ${INSTALL_DIR}/install.sh --inside-ct"

    # ── Retrieve the CT IP for the summary ───────────────────────────────────
    CT_IP=$(pct exec "${CT_ID}" -- bash -c \
        "hostname -I 2>/dev/null | awk '{print \$1}'" 2>/dev/null || echo "unknown")

    # ── Host-side summary ─────────────────────────────────────────────────────
    echo ""
    echo -e "${BOLD}================================================================${NC}"
    echo -e "${BOLD}${GREEN}  FWMsg CT created and provisioned!${NC}"
    echo -e "${BOLD}================================================================${NC}"
    echo ""
    echo "  CT ID      : ${CT_ID}"
    echo "  CT IP      : ${CT_IP}"
    echo "  URL        : http://${ORG_NAME}  (or http://${CT_IP})"
    echo ""
    echo "  Root password: ${CT_ROOT_PW}"
    echo "  (save this — shown only once)"
    echo ""
    echo "  Access the CT:   pct enter ${CT_ID}"
    echo "  Stop  the CT:    pct stop  ${CT_ID}"
    echo ""
    echo -e "${BOLD}================================================================${NC}"
}

# ==============================================================================
# CT MODE — runs inside the LXC container (called automatically by host_setup)
# ==============================================================================

inside_ct_install() {
    echo ""
    echo "================================================================"
    echo "  FWMsg — CT App Installer"
    echo "================================================================"
    echo ""

    # ── Step 1: ORG_NAME ─────────────────────────────────────────────────────

    if [[ -z "${ORG_NAME:-}" ]]; then
        read -rp "Enter ORG_NAME (used as domain/hostname, e.g. fwmsg.local): " ORG_NAME
    fi
    if [[ -z "${ORG_NAME:-}" ]]; then
        msg_error "ORG_NAME is required. Aborting."
        exit 1
    fi
    msg_ok "ORG_NAME = ${ORG_NAME}"

    # Verify repo was cloned correctly
    if [[ ! -f "${SECRETS_EXAMPLE}" ]]; then
        msg_error "Expected repo layout not found at ${INSTALL_DIR}."
        msg_error "Missing: ${SECRETS_EXAMPLE}"
        exit 1
    fi

    # ── Step 2: System packages ───────────────────────────────────────────────

    msg_step "Installing system packages"
    export DEBIAN_FRONTEND=noninteractive
    apt-get update -qq
    apt-get install -y -qq \
        python3 \
        python3-venv \
        python3-pip \
        postgresql \
        postgresql-contrib \
        libpq-dev \
        nginx \
        redis-server \
        git \
        wkhtmltopdf \
        poppler-utils \
        curl \
        build-essential
    msg_ok "System packages installed."

    # ── Step 3: Python venv + dependencies ───────────────────────────────────

    msg_step "Setting up Python environment"
    python3 -m venv "${VENV_DIR}"

    PYTHON="${VENV_DIR}/bin/python"
    PIP="${VENV_DIR}/bin/pip"

    msg_info "Installing Python packages (this may take a few minutes)..."
    "${PIP}" install --quiet --upgrade pip
    "${PIP}" install --quiet -r "${INSTALL_DIR}/requirements.txt"
    "${PIP}" install --quiet psycopg2-binary
    msg_ok "Python environment ready."

    # ── Step 4: PostgreSQL setup ──────────────────────────────────────────────

    msg_step "Setting up PostgreSQL"

    # Start PostgreSQL first (it may not be running yet after fresh install)
    systemctl enable --now postgresql

    # Generate a random 32-char DB password
    DB_PASSWORD="$(python3 -c "
import secrets, string
print(''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(32)))
")"

    # Create role + database (idempotent)
    su - postgres -c "psql -q" <<SQL
DO \$\$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = '${DB_USER}') THEN
        CREATE ROLE ${DB_USER} LOGIN PASSWORD '${DB_PASSWORD}';
    ELSE
        ALTER ROLE ${DB_USER} WITH PASSWORD '${DB_PASSWORD}';
    END IF;
END
\$\$;
SQL

    su - postgres -c "psql -q -tc \"SELECT 1 FROM pg_database WHERE datname='${DB_NAME}'\" \
        | grep -q 1 || createdb -O ${DB_USER} ${DB_NAME}"

    msg_ok "PostgreSQL: database '${DB_NAME}', user '${DB_USER}' ready."

    # ── Step 5: Generate .secrets.json ───────────────────────────────────────

    msg_step "Generating .secrets.json"

    # ── Email / SMTP prompts ──────────────────────────────────────────────────

    msg_info "Email / SMTP configuration (leave blank to configure later in .secrets.json)"
    echo ""
    read -rp  "  Email domain       (e.g. example.com):    " DOMAIN_HOST
    read -rp  "  SMTP server        (e.g. smtp.ionos.de):  " SMTP_SERVER
    read -rp  "  SMTP port          [587]:                 " SMTP_PORT
    read -rp  "  SMTP user          (sender address):      " SMTP_USER
    read -rsp "  SMTP password:                            " SMTP_PASSWORD
    echo ""
    read -rp  "  SMTP use SSL/TLS   [true]:                " SMTP_USE_SSL
    echo ""

    # Apply defaults
    DOMAIN_HOST="${DOMAIN_HOST:-${ORG_NAME}}"
    SMTP_PORT="${SMTP_PORT:-587}"
    SMTP_USE_SSL="${SMTP_USE_SSL:-true}"

    "${PYTHON}" - <<PYEOF
import json, secrets, string, re

example_path  = "${SECRETS_EXAMPLE}"
out_path      = "${SECRETS_FILE}"
org_name      = "${ORG_NAME}"
db_password   = "${DB_PASSWORD}"
domain_host   = "${DOMAIN_HOST}"
smtp_server   = "${SMTP_SERVER}"
smtp_port_raw = "${SMTP_PORT}"
smtp_user     = "${SMTP_USER}"
smtp_password = "${SMTP_PASSWORD}"
smtp_use_ssl  = "${SMTP_USE_SSL}".strip().lower() in ("true", "yes", "1")
smtp_port     = int(smtp_port_raw) if smtp_port_raw.isdigit() else 587

# Build the full public URL (https:// since NPM terminates SSL)
full_domain   = f"{org_name}.{domain_host}" if domain_host and domain_host != org_name else org_name
public_url    = f"https://{full_domain}"

with open(example_path) as f:
    raw = f.read()

# Strip JSON comment keys (lines like "// ...": "...",)
raw_clean = re.sub(r'^\s*"//[^"]*":[^,\n]*,?\n?', '', raw, flags=re.MULTILINE)
template = json.loads(raw_clean)

# Django secret key
chars = string.ascii_letters + string.digits + "!@#\$%^&*(-_=+)"
secret_key = "".join(secrets.choice(chars) for _ in range(50))

# VAPID keys (push notifications)
vapid_public  = "REPLACE_WITH_VAPID_PUBLIC_KEY"
vapid_private = "REPLACE_WITH_VAPID_PRIVATE_KEY"
try:
    from py_vapid import Vapid
    vapid = Vapid()
    vapid.generate_keys()
    vapid_public  = vapid.public_key_urlsafe_base64
    vapid_private = vapid.private_key_urlsafe_base64
    print("  VAPID keys generated.")
except Exception as e:
    print(f"  VAPID key generation skipped ({e}). Set them manually in .secrets.json.")

data = {
    "secret_key":           secret_key,
    "debug":                False,
    "domain":               full_domain,
    "domain_host":          public_url,
    "allowed_hosts":        [full_domain, org_name, "localhost", "127.0.0.1"],
    "csrf_trusted_origins": [public_url, "http://localhost:8000", "http://127.0.0.1:8000"],
    "trusted_orgins":       [public_url],
    "server_mail":    smtp_user   or f"admin@{domain_host}",
    "smtp_server":    smtp_server or f"smtp.{domain_host}",
    "port":           smtp_port,
    "sender_email":   smtp_user   or f"admin@{domain_host}",
    "password":       smtp_password,
    "feedback_email": smtp_user   or f"admin@{domain_host}",
    "imap_server":    f"imap.{domain_host}",
    "imap_port":      993,
    "imap_use_ssl":   smtp_use_ssl,
    "admins":         template.get("admins", [["Admin", smtp_user or f"admin@{domain_host}"]]),
    "vapid_public_key":  vapid_public,
    "vapid_private_key": vapid_private,
    "db_name":     "${DB_NAME}",
    "db_user":     "${DB_USER}",
    "db_password": db_password,
    "db_host":     "localhost",
    "db_port":     "5432",
}

with open(out_path, "w") as f:
    json.dump(data, f, indent=4)

print(f"  Written: {out_path}")
PYEOF

    msg_ok "Secrets file generated."

    # ── Step 6: Patch settings.py DATABASES → PostgreSQL ─────────────────────

    msg_step "Patching settings.py (SQLite → PostgreSQL)"

    "${PYTHON}" - <<'PYEOF'
import re

settings_path = "/opt/fwmsg/FWMsg/FWMsg/settings.py"

with open(settings_path) as f:
    content = f.read()

new_block = '''DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME":     secrets.get("db_name",     "fwmsg"),
        "USER":     secrets.get("db_user",     "fwmsg"),
        "PASSWORD": secrets.get("db_password", ""),
        "HOST":     secrets.get("db_host",     "localhost"),
        "PORT":     secrets.get("db_port",     "5432"),
    },
}'''

content = re.sub(
    r'DATABASES\s*=\s*\{[^{}]*(?:\{[^{}]*\}[^{}]*)?\}',
    new_block,
    content,
    flags=re.DOTALL,
)

with open(settings_path, "w") as f:
    f.write(content)

print("  settings.py patched.")
PYEOF

    msg_ok "settings.py patched."

    # ── Step 7: Django migrate + collectstatic ────────────────────────────────

    msg_step "Running Django migrations and collectstatic"
    cd "${APP_DIR}"
    "${PYTHON}" manage.py migrate --noinput
    "${PYTHON}" manage.py collectstatic --noinput --clear
    msg_ok "Migrations and static files done."

    # ── Step 8: Redis ─────────────────────────────────────────────────────────

    msg_step "Starting Redis"
    systemctl enable --now redis-server
    msg_ok "Redis running."

    # ── Step 9: Daphne systemd service ────────────────────────────────────────

    msg_step "Creating systemd services"

    cat > /etc/systemd/system/fwmsg-daphne.service <<EOF
[Unit]
Description=FWMsg Daphne ASGI Server
After=network.target redis.service postgresql.service

[Service]
User=www-data
Group=www-data
WorkingDirectory=${APP_DIR}
ExecStart=${VENV_DIR}/bin/daphne \\
    -b ${DAPHNE_HOST} \\
    -p ${DAPHNE_PORT} \\
    FWMsg.asgi:application
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal
SyslogIdentifier=fwmsg-daphne

[Install]
WantedBy=multi-user.target
EOF

    # ── Step 10: Celery worker ────────────────────────────────────────────────

    cat > /etc/systemd/system/fwmsg-celery.service <<EOF
[Unit]
Description=FWMsg Celery Worker
After=network.target redis.service postgresql.service

[Service]
User=www-data
Group=www-data
WorkingDirectory=${APP_DIR}
ExecStart=${VENV_DIR}/bin/celery \\
    -A FWMsg worker \\
    --loglevel=info \\
    --concurrency=4
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=fwmsg-celery

[Install]
WantedBy=multi-user.target
EOF

    # ── Step 11: Celery beat ──────────────────────────────────────────────────

    cat > /etc/systemd/system/fwmsg-celerybeat.service <<EOF
[Unit]
Description=FWMsg Celery Beat Scheduler
After=network.target redis.service postgresql.service fwmsg-celery.service

[Service]
User=www-data
Group=www-data
WorkingDirectory=${APP_DIR}
ExecStart=${VENV_DIR}/bin/celery \\
    -A FWMsg beat \\
    --loglevel=info \\
    --scheduler django_celery_beat.schedulers:DatabaseScheduler
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=fwmsg-celerybeat

[Install]
WantedBy=multi-user.target
EOF

    msg_ok "Systemd service files written."

    # ── Step 12: Nginx ────────────────────────────────────────────────────────

    msg_step "Configuring Nginx"

    # Rate-limit zones must be at http level — use conf.d (auto-included by nginx.conf)
    cat > /etc/nginx/conf.d/fwmsg-ratelimit.conf <<'NGINXEOF'
limit_req_zone $binary_remote_addr zone=login:10m  rate=5r/m;
limit_req_zone $binary_remote_addr zone=global:10m rate=30r/s;
NGINXEOF

    cat > /etc/nginx/sites-available/fwmsg <<EOF
upstream daphne {
    server ${DAPHNE_HOST}:${DAPHNE_PORT};
}

server {
    listen 80;
    server_name ${ORG_NAME} localhost;

    client_max_body_size 50M;

    location /static/ {
        alias ${APP_DIR}/static/;
        expires 7d;
        access_log off;
    }

    location /media/ {
        alias ${APP_DIR}/media/;
        expires 7d;
        access_log off;
    }

    # Strict rate limit on login / auth endpoints
    location ~* ^/(login|accounts/login|api/token|admin/login) {
        limit_req zone=login burst=3 nodelay;
        limit_req_status 429;
        proxy_pass http://daphne;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_read_timeout 86400s;
        proxy_send_timeout 86400s;
    }

    location / {
        limit_req zone=global burst=50 nodelay;
        limit_req_status 429;
        proxy_pass http://daphne;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_read_timeout 86400s;
        proxy_send_timeout 86400s;
    }
}
EOF

    ln -sf /etc/nginx/sites-available/fwmsg /etc/nginx/sites-enabled/fwmsg
    rm -f /etc/nginx/sites-enabled/default
    nginx -t
    systemctl enable --now nginx
    systemctl reload nginx
    msg_ok "Nginx configured."

    # ── Step 12b: Security hardening ──────────────────────────────────────────

    msg_step "Security hardening"

    # ── UFW firewall ──────────────────────────────────────────────────────────

    msg_info "Configuring UFW firewall..."
    apt-get install -y -qq ufw
    ufw --force reset                 # start from a clean slate
    ufw default deny incoming
    ufw default allow outgoing
    ufw allow 80/tcp comment 'Nginx HTTP'
    # Port 22 (SSH) intentionally never opened — access via pct enter from Proxmox host
    ufw --force enable
    msg_ok "UFW enabled: only port 80 open."

    # ── Persistent journald logging ───────────────────────────────────────────

    msg_info "Configuring persistent journald logging..."
    mkdir -p /etc/systemd/journald.conf.d
    cat > /etc/systemd/journald.conf.d/fwmsg.conf <<'EOF'
[Journal]
Storage=persistent
Compress=yes
MaxRetentionSec=90day
MaxFileSec=7day
SystemMaxUse=500M
SystemKeepFree=100M
RateLimitIntervalSec=30s
RateLimitBurst=1000
EOF
    systemctl restart systemd-journald
    msg_ok "journald: persistent storage, 90-day retention, 500 MB cap."

    # ── Logrotate for Nginx logs ──────────────────────────────────────────────

    msg_info "Configuring logrotate for Nginx..."
    cat > /etc/logrotate.d/fwmsg-nginx <<'EOF'
/var/log/nginx/*.log {
    daily
    rotate 30
    compress
    delaycompress
    missingok
    notifempty
    sharedscripts
    postrotate
        [ -f /var/run/nginx.pid ] && kill -USR1 $(cat /var/run/nginx.pid)
    endscript
}
EOF
    msg_ok "Logrotate: daily rotation, 30-day history, compressed."

    # ── Fail2ban ──────────────────────────────────────────────────────────────

    msg_info "Installing and configuring fail2ban..."
    apt-get install -y -qq fail2ban

    cat > /etc/fail2ban/jail.d/fwmsg.conf <<'EOF'
[DEFAULT]
bantime  = 1h
findtime = 10m
maxretry = 5
banaction = ufw

[nginx-http-auth]
enabled = true

[nginx-limit-req]
enabled = true
logpath = /var/log/nginx/error.log
EOF

    systemctl enable --now fail2ban
    msg_ok "fail2ban: nginx-http-auth + nginx-limit-req jails active, banning via UFW."

    # ── Unattended security upgrades ──────────────────────────────────────────

    msg_info "Configuring unattended security upgrades..."
    apt-get install -y -qq unattended-upgrades apt-listchanges

    cat > /etc/apt/apt.conf.d/50unattended-upgrades <<'EOF'
Unattended-Upgrade::Allowed-Origins {
    "${distro_id}:${distro_codename}-security";
};
Unattended-Upgrade::AutoFixInterruptedDpkg "true";
Unattended-Upgrade::MinimalSteps "true";
Unattended-Upgrade::Remove-Unused-Dependencies "true";
Unattended-Upgrade::Automatic-Reboot "false";
EOF

    cat > /etc/apt/apt.conf.d/20auto-upgrades <<'EOF'
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Unattended-Upgrade "1";
EOF

    msg_ok "Unattended-upgrades: security patches applied daily, no auto-reboot."

    # ── Fix permissions ───────────────────────────────────────────────────────

    msg_info "Setting file permissions..."
    chown -R www-data:www-data "${INSTALL_DIR}"
    chmod -R 750 "${INSTALL_DIR}"
    chmod 640 "${SECRETS_FILE}"
    msg_ok "Permissions set."

    # ── Start all FWMsg services ──────────────────────────────────────────────

    msg_step "Starting FWMsg services"
    systemctl daemon-reload
    systemctl enable --now fwmsg-daphne
    systemctl enable --now fwmsg-celery
    systemctl enable --now fwmsg-celerybeat
    msg_ok "All services started."

    # ── Step 13: Django test suite ────────────────────────────────────────────

    msg_step "Running Django test suite (parallel)"
    echo ""
    cd "${APP_DIR}"

    set +e
    "${PYTHON}" manage.py test --parallel 4 -v 2 2>&1 | tee /tmp/fwmsg-test-output.txt
    TEST_EXIT_CODE=${PIPESTATUS[0]}
    set -e

    echo ""
    if [[ ${TEST_EXIT_CODE} -eq 0 ]]; then
        msg_ok "All tests passed."
    else
        msg_warn "Some tests failed (exit code ${TEST_EXIT_CODE})."
        msg_warn "Review /tmp/fwmsg-test-output.txt for details."
        msg_warn "The app is installed and may still work — email/VAPID tests can fail until configured."
    fi

    # ── Step 14: CT-side summary ──────────────────────────────────────────────

    echo ""
    echo "================================================================"
    echo -e "${GREEN}${BOLD}  FWMsg app install complete inside CT!${NC}"
    echo "================================================================"
    echo ""
    echo "  URL        : http://${ORG_NAME}"
    echo "  App dir    : ${APP_DIR}"
    echo "  Secrets    : ${SECRETS_FILE}"
    echo ""
    echo "  Services to check:"
    echo "    systemctl status fwmsg-daphne"
    echo "    systemctl status fwmsg-celery"
    echo "    systemctl status fwmsg-celerybeat"
    echo "    systemctl status nginx redis-server postgresql"
    echo ""
    echo "  Logs:"
    echo "    journalctl -u fwmsg-daphne -f"
    echo "    journalctl -u fwmsg-celery -f"
    echo ""
    echo "  IMPORTANT — edit ${SECRETS_FILE} to configure:"
    echo "    email/SMTP credentials, IMAP settings"
    if [[ ${TEST_EXIT_CODE} -ne 0 ]]; then
        echo ""
        echo -e "  ${YELLOW}WARNING: Test failures detected. See /tmp/fwmsg-test-output.txt${NC}"
    fi
    echo "================================================================"
}

# ==============================================================================
# ENTRYPOINT
# ==============================================================================

case "${1:-}" in
    --inside-ct)
        inside_ct_install
        ;;
    *)
        host_setup
        ;;
esac
