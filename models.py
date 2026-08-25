"""
Database layer for QuickPOS.
Uses Python's built-in sqlite3 — no ORM, no extra deps.
"""
import sqlite3
import os
import sys
from contextlib import contextmanager
from datetime import datetime

if getattr(sys, "frozen", False):
    _DATA_DIR = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "QuickPOS")
else:
    _DATA_DIR = os.path.dirname(os.path.abspath(__file__))

os.makedirs(_DATA_DIR, exist_ok=True)

DATA_DIR = _DATA_DIR
DB_PATH = os.path.join(DATA_DIR, "quickpos.db")


def get_db():
    """Get a sqlite3 connection with row factory enabled."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def get_db_cursor():
    """Context manager that commits on success and rolls back on error."""
    conn = get_db()
    try:
        cur = conn.cursor()
        yield cur
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    """Create all tables if they don't exist."""
    with get_db_cursor() as cur:
        cur.executescript("""
        CREATE TABLE IF NOT EXISTS categories (
            id TEXT PRIMARY KEY,
            name TEXT UNIQUE NOT NULL,
            description TEXT,
            color TEXT DEFAULT '#10b981',
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS products (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            sku TEXT UNIQUE NOT NULL,
            barcode TEXT,
            description TEXT,
            category_id TEXT NOT NULL,
            price REAL NOT NULL,
            cost REAL DEFAULT 0,
            stock INTEGER DEFAULT 0,
            low_stock_threshold INTEGER DEFAULT 10,
            unit TEXT DEFAULT 'pcs',
            image_url TEXT,
            is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE RESTRICT
        );

        CREATE TABLE IF NOT EXISTS customers (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT,
            phone TEXT,
            address TEXT,
            loyalty_points INTEGER DEFAULT 0,
            total_spent REAL DEFAULT 0,
            orders_count INTEGER DEFAULT 0,
            note TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT DEFAULT 'cashier',
            is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS password_resets (
            id TEXT PRIMARY KEY,
            email TEXT NOT NULL,
            otp TEXT NOT NULL,
            otp_expires_at TEXT NOT NULL,
            used INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS orders (
            id TEXT PRIMARY KEY,
            order_number TEXT UNIQUE NOT NULL,
            customer_id TEXT,
            user_id TEXT,
            cashier_name TEXT DEFAULT 'Cashier',
            subtotal REAL NOT NULL,
            tax_rate REAL DEFAULT 0,
            tax REAL DEFAULT 0,
            discount REAL DEFAULT 0,
            total REAL NOT NULL,
            payment_method TEXT DEFAULT 'cash',
            payment_status TEXT DEFAULT 'paid',
            status TEXT DEFAULT 'completed',
            note TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE SET NULL,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS order_items (
            id TEXT PRIMARY KEY,
            order_id TEXT NOT NULL,
            product_id TEXT NOT NULL,
            name TEXT NOT NULL,
            price REAL NOT NULL,
            cost REAL DEFAULT 0,
            quantity INTEGER NOT NULL,
            subtotal REAL NOT NULL,
            FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE,
            FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE RESTRICT
        );

        CREATE TABLE IF NOT EXISTS settings (
            id TEXT PRIMARY KEY,
            store_name TEXT DEFAULT 'QuickPOS Store',
            address TEXT DEFAULT '123 Main Street',
            phone TEXT DEFAULT '+1 555 0100',
            email TEXT DEFAULT 'store@quickpos.com',
            tax_rate REAL DEFAULT 8,
            currency TEXT DEFAULT 'PKR',
            currency_symbol TEXT DEFAULT 'Rs',
            receipt_footer TEXT DEFAULT 'Thank you for shopping with us!',
            low_stock_alert_enabled INTEGER DEFAULT 1,
            updated_at TEXT DEFAULT (datetime('now'))
        );

        CREATE INDEX IF NOT EXISTS idx_products_category ON products(category_id);
        CREATE INDEX IF NOT EXISTS idx_products_sku ON products(sku);
        CREATE INDEX IF NOT EXISTS idx_orders_customer ON orders(customer_id);
        CREATE INDEX IF NOT EXISTS idx_orders_created ON orders(created_at);
        CREATE INDEX IF NOT EXISTS idx_order_items_order ON order_items(order_id);
        CREATE INDEX IF NOT EXISTS idx_order_items_product ON order_items(product_id);
        """)

    # Migrate SMTP columns onto settings table (safe for existing DBs)
    for col in ["smtp_host", "smtp_port", "smtp_user", "smtp_pass", "smtp_from_email",
                 "gdrive_client_id", "gdrive_client_secret"]:
        try:
            execute(f"ALTER TABLE settings ADD COLUMN {col} TEXT")
        except Exception:
            pass

    # Existing shops still on the original USD factory default switch to PKR once.
    # A store that already chose another currency is left alone.
    try:
        execute(
            "UPDATE settings SET currency = 'PKR', currency_symbol = 'Rs' "
            "WHERE currency = 'USD' AND currency_symbol = '$'"
        )
    except Exception:
        pass

    # Existing DBs: attach the selling user to each order.
    try:
        execute("ALTER TABLE orders ADD COLUMN user_id TEXT")
    except Exception:
        pass
    try:
        execute("CREATE INDEX IF NOT EXISTS idx_orders_user ON orders(user_id)")
    except Exception:
        pass

    # Remove the seed demo cashier — sales belong to real user accounts.
    try:
        demo = query_one(
            "SELECT id FROM users WHERE email = ?",
            ("cashier@quickpos.com",),
        )
        if demo:
            execute("DELETE FROM users WHERE id = ?", (demo["id"],))
    except Exception:
        pass


# ---- Query helpers ----

def query_all(sql, params=()):
    with get_db_cursor() as cur:
        cur.execute(sql, params)
        return [dict(row) for row in cur.fetchall()]


def query_one(sql, params=()):
    with get_db_cursor() as cur:
        cur.execute(sql, params)
        row = cur.fetchone()
        return dict(row) if row else None


def execute(sql, params=()):
    with get_db_cursor() as cur:
        cur.execute(sql, params)
        return cur.rowcount


def execute_many(sql, params_list):
    with get_db_cursor() as cur:
        cur.executemany(sql, params_list)
        return cur.rowcount


def get_settings():
    s = query_one("SELECT * FROM settings LIMIT 1")
    if not s:
        import uuid
        execute(
            "INSERT INTO settings (id, store_name, currency, currency_symbol) VALUES (?, ?, ?, ?)",
            (str(uuid.uuid4()), "QuickPOS Store", "PKR", "Rs"),
        )
        s = query_one("SELECT * FROM settings LIMIT 1")
    if s:
        s['low_stock_alert_enabled'] = bool(s['low_stock_alert_enabled'])
    return s
