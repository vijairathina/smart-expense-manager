import os
import shutil
import sqlite3
from datetime import datetime
from sqlalchemy import create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker, scoped_session
from backend.config import Config, BACKUPS_DIR

engine = create_engine(
    Config.SQLALCHEMY_DATABASE_URI,
    connect_args={"check_same_thread": False},
    echo=False
)

# Enable WAL mode and foreign key enforcement on every SQLite connection
@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    if isinstance(dbapi_connection, sqlite3.Connection):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.close()

SessionFactory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
db_session = scoped_session(SessionFactory)
Base = declarative_base()
Base.query = db_session.query_property()

def init_db():
    import backend.models  # Ensure models are registered
    Base.metadata.create_all(bind=engine)

def get_db():
    session = db_session()
    try:
        yield session
    finally:
        session.close()

def backup_database():
    """Create a dated snapshot of the SQLite database in the backups directory."""
    db_path = Config.DATABASE_PATH
    if not os.path.exists(db_path):
        return None
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = BACKUPS_DIR / f"expense_manager_{timestamp}.db"
    
    # Use SQLite online backup API to safely copy even while WAL is active
    src = sqlite3.connect(db_path)
    dst = sqlite3.connect(str(backup_file))
    with dst:
        src.backup(dst, pages=100)
    dst.close()
    src.close()
    return str(backup_file)
