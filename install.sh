#!/bin/bash
# ═══════════════════════════════════════════════════════════════
#  TunnelBridge Installer
#  https://github.com/SwanFlutter/TunnelBridge
# ═══════════════════════════════════════════════════════════════
set -eo pipefail

# ── رنگ‌ها ────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'

ok()   { echo -e "${GREEN}  ✓ $1${NC}"; }
info() { echo -e "${CYAN}  → $1${NC}"; }
warn() { echo -e "${YELLOW}  ⚠ $1${NC}"; }
err()  { echo -e "${RED}  ✗ $1${NC}"; exit 1; }
step() { echo -e "\n${BOLD}${BLUE}[$2/$TOTAL] $1${NC}"; }

TOTAL=9
INSTALL_DIR="/opt/tunnelbridge"
SERVICE_NAME="tunnelbridge"
REPO="https://github.com/SwanFlutter/TunnelBridge"
PYTHON_MIN="3.10"

# ── بنر ───────────────────────────────────────────────────────
clear
echo -e "${BOLD}${CYAN}"
cat << 'EOF'
  ╔══════════════════════════════════════════╗
  ║         🌉  TunnelBridge Installer       ║
  ║     Iran ↔ Foreign Server Tunnel         ║
  ╚══════════════════════════════════════════╝
EOF
echo -e "${NC}"
echo -e "  ${BOLD}ریپو:${NC} $REPO"
echo -e "  ${BOLD}مسیر نصب:${NC} $INSTALL_DIR"
echo ""

# ── بررسی root ────────────────────────────────────────────────
[[ $EUID -ne 0 ]] && err "این اسکریپت باید با root اجرا شود: sudo bash install.sh"

# ── بررسی سیستم‌عامل ──────────────────────────────────────────
if [[ -f /etc/os-release ]]; then
    source /etc/os-release
    info "سیستم‌عامل: $PRETTY_NAME"

    if [[ "$ID" == "ubuntu" ]]; then
        VER_MAJOR=$(echo "$VERSION_ID" | cut -d. -f1)
        if [[ "$VER_MAJOR" -lt 20 ]]; then
            err "Ubuntu 20.04+ لازم است. نسخه شما: $VERSION_ID"
        elif [[ "$VERSION_ID" == "25.10" ]]; then
            warn "Ubuntu 25.10 (Oracular+) — نسخه interim، پشتیبانی محدود"
            warn "برای سرور production توصیه می‌شود از Ubuntu 24.04 LTS استفاده کنید"
            ok "Ubuntu 25.10 شناسایی شد — ادامه نصب..."
        elif [[ "$VERSION_ID" == "25.04" ]]; then
            warn "Ubuntu 25.04 (Plucky Puffin) — نسخه interim، پشتیبانی تا ژانویه ۲۰۲۶"
            warn "برای سرور production توصیه می‌شود از Ubuntu 24.04 LTS استفاده کنید"
        elif [[ "$VERSION_ID" == "24.04" ]]; then
            ok "Ubuntu 24.04 LTS — نسخه پایدار و توصیه‌شده"
        else
            info "Ubuntu $VERSION_ID شناسایی شد"
        fi
    elif [[ "$ID" == "debian" ]]; then
        info "Debian $VERSION_ID شناسایی شد"
    else
        warn "این اسکریپت برای Ubuntu/Debian بهینه شده — ادامه با احتیاط"
    fi
fi

# ── معماری ────────────────────────────────────────────────────
ARCH=$(uname -m)
case $ARCH in
    x86_64)  ARCH_GOST="amd64"; ARCH_XRAY="64"; ARCH_RATHOLE="x86_64-unknown-linux-gnu" ;;
    aarch64) ARCH_GOST="arm64"; ARCH_XRAY="arm64-v8a"; ARCH_RATHOLE="aarch64-unknown-linux-gnu" ;;
    *)       err "معماری $ARCH پشتیبانی نمی‌شود" ;;
esac
info "معماری: $ARCH"

