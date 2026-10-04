import os
import sys
import unittest
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

# Use in-memory SQLite for testing
os.environ["DATABASE_PATH"] = ":memory:"

from backend.database import Base, engine, db_session
from backend.models import Expense, Category, PaymentMode
from backend.services.expense_service import ExpenseService
from backend.services.ai_parser import fast_regex_parse

class TestExpenseManager(unittest.TestCase):
    def setUp(self):
        Base.metadata.create_all(bind=engine)
        self.session = db_session()
        self.service = ExpenseService(self.session)

    def tearDown(self):
        self.session.close()
        Base.metadata.drop_all(bind=engine)

    def test_add_and_get_expense(self):
        exp, is_new = self.service.add_expense(
            date="2026-03-01",
            category="Food & Dining",
            subcategory="Groceries",
            description="Mutton 1kg",
            amount=1000.0,
            payment_mode="UPI"
        )
        self.assertTrue(is_new)
        self.assertEqual(exp["amount"], 1000.0)

        # Retrieve
        result = self.service.get_expenses()
        self.assertEqual(result["total"], 1)
        self.assertEqual(result["items"][0]["description"], "Mutton 1kg")

    def test_duplicate_prevention(self):
        self.service.add_expense(
            date="2026-03-01",
            category="Utilities",
            description="Water bill",
            amount=500.0,
            original_msg="500 for water bill"
        )
        # Duplicate attempt with identical original_msg, date, amount
        exp, is_new = self.service.add_expense(
            date="2026-03-01",
            category="Utilities",
            description="Water bill duplicate",
            amount=500.0,
            original_msg="500 for water bill"
        )
        self.assertFalse(is_new)
        self.assertEqual(self.service.get_expenses()["total"], 1)

    def test_fast_regex_parser(self):
        sample = """Mutton 1kg 1000
Vegetable onion 70
600 for tution"""
        parsed = fast_regex_parse(sample)
        self.assertEqual(len(parsed), 3)
        self.assertEqual(parsed[0]["amount"], 1000.0)
        self.assertEqual(parsed[1]["amount"], 70.0)
        self.assertEqual(parsed[2]["amount"], 600.0)

if __name__ == "__main__":
    unittest.main()
