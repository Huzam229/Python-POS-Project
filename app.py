"""
QuickPOS — Desktop Point of Sale (Python edition)
A complete POS application built with Flask + Jinja2 + Tailwind (CDN) + Chart.js.

Run:  python app.py
Open: http://localhost:5001
"""
import csv
import io
import os
import random
import re
import shutil
import smtplib
import uuid
from datetime import datetime, timedelta
from email.message import EmailMessage
from functools import wraps
from pathlib import Path
from flask import Flask, Response, render_template, request, redirect, url_for, jsonify, flash, session
from werkzeug.security import generate_password_hash, check_password_hash

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.auth.transport.requests import Request

from models import init_db, query_all, query_one, execute, get_settings, DB_PATH, DATA_DIR

# Initialize DB on first import
init_db()

app = Flask(__name__)
app.secret_key = "quickpos-dev-secret-change-in-prod"
app.permanent_session_lifetime = timedelta(days=7)

PORT = int(os.environ.get("PORT", 5001))


# ---------- Helpers ----------

def fmt_money(amount, symbol="$"):
    if amount is None:
        amount = 0
    return f"{symbol}{amount:,.2f}"


def fmt_date(dt_str):
    if not dt_str:
        return ""
    try:
        dt = datetime.fromisoformat(dt_str)
    except ValueError:
        try:
            dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return dt_str
    return dt.strftime("%b %d, %Y %I:%M %p")


def fmt_date_short(dt_str):
    if not dt_str:
        return ""
    try:
        dt = datetime.fromisoformat(dt_str)
    except ValueError:
        try:
            dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return dt_str
    return dt.strftime("%b %d, %Y")


