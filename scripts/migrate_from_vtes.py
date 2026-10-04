import os
import sys
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass
import json
from pathlib import Path
from datetime import datetime

# Setup path
CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = CURRENT_DIR.parent
VTES_DIR = PROJECT_DIR.parent.parent

sys.path.insert(0, str(PROJECT_DIR))

from backend.database import init_db, db_session
from backend.models import Expense, Category, Subcategory, PaymentMode, ExpenseQueue, Setting, AuditLog

def migrate_vtes_expense_data():
    print(f"📦 Starting migration from VTES source directory: {VTES_DIR}")
    init_db()
    session = db_session()

    cat_count = 0
    mode_count = 0
    exp_count = 0
    dup_count = 0
    queue_count = 0

    # 1. Migrate Categories and Payment Modes from expense_config.json
    cfg_file = VTES_DIR / "expense_config.json"
    if cfg_file.exists():
        with open(cfg_file, "r", encoding="utf-8") as f:
            vtes_cfg = json.load(f)

        # Migrate Categories
        vtes_cats = vtes_cfg.get("categories", {})
        cat_count = 0
        for cat_name, sub_list in vtes_cats.items():
            cat = session.query(Category).filter_by(name=cat_name).first()
            if not cat:
                cat = Category(name=cat_name)
                session.add(cat)
                session.flush()
                cat_count += 1
            
            existing_subs = {s.name for s in cat.subcategories}
            for sub_name in sub_list:
                if sub_name not in existing_subs:
                    session.add(Subcategory(category_id=cat.id, name=sub_name))

        # Migrate Payment Modes
        vtes_modes = vtes_cfg.get("payment_modes", [])
        mode_count = 0
        for mode_name in vtes_modes:
            mode = session.query(PaymentMode).filter_by(name=mode_name).first()
            if not mode:
                session.add(PaymentMode(name=mode_name))
                mode_count += 1

        # Migrate Expense Configuration Settings
        Setting.set(session, "expense_config", {
            "split_response_enabled": vtes_cfg.get("split_response_enabled", False),
            "feedback_enabled": vtes_cfg.get("feedback_enabled", False),
            "use_gemini": vtes_cfg.get("use_gemini", True),
            "use_openrouter": vtes_cfg.get("use_openrouter", True),
            "openrouter_model": vtes_cfg.get("openrouter_model", "google/gemini-2.0-flash-001"),
            "openrouter_reasoning": vtes_cfg.get("openrouter_reasoning", False),
            "use_local_llm": vtes_cfg.get("use_local_llm", False),
            "use_free_llm": vtes_cfg.get("use_free_llm", True),
            "use_regex_shortcut": vtes_cfg.get("use_regex_shortcut", True),
            "auto_report": vtes_cfg.get("auto_report", {
                "daily": True,
                "weekly": True,
                "monthly": True,
                "daily_time": "23:59",
                "weekly_time": "23:59",
                "monthly_time": "23:59"
            })
        })
        print(f"✓ Migrated {cat_count} categories and {mode_count} payment modes from VTES config")

    # 2. Migrate API Credentials if present
    creds_file = VTES_DIR / "credentials.json"
    if creds_file.exists():
        with open(creds_file, "r", encoding="utf-8") as f:
            creds = json.load(f)
        Setting.set(session, "api_credentials", {
            "gemini_api_keys": creds.get("gemini_api_keys", []),
            "openrouter_api_keys": creds.get("openrouter_api_keys", [])
        })
        print(f"✓ Migrated AI API keys from credentials.json")

    # 3. Migrate Expenses from expenses.json
    expenses_file = VTES_DIR / "expenses.json"
    exp_count = 0
    dup_count = 0
    if expenses_file.exists():
        with open(expenses_file, "r", encoding="utf-8") as f:
            try:
                vtes_expenses = json.load(f)
            except Exception as e:
                print(f"⚠️ Error reading expenses.json: {e}")
                vtes_expenses = []

        print(f"📊 Found {len(vtes_expenses)} expenses in VTES expenses.json. Migrating...")
        for item in vtes_expenses:
            item_id = str(item.get("id") or "")
            if not item_id:
                continue

            existing = session.query(Expense).filter_by(id=item_id).first()
            if existing:
                dup_count += 1
                continue

            created_ts = None
            if item.get("timestamp"):
                try:
                    created_ts = datetime.fromisoformat(item["timestamp"])
                except Exception:
                    created_ts = datetime.utcnow()

            exp = Expense(
                id=item_id,
                date=str(item.get("date", "")),
                time=str(item.get("time", "")),
                category=str(item.get("category", "Miscellaneous")),
                subcategory=str(item.get("subcategory", "")),
                description=str(item.get("description", "")),
                amount=float(item.get("amount", 0.0)),
                payment_mode=str(item.get("payment_mode", "UPI")),
                notes=str(item.get("notes", "")),
                original_msg=str(item.get("original_msg", "")),
                source="VTES_Migration",
                created_at=created_ts or datetime.utcnow()
            )
            session.add(exp)
            exp_count += 1

    # 4. Migrate Queue from expense_queue.json
    queue_file = VTES_DIR / "expense_queue.json"
    queue_count = 0
    if queue_file.exists():
        with open(queue_file, "r", encoding="utf-8") as f:
            try:
                vtes_queue = json.load(f)
            except Exception:
                vtes_queue = []

        for q_item in vtes_queue:
            msg_text = q_item if isinstance(q_item, str) else q_item.get("text", "")
            if msg_text:
                session.add(ExpenseQueue(
                    raw_message=msg_text,
                    sender=q_item.get("sender") if isinstance(q_item, dict) else "VTES",
                    platform=q_item.get("platform") if isinstance(q_item, dict) else "legacy_queue",
                    status="pending"
                ))
                queue_count += 1

    # Log Migration Event
    session.add(AuditLog(
        event_type="migration",
        message=f"Migrated from VTES: {exp_count} expenses, {cat_count} categories, {queue_count} queue items",
        details_json=json.dumps({"expenses_imported": exp_count, "duplicates_skipped": dup_count})
    ))

    session.commit()
    session.close()
    print(f"🎉 Migration Complete! Imported: {exp_count} expenses ({dup_count} duplicates skipped), {queue_count} queue items.")

if __name__ == "__main__":
    migrate_vtes_expense_data()
