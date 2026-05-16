# 🌉 TunnelBridge

مدیریت تانل بین سرور ایران و خارج از طریق داشبورد وب.

---

## 🚀 نصب سریع

### سرور خارج (اول نصب کنید)
```bash
bash <(curl -fsSL https://raw.githubusercontent.com/sadrr7/TunnelBridge/main/install.sh)
# انتخاب: 2 (خارج)
```

### سرور ایران (بعد نصب کنید)
```bash
bash <(curl -fsSL https://raw.githubusercontent.com/sadrr7/TunnelBridge/main/install.sh)
# انتخاب: 1 (ایران) → IP سرور خارج را وارد کنید
```

### اگر GitHub محدود است:
```bash
bash <(curl -fsSL https://fastly.jsdelivr.net/gh/sadrr7/TunnelBridge@main/install.sh)
```

---

## 🖥 داشبورد

بعد از نصب، داشبورد روی پورت **8080** در دسترس است:

```
سرور خارج:  http://IP_خارج:8080
سرور ایران: http://IP_ایران:8080
```

---

## ⚙️ راهنمای ساخت تانل از داشبورد

### مرحله ۱ — روی سرور خارج (exit)

داشبورد را باز کنید → **+ تانل جدید**:

| فیلد | مقدار |
|------|-------|
| نام | هر اسمی (مثلاً `main-tunnel`) |
| روش | GOST v3 یا VLESS یا هر روش دیگر |
| نقش | 🌍 خارج (خروجی) |
| پورت محلی | پورتی که سرور خارج listen میکند (مثلاً `10443`) |
| هدف نهایی (host) | `127.0.0.1` |
| هدف نهایی (port) | پورت سرویس اصلی (مثلاً Xray: `10085`) |

سپس **▶ شروع** بزنید.

---

### مرحله ۲ — روی سرور ایران (entry)

داشبورد را باز کنید → **+ تانل جدید**:

| فیلد | مقدار |
|------|-------|
| نام | همان اسم (مثلاً `main-tunnel`) |
| روش | **همان روش سرور خارج** |
| نقش | 🇮🇷 ایران (ورودی) |
| پورت محلی | پورتی که کاربر ایران به آن وصل میشود (مثلاً `10443`) |
| آدرس سرور ریموت | IP سرور خارج |
| پورت سرور ریموت | همان پورت محلی سرور خارج (مثلاً `10443`) |

سپس **▶ شروع** بزنید.

---

## 🛠 روش‌های تانل

| روش | توضیح | بهترین برای |
|-----|-------|-------------|
| **GOST v3** | TLS / WS+TLS / HTTP2 / QUIC | ساده‌ترین، پایدارترین |
| **Reverse TLS** | تانل معکوس با GOST | فایروال‌های سخت‌گیر |
| **VLESS Reverse** | Xray + REALITY + xtls-rprx-vision | دور زدن DPI |
| **Hysteria2** | QUIC با سرعت بالا | سرعت بالا، پینگ پایین |
| **Rathole** | TCP relay سریع (Rust) | سرورهای پشت NAT |
| **WireGuard TLS** | WireGuard داخل TLS | امنیت بالا + دور زدن UDP filter |
| **OpenVPN** | VPN کلاسیک TCP | سازگاری با همه دستگاه‌ها |

---

## 🔒 راهنمای VLESS Reverse (پیشرفته)

این روش نیاز به کلید Reality دارد. **روی سرور خارج** اجرا کنید:

```bash
xray x25519
```

خروجی:
```
Private key: <PRIVATE_KEY>
Public key:  <PUBLIC_KEY>
```

- هنگام ساخت تانل روی **سرور خارج**: `Reality Private Key` = `<PRIVATE_KEY>`
- هنگام ساخت تانل روی **سرور ایران**: `Reality Public Key` = `<PUBLIC_KEY>`
- UUID باید در هر دو سرور **یکسان** باشد

---

## 🧪 تست تانل

### از داشبورد:
دکمه **⚡** کنار هر تانل → اتصال و latency را نشان میدهد.

### از ترمینال:
```bash
# تست اتصال از سرور ایران به خارج
curl -x socks5://127.0.0.1:LOCAL_PORT https://api.ipify.org

# یا با netcat
nc -zv IP_خارج PORT_خارج
```

---

## 🔗 معماری با Spiritus/Xray

```
کاربر ایران
    ↓
[TunnelBridge ایران :10443]
    ↓  (تانل رمزشده)
[TunnelBridge خارج :10443]
    ↓
[Xray/Spiritus :10085]
```

---

## 💻 دستورات مفید

```bash
systemctl status tunnelbridge      # وضعیت سرویس
systemctl restart tunnelbridge     # ریستارت
journalctl -u tunnelbridge -f      # لاگ زنده
nano /opt/tunnelbridge/.env        # ویرایش تنظیمات
python3 /opt/tunnelbridge/check_syntax.py  # تست سلامت کد
```

---

## 🔄 بروزرسانی

```bash
cd /opt/tunnelbridge
bash update.sh
```

---

## 🐛 عیب‌یابی

| مشکل | راه‌حل |
|------|--------|
| داشبورد باز نمیشود | `systemctl status tunnelbridge` → لاگ را بررسی کنید |
| تانل شروع نمیشود | دکمه 📋 لاگ → خطا را ببینید. دکمه ⚙ خروجی process |
| VLESS کار نمیکند | `xray x25519` اجرا کنید و کلیدها را وارد کنید |
| Hysteria2 نصب نیست | `wget -O /usr/local/bin/hysteria2 https://github.com/apernet/hysteria/releases/latest/download/hysteria-linux-amd64 && chmod +x /usr/local/bin/hysteria2` |
| پورت در دسترس نیست | `lsof -i :PORT` → process قبلی را kill کنید |
| فایروال | `ufw allow PORT` یا `iptables -A INPUT -p tcp --dport PORT -j ACCEPT` |
