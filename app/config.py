from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    APP_NAME: str = "TunnelBridge"
    APP_VERSION: str = "1.0.0"
    HOST: str = "0.0.0.0"
    PORT: int = 8080
    SECRET_KEY: str = "change-me-in-production-use-random-32-chars"
    DATABASE_URL: str = "sqlite+aiosqlite:///./tunnelbridge.db"
    LOG_LEVEL: str = "INFO"

    # Xray binary path
    XRAY_BIN: str = "/usr/local/bin/xray"
    # GOST binary path
    GOST_BIN: str = "/usr/local/bin/gost"
    # Rathole binary path
    RATHOLE_BIN: str = "/usr/local/bin/rathole"
    # Hysteria2 binary path
    HYSTERIA2_BIN: str = "/usr/local/bin/hysteria2"
    # OpenVPN binary path
    OPENVPN_BIN: str = "/usr/sbin/openvpn"

    # This server's role: "iran" (entry) or "foreign" (exit)
    SERVER_ROLE: str = "iran"
    # Foreign server address (used when role=iran)
    FOREIGN_SERVER_IP: Optional[str] = None
    FOREIGN_SERVER_PORT: int = 443

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