echo ""
read -p "  آیا نصب شروع شود؟ (y/n): " CONFIRM
[[ "$CONFIRM" != "y" && "$CONFIRM" != "Y" ]] && echo "لغو شد." && exit 0

# ══════════════════════════════════════════════════════════════
# STEP 1 — بسته‌های سیستمی
# ══════════════════════════════════════════════════════════════
step "نصب بسته‌های سیستمی" 1

info "بروزرسانی apt..."
apt-get update -qq

info "نصب وابستگی‌ها..."
apt-get install -y -qq \
    curl wget git unzip python3 python3-pip python3-venv \
    ca-certificates openssl net-tools lsof \
    > /dev/null 2>&1

ok "بسته‌های سیستمی نصب شدند"

# بررسی نسخه Python
PY_VER=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
info "Python $PY_VER شناسایی شد"
python3 -c "import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)" \
    || err "Python 3.10+ لازم است (نصب‌شده: $PY_VER)"

# ══════════════════════════════════════════════════════════════
# STEP 2 — دانلود کد از گیتهاب
# ══════════════════════════════════════════════════════════════
step "دانلود TunnelBridge از GitHub" 2

if [[ -d "$INSTALL_DIR" ]]; then
    warn "مسیر $INSTALL_DIR وجود دارد — بروزرسانی..."
    cd "$INSTALL_DIR"
    git pull origin main 2>&1 | sed 's/^/    /' || warn "git pull ناموفق بود — از کد موجود استفاده می‌شود"
else
    info "کلون کردن ریپو..."
    git clone "$REPO" "$INSTALL_DIR" 2>&1 | sed 's/^/    /'
fi

ok "کد دانلود شد → $INSTALL_DIR"

# ══════════════════════════════════════════════════════════════
# STEP 3 — نصب Xray-core
# ══════════════════════════════════════════════════════════════
step "نصب Xray-core" 3

if command -v xray &>/dev/null; then
    XRAY_VER=$(xray version 2>/dev/null | head -1 || echo "نامشخص")
    warn "Xray قبلاً نصب است: $XRAY_VER — رد شد"
else
    info "دانلود Xray-core (آخرین نسخه)..."
    XRAY_URL="https://github.com/XTLS/Xray-core/releases/latest/download/Xray-linux-${ARCH_XRAY}.zip"
    wget -q --show-progress "$XRAY_URL" -O /tmp/xray.zip
    
    info "استخراج..."
    unzip -q /tmp/xray.zip -d /tmp/xray_extract
    mv /tmp/xray_extract/xray /usr/local/bin/xray
    chmod +x /usr/local/bin/xray
    rm -rf /tmp/xray.zip /tmp/xray_extract
    
    XRAY_VER=$(xray version 2>/dev/null | head -1 || echo "نصب شد")
    ok "Xray-core نصب شد: $XRAY_VER"
fi

# ══════════════════════════════════════════════════════════════
# STEP 4 — نصب GOST v3
# ══════════════════════════════════════════════════════════════
step "نصب GOST v3" 4

if command -v gost &>/dev/null; then
    warn "GOST قبلاً نصب است — رد شد"
else
    info "دانلود GOST v3..."
    GOST_VER="3.0.0"
    GOST_URL="https://github.com/go-gost/gost/releases/download/v${GOST_VER}/gost_${GOST_VER}_linux_${ARCH_GOST}.tar.gz"
    wget -q --show-progress "$GOST_URL" -O /tmp/gost.tar.gz
    
    info "استخراج..."
    tar -xzf /tmp/gost.tar.gz -C /tmp
    mv /tmp/gost /usr/local/bin/gost
    chmod +x /usr/local/bin/gost
    rm -f /tmp/gost.tar.gz
    
    ok "GOST v${GOST_VER} نصب شد"
fi

# ══════════════════════════════════════════════════════════════
# STEP 5 — نصب Rathole
# ══════════════════════════════════════════════════════════════
step "نصب Rathole" 5

if command -v rathole &>/dev/null; then
    warn "Rathole قبلاً نصب است — رد شد"
