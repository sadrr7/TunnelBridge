"""
TunnelBridge - Tunnel Engine
Supports: VLESS-Reverse (Xray), GOST v3, Rathole, Hysteria2, WireGuard-TLS, Reverse-TLS, OpenVPN
"""

import json
import logging
import os
import select as _select
import signal
import subprocess
import tempfile
import uuid
from typing import Dict, Optional

from app.config import settings

logger = logging.getLogger(__name__)

# Active processes: tunnel_id -> subprocess.Popen
_procs: Dict[str, subprocess.Popen] = {}


# ══════════════════════════════════════════════════════════════
#  Config Generators
# ══════════════════════════════════════════════════════════════

def _xray_reverse_iran_cfg(local_port: int, foreign_ip: str, foreign_port: int,
                            uuid_str: str, public_key: str = "") -> dict:
    """
    Iran (entry) side: listens on local_port, forwards all traffic to foreign server via VLESS+Reality.
    public_key: the Reality public key from the foreign server (xray x25519 output).
    """
    reality_settings: dict = {
        "serverName": "digikala.com",
        "fingerprint": "chrome",
        "shortId": uuid_str[:8],
    }
    if public_key:
        reality_settings["publicKey"] = public_key

    return {
        "log": {"loglevel": "warning"},
        "inbounds": [
            {
                "tag": "tunnel-in",
                "port": local_port,
                "listen": "0.0.0.0",
                "protocol": "dokodemo-door",
                "settings": {
                    "network": "tcp,udp",
                    "followRedirect": False
                },
                "sniffing": {"enabled": False}
            }
        ],
        "outbounds": [
            {
                "tag": "tunnel-out",
                "protocol": "vless",
                "settings": {
                    "vnext": [{
                        "address": foreign_ip,
                        "port": foreign_port,
                        "users": [{"id": uuid_str, "encryption": "none", "flow": "xtls-rprx-vision"}]
                    }]
                },
                "streamSettings": {
                    "network": "tcp",
                    "security": "reality",
                    "realitySettings": reality_settings
                }
            },
            {"tag": "direct", "protocol": "freedom"},
            {"tag": "block", "protocol": "blackhole"}
        ],
        "routing": {
            "rules": [{"type": "field", "inboundTag": ["tunnel-in"], "outboundTag": "tunnel-out"}]
        }
    }


def _xray_reverse_foreign_cfg(listen_port: int, target_host: str, target_port: int,
                               uuid_str: str, reality_private_key: str = "",
                               reality_public_key: str = "") -> dict:
    """
    Foreign (exit) side: accepts VLESS+Reality connections, forwards to target_host:target_port.
    reality_private_key MUST be a real x25519 key (generate with: xray x25519).
    If empty, a placeholder is used — tunnel will fail until a real key is provided.
    """
    if not reality_private_key:
        logger.warning(
            "VLESS Reality private key is empty! "
            "Generate one with: xray x25519  and set it in extra_config.reality_private_key"
        )
        reality_private_key = "REPLACE_WITH_REAL_KEY_run_xray_x25519"

    reality_settings: dict = {
        "show": False,
        "dest": f"{target_host}:{target_port}",
        "serverNames": ["digikala.com"],
        "privateKey": reality_private_key,
        "shortIds": [uuid_str[:8]]
    }
    if reality_public_key:
        reality_settings["publicKey"] = reality_public_key

    return {
        "log": {"loglevel": "warning"},
        "inbounds": [
            {
                "tag": "vless-in",
                "port": listen_port,
                "listen": "0.0.0.0",
                "protocol": "vless",
                "settings": {
                    "clients": [{"id": uuid_str, "flow": "xtls-rprx-vision"}],
                    "decryption": "none"
                },
                "streamSettings": {
                    "network": "tcp",
                    "security": "reality",
                    "realitySettings": reality_settings
                }
            }
        ],
        "outbounds": [
            {"tag": "direct", "protocol": "freedom"},
            {"tag": "block", "protocol": "blackhole"}
        ],
        "routing": {
            "rules": [{"type": "field", "inboundTag": ["vless-in"], "outboundTag": "direct"}]
        }
    }


