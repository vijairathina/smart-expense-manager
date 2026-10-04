# API Reference - Expense Manager

Base URL: `http://localhost:5001/api`

### Health & Auth
- `GET /health` -> `{ "status": "Online", "database": "Online", "service": "Expense Manager" }`
- `POST /auth/login` -> `{ "username": "admin", "password": "..." }`
- `POST /auth/logout` -> Session cleared
- `GET /auth/me` -> Current authenticated user info

### Expenses
- `GET /expenses?page=1&limit=50&category=Food&search=dinner` -> Paginated expense items with total count.
- `POST /expenses` -> Create expense (`date`, `amount`, `category`, `description`, `payment_mode`, `notes`).
- `PUT /expenses/<id>` -> Update expense fields.
- `DELETE /expenses/<id>` -> Delete expense record.

### Dashboard & Analytics
- `GET /dashboard/stats` -> Returns all-time total, monthly total, today total, category breakdown, 7-day daily trends, and pending queue count.

### Categories & Modes
- `GET /categories` -> List of categories and subcategories.
- `POST /categories` -> Create category or subcategory.
- `GET /payment-modes` -> List of payment methods.
- `POST /payment-modes` -> Add payment method.

### AI Parser & Queue
- `POST /parse-text` -> `{ "text": "..." }` -> Returns extracted expense line items.
- `POST /queue/process` -> Processes all pending queue items into formal expenses.

### Database
- `POST /database/backup` -> Generates SQLite snapshot in `backups/`.