def time_ago(dt_str):
    if not dt_str:
        return ""
    try:
        dt = datetime.fromisoformat(dt_str)
    except ValueError:
        try:
            dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return dt_str
    diff = datetime.utcnow() - dt
    secs = diff.total_seconds()
    if secs < 60:
        return "just now"
    mins = int(secs // 60)
    if mins < 60:
        return f"{mins}m ago"
    hours = int(mins // 60)
    if hours < 24:
        return f"{hours}h ago"
    days = int(hours // 24)
    if days < 7:
        return f"{days}d ago"
    return fmt_date_short(dt_str)


def customer_tier(points):
    if points >= 400:
        return ("Platinum", "bg-purple-500")
    if points >= 200:
        return ("Gold", "bg-amber-500")
    if points >= 100:
        return ("Silver", "bg-slate-400")
    return ("Bronze", "bg-orange-700")


app.jinja_env.filters["money"] = lambda v: fmt_money(v, get_settings()["currency_symbol"])
app.jinja_env.filters["date"] = fmt_date
app.jinja_env.filters["date_short"] = fmt_date_short
app.jinja_env.filters["time_ago"] = time_ago
app.jinja_env.filters["tier"] = lambda p: customer_tier(p)[0]
app.jinja_env.filters["tier_color"] = lambda p: customer_tier(p)[1]


def parse_float(s, default=0.0):
    try:
        return float(s) if s else default
    except (ValueError, TypeError):
        return default


def parse_int(s, default=0):
    try:
        return int(s) if s else default
    except (ValueError, TypeError):
        return default


def get_date_range():
    now = datetime.utcnow()
    default_from = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0).isoformat()
    default_to = now.replace(hour=23, minute=59, second=59, microsecond=0).isoformat()
    date_from = request.args.get("date_from", default_from)
    date_to = request.args.get("date_to", default_to)
    try:
        datetime.fromisoformat(date_from)
    except (ValueError, TypeError):
        date_from = default_from
    try:
        datetime.fromisoformat(date_to)
    except (ValueError, TypeError):
        date_to = default_to
    return date_from, date_to


# ---------- Auth helpers ----------

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        user = query_one("SELECT * FROM users WHERE id = ?", (session["user_id"],))
        if not user or not user["is_active"]:
            session.clear()
            return redirect(url_for("login"))
        session["user_name"] = user["name"]
        session["user_role"] = user["role"]
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        user = query_one("SELECT * FROM users WHERE id = ?", (session["user_id"],))
        if not user or not user["is_active"] or user["role"] != "admin":
            flash("Admin access required", "error")
            return redirect(url_for("dashboard"))
        return f(*args, **kwargs)
    return decorated


def send_otp_email(to_email, otp):
    s = get_settings()
    host = s.get("smtp_host")
    port = s.get("smtp_port")
    user = s.get("smtp_user")
    pwd = s.get("smtp_pass")
    from_email = s.get("smtp_from_email") or user
    if not host or not user or not pwd:
        return False
    try:
        msg = EmailMessage()
        msg["Subject"] = f"QuickPOS — Your OTP is {otp}"
        msg["From"] = from_email
        msg["To"] = to_email
        msg.set_content(
            f"Hello,\n\n"
            f"Your OTP for password reset is: {otp}\n\n"
            f"This code expires in 10 minutes.\n\n"
            f"If you did not request this, please ignore this email.\n\n"
            f"— QuickPOS Team"
        )
        port_int = int(port) if port else 587
        with smtplib.SMTP(host, port_int, timeout=10) as server:
            server.starttls()
            server.login(user, pwd)
            server.send_message(msg)
        return True
    except Exception:
        return False


def csv_response(filename, columns, rows):
    si = io.StringIO()
    writer = csv.writer(si)
    writer.writerow([label for _, label in columns])
    for row in rows:
        writer.writerow([str(row.get(key, "") or "") for key, _ in columns])
    output = si.getvalue()
    return Response(
        output,
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


# ---------- Auth routes ----------

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = query_one("SELECT * FROM users WHERE email = ?", (email,))
        if user and user["is_active"] and check_password_hash(user["password_hash"], password):
            session["user_id"] = user["id"]
            session["user_name"] = user["name"]
            session["user_role"] = user["role"]
            session.permanent = True
            flash(f"Welcome back, {user['name']}!", "success")
            return redirect(url_for("dashboard"))
        flash("Invalid email or password", "error")
        return redirect(url_for("login"))
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out", "info")
    return redirect(url_for("login"))


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")
        if not name or not email or not password:
            flash("All fields are required", "error")
            return redirect(url_for("register"))
        if password != confirm:
            flash("Passwords do not match", "error")
            return redirect(url_for("register"))
        if len(password) < 6:
            flash("Password must be at least 6 characters", "error")
            return redirect(url_for("register"))
        existing = query_one("SELECT id FROM users WHERE email = ?", (email,))
        if existing:
            flash("Email already registered", "error")
            return redirect(url_for("register"))
        user_id = str(uuid.uuid4())
        pw_hash = generate_password_hash(password)
        execute(
            "INSERT INTO users (id, name, email, password_hash, role) VALUES (?, ?, ?, ?, 'cashier')",
            (user_id, name, email, pw_hash)
        )
        flash("Registration successful! You can now log in.", "success")
        return redirect(url_for("login"))
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    return render_template("register.html")


@app.route("/forgot", methods=["GET", "POST"])
def forgot():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        user = query_one("SELECT id FROM users WHERE email = ?", (email,))
        if not user:
            flash("No account found with that email", "error")
            return redirect(url_for("forgot"))
        otp = f"{random.randint(100000, 999999)}"
        expires = (datetime.utcnow() + timedelta(minutes=10)).isoformat()
        execute(
            "INSERT INTO password_resets (id, email, otp, otp_expires_at) VALUES (?, ?, ?, ?)",
            (str(uuid.uuid4()), email, otp, expires)
        )
        sent = send_otp_email(email, otp)
        if not sent:
            flash("Could not send email. SMTP not configured. Contact your admin.", "error")
            return redirect(url_for("forgot"))
        session["reset_email"] = email
        flash(f"OTP sent to {email}", "success")
        return redirect(url_for("reset_password"))
    return render_template("forgot.html")


@app.route("/reset-password", methods=["GET", "POST"])
def reset_password():
    email = session.get("reset_email")
    if not email:
        return redirect(url_for("forgot"))
    if request.method == "POST":
        otp = request.form.get("otp", "").strip()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")
        if password != confirm:
            flash("Passwords do not match", "error")
            return redirect(url_for("reset_password"))
        if len(password) < 6:
            flash("Password must be at least 6 characters", "error")
            return redirect(url_for("reset_password"))
        record = query_one(
            "SELECT * FROM password_resets WHERE email = ? AND otp = ? AND used = 0 AND otp_expires_at > ? ORDER BY created_at DESC LIMIT 1",
            (email, otp, datetime.utcnow().isoformat())
        )
        if not record:
            flash("Invalid or expired OTP", "error")
            return redirect(url_for("reset_password"))
        pw_hash = generate_password_hash(password)
        execute("UPDATE users SET password_hash = ? WHERE email = ?", (pw_hash, email))
        execute("UPDATE password_resets SET used = 1 WHERE id = ?", (record["id"],))
        session.pop("reset_email", None)
        flash("Password reset successful! You can now log in.", "success")
        return redirect(url_for("login"))
    return render_template("reset_password.html")


# ---------- User management (admin) ----------

@app.route("/users")
@admin_required
def users_view():
    settings = get_settings()
    users = query_all("SELECT * FROM users ORDER BY created_at DESC")
    return render_template("users.html", active_view="users", settings=settings, users=users)


@app.route("/users/new", methods=["POST"])
@admin_required
def users_new():
    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")
    role = request.form.get("role", "cashier")
    if not name or not email or not password:
        flash("All fields are required", "error")
        return redirect(url_for("users_view"))
    existing = query_one("SELECT id FROM users WHERE email = ?", (email,))
    if existing:
        flash("Email already in use", "error")
        return redirect(url_for("users_view"))
    pw_hash = generate_password_hash(password)
    execute(
        "INSERT INTO users (id, name, email, password_hash, role) VALUES (?, ?, ?, ?, ?)",
        (str(uuid.uuid4()), name, email, pw_hash, role)
    )
    flash(f"User {name} created", "success")
    return redirect(url_for("users_view"))


@app.route("/users/<user_id>/edit", methods=["POST"])
@admin_required
def users_edit(user_id):
    user = query_one("SELECT * FROM users WHERE id = ?", (user_id,))
    if not user:
        flash("User not found", "error")
        return redirect(url_for("users_view"))
    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip().lower()
    role = request.form.get("role", "cashier")
    password = request.form.get("password", "")
    if not name or not email:
        flash("Name and email are required", "error")
        return redirect(url_for("users_view"))
    # Check email uniqueness (exclude self)
    dup = query_one("SELECT id FROM users WHERE email = ? AND id != ?", (email, user_id))
    if dup:
        flash("Email already in use", "error")
        return redirect(url_for("users_view"))
    if password:
        pw_hash = generate_password_hash(password)
        execute(
            "UPDATE users SET name = ?, email = ?, password_hash = ?, role = ?, updated_at = datetime('now') WHERE id = ?",
            (name, email, pw_hash, role, user_id)
        )
    else:
        execute(
            "UPDATE users SET name = ?, email = ?, role = ?, updated_at = datetime('now') WHERE id = ?",
            (name, email, role, user_id)
        )
    flash("User updated", "success")
    return redirect(url_for("users_view"))


@app.route("/users/<user_id>/delete", methods=["POST"])
@admin_required
def users_delete(user_id):
    if user_id == session.get("user_id"):
        flash("You cannot delete yourself", "error")
        return redirect(url_for("users_view"))
    execute("DELETE FROM users WHERE id = ?", (user_id,))
    flash("User deleted", "success")
    return redirect(url_for("users_view"))


@app.route("/users/<user_id>/toggle", methods=["POST"])
@admin_required
def users_toggle(user_id):
    if user_id == session.get("user_id"):
        flash("You cannot deactivate yourself", "error")
        return redirect(url_for("users_view"))
    user = query_one("SELECT * FROM users WHERE id = ?", (user_id,))
    if user:
        new_status = 0 if user["is_active"] else 1
        execute("UPDATE users SET is_active = ? WHERE id = ?", (new_status, user_id))
        flash(f"User {'activated' if new_status else 'deactivated'}", "success")
    return redirect(url_for("users_view"))


# ---------- Backup / Google Drive ----------

BACKUP_DIR = os.path.join(DATA_DIR, "backups")
SCOPES = ["https://www.googleapis.com/auth/drive.file"]


def _ensure_backup_dir():
    os.makedirs(BACKUP_DIR, exist_ok=True)


def _backup_list():
    _ensure_backup_dir()
    files = []
    for f in sorted(Path(BACKUP_DIR).glob("quickpos_*.db"), reverse=True):
        size = os.path.getsize(f)
        mtime = datetime.fromtimestamp(os.path.getmtime(f)).isoformat()
        files.append({"name": f.name, "size": size, "size_fmt": _fmt_size(size), "mtime": mtime})
    return files


def _fmt_size(n):
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def _gdrive_creds():
    s = get_settings()
    cid = s.get("gdrive_client_id")
    csec = s.get("gdrive_client_secret")
    if not cid or not csec:
        return None
    token_path = os.path.join(BACKUP_DIR, "token.json")
    creds = None
    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)
    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            with open(token_path, "w") as f:
                f.write(creds.to_json())
        except Exception:
            return None
    return creds


def _gdrive_list():
    creds = _gdrive_creds()
    if not creds or not creds.valid:
        return []
    try:
        service = build("drive", "v3", credentials=creds)
        results = service.files().list(
            q="name contains 'quickpos_' and mimeType = 'application/octet-stream'",
            orderBy="createdTime desc",
            pageSize=20,
            fields="files(id, name, size, createdTime)"
        ).execute()
        files = results.get("files", [])
        for f in files:
            f["size_fmt"] = _fmt_size(int(f.get("size", 0)))
        return files
    except Exception:
        return []


@app.route("/backup")
@admin_required
def backup_view():
    settings = get_settings()
    db_path = DB_PATH
    db_size = os.path.getsize(db_path) if os.path.exists(db_path) else 0
    db_mtime = datetime.fromtimestamp(os.path.getmtime(db_path)).isoformat() if os.path.exists(db_path) else ""
    snapshots = _backup_list()
    creds = _gdrive_creds()
    gdrive_connected = creds is not None and creds.valid
    gdrive_files = _gdrive_list() if gdrive_connected else []
    return render_template(
        "backup.html",
        active_view="backup",
        settings=settings,
        db_size=db_size,
        db_size_fmt=_fmt_size(db_size),
        db_mtime=db_mtime,
        snapshots=snapshots,
        gdrive_connected=gdrive_connected,
        gdrive_files=gdrive_files,
    )


@app.route("/backup/create", methods=["POST"])
@admin_required
def backup_create():
    _ensure_backup_dir()
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    name = f"quickpos_{ts}.db"
    dest = os.path.join(BACKUP_DIR, name)
    try:
        shutil.copy2(DB_PATH, dest)
        flash(f"Backup created: {name}", "success")
    except Exception as e:
        flash(f"Backup failed: {e}", "error")
    return redirect(url_for("backup_view"))


@app.route("/backup/download")
@admin_required
def backup_download():
    if not os.path.exists(DB_PATH):
        flash("Database file not found", "error")
        return redirect(url_for("backup_view"))
    with open(DB_PATH, "rb") as f:
        data = f.read()
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    return Response(
        data,
        mimetype="application/octet-stream",
        headers={"Content-Disposition": f"attachment; filename=quickpos_{ts}.db"},
    )


@app.route("/backup/download/<filename>")
@admin_required
def backup_download_snapshot(filename):
    safe = os.path.basename(filename)
    path = os.path.join(BACKUP_DIR, safe)
    if not os.path.exists(path) or not safe.startswith("quickpos_") or not safe.endswith(".db"):
        flash("Invalid backup file", "error")
        return redirect(url_for("backup_view"))
    with open(path, "rb") as f:
        data = f.read()
    return Response(
        data,
        mimetype="application/octet-stream",
        headers={"Content-Disposition": f"attachment; filename={safe}"},
    )


@app.route("/backup/delete/<filename>", methods=["POST"])
@admin_required
def backup_delete(filename):
    safe = os.path.basename(filename)
    path = os.path.join(BACKUP_DIR, safe)
    if os.path.exists(path) and safe.startswith("quickpos_") and safe.endswith(".db"):
        os.remove(path)
        flash(f"Deleted {safe}", "success")
    else:
        flash("Invalid backup file", "error")
    return redirect(url_for("backup_view"))


@app.route("/backup/auth/google", methods=["GET", "POST"])
@admin_required
def backup_auth_google():
    s = get_settings()
    cid = s.get("gdrive_client_id")
    csec = s.get("gdrive_client_secret")
    if not cid or not csec:
        flash("Google Drive Client ID and Secret must be configured in Settings", "error")
        return redirect(url_for("backup_view"))
    _ensure_backup_dir()
    import json

    if request.method == "POST":
        code = request.form.get("code", "").strip()
        if not code:
            flash("Authorization code is required", "error")
            return redirect(url_for("backup_auth_google"))
        try:
            cred_path = os.path.join(BACKUP_DIR, "credentials.json")
            flow = InstalledAppFlow.from_client_secrets_file(cred_path, SCOPES)
            flow.redirect_uri = "urn:ietf:wg:oauth:2.0:oob"
            creds = flow.fetch_token(code=code)
            # Get full credentials object
            creds = flow.credentials
            token_path = os.path.join(BACKUP_DIR, "token.json")
            with open(token_path, "w") as f:
                f.write(creds.to_json())
            flash("Google Drive connected successfully!", "success")
            return redirect(url_for("backup_view"))
        except Exception as e:
            flash(f"Token exchange failed: {e}", "error")
            return redirect(url_for("backup_auth_google"))

    # GET: write credentials file, generate auth URL, show form
    cred_data = {
        "installed": {
            "client_id": cid,
            "client_secret": csec,
            "redirect_uris": ["urn:ietf:wg:oauth:2.0:oob"],
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
        }
    }
    cred_path = os.path.join(BACKUP_DIR, "credentials.json")
    with open(cred_path, "w") as f:
        json.dump(cred_data, f)
    flow = InstalledAppFlow.from_client_secrets_file(cred_path, SCOPES)
    flow.redirect_uri = "urn:ietf:wg:oauth:2.0:oob"
    auth_url = flow.authorization_url(access_type="offline", include_granted_scopes="true")[0]
    return render_template("backup_auth.html", auth_url=auth_url)


@app.route("/backup/upload/<filename>", methods=["POST"])
@admin_required
def backup_upload(filename):
    safe = os.path.basename(filename)
    path = os.path.join(BACKUP_DIR, safe)
    if not os.path.exists(path) or not safe.startswith("quickpos_") or not safe.endswith(".db"):
        flash("Invalid backup file", "error")
        return redirect(url_for("backup_view"))
    creds = _gdrive_creds()
    if not creds or not creds.valid:
        flash("Google Drive not connected. Click 'Connect to Google Drive' first.", "error")
        return redirect(url_for("backup_view"))
    try:
        service = build("drive", "v3", credentials=creds)
        file_metadata = {"name": safe, "parents": []}
        media = MediaFileUpload(path, mimetype="application/octet-stream", resumable=True)
        uploaded = service.files().create(body=file_metadata, media_body=media, fields="id,name,size,createdTime").execute()
        file_id = uploaded.get("id")
        file_name = uploaded.get("name")
        flash(f"Uploaded {file_name} to Google Drive (ID: {file_id})", "success")
    except Exception as e:
        flash(f"Upload failed: {e}", "error")
    return redirect(url_for("backup_view"))


# ---------- Main views ----------

@app.route("/")
@login_required
def dashboard():
    settings = get_settings()
    symbol = settings["currency_symbol"]
    now = datetime.utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
    yesterday_start = (now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=1)).isoformat()
    week_start = (now - timedelta(days=7)).isoformat()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0).isoformat()
    thirty_days_ago = (now - timedelta(days=30)).isoformat()
    date_from, date_to = get_date_range()

    today_orders = query_all("SELECT * FROM orders WHERE created_at >= ?", (today_start,))
    yesterday_orders = query_all("SELECT * FROM orders WHERE created_at >= ? AND created_at < ?", (yesterday_start, today_start))
    week_orders = query_all("SELECT * FROM orders WHERE created_at >= ?", (week_start,))
    month_orders = query_all("SELECT * FROM orders WHERE created_at >= ?", (month_start,))

    today_revenue = sum(o["total"] for o in today_orders)
    yesterday_revenue = sum(o["total"] for o in yesterday_orders)
    week_revenue = sum(o["total"] for o in week_orders)
    month_revenue = sum(o["total"] for o in month_orders)
    revenue_change = ((today_revenue - yesterday_revenue) / yesterday_revenue * 100) if yesterday_revenue > 0 else 0
    today_items = sum(
        sum(oi["quantity"] for oi in query_all("SELECT * FROM order_items WHERE order_id = ?", (o["id"],)))
        for o in today_orders
    )

    # Inventory stats
    products = query_all("SELECT * FROM products")
    inventory_value = sum(p["cost"] * p["stock"] for p in products)
    low_stock = query_all(
        "SELECT * FROM products WHERE stock <= low_stock_threshold ORDER BY stock ASC LIMIT 6"
    )
    cats_map = {c["id"]: c for c in query_all("SELECT * FROM categories")}
    for ls in low_stock:
        ls["category"] = cats_map.get(ls["category_id"], {})

    # Recent orders (within date range)
    recent_orders = query_all(
        "SELECT * FROM orders WHERE created_at >= ? AND created_at <= ? ORDER BY created_at DESC LIMIT 8",
        (date_from, date_to)
    )
    for o in recent_orders:
        if o["customer_id"]:
            c = query_one("SELECT name FROM customers WHERE id = ?", (o["customer_id"],))
            o["customer_name"] = c["name"] if c else "Walk-in"
        else:
            o["customer_name"] = "Walk-in"
        o["items"] = query_all("SELECT * FROM order_items WHERE order_id = ?", (o["id"],))

    # Hourly sales today
    hourly_data = [{"hour": f"{h:02d}:00", "sales": 0, "orders": 0} for h in range(24)]
    for o in today_orders:
        try:
            dt = datetime.fromisoformat(o["created_at"])
            h = dt.hour
            hourly_data[h]["sales"] += o["total"]
            hourly_data[h]["orders"] += 1
        except (ValueError, KeyError):
            pass
    hourly_filtered = [h for h in hourly_data if h["orders"] > 0]

    # Date range days
    try:
        dt_from = datetime.fromisoformat(date_from)
        dt_to = datetime.fromisoformat(date_to)
    except (ValueError, TypeError):
        dt_from = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        dt_to = now
    range_days = (dt_to - dt_from).days
    if range_days < 1:
        range_days = 1

    # Daily sales within date range
    range_orders = query_all(
        "SELECT * FROM orders WHERE created_at >= ? AND created_at <= ? ORDER BY created_at ASC",
        (date_from, date_to)
    )
    daily_map = {}
    for o in range_orders:
        try:
            dt = datetime.fromisoformat(o["created_at"])
            key = dt.strftime("%Y-%m-%d")
        except (ValueError, TypeError):
            continue
        if key not in daily_map:
            daily_map[key] = {"date": key, "label": dt.strftime("%b %d"), "sales": 0, "orders": 0}
        daily_map[key]["sales"] += o["total"]
        daily_map[key]["orders"] += 1

    # Top products within date range
    top_items = query_all(
        """SELECT oi.product_id, oi.name, oi.price, oi.cost, oi.quantity, oi.subtotal
        FROM order_items oi
        JOIN orders o ON oi.order_id = o.id
        WHERE o.created_at >= ? AND o.created_at <= ?""",
        (date_from, date_to)
    )
    prod_map = {}
    for it in top_items:
        pid = it["product_id"]
        if pid not in prod_map:
            cat = query_one(
                """SELECT c.name as cat_name FROM products p
                JOIN categories c ON p.category_id = c.id WHERE p.id = ?""", (pid,)
            )
            prod_map[pid] = {
                "name": it["name"],
                "category": cat["cat_name"] if cat else "—",
                "revenue": 0,
                "quantity": 0,
            }
        prod_map[pid]["revenue"] += it["subtotal"]
        prod_map[pid]["quantity"] += it["quantity"]
    top_products = sorted(prod_map.values(), key=lambda x: x["revenue"], reverse=True)[:5]

    # Category breakdown within date range
    cat_rows = query_all(
        """SELECT c.name, c.color, SUM(oi.subtotal) as revenue, SUM(oi.quantity) as quantity
        FROM order_items oi
        JOIN orders o ON oi.order_id = o.id
        JOIN products p ON oi.product_id = p.id
        JOIN categories c ON p.category_id = c.id
        WHERE o.created_at >= ? AND o.created_at <= ?
        GROUP BY c.id
        ORDER BY revenue DESC""",
        (date_from, date_to)
    )
    for c in cat_rows:
        c["revenue"] = round(c["revenue"], 2)

    # Payment breakdown within date range
    pay_rows = query_all(
        """SELECT payment_method, COUNT(*) as count, SUM(total) as total
        FROM orders WHERE created_at >= ? AND created_at <= ?
        GROUP BY payment_method""",
        (date_from, date_to)
    )
    for p in pay_rows:
        p["total"] = round(p["total"], 2)

    # Summary stats for the period
    period_revenue = sum(o["total"] for o in range_orders)
    period_orders = len(range_orders)

    stats = {
        "today_revenue": round(today_revenue, 2),
        "yesterday_revenue": round(yesterday_revenue, 2),
        "revenue_change": round(revenue_change, 2),
        "today_orders": len(today_orders),
        "today_items": today_items,
        "week_revenue": round(week_revenue, 2),
        "month_revenue": round(month_revenue, 2),
        "week_orders": len(week_orders),
        "month_orders": len(month_orders),
        "period_revenue": round(period_revenue, 2),
        "period_orders": period_orders,
        "inventory_value": round(inventory_value, 2),
        "total_products": len(products),
        "active_products": sum(1 for p in products if p["is_active"]),
        "low_stock_count": len(query_all("SELECT id FROM products WHERE stock <= low_stock_threshold")),
    }

    return render_template(
        "dashboard.html",
        active_view="dashboard",
        settings=settings,
        stats=stats,
        hourly_data=hourly_filtered,
        daily_sales=list(daily_map.values()),
        top_products=top_products,
        category_breakdown=cat_rows,
        payment_breakdown=pay_rows,
        recent_orders=recent_orders,
        low_stock=low_stock,
        date_from=date_from[:10],
        date_to=date_to[:10],
    )