else
    info "دانلود Rathole (آخرین نسخه)..."
    RATHOLE_URL="https://github.com/rapiz1/rathole/releases/latest/download/rathole-${ARCH_RATHOLE}.zip"
    wget -q --show-progress "$RATHOLE_URL" -O /tmp/rathole.zip
    
    info "استخراج..."
    unzip -q /tmp/rathole.zip -d /tmp/rathole_extract
    mv /tmp/rathole_extract/rathole /usr/local/bin/rathole
    chmod +x /usr/local/bin/rathole
    rm -rf /tmp/rathole.zip /tmp/rathole_extract
    
    ok "Rathole نصب شد"
fi

# ══════════════════════════════════════════════════════════════
# STEP 6 — نصب Hysteria2
# ══════════════════════════════════════════════════════════════
step "نصب Hysteria2" 6

if command -v hysteria2 &>/dev/null; then
    warn "Hysteria2 قبلاً نصب است — رد شد"
else
    info "دانلود Hysteria2 (آخرین نسخه)..."
    HYSTERIA2_URL="https://github.com/apernet/hysteria/releases/latest/download/hysteria-linux-${ARCH_GOST}"
    wget -q --show-progress "$HYSTERIA2_URL" -O /usr/local/bin/hysteria2
    chmod +x /usr/local/bin/hysteria2
    ok "Hysteria2 نصب شد"
fi

# ══════════════════════════════════════════════════════════════
# STEP 7 — نصب OpenVPN
# ══════════════════════════════════════════════════════════════
step "نصب OpenVPN" 7

if command -v openvpn &>/dev/null; then
    warn "OpenVPN قبلاً نصب است — رد شد"
else
    info "نصب OpenVPN از apt..."
    apt-get install -y -qq openvpn > /dev/null 2>&1
    ok "OpenVPN نصب شد"
fi

# ══════════════════════════════════════════════════════════════
# STEP 8 — محیط Python و وابستگی‌ها
# ══════════════════════════════════════════════════════════════
step "نصب وابستگی‌های Python" 8

cd "$INSTALL_DIR"

info "ساخت virtual environment..."
python3 -m venv venv
source venv/bin/activate

info "نصب پکیج‌ها..."
pip install --upgrade pip -q
pip install -r requirements.txt 2>&1 | grep -E "^(Collecting|Successfully|ERROR)" | sed 's/^/    /' || true

ok "وابستگی‌های Python نصب شدند"

# ── تنظیم .env ────────────────────────────────────────────────
if [[ ! -f "$INSTALL_DIR/.env" ]]; then
    cp "$INSTALL_DIR/.env.example" "$INSTALL_DIR/.env"
    SECRET=$(openssl rand -hex 32)
    sed -i "s/replace-with-random-64-char-string/$SECRET/" "$INSTALL_DIR/.env"
    info "فایل .env ایجاد شد"
else
    info "فایل .env موجود است — بررسی متغیرهای جدید..."
    # اضافه کردن متغیرهای جدید اگر وجود ندارند
    grep -q "^HYSTERIA2_BIN" "$INSTALL_DIR/.env" || echo "HYSTERIA2_BIN=/usr/local/bin/hysteria2" >> "$INSTALL_DIR/.env"
    grep -q "^OPENVPN_BIN"   "$INSTALL_DIR/.env" || echo "OPENVPN_BIN=/usr/sbin/openvpn"         >> "$INSTALL_DIR/.env"
    grep -q "^XRAY_BIN"      "$INSTALL_DIR/.env" || echo "XRAY_BIN=/usr/local/bin/xray"           >> "$INSTALL_DIR/.env"
    grep -q "^GOST_BIN"      "$INSTALL_DIR/.env" || echo "GOST_BIN=/usr/local/bin/gost"           >> "$INSTALL_DIR/.env"
    grep -q "^RATHOLE_BIN"   "$INSTALL_DIR/.env" || echo "RATHOLE_BIN=/usr/local/bin/rathole"     >> "$INSTALL_DIR/.env"
    ok "متغیرهای .env بررسی شدند"
