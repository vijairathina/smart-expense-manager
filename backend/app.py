import os
import sys
import hashlib
from pathlib import Path
from flask import Flask, jsonify, request, session, send_from_directory

BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"

sys.path.insert(0, str(BASE_DIR))

from backend.config import Config
from backend.database import init_db, db_session, backup_database
from backend.models import User, Category, Subcategory, PaymentMode, Setting, AuditLog
from backend.services.expense_service import ExpenseService
from backend.services.ai_parser import parse_expense_text
from backend.scheduler import ExpenseScheduler

app = Flask(__name__, static_folder=str(FRONTEND_DIR), static_url_path="")
app.secret_key = Config.SECRET_KEY

def hash_pw(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()

@app.teardown_appcontext
def shutdown_session(exception=None):
    db_session.remove()

# =========================================================================
# STATIC FRONTEND ROUTES
# =========================================================================

@app.route("/")
def serve_index():
    return send_from_directory(str(FRONTEND_DIR), "index.html")

@app.route("/<path:path>")
def serve_static(path):
    if (FRONTEND_DIR / path).exists():
        return send_from_directory(str(FRONTEND_DIR), path)
    return send_from_directory(str(FRONTEND_DIR), "index.html")

# =========================================================================
# HEALTH CHECK
# =========================================================================

@app.route("/api/health", methods=["GET"])
def health_check():
    db_ok = False
    try:
        from sqlalchemy import text
        db_session.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False

    return jsonify({
        "service": "Expense Manager",
        "status": "Online" if db_ok else "Degraded",
        "database": "Online" if db_ok else "Offline",
        "version": "2.0.0"
    })

# =========================================================================
# AUTHENTICATION
# =========================================================================

@app.route("/api/auth/login", methods=["POST"])
def login():
    data = request.get_json() or {}
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()

    if not username or not password:
        return jsonify({"success": False, "error": "Username and password required"}), 400

    user = db_session.query(User).filter_by(username=username).first()
    if user and user.password_hash == hash_pw(password):
        session["user_id"] = user.id
        session["username"] = user.username
        session["role"] = user.role
        return jsonify({"success": True, "user": user.to_dict()})

    return jsonify({"success": False, "error": "Invalid credentials"}), 401

@app.route("/api/auth/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"success": True})

@app.route("/api/auth/me", methods=["GET"])
def current_user():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"authenticated": False})
    user = db_session.query(User).filter_by(id=user_id).first()
    if not user:
        return jsonify({"authenticated": False})
    return jsonify({"authenticated": True, "user": user.to_dict()})

# =========================================================================
# DASHBOARD STATS & EXPENSES
# =========================================================================

@app.route("/api/dashboard/stats", methods=["GET"])
def dashboard_stats():
    service = ExpenseService(db_session)
    return jsonify(service.get_dashboard_stats())

@app.route("/api/expenses", methods=["GET"])
def list_expenses():
    service = ExpenseService(db_session)
    page = int(request.args.get("page", 1))
    limit = int(request.args.get("limit", 50))
    category = request.args.get("category")
    payment_mode = request.args.get("payment_mode")
    search = request.args.get("search")
    from_date = request.args.get("from_date")
    to_date = request.args.get("to_date")

    result = service.get_expenses(page, limit, category, payment_mode, search, from_date, to_date)
    return jsonify(result)

@app.route("/api/expenses", methods=["POST"])
def create_expense():
    service = ExpenseService(db_session)
    data = request.get_json() or {}

    desc = data.get("description", "").strip()
    amount = data.get("amount")
    category = data.get("category", "").strip()

    if not desc or amount is None or not category:
        return jsonify({"success": False, "error": "Description, amount, and category are required"}), 400

    exp, is_new = service.add_expense(
        date=data.get("date"),
        category=category,
        subcategory=data.get("subcategory", ""),
        description=desc,
        amount=amount,
        payment_mode=data.get("payment_mode", "UPI"),
        notes=data.get("notes", ""),
        original_msg=data.get("original_msg", ""),
        source="Manual"
    )
    return jsonify({"success": True, "expense": exp, "is_new": is_new}), 201

@app.route("/api/expenses/<expense_id>", methods=["PUT"])
def update_expense(expense_id):
    service = ExpenseService(db_session)
    data = request.get_json() or {}
    updated = service.update_expense(expense_id, **data)
    if not updated:
        return jsonify({"success": False, "error": "Expense not found"}), 404
    return jsonify({"success": True, "expense": updated})

@app.route("/api/expenses/<expense_id>", methods=["DELETE"])
def delete_expense(expense_id):
    service = ExpenseService(db_session)
    ok = service.delete_expense(expense_id)
    if not ok:
        return jsonify({"success": False, "error": "Expense not found"}), 404
    return jsonify({"success": True})

# =========================================================================
# CATEGORIES & PAYMENT MODES
# =========================================================================

@app.route("/api/categories", methods=["GET"])
def get_categories():
    cats = db_session.query(Category).all()
    return jsonify([c.to_dict() for c in cats])

