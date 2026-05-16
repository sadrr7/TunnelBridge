"""System info & binary status API"""

import os
import asyncio
import psutil
from fastapi import APIRouter
from fastapi.responses import PlainTextResponse
from app.config import settings
from app import tunnel_engine

router = APIRouter(prefix="/api/system", tags=["system"])


@router.get("/health")
async def health():
    return {"status": "ok", "app": settings.APP_NAME, "version": settings.APP_VERSION}


@router.get("/info")
async def system_info():
    cpu = psutil.cpu_percent(interval=0.2)
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    net = psutil.net_io_counters()

    binaries = {
        "xray":      await tunnel_engine.check_binary("xray", settings.XRAY_BIN),
        "gost":      await tunnel_engine.check_binary("gost", settings.GOST_BIN),
        "rathole":   await tunnel_engine.check_binary("rathole", settings.RATHOLE_BIN),
        "hysteria2": await tunnel_engine.check_binary("hysteria2", settings.HYSTERIA2_BIN),
        "openvpn":   await tunnel_engine.check_binary("openvpn", settings.OPENVPN_BIN),
    }

    return {
        "server_role": settings.SERVER_ROLE,
        "foreign_server": settings.FOREIGN_SERVER_IP,
        "cpu_percent": cpu,
        "memory": {
            "total_gb": round(mem.total / 1e9, 2),
            "used_gb": round(mem.used / 1e9, 2),
            "percent": mem.percent,
        },
        "disk": {
            "total_gb": round(disk.total / 1e9, 2),
            "used_gb": round(disk.used / 1e9, 2),
            "percent": disk.percent,
        },
        "network": {
            "bytes_sent": net.bytes_sent,
            "bytes_recv": net.bytes_recv,
        },
        "binaries": binaries,
        "active_tunnels": len([s for s in tunnel_engine.get_all_statuses().values() if s == "running"]),
    }


@router.get("/service-logs", response_class=PlainTextResponse)
async def service_logs(lines: int = 100):
    """Return recent journalctl logs for the tunnelbridge service."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "journalctl", "-u", "tunnelbridge", "-n", str(lines), "--no-pager", "--output=short",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=5.0)
        return stdout.decode(errors="replace")
    except Exception as e:
        return f"لاگ در دسترس نیست: {e}"
