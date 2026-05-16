"""Run this on the server to verify syntax: python3 check_syntax.py"""
import ast, sys

files = [
    "app/tunnel_engine.py",
    "app/config.py",
    "app/api/system.py",
    "app/api/tunnels.py",
    "app/models.py",
    "app/main.py",
]

ok = True
for f in files:
    try:
        with open(f, encoding="utf-8") as fh:
            ast.parse(fh.read())
        print(f"  ✓ {f}")
    except SyntaxError as e:
        print(f"  ✗ SYNTAX ERROR in {f}: line {e.lineno}: {e.msg}")
        ok = False
    except FileNotFoundError:
        print(f"  ? NOT FOUND: {f}")
        ok = False

print()
if ok:
    print("✅ همه فایل‌ها سالم هستند — می‌توانید سرویس را ریستارت کنید")
    print("   systemctl restart tunnelbridge")
else:
    print("❌ خطای syntax پیدا شد — سرویس را ریستارت نکنید")
    sys.exit(1)
