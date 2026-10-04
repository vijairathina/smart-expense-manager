import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
BACKUPS_DIR = BASE_DIR / "backups"
BACKUPS_DIR.mkdir(parents=True, exist_ok=True)

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "expense-manager-secret-key-trent-2026")
    PORT = int(os.getenv("PORT", 5001))
    HOST = os.getenv("HOST", "0.0.0.0")
    DEBUG = os.getenv("DEBUG", "false").lower() in ("true", "1", "yes")

    # SQLite Database Configuration
    DATABASE_PATH = os.getenv("DATABASE_PATH", str(DATA_DIR / "expense_manager.db"))
    SQLALCHEMY_DATABASE_URI = f"sqlite:///{DATABASE_PATH}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Auth
    DEFAULT_ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
    DEFAULT_ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")

    # AI Keys (can be overridden in SQLite settings)
    GEMINI_API_KEYS = [k.strip() for k in os.getenv("GEMINI_API_KEYS", "").split(",") if k.strip()]
    OPENROUTER_API_KEYS = [k.strip() for k in os.getenv("OPENROUTER_API_KEYS", "").split(",") if k.strip()]
    OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "google/gemini-2.0-flash-001")
    LOCAL_LLM_URL = os.getenv("LOCAL_LLM_URL", "http://127.0.0.1:11434/v1")
