import json
import time
from datetime import datetime, timedelta
from sqlalchemy import func, desc, or_
from backend.models import Expense, Category, Subcategory, PaymentMode, Budget, ExpenseQueue, Setting, AuditLog
from backend.services.ai_parser import parse_expense_text

class ExpenseService:
    def __init__(self, db_session):
        self.db = db_session

    def get_expenses(self, page=1, limit=50, category=None, payment_mode=None, search=None, from_date=None, to_date=None):
        query = self.db.query(Expense)

        if category:
            query = query.filter(Expense.category == category)
        if payment_mode:
            query = query.filter(Expense.payment_mode == payment_mode)
        if search:
            search_term = f"%{search}%"
            query = query.filter(
                or_(
                    Expense.description.ilike(search_term),
                    Expense.notes.ilike(search_term),
                    Expense.subcategory.ilike(search_term)
                )
            )
        if from_date:
            query = query.filter(Expense.date >= from_date)
        if to_date:
            query = query.filter(Expense.date <= to_date)

        total_count = query.count()
        query = query.order_by(desc(Expense.date), desc(Expense.time), desc(Expense.created_at))
        
        offset = (page - 1) * limit
        items = query.offset(offset).limit(limit).all()

        return {
            "total": total_count,
            "page": page,
            "limit": limit,
            "items": [item.to_dict() for item in items]
        }

    def add_expense(self, date, category, description, amount, subcategory="", payment_mode="UPI", notes="", original_msg="", source="Manual"):
        amount = float(amount)
        # Duplicate detection check
        if original_msg:
            existing = self.db.query(Expense).filter(
                Expense.original_msg == original_msg,
                Expense.date == date,
                Expense.amount == amount
            ).first()
            if existing:
                return existing.to_dict(), False

        expense_id = str(int(time.time() * 1000))
        now = datetime.now()

        exp = Expense(
            id=expense_id,
            date=date or now.strftime("%Y-%m-%d"),
            time=now.strftime("%H:%M:%S"),
            category=category,
            subcategory=subcategory,
            description=description,
            amount=amount,
            payment_mode=payment_mode or "UPI",
            notes=notes,
            original_msg=original_msg,
            source=source,
            created_at=now
        )
        self.db.add(exp)
        
        # Log audit
        self.db.add(AuditLog(
            event_type="expense_added",
            message=f"Added {category} expense: {description} (Rs.{amount})",
            details_json=json.dumps({"id": expense_id, "amount": amount, "category": category})
        ))
        self.db.commit()
        return exp.to_dict(), True

    def update_expense(self, expense_id, **kwargs):
        exp = self.db.query(Expense).filter_by(id=expense_id).first()
        if not exp:
            return None

        for field in ("date", "category", "subcategory", "description", "amount", "payment_mode", "notes"):
            if field in kwargs and kwargs[field] is not None:
                val = kwargs[field]
                if field == "amount":
                    val = float(val)
                setattr(exp, field, val)

        self.db.commit()
        return exp.to_dict()

    def delete_expense(self, expense_id):
        exp = self.db.query(Expense).filter_by(id=expense_id).first()
        if not exp:
            return False

        self.db.add(AuditLog(
            event_type="expense_deleted",
            message=f"Deleted expense {exp.description} (Rs.{exp.amount})",
            details_json=json.dumps({"id": exp.id, "amount": exp.amount})
        ))
        self.db.delete(exp)
        self.db.commit()
        return True

    def get_dashboard_stats(self):
        now = datetime.now()
        today_str = now.strftime("%Y-%m-%d")
        current_month = now.strftime("%Y-%m")
        prev_month = (now.replace(day=1) - timedelta(days=1)).strftime("%Y-%m")

        # Total All-Time
        total_all_time = self.db.query(func.coalesce(func.sum(Expense.amount), 0.0)).scalar()
        total_count = self.db.query(func.count(Expense.id)).scalar()

        # Today
        today_total = self.db.query(func.coalesce(func.sum(Expense.amount), 0.0)).filter(Expense.date == today_str).scalar()
        today_count = self.db.query(func.count(Expense.id)).filter(Expense.date == today_str).scalar()

        # This Month
        month_query = self.db.query(Expense).filter(Expense.date.like(f"{current_month}%"))
        this_month_total = self.db.query(func.coalesce(func.sum(Expense.amount), 0.0)).filter(Expense.date.like(f"{current_month}%")).scalar()
        prev_month_total = self.db.query(func.coalesce(func.sum(Expense.amount), 0.0)).filter(Expense.date.like(f"{prev_month}%")).scalar()

        # Category Breakdown for this month
        cat_stats = self.db.query(
            Expense.category,
            func.sum(Expense.amount).label("total"),
            func.count(Expense.id).label("count")
        ).filter(Expense.date.like(f"{current_month}%")).group_by(Expense.category).order_by(desc("total")).all()

        category_breakdown = [
            {"category": row[0], "total": float(row[1]), "count": row[2]}
            for row in cat_stats
        ]

        # Recent 7 days trend
        trends = []
        for i in range(6, -1, -1):
            d = (now - timedelta(days=i)).strftime("%Y-%m-%d")
            day_total = self.db.query(func.coalesce(func.sum(Expense.amount), 0.0)).filter(Expense.date == d).scalar()
            trends.append({"date": d, "total": float(day_total)})

        # Pending Queue Count
        pending_queue = self.db.query(func.count(ExpenseQueue.id)).filter(ExpenseQueue.status == "pending").scalar()

        return {
            "total_all_time": float(total_all_time),
            "total_count": total_count,
            "today_total": float(today_total),
            "today_count": today_count,
            "this_month_total": float(this_month_total),
            "prev_month_total": float(prev_month_total),
            "month_growth_pct": round(((this_month_total - prev_month_total) / prev_month_total * 100), 1) if prev_month_total > 0 else 0,
            "category_breakdown": category_breakdown,
            "daily_trends": trends,
            "pending_queue_count": pending_queue
        }

    def process_queue(self):
        """Batch process queued raw messages using parser service."""
        queue_items = self.db.query(ExpenseQueue).filter_by(status="pending").all()
        categories = self.get_categories_dict()
        cfg = Setting.get(self.db, "expense_config", {})
        creds = Setting.get(self.db, "api_credentials", {})
        if creds:
            cfg.update(creds)

        processed_count = 0
        now = datetime.now()

        for item in queue_items:
            results = parse_expense_text(item.raw_message, config=cfg, categories_dict=categories)
            if results:
                for r in results:
                    exp_data, is_new = self.add_expense(
                        date=now.strftime("%Y-%m-%d"),
                        category=r.get("category", "Miscellaneous"),
                        subcategory=r.get("subcategory", "General"),
                        description=r.get("description", "Expense"),
                        amount=r.get("amount", 0.0),
                        payment_mode="UPI",
                        notes=f"Auto-parsed via {r.get('parser', 'ai')}",
                        original_msg=item.raw_message,
                        source=f"Queue_{item.platform}"
                    )
                    if is_new:
                        processed_count += 1
                item.status = "processed"
                item.processed_at = now
            else:
                item.status = "failed"
                item.processed_at = now

        self.db.commit()
        return processed_count

    def get_categories_dict(self):
        categories = self.db.query(Category).all()
        return {cat.name: [sub.name for sub in cat.subcategories] for cat in categories}

    def get_categories_detailed(self):
        cats = self.db.query(Category).all()
        result = []
        for c in cats:
            # Calculate total spend in this category
            spend = self.db.query(func.coalesce(func.sum(Expense.amount), 0.0)).filter(Expense.category == c.name).scalar()
            count = self.db.query(func.count(Expense.id)).filter(Expense.category == c.name).scalar()
            result.append({
                "id": c.id,
                "name": c.name,
                "color": c.color or "#10B981",
                "icon": c.icon or "fa-tag",
                "total_spend": float(spend),
                "transaction_count": count,
                "subcategories": [{"id": s.id, "name": s.name} for s in c.subcategories]
            })
        return result

    def add_category(self, name: str, color: str = "#10B981", icon: str = "fa-tag"):
        clean_name = name.strip()
        existing = self.db.query(Category).filter_by(name=clean_name).first()
        if existing:
            return existing.to_dict(), False
        cat = Category(name=clean_name, color=color, icon=icon)
        self.db.add(cat)
        self.db.commit()
        return cat.to_dict(), True

    def delete_category(self, category_id: int):
        cat = self.db.query(Category).filter_by(id=category_id).first()
        if not cat:
            return False
        self.db.delete(cat)
        self.db.commit()
        return True

    def add_subcategory(self, category_id: int, sub_name: str):
        cat = self.db.query(Category).filter_by(id=category_id).first()
        if not cat:
            return None
        clean_sub = sub_name.strip()
        existing = self.db.query(Subcategory).filter_by(category_id=category_id, name=clean_sub).first()
        if existing:
            return {"id": existing.id, "name": existing.name}
        sub = Subcategory(category_id=category_id, name=clean_sub)
        self.db.add(sub)
        self.db.commit()
        return {"id": sub.id, "name": sub.name}

    def delete_subcategory(self, subcategory_id: int):
        sub = self.db.query(Subcategory).filter_by(id=subcategory_id).first()
        if not sub:
            return False
        self.db.delete(sub)
        self.db.commit()
        return True

