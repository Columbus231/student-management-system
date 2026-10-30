import os
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATABASE = PROJECT_ROOT / "database" / "college.db"
DEFAULT_DATABASE.parent.mkdir(parents=True, exist_ok=True)


class Config:
    ENVIRONMENT = (
        os.getenv("VERCEL_ENV") if os.getenv("VERCEL") == "1" else os.getenv("FLASK_ENV")
    ) or os.getenv("VERCEL_ENV") or "development"
    ENVIRONMENT = ENVIRONMENT.lower()
    SECRET_KEY = os.getenv("SECRET_KEY") or "local-development-secret-change-me"
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY") or "local-jwt-secret-change-me"
    JWT_TOKEN_LOCATION = ["cookies"]
    JWT_COOKIE_SECURE = ENVIRONMENT in {"production", "preview"}
    JWT_COOKIE_SAMESITE = "Lax"
    JWT_COOKIE_CSRF_PROTECT = True
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=8)
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL") or (
        f"sqlite:///{DEFAULT_DATABASE.as_posix()}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = (
        {"pool_pre_ping": True, "pool_recycle": 300, "pool_size": 1, "max_overflow": 0}
        if SQLALCHEMY_DATABASE_URI.startswith(
            ("postgres://", "postgresql://", "postgresql+psycopg://")
        )
        else {}
    )
    RATELIMIT_STORAGE_URI = os.getenv("RATELIMIT_STORAGE_URI", "memory://")
    RATELIMIT_DEFAULT = "200 per day;50 per hour"
    FRONTEND_URL = os.getenv("FRONTEND_URL", "http://127.0.0.1:5000")
    CORS_ORIGINS = [
        origin.strip()
        for origin in os.getenv("CORS_ORIGINS", FRONTEND_URL).split(",")
        if origin.strip()
    ]
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = ENVIRONMENT in {"production", "preview"}
    AUTO_CREATE_TABLES = os.getenv("AUTO_CREATE_TABLES", "false").lower() == "true"
    MAX_CONTENT_LENGTH = 1024 * 1024