def _gost_command(local_port: int, remote_host: str, remote_port: int, method: str = "tls") -> list:
    transport_map = {
        "tls":    f"relay+tls://:{local_port}/{remote_host}:{remote_port}",
        "ws+tls": f"relay+wss://:{local_port}/{remote_host}:{remote_port}",
        "h2":     f"relay+http2://:{local_port}/{remote_host}:{remote_port}",
        "quic":   f"relay+quic://:{local_port}/{remote_host}:{remote_port}",
    }
    addr = transport_map.get(method, transport_map["tls"])
    return [settings.GOST_BIN, "-L", addr]


def _rathole_server_cfg(tunnel_name: str, local_port: int, token: str) -> str:
    return f"""[server]
bind_addr = "0.0.0.0:{local_port}"

[server.services.{tunnel_name}]
token = "{token}"
bind_addr = "0.0.0.0:{local_port + 1}"
"""


def _rathole_client_cfg(tunnel_name: str, server_host: str, server_port: int,
                         local_host: str, local_port: int, token: str) -> str:
    return f"""[client]
remote_addr = "{server_host}:{server_port}"

[client.services.{tunnel_name}]
token = "{token}"
local_addr = "{local_host}:{local_port}"
"""


# ══════════════════════════════════════════════════════════════
#  Process Management
# ══════════════════════════════════════════════════════════════

def _write_temp_config(content: str, suffix: str) -> str:
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=suffix, delete=False)
    tmp.write(content)
    tmp.flush()
    tmp.close()
    return tmp.name


async def start_tunnel(tunnel_id: str, method: str, role: str,
                        local_port: int, remote_host: str, remote_port: int,
                        target_host: str, target_port: int,
                        extra: dict) -> int:
    if tunnel_id in _procs and _procs[tunnel_id].poll() is None:
        return _procs[tunnel_id].pid

    cmd = []
    config_file = None

    if method == "vless_reverse":
        uid = extra.get("uuid", str(uuid.uuid4()))
        if role == "iran":
            cfg = _xray_reverse_iran_cfg(
                local_port, remote_host, remote_port, uid,
                public_key=extra.get("reality_public_key", ""),
            )
        else:
            cfg = _xray_reverse_foreign_cfg(
                local_port, target_host, target_port, uid,
                reality_private_key=extra.get("reality_private_key", ""),
                reality_public_key=extra.get("reality_public_key", ""),
            )
        config_file = _write_temp_config(json.dumps(cfg, indent=2), ".json")
        cmd = [settings.XRAY_BIN, "run", "-c", config_file]

    elif method == "gost":
        transport = extra.get("transport", "tls")
        cmd = _gost_command(local_port, remote_host, remote_port, transport)

    elif method == "rathole":
        token = extra.get("token", str(uuid.uuid4()))
        if role == "foreign":
            cfg_str = _rathole_server_cfg(tunnel_id[:16], local_port, token)
        else:
            cfg_str = _rathole_client_cfg(tunnel_id[:16], remote_host, remote_port,
                                           target_host or "127.0.0.1", target_port or local_port, token)
        config_file = _write_temp_config(cfg_str, ".toml")
        cmd = [settings.RATHOLE_BIN, config_file]

    elif method == "hysteria2":
        password = extra.get("password", str(uuid.uuid4())[:16])
        if role == "foreign":
            # Hysteria2 server config (v2 format)
            cfg = {
                "listen": f":{local_port}",
                "auth": {
                    "type": "password",
                    "password": password
                },
                "masquerade": {
                    "type": "proxy",
                    "proxy": {
                        "url": "https://www.bing.com",
                        "rewriteHost": True
                    }
                },
                "quic": {
                    "initStreamReceiveWindow": 8388608,
                    "maxStreamReceiveWindow": 8388608,
                    "initConnReceiveWindow": 20971520,
                    "maxConnReceiveWindow": 20971520
                }
            }
            config_file = _write_temp_config(json.dumps(cfg, indent=2), ".json")
            cmd = [settings.HYSTERIA2_BIN, "server", "-c", config_file]
        else:
            # Hysteria2 client config (v2 format)
            cfg = {
                "server": f"{remote_host}:{remote_port}",
                "auth": password,
                "tls": {
                    "sni": extra.get("sni", "www.bing.com"),
                    "insecure": extra.get("insecure", True)
                },
                "fastOpen": True,
                "tcpForwarding": [
                    {
                        "listen": f"127.0.0.1:{local_port}",
                        "remote": f"{target_host}:{target_port}"
                    }
                ]
            }
            config_file = _write_temp_config(json.dumps(cfg, indent=2), ".json")
            cmd = [settings.HYSTERIA2_BIN, "client", "-c", config_file]

    elif method == "openvpn":
        # Simplified OpenVPN over TCP/UDP bridge
        if role == "foreign":
            cmd = [settings.OPENVPN_BIN, "--dev", "tun", "--port", str(local_port), "--proto", "tcp-server", "--ifconfig", "10.8.0.1", "10.8.0.2"]
        else:
            cmd = [settings.OPENVPN_BIN, "--dev", "tun", "--remote", remote_host, "--port", str(remote_port), "--proto", "tcp-client", "--ifconfig", "10.8.0.2", "10.8.0.1"]

    elif method == "wireguard_tls":
        # Using GOST to wrap WireGuard UDP into TLS
        if role == "foreign":
            # Foreign: Listen TLS, forward to local WG port
            cmd = [settings.GOST_BIN, "-L", f"relay+tls://:{local_port}/127.0.0.1:{target_port}?reuse=true"]
        else:
            # Iran: Listen local WG port, forward to Foreign TLS
            cmd = [settings.GOST_BIN, "-L", f"udp://:{local_port}/127.0.0.1:{local_port}", "-F", f"relay+tls://{remote_host}:{remote_port}"]

    elif method == "reverse_tls":
        # Reverse TLS Tunnel using GOST v3 Relay
        if role == "foreign":
            # Exit server: waits for entry server to connect and open a port
            cmd = [settings.GOST_BIN, "-L", f"relay+tls://:{local_port}"]
        else:
            # Entry server: connects to exit and forwards local traffic back through the tunnel
            cmd = [settings.GOST_BIN, "-L", f"rtcp://:{local_port}/127.0.0.1:{local_port}", "-F", f"relay+tls://{remote_host}:{remote_port}"]

    else:
        raise ValueError(f"Unknown tunnel method: {method}")

    logger.info(f"Starting tunnel [{tunnel_id}] cmd: {' '.join(cmd)}")
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        preexec_fn=os.setsid if os.name != "nt" else None,
    )
    _procs[tunnel_id] = proc

    if config_file:
        proc._config_file = config_file  # type: ignore

    return proc.pid


