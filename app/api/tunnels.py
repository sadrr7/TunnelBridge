"""Tunnel CRUD & control API"""

import asyncio
import json
import time
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Tunnel, TunnelLog, get_db
from app import tunnel_engine

router = APIRouter(prefix="/api/tunnels", tags=["tunnels"])


# ── Schemas ───────────────────────────────────────────────────

class TunnelCreate(BaseModel):
    name: str
    method: str          # vless_reverse | gost | rathole | hysteria2 | wireguard_tls | reverse_tls | openvpn
    role: str            # iran | foreign
    local_port: int
    remote_host: Optional[str] = None
    remote_port: Optional[int] = None
    target_host: Optional[str] = None
    target_port: Optional[int] = None
    extra_config: dict = {}

    @field_validator("local_port")
    @classmethod
    def validate_port(cls, v: int) -> int:
        if not (1 <= v <= 65535):
            raise ValueError("port must be between 1 and 65535")
        return v

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("name cannot be empty")
        if len(v) > 128:
            raise ValueError("name too long (max 128 chars)")
        return v


class TunnelOut(BaseModel):
    id: str
    name: str
    method: str
    role: str
    status: str
    local_port: int
    remote_host: Optional[str]
    remote_port: Optional[int]
    target_host: Optional[str]
    target_port: Optional[int]
    extra_config: dict
    bytes_sent: float
    bytes_recv: float
    connections: int
    pid: Optional[int]
    error_msg: Optional[str]

    class Config:
        from_attributes = True


# ── Helpers ───────────────────────────────────────────────────

def _tunnel_out(t: Tunnel) -> TunnelOut:
    extra = {}
    try:
        extra = json.loads(t.extra_config or "{}")
    except Exception:
        pass
    return TunnelOut(
        id=t.id, name=t.name, method=t.method, role=t.role,
        status=tunnel_engine.get_tunnel_status(t.id) if t.status == "running" else t.status,
        local_port=t.local_port, remote_host=t.remote_host, remote_port=t.remote_port,
        target_host=t.target_host, target_port=t.target_port,
        extra_config=extra, bytes_sent=t.bytes_sent, bytes_recv=t.bytes_recv,
        connections=t.connections, pid=t.pid, error_msg=t.error_msg,
    )


async def _log(db: AsyncSession, tunnel_id: str, msg: str, level: str = "INFO"):
    db.add(TunnelLog(tunnel_id=tunnel_id, level=level, message=msg))
    await db.commit()


# ── Routes ────────────────────────────────────────────────────

@router.get("", response_model=List[TunnelOut])
async def list_tunnels(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Tunnel))
    return [_tunnel_out(t) for t in result.scalars().all()]


@router.post("", response_model=TunnelOut, status_code=201)
async def create_tunnel(data: TunnelCreate, db: AsyncSession = Depends(get_db)):
    # Validate method
    allowed_methods = ("vless_reverse", "gost", "rathole", "hysteria2", "openvpn", "wireguard_tls", "reverse_tls")
    if data.method not in allowed_methods:
        raise HTTPException(400, f"method must be one of: {', '.join(allowed_methods)}")
    if data.role not in ("iran", "foreign"):
        raise HTTPException(400, "role must be: iran | foreign")

    tunnel = Tunnel(
        id=str(uuid.uuid4()),
        name=data.name,
        method=data.method,
        role=data.role,
        status="stopped",
        local_port=data.local_port,
        remote_host=data.remote_host,
        remote_port=data.remote_port,
        target_host=data.target_host,
        target_port=data.target_port,
        extra_config=json.dumps(data.extra_config),
    )
    db.add(tunnel)
    await db.commit()
    await db.refresh(tunnel)
    await _log(db, tunnel.id, f"Tunnel '{tunnel.name}' created")
    return _tunnel_out(tunnel)


@router.get("/{tunnel_id}", response_model=TunnelOut)
async def get_tunnel(tunnel_id: str, db: AsyncSession = Depends(get_db)):
    t = await db.get(Tunnel, tunnel_id)
    if not t:
        raise HTTPException(404, "Tunnel not found")
    return _tunnel_out(t)


