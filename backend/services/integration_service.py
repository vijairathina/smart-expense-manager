import requests
import json
from datetime import datetime, timedelta
from sqlalchemy import func, desc
from backend.models import Expense, Setting, AuditLog
from backend.services.ai_parser import parse_expense_text

class IntegrationService:
    def __init__(self, db_session):
        self.db = db_session

    def get_config(self):
        default_cfg = {
            "whatsapp_enabled": True,
            "manywhatsapp_url": "http://127.0.0.1:5003",
            "manywhatsapp_api_key": "",
            "manywhatsapp_account_id": "acc_wa_8ad614",
            "whatsapp_groups": [os.getenv("WHATSAPP_TARGET", "120363213344093218@g.us")],
            "telegram_enabled": True,
            "telegram_bot_token": os.getenv("TELEGRAM_BOT_TOKEN", ""),
            "telegram_chats": [os.getenv("TELEGRAM_CHAT_ID", "1601695381")],
            "auto_report": {
                "daily": True,
                "weekly": True,
                "monthly": True,
                "daily_time": "23:59",
                "weekly_time": "23:59",
                "monthly_time": "23:59",
                "platforms": ["telegram", "whatsapp"]
            }
        }
        stored = Setting.get(self.db, "integration_config")
        if stored and isinstance(stored, dict):
            default_cfg.update(stored)
        return default_cfg

    def save_config(self, cfg_data):
        Setting.set(self.db, "integration_config", cfg_data)

    def send_telegram(self, message: str, chat_ids=None):
        cfg = self.get_config()
        token = cfg.get("telegram_bot_token")
        if not token:
            return False, "Telegram Bot Token not configured"

        targets = chat_ids or cfg.get("telegram_chats", [])
        if not targets:
            return False, "No target Telegram chats configured"

        results = []
        for chat_id in targets:
            try:
                url = f"https://api.telegram.org/bot{token}/sendMessage"
                payload = {
                    "chat_id": chat_id,
                    "text": message,
                    "parse_mode": "Markdown"
                }
                r = requests.post(url, json=payload, timeout=8)
                results.append((chat_id, r.status_code == 200))
            except Exception as e:
                results.append((chat_id, False))

        return True, results

    def send_whatsapp(self, message: str, group_jids=None):
        cfg = self.get_config()
        url = cfg.get("manywhatsapp_url", "http://127.0.0.1:5003").rstrip("/")
        account_id = cfg.get("manywhatsapp_account_id")
        api_key = cfg.get("manywhatsapp_api_key", "")

        targets = group_jids or cfg.get("whatsapp_groups", [])
        if not targets:
            return False, "No target WhatsApp groups configured"

        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["X-API-Key"] = api_key

        results = []
        for target in targets:
            try:
                payload = {
                    "account_id": account_id,
                    "target": target,
                    "message": message,
                    "platform": "whatsapp"
                }
                r = requests.post(f"{url}/api/messages/send", headers=headers, json=payload, timeout=8)
                results.append((target, r.status_code in (200, 201)))
            except Exception as e:
                results.append((target, False))

        return True, results

    def generate_report_text(self, frequency="daily"):
        now = datetime.now()
        today_str = now.strftime("%Y-%m-%d")

        if frequency == "daily":
            start_date = today_str
            end_date = today_str
            title = f"📅 *Daily Expense Report* ({today_str})"
        elif frequency == "weekly":
            start_date = (now - timedelta(days=6)).strftime("%Y-%m-%d")
            end_date = today_str
            title = f"📊 *Weekly Expense Report* ({start_date} to {end_date})"
        else: # monthly
            start_date = now.strftime("%Y-%m-01")
            end_date = today_str
            title = f"💰 *Monthly Expense Report* ({now.strftime('%B %Y')})"

        # Query totals and breakdown
        expenses = self.db.query(Expense).filter(Expense.date >= start_date, Expense.date <= end_date).all()
        total_sum = sum(e.amount for e in expenses)

        cat_breakdown = {}
        for e in expenses:
            cat_breakdown[e.category] = cat_breakdown.get(e.category, 0.0) + e.amount

        sorted_cats = sorted(cat_breakdown.items(), key=lambda x: x[1], reverse=True)

        lines = [
            title,
            "━━━━━━━━━━━━━━━━━━━━",
            f"💵 *Total Spent:* ₹{total_sum:,.2f}",
            f"📝 *Transactions:* {len(expenses)}",
            "",
            "🏷️ *Category Breakdown:*"
        ]

        if not sorted_cats:
            lines.append("  _No expenses recorded in this period._")
        else:
            for cat, amt in sorted_cats:
                pct = (amt / total_sum * 100) if total_sum > 0 else 0
                lines.append(f"  • {cat}: ₹{amt:,.2f} ({pct:.1f}%)")

        lines.append("")
        lines.append("💡 _Expense Manager (Standalone)_")
        return "\n".join(lines)

    def dispatch_report(self, frequency="daily"):
        cfg = self.get_config()
        report_text = self.generate_report_text(frequency)
        platforms = cfg.get("auto_report", {}).get("platforms", ["telegram", "whatsapp"])

        success_tg = False
        success_wa = False

        if "telegram" in platforms:
            success_tg, _ = self.send_telegram(report_text)
        if "whatsapp" in platforms:
            success_wa, _ = self.send_whatsapp(report_text)

        return {
            "frequency": frequency,
            "telegram_sent": success_tg,
            "whatsapp_sent": success_wa,
            "report_preview": report_text
        }

    def list_manywhatsapp_accounts(self):
        """Fetch list of accounts from ManyWhatsApp service (port 5003)."""
        cfg = self.get_config()
        url = cfg.get("manywhatsapp_url", "http://127.0.0.1:5003").rstrip("/")
        api_key = cfg.get("manywhatsapp_api_key", "")
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["X-API-Key"] = api_key

        for endpoint in ["/api/v1/accounts", "/api/accounts"]:
            try:
                r = requests.get(f"{url}{endpoint}", headers=headers, timeout=3)
                if r.status_code == 200:
                    data = r.json()
                    if isinstance(data, dict) and "accounts" in data:
                        return data["accounts"]
                    elif isinstance(data, list):
                        return data
            except Exception:
                pass

        # Return mock / cached defaults if service not reachable
        return [
            {"id": "acc_wa_8ad614", "name": "WhatsApp - Primary", "platform": "whatsapp", "phone": "+91 (Primary)", "status": "Disconnected"},
            {"id": "acc_tg_14f7c2", "name": "Telegram - Primary", "platform": "telegram", "status": "Disconnected"}
        ]

    def get_connections_status(self):
        """Check live connection status for Expense DB, WhatsApp, and Telegram."""
        # 1. Expense DB
        db_ok = True
        try:
            from sqlalchemy import text
            self.db.execute(text("SELECT 1"))
        except Exception:
            db_ok = False

        # 2. WhatsApp (via ManyWhatsApp service)
        cfg = self.get_config()
        wa_url = cfg.get("manywhatsapp_url", "http://127.0.0.1:5003").rstrip("/")
        wa_key = cfg.get("manywhatsapp_api_key", "")
        wa_connected = False
        wa_status_text = "Offline"
        wa_account = cfg.get("manywhatsapp_account_id", "")

        try:
            headers = {"Content-Type": "application/json"}
            if wa_key:
                headers["X-API-Key"] = wa_key
            r = requests.get(f"{wa_url}/api/v1/status", headers=headers, timeout=2)
            if r.status_code == 200:
                s_data = r.json()
                wa_sub = s_data.get("whatsapp", {})
                wa_connected = bool(wa_sub.get("connected", True))
                wa_status_text = "Online" if wa_connected else "Standby"
            else:
                # Try accounts endpoint
                r2 = requests.get(f"{wa_url}/api/v1/accounts", headers=headers, timeout=2)
                if r2.status_code == 200:
                    wa_connected = True
                    wa_status_text = "Online"
        except Exception:
            wa_connected = False
            wa_status_text = "Offline"

        # 3. Telegram
        tg_token = cfg.get("telegram_bot_token", "").strip()
        tg_connected = False
        tg_status_text = "Offline"
        tg_user = None

        if tg_token:
            try:
                r_tg = requests.get(f"https://api.telegram.org/bot{tg_token}/getMe", timeout=3)
                if r_tg.status_code == 200 and r_tg.json().get("ok"):
                    tg_connected = True
                    tg_status_text = "Online"
                    tg_user = r_tg.json().get("result", {}).get("username")
            except Exception:
                tg_connected = False
                tg_status_text = "Offline"

        return {
            "expense_manager": {
                "connected": db_ok,
                "status": "Online" if db_ok else "Degraded"
            },
            "whatsapp": {
                "connected": wa_connected,
                "status": wa_status_text,
                "account_id": wa_account
            },
            "telegram": {
                "connected": tg_connected,
                "status": tg_status_text,
                "bot_username": tg_user
            }
        }

    def process_incoming_message(self, message_text: str, sender: str = "Chat", platform: str = "whatsapp"):
        """Webhook listener for incoming WhatsApp or Telegram expense messages and chat commands."""
        txt = (message_text or "").strip()
        if not txt:
            return None

        low = txt.lower()

        # 1. Chat Report / Summary Commands
        import re
        if re.search(r"\b(report|summary|statement)\b", low):
            freq = "daily"
            if "week" in low:
                freq = "weekly"
            elif "month" in low:
                freq = "monthly"
            rep_text = self.generate_report_text(freq)
            return {
                "is_command": True,
                "parsed_count": 0,
                "reply_message": rep_text
            }

        # 2. Help Command
        if low in ("help", "expense help", "/help", "commands"):
            help_text = (
                "💡 *Expense Manager Help*\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
                "• Send an expense: `Petrol 400` or `Bought Coffee 60`\n"
                "• Multiple expenses: `Milk 40, bread 35, eggs 60`\n"
                "• Daily report: Send `report` or `today report`\n"
                "• Weekly report: Send `weekly report`\n"
                "• Monthly report: Send `monthly report`\n"
            )
            return {
                "is_command": True,
                "parsed_count": 0,
                "reply_message": help_text
            }

        # 3. AI / Regex Expense Parsing
        from backend.services.expense_service import ExpenseService
        service = ExpenseService(self.db)
        categories = service.get_categories_dict()
        ai_cfg = Setting.get(self.db, "ai_config", {})
        api_creds = Setting.get(self.db, "api_credentials", {})
        if api_creds:
            ai_cfg.update(api_creds)

        # Force prefer_ai=True so natural chat messages are parsed with Gemini first
        parsed_items = parse_expense_text(txt, config=ai_cfg, categories_dict=categories, prefer_ai=True)
        if not parsed_items:
            return None

        saved_records = []
        now = datetime.now()
        for item in parsed_items:
            exp_date = item.get("date") or now.strftime("%Y-%m-%d")
            exp, is_new = service.add_expense(
                date=exp_date,
                category=item.get("category", "Miscellaneous"),
                subcategory=item.get("subcategory", "General"),
                description=item.get("description", txt.title()),
                amount=item.get("amount", 0.0),
                payment_mode=item.get("payment_mode", "UPI"),
                notes=f"Auto-captured via {platform} ({item.get('parser', 'ai')})",
                original_msg=txt,
                source=f"{platform.title()}_{sender}"
            )
            saved_records.append(exp)

        # Build response confirmation message in VTES style
        if len(saved_records) == 1:
            rec = saved_records[0]
            reply_message = f"✅ Captured: *{rec['subcategory']}* - ₹{rec['amount']:.2f} ({rec['description']})"
        else:
            total_captured = sum(float(r['amount']) for r in saved_records)
            lines = ["💰 *Captured Multiple Expenses:*"]
            for r in saved_records:
                lines.append(f"• {r['subcategory']} ({r['description']}): ₹{r['amount']:.2f}")
            lines.append("━━━━━━━━━━━━━━")
            lines.append(f"*Total: ₹{total_captured:.2f}*")
            reply_message = "\n".join(lines)

        return {
            "parsed_count": len(saved_records),
            "expenses": saved_records,
            "reply_message": reply_message
        }
