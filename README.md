unzip quickpos-python.zip
cd quickpos-python
pip install -r requirements.txt
python seed.py          # Initialize DB + demo data
python app.py           # Start at http://localhost:5001


Default SQLITE DATABASE BACKUP (AUTOMATICALLY GENERATED WHEN YOU CREATE YOUR ACCOUNT)
C:\Users\Administrator\AppData\Local\QuickPOS\quickpos.db

DEFAULT USER ID AND PASSWORD
USER ID			:	admin@quickpos.com
USER PASSWORD	:	Admin@202600

# QuickPOS — Python Edition

A complete desktop Point of Sale application built with **Python + Flask + Jinja2 + Tailwind CSS + Chart.js**.

Same 8-module POS as the Next.js version, but rewritten as a pure Python app. Run `python app.py` and open in your browser.

## ✨ Features

| Module | Description |
|--------|-------------|
| **Dashboard** | KPI cards, 7-day revenue trend, hourly sales, category breakdown, top products, payment-method mix, recent orders, low-stock alerts |
| **POS Terminal** | Category-filtered product grid, live cart, customer selector, discount, checkout (cash/card/wallet), quick-cash buttons, change calculation, printable receipt |
| **Products** | Filterable table with margins & stock badges, add/edit dialog, tabbed Categories manager with color picker |
| **Orders** | Searchable history, payment-method filters, KPI summary, detailed receipt dialog |
| **Inventory** | Stock-level progress bars, status badges (out/low/healthy/overstock), add/remove/set adjustment dialog with reason |
| **Customers** | Bronze/Silver/Gold/Platinum loyalty tiers, CRUD, lifetime value tracking |
| **Reports** | 7/30/90-day selector, revenue vs profit trend, order volume, category pie + bar charts, top-10 products |
| **Settings** | Store info, tax rate, currency selector with live preview, receipt footer editor, low-stock toggle |

## 🚀 Quick Start

### Prerequisites

- **Python 3.9+** — https://python.org

### Installation

```bash
# 1. (Optional) Create a virtual environment
python -m venv venv
source venv/bin/activate        # Linux/macOS
# venv\Scripts\activate         # Windows

# 2. Install Flask
pip install -r requirements.txt

# 3. Initialize the database + seed demo data
python seed.py

# 4. Run the app
python app.py
```

Open **http://localhost:5001** in your browser.

## 📜 Commands

| Command | Description |
|---------|-------------|
| `python seed.py` | Initialize DB schema + seed demo data (run once) |
| `python app.py` | Start the dev server (port 5001) |
| `pip install -r requirements.txt` | Install dependencies |

## 🗂 Project Structure

```
.
├── app.py                 # Flask app: all routes + checkout API
├── models.py              # SQLite schema + query helpers
├── seed.py                # Demo data seeder
├── requirements.txt       # Flask dependency
├── quickpos.db            # SQLite database (auto-created)
├── templates/
│   ├── base.html          # Layout: sidebar + header + dark mode
│   ├── dashboard.html
│   ├── pos.html
│   ├── products.html
│   ├── orders.html
│   ├── inventory.html
│   ├── customers.html
│   ├── reports.html
│   └── settings.html
└── static/
    ├── css/
    │   └── app.css        # Custom scrollbar + animations
    └── js/
        └── pos.js         # Cart logic + checkout + receipt
```

## 🎨 Tech Stack

- **Python 3.9+**
- **Flask 3.0** — web framework
- **Jinja2** — templating (built into Flask)
- **sqlite3** — stdlib database (no extra install)
- **Tailwind CSS** — via CDN (no build step)
- **Chart.js 4** — via CDN for charts
- **Lucide Icons** — via CDN
- **Vanilla JS** — cart + UI interactions (no framework needed)

## 💾 Database

SQLite database at `quickpos.db` (auto-created in the project folder).

**Schema:**
- `categories` — name, description, color
- `products` — name, SKU, price, cost, stock, category_id, is_active
- `customers` — name, contact, loyalty_points, total_spent
- `orders` — order_number, totals, payment_method, customer_id
- `order_items` — order_id, product_id, quantity, subtotal
- `settings` — store_name, tax_rate, currency, receipt_footer

To switch to PostgreSQL or MySQL, replace `sqlite3` calls in `models.py` with `psycopg2` or `pymysql` (or adopt SQLAlchemy).

## 🔧 Customization

- **Currency / tax**: Settings view (in-app) → updates `settings` table
- **Colors per category**: Products → Categories tab
- **Demo data**: Edit `seed.py` and re-run `python seed.py`

## 🌐 Why Python?

This version is for Python developers who want:
- A self-contained app with **zero build step**
- Easy deployment to any server with Python installed
- Direct access to Python's data ecosystem (Pandas, NumPy) for analytics
- Simple integration with Python ML models or automation

## 📝 License

MIT — use it, fork it, sell it.
