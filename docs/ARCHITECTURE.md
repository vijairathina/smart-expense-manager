# Architecture Documentation - Expense Manager

## Overview
Expense Manager is designed with a clean, decoupled architecture:
1. **Frontend Layer**: Pure Vanilla HTML5, CSS3 Glassmorphism, and Vanilla JavaScript. No heavy frontend framework builds needed; instantaneous load times and zero compilation overhead.
2. **REST API & Controller Layer (`backend/app.py`)**: Flask micro-framework routing HTTP requests, handling authentication and validation, and returning JSON.
3. **Service Layer (`backend/services/`)**: Business logic, statistics computation, category matching, and AI/regex text extraction.
4. **Data Access Layer (`backend/database.py` & `backend/models.py`)**: SQLAlchemy ORM with scoped sessions connected to a dedicated SQLite instance.
5. **Storage Layer (`data/expense_manager.db`)**: Self-contained SQLite database in WAL (Write-Ahead Logging) mode with foreign keys enabled.

## Data Flow
```text
Browser User
     │ (HTTP / JSON)
     ▼
Flask REST API (`backend/app.py`)
     │
     ├── ExpenseService (`backend/services/expense_service.py`)
     │        │
     │        └── SQLAlchemy Models (`backend/models.py`)
     │                 │
     │                 ▼
     │        SQLite (`data/expense_manager.db`)
     │
     └── AIParser (`backend/services/ai_parser.py`)
              │
              ├── Fast Regex Engine
              ├── OpenRouter API
              └── Google Gemini API
```
