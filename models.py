"""
Database layer for QuickPOS.
Uses Python's built-in sqlite3 — no ORM, no extra deps.
"""
import json
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
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            description TEXT,
            color TEXT DEFAULT '#10b981',
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            sku TEXT UNIQUE NOT NULL,
            barcode TEXT,
            description TEXT,
            category_id INTEGER NOT NULL,
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
            id INTEGER PRIMARY KEY AUTOINCREMENT,
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
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT DEFAULT 'cashier',
            is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS password_resets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL,
            otp TEXT NOT NULL,
            otp_expires_at TEXT NOT NULL,
            used INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_number TEXT UNIQUE NOT NULL,
            customer_id INTEGER,
            user_id INTEGER,
            cashier_name TEXT DEFAULT 'Cashier',
            subtotal REAL NOT NULL,
            tax_rate REAL DEFAULT 0,
            tax REAL DEFAULT 0,
            discount REAL DEFAULT 0,
            original_total REAL,
            total REAL NOT NULL,
            cash_received REAL,
            order_detail JSON,
            payment_method TEXT DEFAULT 'cash',
            payment_status TEXT DEFAULT 'paid',
            status TEXT DEFAULT 'completed',
            note TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE SET NULL,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS order_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            original_price REAL,
            price REAL NOT NULL,
            cost REAL DEFAULT 0,
            quantity INTEGER NOT NULL,
            subtotal REAL NOT NULL,
            FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE,
            FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE RESTRICT
        );

        CREATE TABLE IF NOT EXISTS settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            store_name TEXT DEFAULT 'QuickPOS Store',
            address TEXT DEFAULT '123 Main Street',
            phone TEXT DEFAULT '+1 555 0100',
            email TEXT DEFAULT 'store@quickpos.com',
            tax_rate REAL DEFAULT 8,
            currency TEXT DEFAULT 'PKR',
            currency_symbol TEXT DEFAULT 'Rs',
            receipt_footer TEXT DEFAULT 'Thank you for shopping with us!',
            low_stock_alert_enabled INTEGER DEFAULT 1,
            smtp_host TEXT,
            smtp_port TEXT,
            smtp_user TEXT,
            smtp_pass TEXT,
            smtp_from_email TEXT,
            gdrive_client_id TEXT,
            gdrive_client_secret TEXT,
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

    # Existing DBs: persist cash tendered at checkout.
    try:
        execute("ALTER TABLE orders ADD COLUMN cash_received REAL")
    except Exception:
        pass

    # Catalog total before line-price edits, discount, and final-total override.
    try:
        execute("ALTER TABLE orders ADD COLUMN original_total REAL")
    except Exception:
        pass

    # Full sale snapshot (items, catalog vs sold prices, totals) as JSON.
    try:
        execute("ALTER TABLE orders ADD COLUMN order_detail JSON")
    except Exception:
        pass

    try:
        execute("ALTER TABLE order_items ADD COLUMN original_price REAL")
    except Exception:
        pass
    try:
        execute("CREATE INDEX IF NOT EXISTS idx_orders_user ON orders(user_id)")
    except Exception:
        pass

    # Remove the seed demo cashier before ID rebuild so 1,2,3 stay contiguous.
    try:
        demo = query_one(
            "SELECT id FROM users WHERE email = ?",
            ("cashier@quickpos.com",),
        )
        if demo:
            execute("DELETE FROM users WHERE id = ?", (demo["id"],))
    except Exception:
        pass

    _migrate_text_ids_to_integer()


def _id_is_integer(conn, table):
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    for col in rows:
        if col[1] == "id":
            return str(col[2] or "").upper().startswith("INT")
    return False


def _map_fk(mapping, old_value):
    if old_value is None:
        return None
    return mapping.get(str(old_value))


def _remap_order_detail(raw, new_order_id, maps):
    if not raw:
        return None
    try:
        detail = json.loads(raw) if isinstance(raw, str) else dict(raw)
    except (TypeError, ValueError, json.JSONDecodeError):
        return raw
    detail["order_id"] = new_order_id
    if detail.get("customer_id") is not None:
        mapped = maps["customers"].get(str(detail["customer_id"]))
        if mapped is not None:
            detail["customer_id"] = mapped
    if detail.get("user_id") is not None:
        mapped = maps["users"].get(str(detail["user_id"]))
        if mapped is not None:
            detail["user_id"] = mapped
    for it in detail.get("items") or []:
        if it.get("product_id") is not None:
            mapped = maps["products"].get(str(it["product_id"]))
            if mapped is not None:
                it["product_id"] = mapped
    for it in detail.get("price_changes") or []:
        if it.get("product_id") is not None:
            mapped = maps["products"].get(str(it["product_id"]))
            if mapped is not None:
                it["product_id"] = mapped
    return json.dumps(detail, ensure_ascii=False)