@app.route("/api/categories/detailed", methods=["GET"])
def get_categories_detailed():
    service = ExpenseService(db_session)
    return jsonify(service.get_categories_detailed())

@app.route("/api/categories", methods=["POST"])
def add_category():
    data = request.get_json() or {}
    name = data.get("name", "").strip()
    color = data.get("color", "#10B981")
    icon = data.get("icon", "fa-tag")
    if not name:
        return jsonify({"error": "Category name required"}), 400

    service = ExpenseService(db_session)
    cat_data, is_new = service.add_category(name, color, icon)
    return jsonify({"success": True, "category": cat_data, "is_new": is_new}), 201

@app.route("/api/categories/<int:cat_id>", methods=["DELETE"])
def delete_category(cat_id):
    service = ExpenseService(db_session)
    ok = service.delete_category(cat_id)
    if not ok:
        return jsonify({"success": False, "error": "Category not found"}), 404
    return jsonify({"success": True})

@app.route("/api/categories/<int:cat_id>/subcategories", methods=["POST"])
def add_subcategory(cat_id):
    data = request.get_json() or {}
    name = data.get("name", "").strip()
    if not name:
        return jsonify({"error": "Subcategory name required"}), 400

    service = ExpenseService(db_session)
    sub = service.add_subcategory(cat_id, name)
    if not sub:
        return jsonify({"success": False, "error": "Category not found"}), 404
    return jsonify({"success": True, "subcategory": sub}), 201

@app.route("/api/subcategories/<int:sub_id>", methods=["DELETE"])
def delete_subcategory(sub_id):
    service = ExpenseService(db_session)
    ok = service.delete_subcategory(sub_id)
    if not ok:
        return jsonify({"success": False, "error": "Subcategory not found"}), 404
    return jsonify({"success": True})

@app.route("/api/payment-modes", methods=["GET"])
def get_payment_modes():
    modes = db_session.query(PaymentMode).all()
    return jsonify([m.to_dict() for m in modes])

@app.route("/api/payment-modes", methods=["POST"])
def add_payment_mode():
    data = request.get_json() or {}
    name = data.get("name", "").strip()
    if not name:
        return jsonify({"error": "Payment mode name required"}), 400

    existing = db_session.query(PaymentMode).filter_by(name=name).first()
    if not existing:
        mode = PaymentMode(name=name)
        db_session.add(mode)
        db_session.commit()
        return jsonify({"success": True, "payment_mode": mode.to_dict()}), 201
    return jsonify({"success": True, "payment_mode": existing.to_dict()})

# =========================================================================
# AI / REGEX PARSING & QUEUE
# =========================================================================

@app.route("/api/settings/ai", methods=["GET", "POST"])
def ai_settings():
    if request.method == "POST":
        data = request.get_json() or {}
        Setting.set(db_session, "ai_config", data)
        return jsonify({"success": True, "config": data})

    cfg = Setting.get(db_session, "ai_config", {
        "use_gemini": True,
        "use_openrouter": True,
        "openrouter_model": "google/gemini-2.0-flash-001",
        "openrouter_reasoning": False,
        "use_local_llm": False,
        "local_llm_url": "http://localhost:11434/api/generate",
        "local_llm_model": "llama3",
        "use_free_llm": True,
        "use_regex_shortcut": True,
        "gemini_api_keys": Config.GEMINI_API_KEYS,
        "openrouter_api_keys": Config.OPENROUTER_API_KEYS
    })
    return jsonify({"success": True, "config": cfg})

@app.route("/api/settings/integrations", methods=["GET", "POST"])
def integration_settings():
    from backend.services.integration_service import IntegrationService
    service = IntegrationService(db_session)
    if request.method == "POST":
        data = request.get_json() or {}
        service.save_config(data)
        return jsonify({"success": True, "config": data})

    return jsonify({"success": True, "config": service.get_config()})

@app.route("/api/reports/test/<frequency>", methods=["POST"])
def test_dispatch_report(frequency):
    from backend.services.integration_service import IntegrationService
    service = IntegrationService(db_session)
    res = service.dispatch_report(frequency)
    return jsonify({"success": True, "result": res})

@app.route("/api/webhook/message", methods=["POST"])
def webhook_incoming_message():
    """Receives incoming message from WhatsApp or Telegram bot, parses and inserts into SQLite."""
    data = request.get_json() or {}
    text = data.get("text") or data.get("message") or ""
    sender = data.get("sender") or data.get("from") or "Unknown"
    platform = data.get("platform") or "whatsapp"

    from backend.services.integration_service import IntegrationService
    service = IntegrationService(db_session)
    result = service.process_incoming_message(text, sender, platform)
    if not result:
        return jsonify({"success": False, "message": "No expense detected"}), 200

    return jsonify({"success": True, "result": result}), 201

