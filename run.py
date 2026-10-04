#!/usr/bin/env python3
"""Expense Manager - Standalone Runner"""
import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from backend.config import Config
from backend.database import init_db
from backend.scheduler import ExpenseScheduler
from backend.app import app

if __name__ == "__main__":
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')

    init_db()
    scheduler = ExpenseScheduler()
    scheduler.start()
    print(f"""
    ==================================================
    * Expense Manager (Standalone Project)
    * URL: http://localhost:{Config.PORT}
    * Database: {Config.DATABASE_PATH}
    ==================================================
    """)
    app.run(host=Config.HOST, port=Config.PORT, debug=Config.DEBUG)