@app.route("/pos")
@login_required
def pos_terminal():
    settings = get_settings()
    categories = query_all("SELECT * FROM categories ORDER BY name ASC")
    products = query_all(
        """SELECT p.*, c.name as category_name, c.color as category_color
        FROM products p
        JOIN categories c ON p.category_id = c.id
        WHERE p.is_active = 1
        ORDER BY p.name ASC"""
    )
    customers = query_all("SELECT * FROM customers ORDER BY name ASC")
    return render_template(
        "pos.html",
        active_view="pos",
        settings=settings,
        categories=categories,
        products=products,
        customers=customers,
    )


@app.route("/products")
@login_required
def products_view():
    settings = get_settings()
    categories = query_all("SELECT c.*, (SELECT COUNT(*) FROM products p WHERE p.category_id = c.id) as product_count FROM categories c ORDER BY name ASC")
    products = query_all(
        """SELECT p.*, c.name as category_name, c.color as category_color
        FROM products p
        JOIN categories c ON p.category_id = c.id
        ORDER BY p.name ASC"""
    )
    for p in products:
        p["margin"] = ((p["price"] - p["cost"]) / p["price"] * 100) if p["price"] > 0 else 0
        p["is_low"] = p["stock"] <= p["low_stock_threshold"]
        p["stock_value"] = p["cost"] * p["stock"]

    if request.args.get("export") == "csv":
        cols = [("name", "Name"), ("sku", "SKU"), ("barcode", "Barcode"),
                ("category_name", "Category"), ("price", "Price"), ("cost", "Cost"),
                ("margin", "Margin %"), ("stock", "Stock"), ("stock_value", "Stock Value"),
                ("is_active", "Status")]
        rows = []
        for p in products:
            row = dict(p)
            row["margin"] = round(p["margin"], 1)
            row["stock_value"] = round(p["stock_value"], 2)
            row["is_active"] = "Active" if p["is_active"] else "Inactive"
            rows.append(row)
        return csv_response("products.csv", cols, rows)

    total_value = sum(p["cost"] * p["stock"] for p in products)
    retail_value = sum(p["price"] * p["stock"] for p in products)

    return render_template(
        "products.html",
        active_view="products",
        settings=settings,
        categories=categories,
        products=products,
        total_value=total_value,
        retail_value=retail_value,
        potential_profit=retail_value - total_value,
    )


