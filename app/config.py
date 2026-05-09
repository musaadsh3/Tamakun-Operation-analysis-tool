import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

class Settings:
    APP_NAME: str = "تمكّن - إدارة المتاجر"
    SECRET_KEY: str = os.getenv("SECRET_KEY", "change-me-in-production-tamakun-2024")

    # Database
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        f"sqlite:///{BASE_DIR / 'tamakun.db'}"
    )

    # External Postgres (Salla ingest DB) — values come from .env, no defaults committed.
    EXTERNAL_DB_HOST: str = os.getenv("EXTERNAL_DB_HOST", "")
    EXTERNAL_DB_PORT: str = os.getenv("EXTERNAL_DB_PORT", "5432")
    EXTERNAL_DB_USERNAME: str = os.getenv("EXTERNAL_DB_USERNAME", "")
    EXTERNAL_DB_PASSWORD: str = os.getenv("EXTERNAL_DB_PASSWORD", "")
    EXTERNAL_DB_NAME: str = os.getenv("EXTERNAL_DB_NAME", "")
    EXTERNAL_DB_TYPE: str = os.getenv("EXTERNAL_DB_TYPE", "postgres")
    EXTERNAL_USE_SSL: bool = os.getenv("EXTERNAL_USE_SSL", "false").lower() == "true"

    # File paths
    UPLOAD_DIR: Path = BASE_DIR / "uploads"
    EXPORT_DIR: Path = BASE_DIR / "exports"

    # Admin defaults
    ADMIN_EMAIL: str = "m.alshathri@tamakun.sa"
    ADMIN_NAME: str = "مساعد"
    ADMIN_DEFAULT_PASSWORD: str = "Tamakun@2024"

    # Session
    SESSION_EXPIRE_HOURS: int = 24

settings = Settings()

# Ensure directories exist
settings.UPLOAD_DIR.mkdir(exist_ok=True)
settings.EXPORT_DIR.mkdir(exist_ok=True)