async def stop_tunnel(tunnel_id: str) -> bool:
    proc = _procs.get(tunnel_id)
    if not proc:
        return False
    try:
        if os.name != "nt":
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
        else:
            proc.terminate()
        proc.wait(timeout=5)
    except Exception as e:
        logger.warning(f"Force killing tunnel [{tunnel_id}]: {e}")
        proc.kill()

    cfg = getattr(proc, "_config_file", None)
    if cfg and os.path.exists(cfg):
        os.unlink(cfg)

    del _procs[tunnel_id]
    return True


def get_tunnel_status(tunnel_id: str) -> str:
    proc = _procs.get(tunnel_id)
    if not proc:
        return "stopped"
    rc = proc.poll()
    if rc is None:
        return "running"
    return "error" if rc != 0 else "stopped"


def get_all_statuses() -> Dict[str, str]:
    return {tid: get_tunnel_status(tid) for tid in _procs}


async def check_binary(name: str, path: str) -> bool:
    return os.path.isfile(path) and os.access(path, os.X_OK)


async def read_process_output(tunnel_id: str, max_lines: int = 50) -> str:
    """Read buffered stdout/stderr from a running or recently stopped process."""
    proc = _procs.get(tunnel_id)
    if not proc or not proc.stdout:
        return ""
    try:
        lines = []
        while len(lines) < max_lines:
            ready, _, _ = _select.select([proc.stdout], [], [], 0)
            if not ready:
                break
            line = proc.stdout.readline()
            if not line:
                break
            lines.append(line.decode(errors="replace").rstrip())
        return "\n".join(lines)
    except Exception:
        return ""
