import json
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Float, Text, Boolean, DateTime, ForeignKey, Index
)
from sqlalchemy.orm import relationship
from backend.database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(80), unique=True, nullable=False, index=True)
    password_hash = Column(String(256), nullable=False)
    role = Column(String(20), default="admin")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "username": self.username,
            "role": self.role,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }

class Category(Base):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), unique=True, nullable=False, index=True)
    color = Column(String(30), default="#10B981")
    icon = Column(String(50), default="fa-tag")
    is_active = Column(Boolean, default=True)

    subcategories = relationship("Subcategory", back_populates="category", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "color": self.color,
            "icon": self.icon,
            "is_active": self.is_active,
            "subcategories": [sub.name for sub in self.subcategories]
        }

class Subcategory(Base):
    __tablename__ = "subcategories"

    id = Column(Integer, primary_key=True, autoincrement=True)
    category_id = Column(Integer, ForeignKey("categories.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(100), nullable=False)

    category = relationship("Category", back_populates="subcategories")

class PaymentMode(Base):
    __tablename__ = "payment_modes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(50), unique=True, nullable=False)
    is_default = Column(Boolean, default=False)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "is_default": self.is_default
        }

class Expense(Base):
    __tablename__ = "expenses"

    id = Column(String(50), primary_key=True) # supports original VTES millisecond timestamps
    date = Column(String(20), nullable=False, index=True)
    time = Column(String(20), nullable=True)
    category = Column(String(100), nullable=False, index=True)
    subcategory = Column(String(100), nullable=True)
    description = Column(String(255), nullable=False)
    amount = Column(Float, nullable=False, index=True)
    payment_mode = Column(String(50), default="UPI")
    notes = Column(Text, nullable=True)
    original_msg = Column(Text, nullable=True)
    source = Column(String(50), default="Manual") # Manual, WhatsApp, Telegram, AI Batch
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    __table_args__ = (
        Index("idx_expense_date_category", "date", "category"),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "date": self.date,
            "time": self.time or "",
            "category": self.category,
            "subcategory": self.subcategory or "",
            "description": self.description,
            "amount": self.amount,
            "payment_mode": self.payment_mode or "UPI",
            "notes": self.notes or "",
            "original_msg": self.original_msg or "",
            "source": self.source or "Manual",
            "created_at": self.created_at.isoformat() if self.created_at else None
        }

class Budget(Base):
    __tablename__ = "budgets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    month_year = Column(String(7), nullable=False, index=True) # YYYY-MM
    category_id = Column(Integer, ForeignKey("categories.id", ondelete="SET NULL"), nullable=True)
    amount_limit = Column(Float, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "month_year": self.month_year,
            "category_id": self.category_id,
            "amount_limit": self.amount_limit,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }

class ExpenseQueue(Base):
    __tablename__ = "expense_queue"

    id = Column(Integer, primary_key=True, autoincrement=True)
    raw_message = Column(Text, nullable=False)
    sender = Column(String(100), nullable=True)
    platform = Column(String(50), default="direct")
    status = Column(String(30), default="pending") # pending, processed, failed, ignored
    received_at = Column(DateTime, default=datetime.utcnow)
    processed_at = Column(DateTime, nullable=True)
    parsed_expense_id = Column(String(50), nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "raw_message": self.raw_message,
            "sender": self.sender or "",
            "platform": self.platform or "",
            "status": self.status,
            "received_at": self.received_at.isoformat() if self.received_at else None,
            "processed_at": self.processed_at.isoformat() if self.processed_at else None,
            "parsed_expense_id": self.parsed_expense_id
        }

class Setting(Base):
    __tablename__ = "settings"

    key = Column(String(100), primary_key=True)
    value_json = Column(Text, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @classmethod
    def get(cls, session, key, default=None):
        row = session.query(cls).filter_by(key=key).first()
        if not row:
            return default
        try:
            return json.loads(row.value_json)
        except Exception:
            return row.value_json

    @classmethod
    def set(cls, session, key, value):
        val_str = json.dumps(value) if not isinstance(value, str) else value
        row = session.query(cls).filter_by(key=key).first()
        if row:
            row.value_json = val_str
            row.updated_at = datetime.utcnow()
        else:
            row = cls(key=key, value_json=val_str)
            session.add(row)
        session.commit()

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_type = Column(String(50), nullable=False, index=True) # expense_added, category_created, ai_parsed, backup
    message = Column(String(255), nullable=False)
    details_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    def to_dict(self):
        return {
            "id": self.id,
            "event_type": self.event_type,
            "message": self.message,
            "details": json.loads(self.details_json) if self.details_json else {},
            "created_at": self.created_at.isoformat() if self.created_at else None
        }