@app.route("/api/parse-text", methods=["POST"])
def test_parse_text():
    data = request.get_json() or {}
    text = data.get("text", "").strip()
    service = ExpenseService(db_session)
    categories = service.get_categories_dict()
    cfg = Setting.get(db_session, "ai_config", {})
    creds = Setting.get(db_session, "api_credentials", {})
    if creds:
        cfg.update(creds)

    parsed = parse_expense_text(text, config=cfg, categories_dict=categories)
    return jsonify({"success": True, "items": parsed})

@app.route("/api/queue/process", methods=["POST"])
def process_queue():
    service = ExpenseService(db_session)
    count = service.process_queue()
    stats = service.get_dashboard_stats()
    return jsonify({"success": True, "processed": count, "stats": stats})


# =========================================================================
# SYSTEM STATUS & INTEGRATIONS PROXY
# =========================================================================

@app.route("/api/system/status", methods=["GET"])
def system_status():
    from backend.services.integration_service import IntegrationService
    service = IntegrationService(db_session)
    return jsonify(service.get_connections_status())

@app.route("/api/manywhatsapp/accounts", methods=["GET"])
def manywhatsapp_accounts():
    from backend.services.integration_service import IntegrationService
    service = IntegrationService(db_session)
    accounts = service.list_manywhatsapp_accounts()
    cfg = service.get_config()
    return jsonify({
        "success": True,
        "accounts": accounts,
        "current_wa_account_id": cfg.get("manywhatsapp_account_id", ""),
        "current_wa_target": (cfg.get("whatsapp_groups") or [""])[0],
        "current_tg_target": (cfg.get("telegram_chats") or [""])[0]
    })

@app.route("/api/ai/analyze", methods=["POST"])
def ai_analyze_expense():
    data = request.get_json() or {}
    text = data.get("text", "").strip()
    if not text:
        return jsonify({"success": False, "error": "No description text provided"}), 400

    from backend.services.ai_parser import analyze_single_expense
    service = ExpenseService(db_session)
    categories = service.get_categories_dict()
    cfg = Setting.get(db_session, "ai_config", {})
    creds = Setting.get(db_session, "api_credentials", {})
    if creds:
        cfg.update(creds)

    result = analyze_single_expense(text, categories_dict=categories, config=cfg)
    return jsonify(result)

@app.route("/api/ai/test", methods=["POST"])
def ai_test_connection():
    data = request.get_json() or {}
    text = data.get("text", "Coffee and pastry 180").strip()
    from backend.services.ai_parser import parse_expense_text
    service = ExpenseService(db_session)
    categories = service.get_categories_dict()
    cfg = Setting.get(db_session, "ai_config", {})
    creds = Setting.get(db_session, "api_credentials", {})
    if creds:
        cfg.update(creds)

    items = parse_expense_text(text, config=cfg, categories_dict=categories, prefer_ai=True)
    return jsonify({
        "success": True if items else False,
        "items": items,
        "message": f"Successfully parsed {len(items)} expense(s) using AI" if items else "AI parsing returned no items"
    })

# =========================================================================
# EXPENSE EXPORT (CSV / JSON)
# =========================================================================

@app.route("/api/expenses/export", methods=["GET"])
def export_expenses():
    import csv
    import io
    from datetime import datetime
    from flask import Response

    fmt = request.args.get("format", "csv").lower()
    category = request.args.get("category")
    payment_mode = request.args.get("payment_mode")
    search = request.args.get("search")
    from_date = request.args.get("from_date")
    to_date = request.args.get("to_date")

    service = ExpenseService(db_session)
    data = service.get_expenses(page=1, limit=10000, category=category, payment_mode=payment_mode, search=search, from_date=from_date, to_date=to_date)
    items = data.get("items", [])

    if fmt == "json":
        return jsonify(items)

    si = io.StringIO()
    writer = csv.writer(si)
    writer.writerow(["ID", "Date", "Description", "Category", "Subcategory", "Amount", "Payment Mode", "Notes", "Source"])
    for item in items:
        writer.writerow([
            item.get("id"),
            item.get("date"),
            item.get("description"),
            item.get("category"),
            item.get("subcategory"),
            item.get("amount"),
            item.get("payment_mode"),
            item.get("notes"),
            item.get("source")
        ])

    output = si.getvalue()
    filename = f"expenses_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    return Response(
        output,
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment;filename={filename}"}
    )

# =========================================================================
# DATABASE BACKUP
# =========================================================================

@app.route("/api/database/backup", methods=["POST"])
def trigger_backup():
    try:
        path = backup_database()
        return jsonify({"success": True, "backup_file": path})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

def create_app():
    init_db()
    scheduler = ExpenseScheduler()
    scheduler.start()
    return app

if __name__ == "__main__":
    init_db()
    scheduler = ExpenseScheduler()
    scheduler.start()
    print(f"🚀 Expense Manager starting on http://{Config.HOST}:{Config.PORT}")
    app.run(host=Config.HOST, port=Config.PORT, debug=Config.DEBUG)
