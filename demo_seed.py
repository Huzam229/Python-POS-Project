"""
Seed QuickPOS database with demo data:
- 6 categories
- 31 products
- 6 customers (including Walk-in)
- 80 historical orders
- Default settings

Run: python seed.py
"""
import sqlite3
import uuid
import random
from datetime import datetime, timedelta
from models import DB_PATH, init_db, execute, query_all, query_one
from werkzeug.security import generate_password_hash

random.seed(42)  # Reproducible demo data


def uid():
    return str(uuid.uuid4())


def now_iso():
    return datetime.utcnow().isoformat()


def random_date(days_back):
    date = datetime.utcnow() - timedelta(days=random.randint(0, days_back - 1))
    date = date.replace(hour=random.randint(8, 20), minute=random.randint(0, 59), second=0, microsecond=0)
    return date.isoformat()


CATEGORIES = [
    {"name": "Beverages", "description": "Hot and cold drinks", "color": "#f97316"},
    {"name": "Bakery", "description": "Bread, pastries, cakes", "color": "#eab308"},
    {"name": "Snacks", "description": "Chips, candy, nuts", "color": "#22c55e"},
    {"name": "Dairy", "description": "Milk, cheese, yogurt", "color": "#06b6d4"},
    {"name": "Produce", "description": "Fruits and vegetables", "color": "#84cc16"},
    {"name": "Household", "description": "Cleaning and home supplies", "color": "#a855f7"},
]

PRODUCTS = [
    # Beverages
    {"name": "Espresso Coffee", "sku": "BEV-001", "barcode": "8901234500011", "cat": 0, "price": 3.50, "cost": 1.20, "stock": 120, "low": 20, "unit": "cup"},
    {"name": "Cappuccino", "sku": "BEV-002", "barcode": "8901234500028", "cat": 0, "price": 4.50, "cost": 1.50, "stock": 95, "low": 20, "unit": "cup"},
    {"name": "Orange Juice 1L", "sku": "BEV-003", "barcode": "8901234500035", "cat": 0, "price": 5.99, "cost": 2.80, "stock": 60, "low": 15, "unit": "bottle"},
    {"name": "Green Tea", "sku": "BEV-004", "barcode": "8901234500042", "cat": 0, "price": 2.75, "cost": 0.90, "stock": 30, "low": 15, "unit": "box"},
    {"name": "Sparkling Water 500ml", "sku": "BEV-005", "barcode": "8901234500059", "cat": 0, "price": 1.99, "cost": 0.60, "stock": 200, "low": 30, "unit": "bottle"},
    {"name": "Cola Can 330ml", "sku": "BEV-006", "barcode": "8901234500066", "cat": 0, "price": 1.25, "cost": 0.45, "stock": 350, "low": 50, "unit": "can"},
    # Bakery
    {"name": "Croissant", "sku": "BAK-001", "barcode": "8901234501011", "cat": 1, "price": 2.25, "cost": 0.85, "stock": 45, "low": 15, "unit": "pcs"},
    {"name": "Bagel", "sku": "BAK-002", "barcode": "8901234501028", "cat": 1, "price": 1.99, "cost": 0.70, "stock": 38, "low": 15, "unit": "pcs"},
    {"name": "Whole Wheat Bread", "sku": "BAK-003", "barcode": "8901234501035", "cat": 1, "price": 3.49, "cost": 1.40, "stock": 22, "low": 10, "unit": "loaf"},
    {"name": "Chocolate Muffin", "sku": "BAK-004", "barcode": "8901234501042", "cat": 1, "price": 2.75, "cost": 1.00, "stock": 30, "low": 12, "unit": "pcs"},
    {"name": "Donut Glazed", "sku": "BAK-005", "barcode": "8901234501059", "cat": 1, "price": 1.75, "cost": 0.55, "stock": 25, "low": 12, "unit": "pcs"},
    # Snacks
    {"name": "Potato Chips 150g", "sku": "SNK-001", "barcode": "8901234502011", "cat": 2, "price": 2.99, "cost": 1.20, "stock": 80, "low": 20, "unit": "bag"},
    {"name": "Chocolate Bar", "sku": "SNK-002", "barcode": "8901234502028", "cat": 2, "price": 1.50, "cost": 0.55, "stock": 150, "low": 30, "unit": "pcs"},
    {"name": "Mixed Nuts 200g", "sku": "SNK-003", "barcode": "8901234502035", "cat": 2, "price": 4.99, "cost": 2.10, "stock": 25, "low": 10, "unit": "pack"},
    {"name": "Popcorn Microwave", "sku": "SNK-004", "barcode": "8901234502042", "cat": 2, "price": 2.25, "cost": 0.85, "stock": 30, "low": 15, "unit": "pack"},
    {"name": "Cookies Pack", "sku": "SNK-005", "barcode": "8901234502059", "cat": 2, "price": 3.25, "cost": 1.30, "stock": 60, "low": 20, "unit": "pack"},
    # Dairy
    {"name": "Whole Milk 1L", "sku": "DRY-001", "barcode": "8901234503011", "cat": 3, "price": 1.85, "cost": 0.90, "stock": 70, "low": 20, "unit": "bottle"},
    {"name": "Cheddar Cheese 250g", "sku": "DRY-002", "barcode": "8901234503028", "cat": 3, "price": 4.49, "cost": 2.20, "stock": 28, "low": 10, "unit": "pack"},
    {"name": "Greek Yogurt 500g", "sku": "DRY-003", "barcode": "8901234503035", "cat": 3, "price": 3.99, "cost": 1.70, "stock": 35, "low": 12, "unit": "tub"},
    {"name": "Butter 200g", "sku": "DRY-004", "barcode": "8901234503042", "cat": 3, "price": 2.49, "cost": 1.10, "stock": 14, "low": 10, "unit": "pack"},
    {"name": "Eggs Dozen", "sku": "DRY-005", "barcode": "8901234503059", "cat": 3, "price": 3.25, "cost": 1.60, "stock": 40, "low": 15, "unit": "dozen"},
    # Produce
    {"name": "Banana (per kg)", "sku": "PRD-001", "barcode": "8901234504011", "cat": 4, "price": 1.29, "cost": 0.60, "stock": 100, "low": 25, "unit": "kg"},
    {"name": "Apple (per kg)", "sku": "PRD-002", "barcode": "8901234504028", "cat": 4, "price": 2.49, "cost": 1.20, "stock": 75, "low": 20, "unit": "kg"},
    {"name": "Tomato (per kg)", "sku": "PRD-003", "barcode": "8901234504035", "cat": 4, "price": 2.99, "cost": 1.40, "stock": 20, "low": 15, "unit": "kg"},
    {"name": "Lettuce", "sku": "PRD-004", "barcode": "8901234504042", "cat": 4, "price": 1.50, "cost": 0.70, "stock": 22, "low": 10, "unit": "head"},
    {"name": "Avocado", "sku": "PRD-005", "barcode": "8901234504059", "cat": 4, "price": 1.99, "cost": 0.95, "stock": 50, "low": 15, "unit": "pcs"},
    # Household
    {"name": "Dish Soap 500ml", "sku": "HSH-001", "barcode": "8901234505011", "cat": 5, "price": 2.99, "cost": 1.30, "stock": 42, "low": 12, "unit": "bottle"},
    {"name": "Paper Towels 2-pack", "sku": "HSH-002", "barcode": "8901234505028", "cat": 5, "price": 4.49, "cost": 2.00, "stock": 28, "low": 10, "unit": "pack"},
    {"name": "Laundry Detergent 1L", "sku": "HSH-003", "barcode": "8901234505035", "cat": 5, "price": 6.99, "cost": 3.20, "stock": 18, "low": 8, "unit": "bottle"},
    {"name": "Trash Bags 30ct", "sku": "HSH-004", "barcode": "8901234505042", "cat": 5, "price": 5.49, "cost": 2.50, "stock": 33, "low": 10, "unit": "pack"},
    {"name": "Hand Sanitizer 250ml", "sku": "HSH-005", "barcode": "8901234505059", "cat": 5, "price": 3.25, "cost": 1.40, "stock": 20, "low": 12, "unit": "bottle"},
]

