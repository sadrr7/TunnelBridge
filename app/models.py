from sqlalchemy import Column, String, Integer, DateTime, Text, Float
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.sql import func
from app.config import settings

Base = declarative_base()


class Tunnel(Base):
    __tablename__ = "tunnels"

    id = Column(String(36), primary_key=True)
    name = Column(String(128), unique=True, nullable=False)
    method = Column(String(32), nullable=False)   # vless_reverse | gost | rathole | wg
    status = Column(String(16), default="stopped") # running | stopped | error
    role = Column(String(16), nullable=False)      # iran | foreign

    # Connection params
    local_port = Column(Integer, nullable=False)
    remote_host = Column(String(255), nullable=True)
    remote_port = Column(Integer, nullable=True)
    target_host = Column(String(255), nullable=True)  # final destination
    target_port = Column(Integer, nullable=True)

    # Extra config (JSON string)
    extra_config = Column(Text, default="{}")

    # Stats
    bytes_sent = Column(Float, default=0.0)
    bytes_recv = Column(Float, default=0.0)
    connections = Column(Integer, default=0)

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    pid = Column(Integer, nullable=True)  # process PID when running
    error_msg = Column(Text, nullable=True)


class TunnelLog(Base):
    __tablename__ = "tunnel_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tunnel_id = Column(String(36), nullable=False)
    level = Column(String(8), default="INFO")
    message = Column(Text, nullable=False)
    created_at = Column(DateTime, server_default=func.now())


# ── DB setup ──────────────────────────────────────────────────
engine = create_async_engine(settings.DATABASE_URL, echo=False)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