@router.delete("/{tunnel_id}", status_code=204)
async def delete_tunnel(tunnel_id: str, db: AsyncSession = Depends(get_db)):
    t = await db.get(Tunnel, tunnel_id)
    if not t:
        raise HTTPException(404, "Tunnel not found")
    await tunnel_engine.stop_tunnel(tunnel_id)
    await db.delete(t)
    await db.commit()


@router.post("/{tunnel_id}/start", response_model=TunnelOut)
async def start_tunnel(tunnel_id: str, db: AsyncSession = Depends(get_db)):
    t = await db.get(Tunnel, tunnel_id)
    if not t:
        raise HTTPException(404, "Tunnel not found")

    extra = {}
    try:
        extra = json.loads(t.extra_config or "{}")
    except Exception:
        pass

    try:
        pid = await tunnel_engine.start_tunnel(
            tunnel_id=t.id,
            method=t.method,
            role=t.role,
            local_port=t.local_port,
            remote_host=t.remote_host or "",
            remote_port=t.remote_port or 0,
            target_host=t.target_host or "",
            target_port=t.target_port or 0,
            extra=extra,
        )
        t.status = "running"
        t.pid = pid
        t.error_msg = None
        await db.commit()
        await _log(db, t.id, f"Started (PID {pid})")
    except Exception as e:
        t.status = "error"
        t.error_msg = str(e)
        await db.commit()
        await _log(db, t.id, f"Start failed: {e}", "ERROR")
        raise HTTPException(500, str(e))

    return _tunnel_out(t)


@router.post("/{tunnel_id}/stop", response_model=TunnelOut)
async def stop_tunnel(tunnel_id: str, db: AsyncSession = Depends(get_db)):
    t = await db.get(Tunnel, tunnel_id)
    if not t:
        raise HTTPException(404, "Tunnel not found")

    await tunnel_engine.stop_tunnel(tunnel_id)
    t.status = "stopped"
    t.pid = None
    await db.commit()
    await _log(db, t.id, "Stopped")
    return _tunnel_out(t)


@router.get("/{tunnel_id}/logs")
async def get_logs(tunnel_id: str, limit: int = 50, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(TunnelLog)
        .where(TunnelLog.tunnel_id == tunnel_id)
        .order_by(TunnelLog.created_at.asc())
        .limit(limit)
    )
    logs = result.scalars().all()
    return [{"id": l.id, "level": l.level, "message": l.message,
             "created_at": str(l.created_at)} for l in logs]


@router.get("/{tunnel_id}/process-output")
async def get_process_output(tunnel_id: str, db: AsyncSession = Depends(get_db)):
    """Read live stdout/stderr from the tunnel's running process."""
    t = await db.get(Tunnel, tunnel_id)
    if not t:
        raise HTTPException(404, "Tunnel not found")
    output = await tunnel_engine.read_process_output(tunnel_id)
    return {"tunnel_id": tunnel_id, "output": output or "(no output available)"}


@router.post("/{tunnel_id}/test")
async def test_tunnel_connection(tunnel_id: str, db: AsyncSession = Depends(get_db)):    """Check if the tunnel's target (remote server or destination) is reachable."""
    t = await db.get(Tunnel, tunnel_id)
    if not t:
        raise HTTPException(404, "Tunnel not found")

    host = t.remote_host if t.role == "iran" else t.target_host
    port = t.remote_port if t.role == "iran" else t.target_port

    if not host or not port:
        return {"status": "error", "message": "Host or Port not defined for this role"}

    start = time.time()
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port), timeout=3.0
        )
        writer.close()
        await writer.wait_closed()
        latency = (time.time() - start) * 1000
        return {"status": "success", "latency": f"{latency:.1f}ms", "message": f"Connection to {host}:{port} OK"}
    except Exception as e:
        return {"status": "fail", "message": f"Connection to {host}:{port} failed: {str(e)}"}
