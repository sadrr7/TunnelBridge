#!/bin/bash
# ═══════════════════════════════════════════════════════════════
#  TunnelBridge Updater — اجرا روی سرور
#  فایل‌های اصلاح‌شده را از ریپو می‌گیرد و سرویس را ریستارت می‌کند
# ═══════════════════════════════════════════════════════════════

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'

ok()   { echo -e "${GREEN}  ✓ $1${NC}"; }
info() { echo -e "${CYAN}  → $1${NC}"; }
warn() { echo -e "${YELLOW}  ⚠ $1${NC}"; }
err()  { echo -e "${RED}  ✗ $1${NC}"; exit 1; }

INSTALL_DIR="/opt/tunnelbridge"
SERVICE_NAME="tunnelbridge"

[[ $EUID -ne 0 ]] && err "با root اجرا کنید: sudo bash update.sh"
[[ ! -d "$INSTALL_DIR" ]] && err "TunnelBridge نصب نشده: $INSTALL_DIR"

echo -e "\n${BOLD}${CYAN}  🔄 TunnelBridge Updater${NC}\n"

# ── بکاپ .env ─────────────────────────────────────────────────
info "بکاپ .env..."
cp "$INSTALL_DIR/.env" "$INSTALL_DIR/.env.bak"
ok ".env.bak ذخیره شد"

# ── دریافت آخرین کد ───────────────────────────────────────────
info "دریافت آخرین کد از GitHub..."
cd "$INSTALL_DIR"
git fetch origin main 2>&1 | sed 's/^/    /'
git reset --hard origin/main 2>&1 | sed 's/^/    /'
ok "کد آپدیت شد"

# ── بازگرداندن .env ───────────────────────────────────────────
cp "$INSTALL_DIR/.env.bak" "$INSTALL_DIR/.env"
ok ".env بازگردانده شد"

# ── اضافه کردن متغیرهای جدید به .env ─────────────────────────
info "بررسی متغیرهای جدید .env..."
grep -q "^HYSTERIA2_BIN" "$INSTALL_DIR/.env" || echo "HYSTERIA2_BIN=/usr/local/bin/hysteria2" >> "$INSTALL_DIR/.env"
grep -q "^OPENVPN_BIN"   "$INSTALL_DIR/.env" || echo "OPENVPN_BIN=/usr/sbin/openvpn"         >> "$INSTALL_DIR/.env"
grep -q "^XRAY_BIN"      "$INSTALL_DIR/.env" || echo "XRAY_BIN=/usr/local/bin/xray"           >> "$INSTALL_DIR/.env"
grep -q "^GOST_BIN"      "$INSTALL_DIR/.env" || echo "GOST_BIN=/usr/local/bin/gost"           >> "$INSTALL_DIR/.env"
grep -q "^RATHOLE_BIN"   "$INSTALL_DIR/.env" || echo "RATHOLE_BIN=/usr/local/bin/rathole"     >> "$INSTALL_DIR/.env"
ok "متغیرهای .env بررسی شدند"

# ── آپدیت وابستگی‌های Python ──────────────────────────────────
info "آپدیت وابستگی‌های Python..."
source "$INSTALL_DIR/venv/bin/activate"
pip install -q --upgrade pip
pip install -q -r "$INSTALL_DIR/requirements.txt"
ok "وابستگی‌ها آپدیت شدند"

# ── تست syntax ────────────────────────────────────────────────
info "بررسی syntax فایل‌های Python..."
cd "$INSTALL_DIR"
python3 check_syntax.py || err "خطای syntax — سرویس ریستارت نشد"

# ── ریستارت سرویس ─────────────────────────────────────────────
info "ریستارت سرویس..."
systemctl restart "$SERVICE_NAME"
sleep 3

if systemctl is-active --quiet "$SERVICE_NAME"; then
    ok "سرویس با موفقیت ریستارت شد"
    echo ""
    echo -e "  ${BOLD}داشبورد:${NC} http://$(curl -s --max-time 3 ifconfig.me 2>/dev/null || hostname -I | awk '{print $1}'):8080"
else
    err "سرویس شروع نشد — لاگ:"
    journalctl -u "$SERVICE_NAME" -n 30 --no-pager
fi