@app.route("/products/new", methods=["POST"])
@login_required
def products_new():
    execute(
        """INSERT INTO products
        (id, name, sku, barcode, description, category_id, price, cost, stock, low_stock_threshold, unit, is_active)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            str(uuid.uuid4()),
            request.form.get("name", ""),
            request.form.get("sku", ""),
            request.form.get("barcode") or None,
            request.form.get("description") or None,
            request.form.get("category_id"),
            parse_float(request.form.get("price")),
            parse_float(request.form.get("cost")),
            parse_int(request.form.get("stock")),
            parse_int(request.form.get("low_stock_threshold"), 10),
            request.form.get("unit", "pcs"),
            1 if request.form.get("is_active") in ("on", "true", "1") else 0,
        )
    )
    flash("Product created successfully", "success")
    return redirect(url_for("products_view"))


@app.route("/products/<product_id>/edit", methods=["POST"])
@login_required
def products_edit(product_id):
    execute(
        """UPDATE products SET
        name = ?, sku = ?, barcode = ?, description = ?, category_id = ?,
        price = ?, cost = ?, stock = ?, low_stock_threshold = ?, unit = ?, is_active = ?,
        updated_at = datetime('now')
        WHERE id = ?""",
        (
            request.form.get("name"),
            request.form.get("sku"),
            request.form.get("barcode") or None,
            request.form.get("description") or None,
            request.form.get("category_id"),
            parse_float(request.form.get("price")),
            parse_float(request.form.get("cost")),
            parse_int(request.form.get("stock")),
            parse_int(request.form.get("low_stock_threshold"), 10),
            request.form.get("unit", "pcs"),
            1 if request.form.get("is_active") in ("on", "true", "1") else 0,
            product_id,
        )
    )
    flash("Product updated", "success")
    return redirect(url_for("products_view"))


@app.route("/products/<product_id>/delete", methods=["POST"])
@login_required
def products_delete(product_id):
    execute("DELETE FROM products WHERE id = ?", (product_id,))
    flash("Product deleted", "success")
    return redirect(url_for("products_view"))


@app.route("/categories/new", methods=["POST"])
@login_required
def categories_new():
    execute(
        "INSERT INTO categories (id, name, description, color) VALUES (?, ?, ?, ?)",
        (str(uuid.uuid4()), request.form.get("name"), request.form.get("description") or None,
         request.form.get("color", "#10b981"))
    )
    flash("Category created", "success")
    return redirect(url_for("products_view"))


@app.route("/categories/<cat_id>/delete", methods=["POST"])
@login_required
def categories_delete(cat_id):
    count = query_one("SELECT COUNT(*) as c FROM products WHERE category_id = ?", (cat_id,))["c"]
    if count > 0:
        flash(f"Cannot delete: {count} products still in this category", "error")
    else:
        execute("DELETE FROM categories WHERE id = ?", (cat_id,))
        flash("Category deleted", "success")
    return redirect(url_for("products_view"))


@app.route("/orders")
@login_required
def orders_view():
    settings = get_settings()
    search = request.args.get("search", "")
    payment = request.args.get("payment", "all")
    date_from, date_to = get_date_range()

    sql = """
        SELECT o.*, c.name as customer_name
        FROM orders o
        LEFT JOIN customers c ON o.customer_id = c.id
    """
    where = []
    params = []
    if search:
        where.append("(o.order_number LIKE ? OR c.name LIKE ?)")
        params.extend([f"%{search}%", f"%{search}%"])
    if payment != "all":
        where.append("o.payment_method = ?")
        params.append(payment)
    where.append("o.created_at >= ?")
    params.append(date_from)
    where.append("o.created_at <= ?")
    params.append(date_to)
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY o.created_at DESC LIMIT 200"

    orders = query_all(sql, params)
    for o in orders:
        o["customer_name"] = o["customer_name"] or "Walk-in Customer"
        o["items"] = query_all("SELECT * FROM order_items WHERE order_id = ?", (o["id"],))
        o["items_count"] = sum(i["quantity"] for i in o["items"])

    if request.args.get("export") == "csv":
        cols = [("order_number", "Order #"), ("created_at", "Date"),
                ("customer_name", "Customer"), ("cashier_name", "Cashier"),
                ("items_count", "Items"), ("payment_method", "Payment"),
                ("subtotal", "Subtotal"), ("tax", "Tax"), ("discount", "Discount"),
                ("total", "Total")]
        return csv_response("orders.csv", cols, orders)

    total_revenue = sum(o["total"] for o in orders)
    avg_order = total_revenue / len(orders) if orders else 0
    total_items = sum(o["items_count"] for o in orders)

    return render_template(
        "orders.html",
        active_view="orders",
        settings=settings,
        orders=orders,
        search=search,
        payment_filter=payment,
        total_revenue=total_revenue,
        avg_order=avg_order,
        total_items=total_items,
        date_from=date_from[:10],
        date_to=date_to[:10],
    )


@app.route("/orders/<order_id>")
@login_required
def order_detail(order_id):
    order = query_one("SELECT o.*, c.name as customer_name FROM orders o LEFT JOIN customers c ON o.customer_id = c.id WHERE o.id = ?", (order_id,))
    if not order:
        return jsonify({"error": "Not found"}), 404
    order["customer_name"] = order["customer_name"] or "Walk-in Customer"
    items = query_all(
        """SELECT oi.*, p.category_id, c.name as category_name
        FROM order_items oi
        LEFT JOIN products p ON oi.product_id = p.id
        LEFT JOIN categories c ON p.category_id = c.id
        WHERE oi.order_id = ?""",
        (order_id,)
    )
    order["items"] = items
    return jsonify(order)


@app.route("/inventory")
@login_required
def inventory_view():
    settings = get_settings()
    products = query_all(
        """SELECT p.*, c.name as category_name, c.color as category_color
        FROM products p
        JOIN categories c ON p.category_id = c.id
        ORDER BY p.name ASC"""
    )
    categories = query_all("SELECT * FROM categories ORDER BY name ASC")

    total_stock = sum(p["stock"] for p in products)
    total_value = sum(p["cost"] * p["stock"] for p in products)
    out_of_stock = sum(1 for p in products if p["stock"] == 0)
    low_count = sum(1 for p in products if 0 < p["stock"] <= p["low_stock_threshold"])

    if request.args.get("export") == "csv":
        cols = [("name", "Name"), ("sku", "SKU"), ("category_name", "Category"),
                ("stock", "Current Stock"), ("low_stock_threshold", "Threshold"),
                ("stock_value", "Stock Value"), ("status", "Status")]
        rows = []
        for p in products:
            row = dict(p)
            row["stock_value"] = round(p["cost"] * p["stock"], 2)
            if p["stock"] == 0:
                row["status"] = "Out of Stock"
            elif p["stock"] <= p["low_stock_threshold"]:
                row["status"] = "Low Stock"
            elif p["stock"] > 200:
                row["status"] = "Overstock"
            else:
                row["status"] = "Healthy"
            rows.append(row)
        return csv_response("inventory.csv", cols, rows)

    # Category distribution
    cat_dist = query_all(
        """SELECT c.name, c.color,
        SUM(p.cost * p.stock) as value, SUM(p.stock) as items
        FROM categories c JOIN products p ON p.category_id = c.id
        GROUP BY c.id ORDER BY value DESC"""
    )
    for c in cat_dist:
        c["value"] = round(c["value"], 2)

    return render_template(
        "inventory.html",
        active_view="inventory",
        settings=settings,
        products=products,
        categories=categories,
        total_stock=total_stock,
        total_value=total_value,
        out_of_stock=out_of_stock,
        low_count=low_count,
        category_dist=cat_dist,
    )


@app.route("/inventory/<product_id>/adjust", methods=["POST"])
@login_required
def inventory_adjust(product_id):
    p = query_one("SELECT * FROM products WHERE id = ?", (product_id,))
    if not p:
        flash("Product not found", "error")
        return redirect(url_for("inventory_view"))

    adjust_type = request.form.get("type", "add")
    amount = parse_int(request.form.get("amount"), 0)
    if amount < 0:
        amount = 0

    if adjust_type == "add":
        new_stock = p["stock"] + amount
    elif adjust_type == "remove":
        new_stock = max(0, p["stock"] - amount)
    else:  # set
        new_stock = amount

    execute("UPDATE products SET stock = ?, updated_at = datetime('now') WHERE id = ?", (new_stock, product_id))
    flash(f"Stock adjusted: {p['stock']} → {new_stock}", "success")
    return redirect(url_for("inventory_view"))


@app.route("/customers")
@login_required
def customers_view():
    settings = get_settings()
    search = request.args.get("search", "")
    if search:
        customers = query_all(
            """SELECT * FROM customers
            WHERE name LIKE ? OR email LIKE ? OR phone LIKE ?
            ORDER BY created_at DESC""",
            (f"%{search}%", f"%{search}%", f"%{search}%")
        )
    else:
        customers = query_all("SELECT * FROM customers ORDER BY created_at DESC")

    if request.args.get("export") == "csv":
        cols = [("name", "Name"), ("email", "Email"), ("phone", "Phone"),
                ("address", "Address"), ("loyalty_points", "Points"),
                ("total_spent", "Total Spent"), ("orders_count", "Orders"),
                ("tier", "Tier"), ("created_at", "Joined")]
        rows = []
        for c in customers:
            row = dict(c)
            row["tier"] = customer_tier(c["loyalty_points"])[0]
            rows.append(row)
        return csv_response("customers.csv", cols, rows)

    total_loyalty = sum(c["loyalty_points"] for c in customers)
    total_spent = sum(c["total_spent"] for c in customers)
    avg_spent = total_spent / len(customers) if customers else 0
    real_count = sum(1 for c in customers if c["name"] != "Walk-in Customer")

    return render_template(
        "customers.html",
        active_view="customers",
        settings=settings,
        customers=customers,
        search=search,
        total_loyalty=total_loyalty,
        total_spent=total_spent,
        avg_spent=avg_spent,
        real_count=real_count,
    )


@app.route("/customers/new", methods=["POST"])
@login_required
def customers_new():
    execute(
        """INSERT INTO customers
        (id, name, email, phone, address, loyalty_points, note)
        VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (str(uuid.uuid4()), request.form.get("name"),
         request.form.get("email") or None, request.form.get("phone") or None,
         request.form.get("address") or None,
         parse_int(request.form.get("loyalty_points"), 0),
         request.form.get("note") or None)
    )
    flash("Customer added", "success")
    return redirect(url_for("customers_view"))