fi

# ── پرسیدن نقش سرور ──────────────────────────────────────────
echo ""
echo -e "  ${BOLD}نقش این سرور را انتخاب کنید:${NC}"
echo "    1) 🇮🇷 ایران  (ورودی — entry point)"
echo "    2) 🌍 خارج   (خروجی — exit point)"
read -p "  انتخاب (1/2): " ROLE_CHOICE

if [[ "$ROLE_CHOICE" == "1" ]]; then
    sed -i "s/SERVER_ROLE=.*/SERVER_ROLE=iran/" "$INSTALL_DIR/.env"
    read -p "  آدرس IP سرور خارج: " FOREIGN_IP
    sed -i "s/FOREIGN_SERVER_IP=.*/FOREIGN_SERVER_IP=$FOREIGN_IP/" "$INSTALL_DIR/.env"
    ok "نقش: ایران | سرور خارج: $FOREIGN_IP"
else
    sed -i "s/SERVER_ROLE=.*/SERVER_ROLE=foreign/" "$INSTALL_DIR/.env"
    ok "نقش: خارج (exit)"
fi

# ══════════════════════════════════════════════════════════════
# STEP 9 — سرویس systemd
# ══════════════════════════════════════════════════════════════
step "ایجاد سرویس systemd" 9

cat > /etc/systemd/system/${SERVICE_NAME}.service << EOF
[Unit]
Description=TunnelBridge - Server Tunnel Manager
After=network.target
Wants=network-online.target

[Service]
Type=simple
User=root
WorkingDirectory=${INSTALL_DIR}
EnvironmentFile=${INSTALL_DIR}/.env
ExecStart=${INSTALL_DIR}/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8080
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable "$SERVICE_NAME" > /dev/null 2>&1
systemctl start "$SERVICE_NAME"

sleep 2
if systemctl is-active --quiet "$SERVICE_NAME"; then
    ok "سرویس systemd فعال و در حال اجراست"
else
    warn "سرویس شروع نشد — لاگ:"
    journalctl -u "$SERVICE_NAME" -n 20 --no-pager | sed 's/^/    /'
fi

# ══════════════════════════════════════════════════════════════
# خلاصه نهایی
# ══════════════════════════════════════════════════════════════
SERVER_IP=$(curl -s --max-time 5 ifconfig.me 2>/dev/null || hostname -I | awk '{print $1}')

echo ""
echo -e "${BOLD}${GREEN}"
cat << 'EOF'
  ╔══════════════════════════════════════════╗
  ║        ✅  نصب با موفقیت انجام شد        ║
  ╚══════════════════════════════════════════╝
EOF
echo -e "${NC}"
echo -e "  ${BOLD}داشبورد:${NC}       http://${SERVER_IP}:8080"
echo -e "  ${BOLD}مسیر نصب:${NC}     $INSTALL_DIR"
echo -e "  ${BOLD}فایل تنظیمات:${NC} $INSTALL_DIR/.env"
echo ""
echo -e "  ${BOLD}دستورات مفید:${NC}"
echo -e "    systemctl status $SERVICE_NAME     # وضعیت سرویس"
echo -e "    systemctl restart $SERVICE_NAME    # ریستارت"
echo -e "    journalctl -u $SERVICE_NAME -f     # لاگ زنده"
echo -e "    nano $INSTALL_DIR/.env             # ویرایش تنظیمات"
echo ""
echo -e "  ${BOLD}بایناری‌های نصب‌شده:${NC}"
command -v xray      &>/dev/null && echo -e "    ✓ xray      → $(which xray)"
command -v gost      &>/dev/null && echo -e "    ✓ gost      → $(which gost)"
command -v rathole   &>/dev/null && echo -e "    ✓ rathole   → $(which rathole)"
command -v hysteria2 &>/dev/null && echo -e "    ✓ hysteria2 → $(which hysteria2)"
command -v openvpn   &>/dev/null && echo -e "    ✓ openvpn   → $(which openvpn)"
echo ""
