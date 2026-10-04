import os
import sys
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass
import hashlib
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from backend.database import init_db, db_session
from backend.models import User, Category, Subcategory, PaymentMode, Setting

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()

def run_migrations():
    print("🚀 Initializing Expense Manager SQLite schema...")
    init_db()
    session = db_session()

    # Seed Admin User if none exists
    admin = session.query(User).filter_by(username="admin").first()
    if not admin:
        admin = User(
            username="admin",
            password_hash=hash_password("admin123"),
            role="admin"
        )
        session.add(admin)
        print("✓ Created default admin user (admin / admin123)")

    # Seed Default Payment Modes
    default_modes = ["UPI", "Cash", "Credit Card", "Debit Card", "Net Banking"]
    for mode_name in default_modes:
        existing = session.query(PaymentMode).filter_by(name=mode_name).first()
        if not existing:
            session.add(PaymentMode(name=mode_name, is_default=(mode_name == "UPI")))
    print("✓ Seeded default payment modes")

    # Seed Baseline Categories if empty
    if session.query(Category).count() == 0:
        default_cats = {
            "Home & Living": ["Groceries", "Vegetables", "Milk", "Household", "Maintenance"],
            "Food & Dining": ["Restaurants", "Snacks", "Coffee", "Delivery"],
            "Utilities": ["Electricity", "Water", "Internet", "Gas", "Mobile Recharge"],
            "Transportation": ["Fuel", "Cab", "Public Transport", "Service"],
            "Health & Medical": ["Medicines", "Doctor", "Tests"],
            "Education": ["Tuition", "Books", "Courses"],
            "Family & Personal": ["Kids", "Clothing", "Gifts", "Personal Care"],
            "Investments & Savings": ["SIP", "Mutual Funds", "Recurring Deposit", "Stocks"],
            "Entertainment": ["Movies", "Subscriptions", "Outing"],
            "Miscellaneous": ["General"]
        }
        for cat_name, subs in default_cats.items():
            cat = Category(name=cat_name)
            session.add(cat)
            session.flush()
            for sub_name in subs:
                session.add(Subcategory(category_id=cat.id, name=sub_name))
        print("✓ Seeded initial default categories")

    session.commit()
    session.close()
    print("✅ Expense Manager database initialized successfully!")

if __name__ == "__main__":
    run_migrations()