@app.route("/customers/<customer_id>/edit", methods=["POST"])
@login_required
def customers_edit(customer_id):
    execute(
        """UPDATE customers SET
        name = ?, email = ?, phone = ?, address = ?, note = ?, loyalty_points = ?,
        updated_at = datetime('now')
        WHERE id = ?""",
        (request.form.get("name"), request.form.get("email") or None,
         request.form.get("phone") or None, request.form.get("address") or None,
         request.form.get("note") or None,
         parse_int(request.form.get("loyalty_points"), 0),
         customer_id)
    )
    flash("Customer updated", "success")
    return redirect(url_for("customers_view"))


@app.route("/customers/<customer_id>/delete", methods=["POST"])
@login_required
def customers_delete(customer_id):
    execute("DELETE FROM customers WHERE id = ?", (customer_id,))
    flash("Customer deleted", "success")
    return redirect(url_for("customers_view"))


@app.route("/reports")
@login_required
def reports_view():
    settings = get_settings()
    days = parse_int(request.args.get("days"), 0)
    if days > 0 and days <= 365:
        now = datetime.utcnow()
        cutoff = (now - timedelta(days=days)).isoformat()
        date_from = cutoff
        date_to = now.replace(hour=23, minute=59, second=59, microsecond=0).isoformat()
    else:
        date_from, date_to = get_date_range()

    orders = query_all(
        """SELECT o.*, c.name as customer_name
        FROM orders o LEFT JOIN customers c ON o.customer_id = c.id
        WHERE o.created_at >= ? AND o.created_at <= ?
        ORDER BY o.created_at ASC""",
        (date_from, date_to)
    )

    # Daily sales
    daily_map = {}
    for o in orders:
        try:
            dt = datetime.fromisoformat(o["created_at"])
        except (ValueError, TypeError):
            continue
        key = dt.strftime("%Y-%m-%d")
        if key not in daily_map:
            daily_map[key] = {
                "date": key,
                "label": dt.strftime("%b %d"),
                "sales": 0, "orders": 0, "profit": 0,
            }
        daily_map[key]["sales"] += o["total"]
        daily_map[key]["orders"] += 1
        items = query_all("SELECT * FROM order_items WHERE order_id = ?", (o["id"],))
        daily_map[key]["profit"] += sum((i["price"] - i["cost"]) * i["quantity"] for i in items)
    daily_sales = list(daily_map.values())
    for d in daily_sales:
        d["sales"] = round(d["sales"], 2)
        d["profit"] = round(d["profit"], 2)

    # Top products
    top_rows = query_all(
        """SELECT oi.product_id, oi.name, oi.price, oi.cost,
        SUM(oi.quantity) as quantity, SUM(oi.subtotal) as revenue,
        SUM((oi.price - oi.cost) * oi.quantity) as profit
        FROM order_items oi JOIN orders o ON oi.order_id = o.id
        WHERE o.created_at >= ? AND o.created_at <= ?
        GROUP BY oi.product_id
        ORDER BY revenue DESC""",
        (date_from, date_to)
    )
    for r in top_rows:
        r["revenue"] = round(r["revenue"], 2)
        r["profit"] = round(r["profit"], 2)
        r["margin"] = (r["profit"] / r["revenue"] * 100) if r["revenue"] > 0 else 0
        cat = query_one(
            """SELECT c.name FROM products p JOIN categories c ON p.category_id = c.id
            WHERE p.id = ?""", (r["product_id"],)
        )
        r["category"] = cat["name"] if cat else "—"

    # Category breakdown
    cat_rows = query_all(
        """SELECT c.name, c.color,
        SUM(oi.subtotal) as revenue, SUM(oi.quantity) as quantity,
        SUM((oi.price - oi.cost) * oi.quantity) as profit
        FROM order_items oi
        JOIN orders o ON oi.order_id = o.id
        JOIN products p ON oi.product_id = p.id
        JOIN categories c ON p.category_id = c.id
        WHERE o.created_at >= ? AND o.created_at <= ?
        GROUP BY c.id ORDER BY revenue DESC""",
        (date_from, date_to)
    )
    for c in cat_rows:
        c["revenue"] = round(c["revenue"], 2)
        c["profit"] = round(c["profit"], 2)

    # Payment breakdown
    pay_rows = query_all(
        """SELECT payment_method, COUNT(*) as count, SUM(total) as total
        FROM orders WHERE created_at >= ? AND created_at <= ?
        GROUP BY payment_method""",
        (date_from, date_to)
    )
    for p in pay_rows:
        p["total"] = round(p["total"], 2)

    total_revenue = sum(o["total"] for o in orders)
    total_profit = sum(
        sum((i["price"] - i["cost"]) * i["quantity"] for i in query_all("SELECT * FROM order_items WHERE order_id = ?", (o["id"],)))
        for o in orders
    )
    total_items = sum(
        sum(i["quantity"] for i in query_all("SELECT * FROM order_items WHERE order_id = ?", (o["id"],)))
        for o in orders
    )
    summary = {
        "total_revenue": round(total_revenue, 2),
        "total_profit": round(total_profit, 2),
        "total_orders": len(orders),
        "total_items": total_items,
        "avg_order_value": round(total_revenue / len(orders), 2) if orders else 0,
        "profit_margin": round(total_profit / total_revenue * 100, 2) if total_revenue > 0 else 0,
    }

    return render_template(
        "reports.html",
        active_view="reports",
        settings=settings,
        days=days,
        date_from=date_from[:10],
        date_to=date_to[:10],
        summary=summary,
        daily_sales=daily_sales,
        top_products=top_rows,
        category_breakdown=cat_rows,
        payment_breakdown=pay_rows,
    )


