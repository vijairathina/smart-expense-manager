# VTES Data Migration - Expense Manager

## Overview
This document describes how historical data from the legacy VTES monolithic application was migrated into Expense Manager's standalone SQLite database.

## Source Files in VTES
- `expenses.json`: 148 historical transaction records.
- `expense_config.json`: Categories, subcategories, payment modes, and AI feature toggles.
- `credentials.json`: Gemini and OpenRouter API keys.
- `expense_queue.json`: Pending raw messages.

## Execution
The migration is performed by `scripts/migrate_from_vtes.py`:
```bash
python scripts/migrate_from_vtes.py
```

## Migration Verification
1. Open the Expense Manager dashboard at `http://localhost:5001`.
2. Verify total transaction count matches the 148 entries from `expenses.json`.
3. Check category breakdown and all-time total amount.
4. Verify all payment modes (UPI, Cash, etc.) are available in the dropdown.