CUSTOMERS = [
    {"name": "Walk-in Customer", "email": None, "phone": None, "address": None, "loyalty_points": 0},
    {"name": "Alice Johnson", "email": "alice@example.com", "phone": "+1 555 0142", "address": "42 Oak Street", "loyalty_points": 230},
    {"name": "Bob Martinez", "email": "bob.m@example.com", "phone": "+1 555 0177", "address": "88 Pine Ave", "loyalty_points": 145},
    {"name": "Catherine Lee", "email": "cath.lee@example.com", "phone": "+1 555 0193", "address": "7 Maple Road", "loyalty_points": 410},
    {"name": "David Kim", "email": "d.kim@example.com", "phone": "+1 555 0124", "address": "210 Cedar Lane", "loyalty_points": 95},
    {"name": "Emma Wilson", "email": "emma.w@example.com", "phone": "+1 555 0188", "address": "15 Birch Court", "loyalty_points": 320},
]

PAYMENT_METHODS = ["cash", "card", "wallet"]


def main():
    print("Initializing database schema...")
    init_db()

    # Wipe existing data
    print("Clearing existing data...")
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    for table in ["order_items", "orders", "products", "categories", "customers", "settings", "users", "password_resets"]:
        cur.execute(f"DELETE FROM {table}")
    conn.commit()

    # Categories
    print("Creating categories...")
    cat_ids = []
    for c in CATEGORIES:
        cid = uid()
        cat_ids.append(cid)
        cur.execute(
            "INSERT INTO categories (id, name, description, color) VALUES (?, ?, ?, ?)",
            (cid, c["name"], c["description"], c["color"])
        )

    # Products
    print("Creating products...")
    prod_ids = []
    for p in PRODUCTS:
        pid = uid()
        prod_ids.append((pid, p))
        cur.execute(
            """INSERT INTO products
            (id, name, sku, barcode, description, category_id, price, cost, stock, low_stock_threshold, unit, is_active)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)""",
            (pid, p["name"], p["sku"], p["barcode"], None, cat_ids[p["cat"]],
             p["price"], p["cost"], p["stock"], p["low"], p["unit"])
        )

    # Customers
    print("Creating customers...")
    cust_ids = []
    for c in CUSTOMERS:
        cid = uid()
        cust_ids.append(cid)
        cur.execute(
            """INSERT INTO customers
            (id, name, email, phone, address, loyalty_points)
            VALUES (?, ?, ?, ?, ?, ?)""",
            (cid, c["name"], c["email"], c["phone"], c["address"], c["loyalty_points"])
        )

    # Settings
    print("Creating settings...")
    cur.execute(
        """INSERT INTO settings
        (id, store_name, address, phone, email, tax_rate, currency, currency_symbol, receipt_footer, low_stock_alert_enabled)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1)""",
        (uid(), "QuickPOS Market", "123 Main Street, Springfield", "+1 555 0100",
         "hello@quickpos.market", 8, "PKR", "Rs",
         "Thank you for shopping at QuickPOS! Come back soon.")
    )

    # Default admin — created before orders so sales are attributed to a real user
    print("Creating default admin user...")
    admin_id = uid()
    admin_pw = generate_password_hash("admin123")
    cur.execute(
        "INSERT INTO users (id, name, email, password_hash, role, is_active) VALUES (?, ?, ?, ?, 'admin', 1)",
        (admin_id, "Admin", "admin@quickpos.com", admin_pw)
    )

    # Demo orders
    print("Generating demo orders...")
    # Build (id, stock_remaining) map for stock tracking
    stock_map = {pid: p["stock"] for pid, p in prod_ids}
    product_lookup = {pid: p for pid, p in prod_ids}

    order_count = 0
    for i in range(80):
        item_count = random.randint(1, 4)
        items = []
        subtotal = 0.0
        used_pids = set()

        for _ in range(item_count):
            # Find a product with stock
            available = [pid for pid in prod_ids if pid[0] not in used_pids and stock_map.get(pid[0], 0) > 0]
            if not available:
                break
            pid, p = random.choice(available)
            used_pids.add(pid)
            max_qty = min(3, stock_map[pid])
            qty = random.randint(1, max_qty)
            stock_map[pid] -= qty
            line_total = round(p["price"] * qty, 2)
            subtotal += line_total
            items.append({
                "product_id": pid,
                "name": p["name"],
                "price": p["price"],
                "cost": p["cost"],
                "quantity": qty,
                "subtotal": line_total,
            })

        if not items:
            continue

        tax_rate = 8
        tax = round(subtotal * tax_rate / 100, 2)
        discount = round(subtotal * 0.1, 2) if random.random() > 0.85 else 0
        total = round(subtotal + tax - discount, 2)

        # 40% chance of attaching a non-walk-in customer
        customer_id = None
        if random.random() > 0.6:
            customer_id = random.choice(cust_ids[1:])

        order_number = f"ORD-{10000 + order_count + 1}"
        order_count += 1
        order_id = uid()
        cur.execute(
            """INSERT INTO orders
            (id, order_number, customer_id, user_id, cashier_name, subtotal, tax_rate, tax, discount, total,
             payment_method, payment_status, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'paid', 'completed', ?)""",
            (order_id, order_number, customer_id, admin_id, "Admin",
             round(subtotal, 2), tax_rate, tax, discount, total,
             random.choice(PAYMENT_METHODS), random_date(30))
        )

        for item in items:
            cur.execute(
                """INSERT INTO order_items
                (id, order_id, product_id, name, price, cost, quantity, subtotal)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (uid(), order_id, item["product_id"], item["name"],
                 item["price"], item["cost"], item["quantity"], item["subtotal"])
            )

        # Decrement stock
        for item in items:
            cur.execute(
                "UPDATE products SET stock = stock - ? WHERE id = ?",
                (item["quantity"], item["product_id"])
            )

        # Update customer stats
        if customer_id:
            cur.execute(
                """UPDATE customers
                SET total_spent = total_spent + ?, orders_count = orders_count + 1,
                    loyalty_points = loyalty_points + ?
                WHERE id = ?""",
                (total, int(total), customer_id)
            )

    conn.commit()
    conn.close()

    print()
    print("✓ Seed completed successfully!")
    print(f"  - {len(CATEGORIES)} categories")
    print(f"  - {len(PRODUCTS)} products")
    print(f"  - {len(CUSTOMERS)} customers")
    print(f"  - {order_count} orders")
    print(f"  - 1 user (admin@quickpos.com / admin123)")
    print()
    print("Run the app with: python app.py")


if __name__ == "__main__":
    main()