@app.route("/settings", methods=["GET", "POST"])
@login_required
def settings_view():
    if request.method == "POST":
        s = get_settings()
        execute(
            """UPDATE settings SET
            store_name = ?, address = ?, phone = ?, email = ?,
            tax_rate = ?, currency = ?, currency_symbol = ?,
            receipt_footer = ?, low_stock_alert_enabled = ?,
            smtp_host = ?, smtp_port = ?, smtp_user = ?, smtp_pass = ?, smtp_from_email = ?,
            gdrive_client_id = ?, gdrive_client_secret = ?,
            updated_at = datetime('now')
            WHERE id = ?""",
            (
                request.form.get("store_name"),
                request.form.get("address"),
                request.form.get("phone"),
                request.form.get("email"),
                parse_float(request.form.get("tax_rate"), 0),
                request.form.get("currency", "USD"),
                request.form.get("currency_symbol", "$"),
                request.form.get("receipt_footer", ""),
                1 if request.form.get("low_stock_alert_enabled") in ("on", "true", "1") else 0,
                request.form.get("smtp_host") or None,
                request.form.get("smtp_port") or None,
                request.form.get("smtp_user") or None,
                request.form.get("smtp_pass") or None,
                request.form.get("smtp_from_email") or None,
                request.form.get("gdrive_client_id") or None,
                request.form.get("gdrive_client_secret") or None,
                s["id"],
            )
        )
        flash("Settings saved successfully", "success")
        return redirect(url_for("settings_view"))

    settings = get_settings()
    currencies = [
        ("USD", "$", "US Dollar"), ("EUR", "€", "Euro"), ("GBP", "£", "British Pound"),
        ("INR", "₹", "Indian Rupee"), ("JPY", "¥", "Japanese Yen"),
        ("CNY", "¥", "Chinese Yuan"), ("AUD", "A$", "Australian Dollar"),
        ("CAD", "C$", "Canadian Dollar"),
    ]
    return render_template(
        "settings.html",
        active_view="settings",
        settings=settings,
        currencies=currencies,
    )


