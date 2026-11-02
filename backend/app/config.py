import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./nexus.db")
    jwt_secret: str = os.getenv("JWT_SECRET", "")
    jwt_minutes: int = int(os.getenv("JWT_MINUTES", "30"))
    pairing_minutes: int = int(os.getenv("PAIRING_MINUTES", "10"))
    login_max_attempts: int = int(os.getenv("LOGIN_MAX_ATTEMPTS", "5"))
    login_window_seconds: int = int(os.getenv("LOGIN_WINDOW_SECONDS", "300"))
    online_seconds: int = int(os.getenv("ONLINE_SECONDS", "120"))


def get_settings() -> Settings:
    s = Settings()
    if not s.jwt_secret or len(s.jwt_secret) < 32:
        raise RuntimeError("JWT_SECRET must be set (min 32 chars). See .env.example")
    return s
