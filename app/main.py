"""TunnelBridge - FastAPI Application"""

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select

from app.config import settings
from app.models import init_db, AsyncSessionLocal, Tunnel
from app.api import tunnels, system
from app import tunnel_engine

logging.basicConfig(
    level=settings.LOG_LEVEL,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# مسیر مطلق پروژه — مستقل از working directory
BASE_DIR = Path(__file__).resolve().parent.parent


async def _sync_tunnel_statuses():
    """Background task: detect crashed tunnels and update their DB status."""
    while True:
        await asyncio.sleep(15)
        try:
            async with AsyncSessionLocal() as db:
                result = await db.execute(
                    select(Tunnel).where(Tunnel.status == "running")
                )
                running_tunnels = result.scalars().all()
                for t in running_tunnels:
                    live_status = tunnel_engine.get_tunnel_status(t.id)
                    if live_status != "running":
                        logger.warning(f"Tunnel [{t.id}] '{t.name}' crashed — updating status to error")
                        t.status = "error"
                        t.pid = None
                        t.error_msg = "Process exited unexpectedly"
                await db.commit()
        except Exception as e:
            logger.error(f"Status sync error: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    await init_db()
    logger.info("Database ready")
    # Reset any stale 'running' statuses from previous session
    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(Tunnel).where(Tunnel.status == "running"))
            stale = result.scalars().all()
            for t in stale:
                t.status = "stopped"
                t.pid = None
                t.error_msg = "Service restarted"
            if stale:
                await db.commit()
                logger.info(f"Reset {len(stale)} stale tunnel(s) to stopped")
    except Exception as e:
        logger.warning(f"Could not reset stale tunnels: {e}")
    # Start background status monitor
    task = asyncio.create_task(_sync_tunnel_statuses())
    yield
    task.cancel()
    logger.info("Shutting down...")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan,
    docs_url="/docs",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(tunnels.router)
app.include_router(system.router)

templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    return templates.TemplateResponse("dashboard.html", {"request": request})