@app.route("/invoices")
@login_required
def invoices_view():
    settings = get_settings()
    date_from, date_to = get_date_range()
    orders = query_all(
        """SELECT o.*, c.name as customer_name
        FROM orders o
        LEFT JOIN customers c ON o.customer_id = c.id
        WHERE o.created_at >= ? AND o.created_at <= ?
        ORDER BY o.created_at DESC LIMIT 200""",
        (date_from, date_to)
    )
    for o in orders:
        o["customer_name"] = o["customer_name"] or "Walk-in Customer"
        o["items"] = query_all(
            """SELECT oi.*, c.name as category_name
            FROM order_items oi
            LEFT JOIN products p ON oi.product_id = p.id
            LEFT JOIN categories c ON p.category_id = c.id
            WHERE oi.order_id = ?""",
            (o["id"],)
        )
        o["items_count"] = sum(i["quantity"] for i in o["items"])

    if request.args.get("export") == "csv":
        cols = [("order_number", "Invoice #"), ("created_at", "Date"),
                ("customer_name", "Customer"), ("cashier_name", "Cashier"),
                ("items_count", "Items"), ("subtotal", "Subtotal"),
                ("tax", "Tax"), ("discount", "Discount"), ("total", "Total"),
                ("payment_method", "Payment")]
        return csv_response("invoices.csv", cols, orders)

    total_revenue = sum(o["total"] for o in orders)
    total_orders = len(orders)
    total_items = sum(o["items_count"] for o in orders)

    return render_template(
        "invoices.html",
        active_view="invoices",
        settings=settings,
        orders=orders,
        total_revenue=total_revenue,
        total_orders=total_orders,
        total_items=total_items,
        date_from=date_from[:10],
        date_to=date_to[:10],
    )


