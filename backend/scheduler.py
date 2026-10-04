import time
import threading
from datetime import datetime
from backend.database import db_session, backup_database
from backend.services.expense_service import ExpenseService
from backend.models import Setting

class ExpenseScheduler:
    def __init__(self):
        self._running = False
        self._thread = None

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        print("[Scheduler] Expense Manager background scheduler active.")

    def stop(self):
        self._running = False

    def _loop(self):
        last_backup_date = None
        while self._running:
            time.sleep(30)
            now = datetime.now()
            today_str = now.strftime("%Y-%m-%d")

            # 1. Automated Daily SQLite Backup at 03:00 AM
            if now.hour == 3 and last_backup_date != today_str:
                try:
                    b_file = backup_database()
                    last_backup_date = today_str
                    print(f"📦 Automated daily database backup created: {b_file}")
                except Exception as e:
                    print(f"⚠️ Backup failed: {e}")

            # 2. Automated Queue Processing (every 5 minutes)
            if now.minute % 5 == 0 and now.second < 30:
                try:
                    session = db_session()
                    service = ExpenseService(session)
                    count = service.process_queue()
                    if count > 0:
                        print(f"🔄 Auto-processed {count} queued expense items.")
                    session.close()
                except Exception as e:
                    print(f"⚠️ Queue processor error: {e}")