def _copy_autoinc(cur, src, dst, columns, row_fn=None):
    """Copy src -> dst (no id column); return {old_id: new_id}."""
    mapping = {}
    placeholders = ", ".join("?" * len(columns))
    col_sql = ", ".join(columns)
    for row in cur.execute(f"SELECT * FROM {src}").fetchall():
        old = dict(row)
        values = []
        for col in columns:
            values.append(old.get(col) if not row_fn else row_fn(old, col))
        cur.execute(
            f"INSERT INTO {dst} ({col_sql}) VALUES ({placeholders})",
            values,
        )
        mapping[str(old["id"])] = cur.lastrowid
    return mapping


def _migrate_text_ids_to_integer():
    """Rebuild TEXT UUID primary keys as INTEGER AUTOINCREMENT 1, 2, 3..."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = OFF")
    try:
        existing = {
            r[0]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        if "orders" not in existing:
            return
        if _id_is_integer(conn, "orders") and _id_is_integer(conn, "users"):
            return

        cur = conn.cursor()
        for leftover in ["categories_new", "products_new", "customers_new", "users_new",
                         "password_resets_new", "orders_new", "order_items_new", "settings_new"]:
            cur.execute(f"DROP TABLE IF EXISTS {leftover}")
        cur.executescript("""
        CREATE TABLE categories_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            description TEXT,
            color TEXT DEFAULT '#10b981',
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE products_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            sku TEXT UNIQUE NOT NULL,
            barcode TEXT,
            description TEXT,
            category_id INTEGER NOT NULL,
            price REAL NOT NULL,
            cost REAL DEFAULT 0,
            stock INTEGER DEFAULT 0,
            low_stock_threshold INTEGER DEFAULT 10,
            unit TEXT DEFAULT 'pcs',
            image_url TEXT,
            is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE customers_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
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
        CREATE TABLE users_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT DEFAULT 'cashier',
            is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE password_resets_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL,
            otp TEXT NOT NULL,
            otp_expires_at TEXT NOT NULL,
            used INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE orders_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_number TEXT UNIQUE NOT NULL,
            customer_id INTEGER,
            user_id INTEGER,
            cashier_name TEXT DEFAULT 'Cashier',
            subtotal REAL NOT NULL,
            tax_rate REAL DEFAULT 0,
            tax REAL DEFAULT 0,
            discount REAL DEFAULT 0,
            original_total REAL,
            total REAL NOT NULL,
            cash_received REAL,
            order_detail JSON,
            payment_method TEXT DEFAULT 'cash',
            payment_status TEXT DEFAULT 'paid',
            status TEXT DEFAULT 'completed',
            note TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE order_items_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            original_price REAL,
            price REAL NOT NULL,
            cost REAL DEFAULT 0,
            quantity INTEGER NOT NULL,
            subtotal REAL NOT NULL
        );
        CREATE TABLE settings_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            store_name TEXT DEFAULT 'QuickPOS Store',
            address TEXT DEFAULT '123 Main Street',
            phone TEXT DEFAULT '+1 555 0100',
            email TEXT DEFAULT 'store@quickpos.com',
            tax_rate REAL DEFAULT 8,
            currency TEXT DEFAULT 'PKR',
            currency_symbol TEXT DEFAULT 'Rs',
            receipt_footer TEXT DEFAULT 'Thank you for shopping with us!',
            low_stock_alert_enabled INTEGER DEFAULT 1,
            smtp_host TEXT,
            smtp_port TEXT,
            smtp_user TEXT,
            smtp_pass TEXT,
            smtp_from_email TEXT,
            gdrive_client_id TEXT,
            gdrive_client_secret TEXT,
            updated_at TEXT DEFAULT (datetime('now'))
        );
        """)

        cat_map = _copy_autoinc(
            cur, "categories", "categories_new",
            ["name", "description", "color", "created_at", "updated_at"],
        )
        user_map = _copy_autoinc(
            cur, "users", "users_new",
            ["name", "email", "password_hash", "role", "is_active", "created_at", "updated_at"],
        )
        cust_map = _copy_autoinc(
            cur, "customers", "customers_new",
            ["name", "email", "phone", "address", "loyalty_points", "total_spent",
             "orders_count", "note", "created_at", "updated_at"],
        )
        _copy_autoinc(
            cur, "password_resets", "password_resets_new",
            ["email", "otp", "otp_expires_at", "used", "created_at"],
        )
        settings_cols = [
            "store_name", "address", "phone", "email", "tax_rate", "currency",
            "currency_symbol", "receipt_footer", "low_stock_alert_enabled",
            "smtp_host", "smtp_port", "smtp_user", "smtp_pass", "smtp_from_email",
            "gdrive_client_id", "gdrive_client_secret", "updated_at",
        ]
        existing_settings = {
            r[1] for r in cur.execute("PRAGMA table_info(settings)").fetchall()
        }

        def settings_val(old, col):
            return old.get(col) if col in existing_settings else None

        _copy_autoinc(cur, "settings", "settings_new", settings_cols, settings_val)

        prod_map = {}
        for row in cur.execute("SELECT * FROM products").fetchall():
            old = dict(row)
            new_cat = _map_fk(cat_map, old.get("category_id"))
            if new_cat is None:
                continue
            cur.execute(
                """INSERT INTO products_new
                (name, sku, barcode, description, category_id, price, cost, stock,
                 low_stock_threshold, unit, image_url, is_active, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (old.get("name"), old.get("sku"), old.get("barcode"), old.get("description"),
                 new_cat, old.get("price"), old.get("cost"), old.get("stock"),
                 old.get("low_stock_threshold"), old.get("unit"), old.get("image_url"),
                 old.get("is_active"), old.get("created_at"), old.get("updated_at")),
            )
            prod_map[str(old["id"])] = cur.lastrowid

        maps = {"customers": cust_map, "users": user_map, "products": prod_map}
        order_map = {}
        order_cols = {r[1] for r in cur.execute("PRAGMA table_info(orders)").fetchall()}
        for row in cur.execute("SELECT * FROM orders").fetchall():
            old = dict(row)
            cur.execute(
                """INSERT INTO orders_new
                (order_number, customer_id, user_id, cashier_name, subtotal, tax_rate, tax,
                 discount, original_total, total, cash_received, order_detail, payment_method,
                 payment_status, status, note, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    old.get("order_number"),
                    _map_fk(cust_map, old.get("customer_id")),
                    _map_fk(user_map, old.get("user_id")),
                    old.get("cashier_name"),
                    old.get("subtotal"),
                    old.get("tax_rate"),
                    old.get("tax"),
                    old.get("discount"),
                    old.get("original_total") if "original_total" in order_cols else None,
                    old.get("total"),
                    old.get("cash_received") if "cash_received" in order_cols else None,
                    None,
                    old.get("payment_method"),
                    old.get("payment_status"),
                    old.get("status"),
                    old.get("note"),
                    old.get("created_at"),
                ),
            )
            new_oid = cur.lastrowid
            order_map[str(old["id"])] = new_oid
            detail = _remap_order_detail(old.get("order_detail"), new_oid, maps) if "order_detail" in order_cols else None
            if detail:
                cur.execute("UPDATE orders_new SET order_detail = ? WHERE id = ?", (detail, new_oid))

        item_cols = {r[1] for r in cur.execute("PRAGMA table_info(order_items)").fetchall()}
        for row in cur.execute("SELECT * FROM order_items").fetchall():
            old = dict(row)
            new_oid = _map_fk(order_map, old.get("order_id"))
            new_pid = _map_fk(prod_map, old.get("product_id"))
            if new_oid is None or new_pid is None:
                continue
            cur.execute(
                """INSERT INTO order_items_new
                (order_id, product_id, name, original_price, price, cost, quantity, subtotal)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    new_oid, new_pid, old.get("name"),
                    old.get("original_price") if "original_price" in item_cols else None,
                    old.get("price"), old.get("cost"), old.get("quantity"), old.get("subtotal"),
                ),
            )

        for table in ["order_items", "orders", "products", "categories", "customers",
                      "users", "password_resets", "settings"]:
            cur.execute(f"DROP TABLE {table}")
            cur.execute(f"ALTER TABLE {table}_new RENAME TO {table}")

        cur.executescript("""
        CREATE INDEX IF NOT EXISTS idx_products_category ON products(category_id);
        CREATE INDEX IF NOT EXISTS idx_products_sku ON products(sku);
        CREATE INDEX IF NOT EXISTS idx_orders_customer ON orders(customer_id);
        CREATE INDEX IF NOT EXISTS idx_orders_created ON orders(created_at);
        CREATE INDEX IF NOT EXISTS idx_orders_user ON orders(user_id);
        CREATE INDEX IF NOT EXISTS idx_order_items_order ON order_items(order_id);
        CREATE INDEX IF NOT EXISTS idx_order_items_product ON order_items(product_id);
        """)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.close()


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


def insert(sql, params=()):
    """INSERT a row and return the new auto-increment id."""
    with get_db_cursor() as cur:
        cur.execute(sql, params)
        return cur.lastrowid


def execute_many(sql, params_list):
    with get_db_cursor() as cur:
        cur.executemany(sql, params_list)
        return cur.rowcount


def get_settings():
    s = query_one("SELECT * FROM settings LIMIT 1")
    if not s:
        insert(
            "INSERT INTO settings (store_name, currency, currency_symbol) VALUES (?, ?, ?)",
            ("QuickPOS Store", "PKR", "Rs"),
        )
        s = query_one("SELECT * FROM settings LIMIT 1")
    if s:
        s['low_stock_alert_enabled'] = bool(s['low_stock_alert_enabled'])
    return s