# ---------- API endpoints (POS checkout) ----------

@app.route("/api/checkout", methods=["POST"])
def checkout():
    """Create a new order from cart JSON."""
    try:
        data = request.get_json(force=True)
        items = data.get("items", [])
        if not items:
            return jsonify({"error": "Cart is empty"}), 400

        settings = get_settings()
        tax_rate = float(data.get("tax_rate", settings["tax_rate"]))
        discount = float(data.get("discount", 0))
        payment_method = data.get("payment_method", "cash")
        customer_id = data.get("customer_id") or None
        cashier_name = data.get("cashier_name", "Cashier")

        # Validate stock and compute totals
        subtotal = 0.0
        order_items = []
        for item in items:
            p = query_one("SELECT * FROM products WHERE id = ?", (item["productId"],))
            if not p:
                return jsonify({"error": f"Product not found: {item['productId']}"}), 400
            qty = int(item["quantity"])
            if p["stock"] < qty:
                return jsonify({"error": f"Insufficient stock for {p['name']}"}), 400
            line_total = round(p["price"] * qty, 2)
            subtotal += line_total
            order_items.append({
                "product_id": p["id"],
                "name": p["name"],
                "price": p["price"],
                "cost": p["cost"],
                "quantity": qty,
                "subtotal": line_total,
            })

        subtotal = round(subtotal, 2)
        tax = round(subtotal * tax_rate / 100, 2)
        total = round(subtotal + tax - discount, 2)

        # Generate order number
        count = query_one("SELECT COUNT(*) as c FROM orders")["c"]
        order_number = f"ORD-{10000 + count + 1}"
        order_id = str(uuid.uuid4())

        # Insert order + items + decrement stock + update customer (transaction)
        from models import get_db
        conn = get_db()
        try:
            cur = conn.cursor()
            cur.execute(
                """INSERT INTO orders
                (id, order_number, customer_id, cashier_name, subtotal, tax_rate, tax,
                 discount, total, payment_method, payment_status, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'paid', 'completed')""",
                (order_id, order_number, customer_id, cashier_name, subtotal, tax_rate,
                 tax, discount, total, payment_method)
            )
            for it in order_items:
                cur.execute(
                    """INSERT INTO order_items
                    (id, order_id, product_id, name, price, cost, quantity, subtotal)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (str(uuid.uuid4()), order_id, it["product_id"], it["name"],
                     it["price"], it["cost"], it["quantity"], it["subtotal"])
                )
                cur.execute(
                    "UPDATE products SET stock = stock - ? WHERE id = ?",
                    (it["quantity"], it["product_id"])
                )
            if customer_id:
                cur.execute(
                    """UPDATE customers SET
                    total_spent = total_spent + ?, orders_count = orders_count + 1,
                    loyalty_points = loyalty_points + ? WHERE id = ?""",
                    (total, int(total), customer_id)
                )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

        # Fetch the completed order with customer info
        order = query_one("SELECT o.*, c.name as customer_name FROM orders o LEFT JOIN customers c ON o.customer_id = c.id WHERE o.id = ?", (order_id,))
        order["customer_name"] = order["customer_name"] or "Walk-in Customer"
        order["items"] = order_items
        order["currency_symbol"] = settings["currency_symbol"]

        return jsonify({"order": order})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ---------- Barcode API ----------

@app.route("/api/products/by-barcode/<barcode>")
@login_required
def product_by_barcode(barcode):
    p = query_one("SELECT id, name, price, cost, stock, unit FROM products WHERE barcode = ? AND is_active = 1", (barcode,))
    if not p:
        return jsonify({"error": "Product not found"}), 404
    return jsonify(p)


# ---------- Run ----------

if __name__ == "__main__":
    print(f"\n🚀 QuickPOS running at http://localhost:{PORT}\n")
    app.run(host="0.0.0.0", port=PORT, debug=False)
