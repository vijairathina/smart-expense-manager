# Setup & Deployment Guide - Expense Manager

## Local Development Setup
1. Open terminal in `Projects/ExpenseManager/`.
2. Create and activate a Python virtual environment:
   ```bash
   python -m venv venv
   # Windows:
   .\venv\Scripts\activate
   # Linux/macOS:
   source venv/bin/activate
   ```
3. Install required packages:
   ```bash
   pip install -r requirements.txt
   ```
4. Copy `.env.example` to `.env` and configure settings as desired:
   ```bash
   copy .env.example .env
   ```
5. Initialize the SQLite database:
   ```bash
   python migrations/init_db.py
   ```
6. Run the application:
   ```bash
   python run.py
   ```
7. Visit `http://localhost:5001`.

## Production Deployment (Windows Service / Linux Systemd)
### Systemd Service (Linux)
Create `/etc/systemd/system/expense-manager.service`:
```ini
[Unit]
Description=Expense Manager Service
After=network.target

[Service]
User=appuser
WorkingDirectory=/opt/ExpenseManager
ExecStart=/opt/ExpenseManager/venv/bin/gunicorn -w 4 -b 0.0.0.0:5001 backend.app:app
Restart=always

[Install]
WantedBy=multi-user.target
```
Start and enable:
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now expense-manager
```
