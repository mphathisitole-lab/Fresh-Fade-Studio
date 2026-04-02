import os
import re
import hashlib

try:
    from dotenv import load_dotenv  # type: ignore[import]
    load_dotenv()
except ImportError:
    pass  # python-dotenv not installed; use system env vars
import secrets
import string
import random
import urllib.parse
from datetime import datetime, timedelta, date, time
from functools import wraps

from flask import (
    Flask, render_template, request, redirect, url_for,
    flash, session, jsonify, abort
)
from flask_sqlalchemy import SQLAlchemy
from flask_mail import Mail, Message
from werkzeug.security import generate_password_hash, check_password_hash
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature

# ---------------------------------------------------------------------------
# App configuration
# ---------------------------------------------------------------------------
app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get(
    "SECRET_KEY", "change-me-in-production-use-a-real-secret"
)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///csas.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# Set APP_URL to your production domain (e.g. "https://aurastudio.onrender.com")
# Leave unset in dev — Flask will use the request host automatically
_app_url = os.environ.get("APP_URL", "").rstrip("/")
if _app_url:
    from urllib.parse import urlparse as _urlparse
    _parsed = _urlparse(_app_url)
    app.config["SERVER_NAME"] = _parsed.netloc
    app.config["PREFERRED_URL_SCHEME"] = _parsed.scheme

# Flask-Mail — Gmail requires sender to match your actual email address
app.config["MAIL_SERVER"] = os.environ.get("MAIL_SERVER", "smtp.gmail.com")
app.config["MAIL_PORT"] = int(os.environ.get("MAIL_PORT", 587))
app.config["MAIL_USE_TLS"] = True   # Gmail port 587 needs TLS
app.config["MAIL_USE_SSL"] = False  # Only True if using port 465
app.config["MAIL_USERNAME"] = os.environ.get("MAIL_USERNAME", "aurastudio.co6@gmail.com")
app.config["MAIL_PASSWORD"] = os.environ.get("MAIL_PASSWORD", "")  # Set via env var or .env file
# CRITICAL: Sender MUST be your actual Gmail address
app.config["MAIL_DEFAULT_SENDER"] = (
    "Aura Studio.co <" + app.config["MAIL_USERNAME"] + ">"
)
app.config["MAIL_DEBUG"] = True  # Print SMTP conversation to console

db = SQLAlchemy(app)
mail = Mail(app)
serializer = URLSafeTimedSerializer(app.config["SECRET_KEY"])

# ---------------------------------------------------------------------------
# Contact details
# ---------------------------------------------------------------------------
CONTACT_PHONE = "+27 79 909 7678"
CONTACT_EMAIL = "aurastudio.co6@gmail.com"

# ---------------------------------------------------------------------------
# Payment Gateway Credentials
# ---------------------------------------------------------------------------
# PayFast — supports Card, EFT, Capitec Pay, SnapScan, Zapper, Mobicred
# Sign up at https://www.payfast.co.za and get your credentials
# PayFast handles Capitec Pay natively — your Capitec acc 2208645495 is
# linked via your PayFast merchant profile settings.
PAYFAST_MERCHANT_ID = os.environ.get("PAYFAST_MERCHANT_ID", "34375701")
PAYFAST_MERCHANT_KEY = os.environ.get("PAYFAST_MERCHANT_KEY", "tcjt2xv6kexwg")
PAYFAST_PASSPHRASE = os.environ.get("PAYFAST_PASSPHRASE", "Thegreatbeginning01")
PAYFAST_SANDBOX = os.environ.get("PAYFAST_SANDBOX", "false").lower() == "true"
PAYFAST_URL = (
    "https://sandbox.payfast.co.za/eng/process"
    if PAYFAST_SANDBOX
    else "https://www.payfast.co.za/eng/process"
)

# ---------------------------------------------------------------------------
# Hairstyle catalogue
# ---------------------------------------------------------------------------
HAIRSTYLES = [
    {"id": "taper_fade",    "name": "Taper Fade",          "price": 150},
    {"id": "low_fade",      "name": "Low Fade",            "price": 150},
    {"id": "mid_fade",      "name": "Mid Fade",            "price": 150},
    {"id": "high_fade",     "name": "High Fade",           "price": 150},
    {"id": "skin_fade",     "name": "Skin Fade",           "price": 160},
    {"id": "buzz_cut",      "name": "Buzz Cut",            "price": 100},
    {"id": "crew_cut",      "name": "Crew Cut",            "price": 120},
    {"id": "flat_top",      "name": "Flat Top",            "price": 140},
    {"id": "pompadour",     "name": "Pompadour",           "price": 180},
    {"id": "quiff",         "name": "Quiff",               "price": 170},
    {"id": "slick_back",    "name": "Slick Back",          "price": 160},
    {"id": "comb_over",     "name": "Comb Over",           "price": 150},
    {"id": "undercut",      "name": "Undercut",            "price": 160},
    {"id": "mohawk",        "name": "Mohawk",              "price": 180},
    {"id": "faux_hawk",     "name": "Faux Hawk",           "price": 170},
    {"id": "caesar_cut",    "name": "Caesar Cut",          "price": 130},
    {"id": "french_crop",   "name": "French Crop",         "price": 140},
    {"id": "textured_crop", "name": "Textured Crop",       "price": 150},
    {"id": "line_up",       "name": "Line Up / Shape Up",  "price": 100},
    {"id": "box_braids",    "name": "Box Braids",          "price": 350},
    {"id": "cornrows",      "name": "Cornrows",            "price": 300},
    {"id": "dreadlocks",    "name": "Dreadlocks (Start)",  "price": 400},
    {"id": "twist_out",     "name": "Twist Out",           "price": 250},
    {"id": "afro_shape",    "name": "Afro Shape-Up",       "price": 180},
    {"id": "mullet",        "name": "Modern Mullet",       "price": 160},
    {"id": "shag",          "name": "Shag Cut",            "price": 170},
    {"id": "beard_trim",    "name": "Beard Trim (Add-on)", "price": 80},
    {"id": "hot_towel",     "name": "Hot Towel Shave",     "price": 120},
    {"id": "kids_cut",      "name": "Kids Cut (Under 12)", "price": 100},
]

# ---------------------------------------------------------------------------
# Working hours config
# ---------------------------------------------------------------------------
WORK_START = 8
WORK_END = 17
SLOT_MINUTES = 45
WORK_DAYS = [0, 1, 2, 3, 4, 5]


def generate_slots(for_date):
    slots = []
    current = datetime.combine(for_date, time(WORK_START, 0))
    end = datetime.combine(for_date, time(WORK_END, 0))
    while current + timedelta(minutes=SLOT_MINUTES) <= end:
        slots.append(current.time())
        current += timedelta(minutes=SLOT_MINUTES)
    return slots


# ---------------------------------------------------------------------------
# Password helpers
# ---------------------------------------------------------------------------
def validate_password(pw):
    if len(pw) < 8:
        return False, "Password must be at least 8 characters long."
    if not re.search(r"[A-Z]", pw):
        return False, "Must contain at least one uppercase letter."
    if not re.search(r"[a-z]", pw):
        return False, "Must contain at least one lowercase letter."
    if not re.search(r"\d", pw):
        return False, "Must contain at least one digit."
    if not re.search(r"[!@#$%^&*()_+\-=\[\]{};':\"\\|,.<>\/?]", pw):
        return False, "Must contain at least one special character."
    return True, "Password is strong."


def generate_strong_password(length=14):
    upper = random.choices(string.ascii_uppercase, k=2)
    lower = random.choices(string.ascii_lowercase, k=4)
    digits = random.choices(string.digits, k=3)
    specials = random.choices("!@#$%^&*_+-=", k=2)
    filler = random.choices(
        string.ascii_letters + string.digits + "!@#$%^&*", k=length - 11
    )
    pool = upper + lower + digits + specials + filler
    random.shuffle(pool)
    return "".join(pool)


# ---------------------------------------------------------------------------
# Token helpers (email verification & password reset)
# ---------------------------------------------------------------------------
def generate_token(email, salt):
    return serializer.dumps(email, salt=salt)


def verify_token(token, salt, max_age=3600):
    """Verify a timed token. Default max_age = 1 hour."""
    try:
        email = serializer.loads(token, salt=salt, max_age=max_age)
        return email
    except (SignatureExpired, BadSignature):
        return None


# ---------------------------------------------------------------------------
# Database models
# ---------------------------------------------------------------------------
class User(db.Model):
    __tablename__ = "users"
    id               = db.Column(db.Integer, primary_key=True)
    first_name       = db.Column(db.String(100), nullable=False)
    last_name        = db.Column(db.String(100), nullable=False)
    email            = db.Column(db.String(200), unique=True, nullable=False)
    phone            = db.Column(db.String(30), nullable=False)
    physical_address = db.Column(db.String(300))
    street_number    = db.Column(db.String(30))
    postal_code      = db.Column(db.String(20))
    password_hash    = db.Column(db.String(256), nullable=False)
    is_verified      = db.Column(db.Boolean, default=False)
    is_admin         = db.Column(db.Boolean, default=False)
    created_at       = db.Column(db.DateTime, default=datetime.utcnow)
    appointments     = db.relationship("Appointment", backref="user", lazy=True)

    def set_password(self, pw):
        self.password_hash = generate_password_hash(pw)

    def check_password(self, pw):
        return check_password_hash(self.password_hash, pw)


class Appointment(db.Model):
    __tablename__ = "appointments"
    id               = db.Column(db.Integer, primary_key=True)
    user_id          = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    hairstyle_id     = db.Column(db.String(50), nullable=False)
    hairstyle_name   = db.Column(db.String(100), nullable=False)
    price            = db.Column(db.Float, nullable=False)
    appointment_date = db.Column(db.Date, nullable=False)
    appointment_time = db.Column(db.Time, nullable=False)
    payment_method   = db.Column(db.String(30), nullable=False)
    payment_provider = db.Column(db.String(50), default="")
    payment_reference = db.Column(db.String(100), default="")
    payment_status   = db.Column(db.String(20), default="pending")
    status           = db.Column(db.String(20), default="confirmed")
    review_rating    = db.Column(db.Integer, nullable=True)
    review_sent      = db.Column(db.Boolean, default=False)
    created_at       = db.Column(db.DateTime, default=datetime.utcnow)


class AdminSettings(db.Model):
    __tablename__ = "admin_settings"
    id           = db.Column(db.Integer, primary_key=True)
    is_available = db.Column(db.Boolean, default=True)


class BlockedSlot(db.Model):
    __tablename__ = "blocked_slots"
    id         = db.Column(db.Integer, primary_key=True)
    block_date = db.Column(db.Date, nullable=False)
    start_time = db.Column(db.Time, nullable=False)
    end_time   = db.Column(db.Time, nullable=False)
    reason     = db.Column(db.String(200), default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class ChatMessage(db.Model):
    __tablename__ = "chat_messages"
    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    sender     = db.Column(db.String(10), nullable=False)  # "user" or "admin"
    message    = db.Column(db.Text, nullable=False)
    is_read    = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user       = db.relationship("User", backref="messages")


# ---------------------------------------------------------------------------
# Decorators
# ---------------------------------------------------------------------------
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in first.", "warning")
            return redirect(url_for("login", next=request.url))
        return f(*args, **kwargs)
    return decorated


def verified_required(f):
    """User must be logged in AND email-verified."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in first.", "warning")
            return redirect(url_for("login", next=request.url))
        user = User.query.get(session["user_id"])
        if not user:
            session.clear()
            flash("Session expired. Please log in again.", "warning")
            return redirect(url_for("login", next=request.url))
        if not user.is_verified:
            flash("Please verify your email before booking.", "warning")
            return redirect(url_for("unverified"))
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("is_admin"):
            flash("Admin access required.", "danger")
            return redirect(url_for("admin_login"))
        return f(*args, **kwargs)
    return decorated


# ---------------------------------------------------------------------------
# Email senders
# ---------------------------------------------------------------------------
def check_mail_configured():
    """Return True if SMTP credentials are set."""
    return bool(app.config.get("MAIL_USERNAME")) and bool(app.config.get("MAIL_PASSWORD"))


def send_verification_email(user):
    """Send email verification link."""
    if not check_mail_configured():
        print("⚠ MAIL NOT CONFIGURED — Set MAIL_USERNAME and MAIL_PASSWORD env vars.")
        print(f"  Verification link for {user.email} would be:")
        token = generate_token(user.email, salt="email-verify")
        print(f"  {url_for('verify_email', token=token, _external=True)}")
        return False
    try:
        token = generate_token(user.email, salt="email-verify")
        verify_url = url_for("verify_email", token=token, _external=True)
        msg = Message(
            subject="Aura Studio.co — Verify Your Email",
            recipients=[user.email],
        )
        msg.html = render_template(
            "email_verify.html", user=user, verify_url=verify_url
        )
        mail.send(msg)
        print(f"✓ Verification email sent to {user.email}")
        return True
    except Exception as e:
        print(f"✗ Verification email FAILED for {user.email}: {e}")
        return False


def send_reset_email(user):
    """Send password reset link."""
    if not check_mail_configured():
        print("⚠ MAIL NOT CONFIGURED — Set MAIL_USERNAME and MAIL_PASSWORD env vars.")
        token = generate_token(user.email, salt="password-reset")
        print(f"  Reset link for {user.email}:")
        print(f"  {url_for('reset_password', token=token, _external=True)}")
        return False
    try:
        token = generate_token(user.email, salt="password-reset")
        reset_url = url_for("reset_password", token=token, _external=True)
        msg = Message(
            subject="Aura Studio.co — Reset Your Password",
            recipients=[user.email],
        )
        msg.html = render_template(
            "email_reset.html", user=user, reset_url=reset_url
        )
        mail.send(msg)
        print(f"✓ Reset email sent to {user.email}")
        return True
    except Exception as e:
        print(f"✗ Reset email FAILED for {user.email}: {e}")
        return False


def send_confirmation_email(user, appointment):
    if not check_mail_configured():
        print(f"⚠ MAIL NOT CONFIGURED — Booking confirmation for {user.email} not sent.")
        return False
    try:
        msg = Message(
            subject="Aura Studio.co — Booking Confirmation",
            recipients=[user.email],
        )
        msg.html = render_template(
            "email_confirmation.html", user=user, appointment=appointment
        )
        mail.send(msg)
        print(f"✓ Booking confirmation sent to {user.email}")
        return True
    except Exception as e:
        print(f"✗ Booking confirmation FAILED for {user.email}: {e}")
        return False


def send_review_email(user, appointment):
    if not check_mail_configured():
        print(f"⚠ MAIL NOT CONFIGURED — Review email for {user.email} not sent.")
        return False
    try:
        msg = Message(
            subject="Aura Studio.co — How Was Your Cut?",
            recipients=[user.email],
        )
        msg.html = render_template(
            "email_review.html", user=user, appointment=appointment
        )
        mail.send(msg)
        appointment.review_sent = True
        db.session.commit()
        print(f"✓ Review email sent to {user.email}")
        return True
    except Exception as e:
        print(f"✗ Review email FAILED for {user.email}: {e}")
        return False


def get_admin_settings():
    settings = AdminSettings.query.first()
    if not settings:
        settings = AdminSettings(is_available=True)
        db.session.add(settings)
        db.session.commit()
    return settings


def get_blocked_times(for_date):
    blocks = BlockedSlot.query.filter_by(block_date=for_date).all()
    blocked = set()
    all_slots = generate_slots(for_date)
    for slot in all_slots:
        slot_end = (
            datetime.combine(for_date, slot) + timedelta(minutes=SLOT_MINUTES)
        ).time()
        for b in blocks:
            if slot < b.end_time and slot_end > b.start_time:
                blocked.add(slot)
    return blocked


# ---------------------------------------------------------------------------
# PayFast signature generation
# ---------------------------------------------------------------------------
def payfast_generate_signature(data_dict, passphrase=None):
    """Generate MD5 signature for PayFast."""
    # Create parameter string
    pf_output = ""
    for key, val in data_dict.items():
        if val != "":
            pf_output += f"{key}={urllib.parse.quote_plus(str(val).strip())}&"
    # Remove trailing &
    pf_output = pf_output[:-1]
    if passphrase:
        pf_output += f"&passphrase={urllib.parse.quote_plus(passphrase.strip())}"
    return hashlib.md5(pf_output.encode()).hexdigest()



# ===================================================================
# ROUTES — Public pages
# ===================================================================
@app.route("/")
def index():
    settings = get_admin_settings()
    return render_template("index.html", barber_available=settings.is_available)


@app.route("/services")
def services():
    return render_template("services.html", hairstyles=HAIRSTYLES)


@app.route("/services/book/<style_id>")
def service_book(style_id):
    style = next((s for s in HAIRSTYLES if s["id"] == style_id), None)
    if not style:
        flash("Hairstyle not found.", "danger")
        return redirect(url_for("services"))
    if "user_id" not in session:
        flash("Please log in or create an account to book.", "warning")
        return redirect(url_for("login", next=url_for("book", style=style_id)))
    return redirect(url_for("book", style=style_id))


@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/contact")
def contact():
    return render_template("contact.html")


# ===================================================================
# ROUTES — Auth (register, login, verify, reset)
# ===================================================================
@app.route("/api/suggest-password")
def api_suggest_password():
    return jsonify({"password": generate_strong_password()})


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")

        ok, msg = validate_password(password)
        if not ok:
            flash(msg, "danger")
            return redirect(url_for("register"))
        if password != confirm:
            flash("Passwords do not match.", "danger")
            return redirect(url_for("register"))
        if User.query.filter_by(email=email).first():
            flash("An account with this email already exists.", "danger")
            return redirect(url_for("register"))

        user = User(
            first_name=request.form["first_name"].strip(),
            last_name=request.form["last_name"].strip(),
            email=email,
            phone=request.form["phone"].strip(),
            physical_address=request.form.get("physical_address", "").strip(),
            street_number=request.form.get("street_number", "").strip(),
            postal_code=request.form.get("postal_code", "").strip(),
            is_verified=False,
        )
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        # Send verification email
        email_sent = send_verification_email(user)

        # Auto-login and redirect to verification page
        session["user_id"] = user.id
        session["user_name"] = user.first_name

        if email_sent:
            flash(
                "Account created! Check your email inbox (and spam folder) for the verification link.",
                "success",
            )
        else:
            flash(
                "Account created! We couldn't send the verification email. "
                "Click 'Resend' on the next page, or check your terminal for the link.",
                "warning",
            )
        return redirect(url_for("unverified"))
    return render_template("register.html")


@app.route("/verify-email/<token>")
def verify_email(token):
    email = verify_token(token, salt="email-verify", max_age=86400)  # 24h
    if not email:
        flash("Verification link is invalid or has expired.", "danger")
        return redirect(url_for("login"))
    user = User.query.filter_by(email=email).first()
    if not user:
        flash("Account not found.", "danger")
        return redirect(url_for("register"))
    if user.is_verified:
        flash("Email already verified. You can log in.", "info")
        return redirect(url_for("login"))
    user.is_verified = True
    db.session.commit()
    flash("Email verified successfully! You can now log in and book.", "success")
    return redirect(url_for("login"))


@app.route("/unverified")
@login_required
def unverified():
    user = User.query.get(session["user_id"])
    if user.is_verified:
        return redirect(url_for("dashboard"))
    return render_template("unverified.html", user=user)


@app.route("/resend-verification")
@login_required
def resend_verification():
    user = User.query.get(session["user_id"])
    if user.is_verified:
        flash("Your email is already verified.", "info")
        return redirect(url_for("dashboard"))
    send_verification_email(user)
    flash("Verification email resent! Check your inbox.", "success")
    return redirect(url_for("unverified"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            session["user_id"] = user.id
            session["user_name"] = user.first_name
            if not user.is_verified:
                flash("Please verify your email to use all features.", "warning")
                return redirect(url_for("unverified"))
            flash(f"Welcome back, {user.first_name}!", "success")
            next_url = request.args.get("next") or request.form.get("next")
            if next_url:
                return redirect(next_url)
            return redirect(url_for("dashboard"))
        flash("Invalid email or password.", "danger")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("You've been logged out.", "info")
    return redirect(url_for("index"))


@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        user = User.query.filter_by(email=email).first()
        if user:
            send_reset_email(user)
        # Always show same message to prevent email enumeration
        flash(
            "If an account exists with that email, a reset link has been sent.",
            "info",
        )
        return redirect(url_for("login"))
    return render_template("forgot_password.html")


@app.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):
    email = verify_token(token, salt="password-reset", max_age=3600)  # 1h
    if not email:
        flash("Reset link is invalid or has expired.", "danger")
        return redirect(url_for("forgot_password"))
    user = User.query.filter_by(email=email).first()
    if not user:
        flash("Account not found.", "danger")
        return redirect(url_for("register"))

    if request.method == "POST":
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")
        ok, msg = validate_password(password)
        if not ok:
            flash(msg, "danger")
            return redirect(url_for("reset_password", token=token))
        if password != confirm:
            flash("Passwords do not match.", "danger")
            return redirect(url_for("reset_password", token=token))
        user.set_password(password)
        db.session.commit()
        flash("Password reset successfully! Please log in.", "success")
        return redirect(url_for("login"))

    return render_template("reset_password.html", token=token)


# ===================================================================
# ROUTES — Client dashboard & booking
# ===================================================================
@app.route("/dashboard")
@login_required
def dashboard():
    user = User.query.get(session["user_id"])
    upcoming = (
        Appointment.query.filter_by(user_id=user.id)
        .filter(Appointment.appointment_date >= date.today())
        .filter(Appointment.status != "cancelled")
        .order_by(Appointment.appointment_date, Appointment.appointment_time)
        .all()
    )
    past = (
        Appointment.query.filter_by(user_id=user.id)
        .filter(
            db.or_(
                Appointment.appointment_date < date.today(),
                Appointment.status == "completed",
            )
        )
        .order_by(Appointment.appointment_date.desc())
        .limit(10)
        .all()
    )
    return render_template("dashboard.html", user=user, upcoming=upcoming, past=past)


@app.route("/book", methods=["GET", "POST"])
@verified_required
def book():
    settings = get_admin_settings()
    if not settings.is_available:
        flash("The barber is currently unavailable. Try again later.", "warning")
        return redirect(url_for("dashboard"))

    preselected_style = request.args.get("style", "")

    if request.method == "POST":
        hairstyle_id = request.form.get("hairstyle")
        style = next((s for s in HAIRSTYLES if s["id"] == hairstyle_id), None)
        if not style:
            flash("Invalid hairstyle selected.", "danger")
            return redirect(url_for("book"))

        appt_date = datetime.strptime(request.form["date"], "%Y-%m-%d").date()
        appt_time = datetime.strptime(request.form["time"], "%H:%M").time()
        payment = request.form.get("payment_method", "cash")

        existing = Appointment.query.filter_by(
            appointment_date=appt_date, appointment_time=appt_time,
            status="confirmed",
        ).first()
        if existing:
            flash("That time slot is already booked.", "danger")
            return redirect(url_for("book"))

        blocked = get_blocked_times(appt_date)
        if appt_time in blocked:
            flash("That slot is blocked by the barber.", "danger")
            return redirect(url_for("book"))

        if appt_date.weekday() not in WORK_DAYS:
            flash("We are closed on Sundays.", "danger")
            return redirect(url_for("book"))

        # Create appointment (pending payment for non-cash)
        appointment = Appointment(
            user_id=session["user_id"],
            hairstyle_id=style["id"],
            hairstyle_name=style["name"],
            price=style["price"],
            appointment_date=appt_date,
            appointment_time=appt_time,
            payment_method=payment,
            payment_status="pending",
        )
        db.session.add(appointment)
        db.session.commit()

        # Route to payment gateway
        if payment == "cash":
            appointment.payment_status = "pay_on_arrival"
            appointment.status = "confirmed"
            db.session.commit()
            user = User.query.get(session["user_id"])
            send_confirmation_email(user, appointment)
            flash("Appointment booked! Pay on arrival.", "success")
            return redirect(url_for("dashboard"))

        elif payment == "payfast":
            return redirect(url_for("pay_payfast", appt_id=appointment.id))

        else:
            flash("Invalid payment method.", "danger")
            return redirect(url_for("book"))

    return render_template(
        "book.html",
        hairstyles=HAIRSTYLES,
        preselected_style=preselected_style,
    )


@app.route("/cancel/<int:appt_id>", methods=["POST"])
@login_required
def cancel_appointment(appt_id):
    appt = Appointment.query.get_or_404(appt_id)
    if appt.user_id != session["user_id"]:
        abort(403)
    appt.status = "cancelled"
    db.session.commit()
    flash("Appointment cancelled.", "info")
    return redirect(url_for("dashboard"))


# ===================================================================
# ROUTES — Real Payment Gateways
# ===================================================================

# --- PayFast (Card, EFT, Capitec Pay, SnapScan, Zapper) ---
@app.route("/pay/payfast/<int:appt_id>")
@login_required
def pay_payfast(appt_id):
    """Build PayFast payment form and redirect user."""
    appt = Appointment.query.get_or_404(appt_id)
    if appt.user_id != session["user_id"]:
        abort(403)
    user = User.query.get(session["user_id"])

    # PayFast data dict — order matters for signature!
    data = {
        "merchant_id": PAYFAST_MERCHANT_ID,
        "merchant_key": PAYFAST_MERCHANT_KEY,
        "return_url": url_for("payment_success", appt_id=appt.id, _external=True),
        "cancel_url": url_for("payment_cancel", appt_id=appt.id, _external=True),
        "notify_url": url_for("payfast_notify", _external=True),
        "name_first": user.first_name,
        "name_last": user.last_name,
        "email_address": user.email,
        "cell_number": user.phone.replace(" ", "").replace("+", ""),
        "m_payment_id": str(appt.id),
        "amount": f"{appt.price:.2f}",
        "item_name": f"Aura Studio.co - {appt.hairstyle_name}",
        "item_description": (
            f"{appt.hairstyle_name} on {appt.appointment_date.strftime('%d %b %Y')}"
            f" at {appt.appointment_time.strftime('%H:%M')}"
        ),
    }

    # Generate signature
    signature = payfast_generate_signature(data, PAYFAST_PASSPHRASE or None)
    data["signature"] = signature

    appt.payment_provider = "PayFast"
    db.session.commit()

    return render_template(
        "payment_redirect.html",
        gateway_name="PayFast",
        gateway_url=PAYFAST_URL,
        form_data=data,
        appointment=appt,
    )


@app.route("/pay/payfast/notify", methods=["POST"])
def payfast_notify():
    """PayFast ITN (Instant Transaction Notification) callback."""
    pf_data = request.form.to_dict()
    appt_id = pf_data.get("m_payment_id")
    payment_status = pf_data.get("payment_status")

    if appt_id and payment_status == "COMPLETE":
        appt = Appointment.query.get(int(appt_id))
        if appt:
            appt.payment_status = "paid"
            appt.payment_reference = pf_data.get("pf_payment_id", "")
            appt.status = "confirmed"
            db.session.commit()
            user = User.query.get(appt.user_id)
            send_confirmation_email(user, appt)

    return "OK", 200


# --- Payment return pages ---
@app.route("/pay/success/<int:appt_id>")
def payment_success(appt_id):
    appt = Appointment.query.get_or_404(appt_id)
    # Mark as paid if not already done by notify callback
    if appt.payment_status != "paid":
        appt.payment_status = "paid"
        appt.status = "confirmed"
        db.session.commit()
        user = User.query.get(appt.user_id)
        send_confirmation_email(user, appt)
    flash("Payment successful! Your appointment is confirmed.", "success")
    return render_template("payment_success.html", appointment=appt)


@app.route("/pay/cancel/<int:appt_id>")
def payment_cancel(appt_id):
    appt = Appointment.query.get_or_404(appt_id)
    appt.status = "cancelled"
    appt.payment_status = "cancelled"
    db.session.commit()
    flash("Payment was cancelled. Appointment has been removed.", "warning")
    return redirect(url_for("dashboard"))


# ===================================================================
# ROUTES — Review
# ===================================================================
@app.route("/review/<int:appt_id>", methods=["GET", "POST"])
def submit_review(appt_id):
    appt = Appointment.query.get_or_404(appt_id)
    if appt.status != "completed":
        flash("This appointment is not eligible for review.", "warning")
        return redirect(url_for("index"))
    if appt.review_rating is not None:
        flash("You've already submitted a review.", "info")
        return redirect(url_for("index"))

    if request.method == "POST":
        rating = int(request.form.get("rating", 0))
        if 1 <= rating <= 10:
            appt.review_rating = rating
            db.session.commit()
            flash(f"Thank you for your {rating}/10 rating!", "success")
        else:
            flash("Please select a valid rating.", "danger")
            return redirect(url_for("submit_review", appt_id=appt_id))
        return redirect(url_for("index"))

    return render_template("review.html", appointment=appt)


# ===================================================================
# ROUTES — Live Chat (User ↔ Admin)
# ===================================================================
@app.route("/api/chat/send", methods=["POST"])
@login_required
def chat_send():
    """User sends a message."""
    data = request.get_json()
    msg_text = (data.get("message") or "").strip()
    if not msg_text:
        return jsonify({"error": "Empty message"}), 400
    msg = ChatMessage(
        user_id=session["user_id"],
        sender="user",
        message=msg_text,
    )
    db.session.add(msg)
    db.session.commit()
    return jsonify({"success": True, "id": msg.id})


@app.route("/api/chat/messages")
@login_required
def chat_messages():
    """Get chat history for the logged-in user."""
    msgs = (
        ChatMessage.query.filter_by(user_id=session["user_id"])
        .order_by(ChatMessage.created_at.asc())
        .all()
    )
    # Mark admin messages as read
    for m in msgs:
        if m.sender == "admin" and not m.is_read:
            m.is_read = True
    db.session.commit()
    return jsonify({
        "messages": [
            {
                "id": m.id,
                "sender": m.sender,
                "message": m.message,
                "time": m.created_at.strftime("%H:%M"),
                "date": m.created_at.strftime("%d %b"),
            }
            for m in msgs
        ]
    })


@app.route("/api/chat/unread-count")
@login_required
def chat_unread_count():
    """Return count of unread admin messages for this user."""
    count = ChatMessage.query.filter_by(
        user_id=session["user_id"], sender="admin", is_read=False
    ).count()
    return jsonify({"count": count})


# --- Admin chat routes ---
@app.route("/admin/api/chat/conversations")
@admin_required
def admin_chat_conversations():
    """Get list of users who have sent messages, with unread counts."""
    # Get all users who have chat messages
    user_ids = db.session.query(ChatMessage.user_id).distinct().all()
    conversations = []
    for (uid,) in user_ids:
        user = User.query.get(uid)
        if not user:
            continue
        last_msg = (
            ChatMessage.query.filter_by(user_id=uid)
            .order_by(ChatMessage.created_at.desc())
            .first()
        )
        unread = ChatMessage.query.filter_by(
            user_id=uid, sender="user", is_read=False
        ).count()
        conversations.append({
            "user_id": uid,
            "name": f"{user.first_name} {user.last_name}",
            "email": user.email,
            "last_message": last_msg.message[:50] if last_msg else "",
            "last_time": last_msg.created_at.strftime("%H:%M %d %b") if last_msg else "",
            "unread": unread,
        })
    # Sort by unread first, then most recent
    conversations.sort(key=lambda c: (-c["unread"], c["last_time"]), reverse=False)
    return jsonify({"conversations": conversations})


@app.route("/admin/api/chat/messages/<int:user_id>")
@admin_required
def admin_chat_messages(user_id):
    """Get chat history for a specific user."""
    msgs = (
        ChatMessage.query.filter_by(user_id=user_id)
        .order_by(ChatMessage.created_at.asc())
        .all()
    )
    # Mark user messages as read
    for m in msgs:
        if m.sender == "user" and not m.is_read:
            m.is_read = True
    db.session.commit()
    user = User.query.get(user_id)
    return jsonify({
        "user_name": f"{user.first_name} {user.last_name}" if user else "Unknown",
        "messages": [
            {
                "id": m.id,
                "sender": m.sender,
                "message": m.message,
                "time": m.created_at.strftime("%H:%M"),
                "date": m.created_at.strftime("%d %b"),
            }
            for m in msgs
        ],
    })


@app.route("/admin/api/chat/send", methods=["POST"])
@admin_required
def admin_chat_send():
    """Admin sends a message to a user."""
    data = request.get_json()
    user_id = data.get("user_id")
    msg_text = (data.get("message") or "").strip()
    if not msg_text or not user_id:
        return jsonify({"error": "Missing data"}), 400
    msg = ChatMessage(
        user_id=int(user_id),
        sender="admin",
        message=msg_text,
    )
    db.session.add(msg)
    db.session.commit()
    return jsonify({"success": True, "id": msg.id})


@app.route("/admin/api/chat/unread-total")
@admin_required
def admin_chat_unread_total():
    """Total unread user messages across all conversations."""
    count = ChatMessage.query.filter_by(sender="user", is_read=False).count()
    return jsonify({"count": count})


# ===================================================================
# API — Calendar slots
# ===================================================================
@app.route("/api/slots/<date_str>")
def api_slots(date_str):
    try:
        target = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        return jsonify({"error": "Invalid date"}), 400

    if target.weekday() not in WORK_DAYS:
        return jsonify({"slots": [], "message": "Closed on Sundays"})
    if target < date.today():
        return jsonify({"slots": [], "message": "Cannot book in the past"})

    all_slots = generate_slots(target)
    booked = {
        a.appointment_time
        for a in Appointment.query.filter_by(
            appointment_date=target, status="confirmed"
        ).all()
    }
    blocked = get_blocked_times(target)

    result = []
    for s in all_slots:
        if target == date.today() and s <= datetime.now().time():
            continue
        result.append({
            "time": s.strftime("%H:%M"),
            "available": s not in booked and s not in blocked,
            "blocked": s in blocked,
        })
    return jsonify({"slots": result, "date": date_str})


@app.route("/api/calendar/<int:year>/<int:month>")
def api_calendar(year, month):
    first_day = date(year, month, 1)
    if month == 12:
        last_day = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        last_day = date(year, month + 1, 1) - timedelta(days=1)

    days = []
    current = first_day
    while current <= last_day:
        if current.weekday() in WORK_DAYS:
            all_slots = generate_slots(current)
            booked_count = Appointment.query.filter_by(
                appointment_date=current, status="confirmed"
            ).count()
            blocked_count = len(get_blocked_times(current))
            total_available = len(all_slots) - booked_count - blocked_count
            days.append({
                "date": current.isoformat(),
                "day": current.day,
                "weekday": current.strftime("%a"),
                "total_slots": len(all_slots),
                "booked": booked_count,
                "blocked": blocked_count,
                "available": max(total_available, 0),
                "is_past": current < date.today(),
            })
        else:
            days.append({
                "date": current.isoformat(),
                "day": current.day,
                "weekday": current.strftime("%a"),
                "total_slots": 0, "booked": 0, "available": 0, "closed": True,
            })
        current += timedelta(days=1)

    return jsonify({
        "year": year, "month": month,
        "month_name": first_day.strftime("%B"),
        "days": days,
        "work_hours": f"{WORK_START}:00 – {WORK_END}:00",
        "slot_duration": f"{SLOT_MINUTES} min",
    })


# ===================================================================
# ROUTES — Admin
# ===================================================================
@app.route("/admin/register", methods=["GET", "POST"])
def admin_register():
    if request.method == "POST":
        email    = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        ADMIN_EMAIL = "aurastudio.co6@gmail.com"
        if email != ADMIN_EMAIL:
            flash("Wrong email.", "danger")
            return render_template("admin_register.html")

        if User.query.filter_by(is_admin=True).count() >= 2:
            flash("Maximum of 2 admin accounts already exist.", "danger")
            return render_template("admin_register.html")

        if User.query.filter_by(email=email).first():
            flash("An account with that email already exists.", "danger")
            return render_template("admin_register.html")

        admin = User(
            first_name="Admin",
            last_name="",
            email=email,
            phone="",
            is_verified=False,
            is_admin=True,
        )
        admin.set_password(password)
        db.session.add(admin)
        db.session.commit()

        email_sent = send_verification_email(admin)
        session["user_id"] = admin.id
        session["user_name"] = admin.first_name

        if email_sent:
            flash(
                "Admin account created! Check your email inbox for the verification link.",
                "success",
            )
        else:
            flash(
                "Admin account created! Verification email could not be sent — check the terminal for the link.",
                "warning",
            )
        return redirect(url_for("unverified"))

    return render_template("admin_register.html")


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        email    = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = User.query.filter_by(email=email, is_admin=True).first()
        if user and user.check_password(password):
            if not user.is_verified:
                session["user_id"] = user.id
                session["user_name"] = user.first_name
                flash("Please verify your email before logging in.", "warning")
                return redirect(url_for("unverified"))
            session["is_admin"] = True
            session["admin_id"] = user.id
            flash("Welcome, Admin!", "success")
            return redirect(url_for("admin_dashboard"))
        flash("Invalid credentials.", "danger")
    return render_template("admin_login.html")


@app.route("/admin")
@admin_required
def admin_dashboard():
    settings = get_admin_settings()
    today_appts = (
        Appointment.query.filter_by(appointment_date=date.today(), status="confirmed")
        .order_by(Appointment.appointment_time).all()
    )
    upcoming_appts = (
        Appointment.query.filter(Appointment.appointment_date > date.today())
        .filter_by(status="confirmed")
        .order_by(Appointment.appointment_date, Appointment.appointment_time).all()
    )
    total_clients = User.query.count()
    total_revenue = (
        db.session.query(db.func.sum(Appointment.price))
        .filter(Appointment.status != "cancelled").scalar() or 0
    )
    blocked_slots = (
        BlockedSlot.query.filter(BlockedSlot.block_date >= date.today())
        .order_by(BlockedSlot.block_date, BlockedSlot.start_time).all()
    )
    avg_rating = (
        db.session.query(db.func.avg(Appointment.review_rating))
        .filter(Appointment.review_rating.isnot(None)).scalar()
    )

    return render_template(
        "admin_dashboard.html",
        settings=settings, today_appts=today_appts,
        upcoming_appts=upcoming_appts, total_clients=total_clients,
        total_revenue=total_revenue, blocked_slots=blocked_slots,
        avg_rating=round(avg_rating, 1) if avg_rating else "N/A",
    )


@app.route("/admin/toggle-availability", methods=["POST"])
@admin_required
def toggle_availability():
    settings = get_admin_settings()
    settings.is_available = not settings.is_available
    db.session.commit()
    flash(f"Barber is now {'available' if settings.is_available else 'unavailable'}.", "info")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/block-time", methods=["POST"])
@admin_required
def block_time():
    block_date = datetime.strptime(request.form["block_date"], "%Y-%m-%d").date()
    start_time = datetime.strptime(request.form["start_time"], "%H:%M").time()
    end_time = datetime.strptime(request.form["end_time"], "%H:%M").time()
    reason = request.form.get("reason", "").strip()
    if end_time <= start_time:
        flash("End time must be after start time.", "danger")
        return redirect(url_for("admin_dashboard"))
    if block_date < date.today():
        flash("Cannot block past dates.", "danger")
        return redirect(url_for("admin_dashboard"))
    db.session.add(BlockedSlot(
        block_date=block_date, start_time=start_time,
        end_time=end_time, reason=reason,
    ))
    db.session.commit()
    flash(f"Blocked {start_time.strftime('%H:%M')}–{end_time.strftime('%H:%M')} on {block_date.strftime('%d %B %Y')}.", "success")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/unblock/<int:block_id>", methods=["POST"])
@admin_required
def unblock_time(block_id):
    block = BlockedSlot.query.get_or_404(block_id)
    db.session.delete(block)
    db.session.commit()
    flash("Time block removed.", "info")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/complete/<int:appt_id>", methods=["POST"])
@admin_required
def complete_appointment(appt_id):
    appt = Appointment.query.get_or_404(appt_id)
    appt.status = "completed"
    appt.payment_status = "paid"
    db.session.commit()
    user = User.query.get(appt.user_id)
    send_review_email(user, appt)
    flash("Appointment completed. Review request sent.", "success")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/logout")
def admin_logout():
    session.pop("is_admin", None)
    flash("Admin logged out.", "info")
    return redirect(url_for("index"))


# ===================================================================
# Context processor & init
# ===================================================================
@app.context_processor
def inject_globals():
    return {
        "now": datetime.utcnow(),
        "contact_phone": CONTACT_PHONE,
        "contact_email": CONTACT_EMAIL,
    }


# --- Test email route — raw SMTP debug (bypasses Flask-Mail) ---
@app.route("/test-email")
def test_email():
    """Step-by-step SMTP debug. Visit /test-email"""
    import smtplib
    from email.mime.text import MIMEText

    username = app.config.get("MAIL_USERNAME", "")
    password = app.config.get("MAIL_PASSWORD", "")
    server_host = app.config.get("MAIL_SERVER", "smtp.gmail.com")
    port = app.config.get("MAIL_PORT", 587)
    to_addr = request.args.get("to", username)

    steps = []

    if not username or not password:
        return (
            "<h2 style='color:red;'>Email NOT configured</h2>"
            f"<p>MAIL_USERNAME: <b>{username or '(empty)'}</b></p>"
            f"<p>MAIL_PASSWORD: <b>{'(empty)' if not password else '***set***'}</b></p>"
            "<p>Set your App Password in app.py line 45 or via env var.</p>"
        )

    # Step 1: Connect
    try:
        smtp = smtplib.SMTP(server_host, port, timeout=10)
        steps.append(("✅", f"Connected to {server_host}:{port}"))
    except Exception as e:
        steps.append(("❌", f"Connection FAILED: {e}"))
        return _render_email_debug(steps, username, password)

    # Step 2: STARTTLS
    try:
        smtp.starttls()
        steps.append(("✅", "STARTTLS encryption established"))
    except Exception as e:
        steps.append(("❌", f"STARTTLS FAILED: {e}"))
        smtp.quit()
        return _render_email_debug(steps, username, password)

    # Step 3: Login
    try:
        smtp.login(username, password)
        steps.append(("✅", f"Logged in as {username}"))
    except smtplib.SMTPAuthenticationError as e:
        steps.append(("❌", f"LOGIN FAILED — Wrong password or App Password needed: {e}"))
        smtp.quit()
        return _render_email_debug(steps, username, password)
    except Exception as e:
        steps.append(("❌", f"LOGIN FAILED: {e}"))
        smtp.quit()
        return _render_email_debug(steps, username, password)

    # Step 4: Send
    try:
        msg = MIMEText("<h1 style='color:#c9a84c;'>✂ Aura Studio.co</h1>"
                       "<p>Email is working!</p>", "html", _charset="utf-8")
        msg["Subject"] = "Aura Studio.co — Test Email"
        msg["From"] = f"Aura Studio.co <{username}>"
        msg["To"] = to_addr
        smtp.send_message(msg)
        steps.append(("✅", f"Email SENT to {to_addr}"))
    except Exception as e:
        steps.append(("❌", f"SEND FAILED: {e}"))
    finally:
        smtp.quit()

    return _render_email_debug(steps, username, password)


def _render_email_debug(steps, username, password):
    html = "<div style='font-family:Arial;max-width:600px;margin:2rem auto;padding:1rem;'>"
    html += "<h2>✂ Aura Studio.co — Email Debug</h2>"
    for icon, text in steps:
        color = "green" if "✅" in icon else "red"
        html += f"<p style='color:{color};font-size:1.1rem;'>{icon} {text}</p>"
    html += "<hr>"
    html += f"<p><b>Username:</b> {username}</p>"
    html += f"<p><b>Password:</b> {'***' + password[-4:] if len(password) > 4 else '***set***'}</p>"
    html += "<h3>If login failed:</h3><ol>"
    html += "<li>Go to <a href='https://myaccount.google.com/security'>Google Account Security</a></li>"
    html += "<li>Make sure <b>2-Step Verification is ON</b></li>"
    html += "<li>Go to <a href='https://myaccount.google.com/apppasswords'>App Passwords</a></li>"
    html += "<li>Create a new app password (select 'Mail' + 'Windows Computer')</li>"
    html += "<li>Copy the <b>16-character password</b> (no spaces) into app.py line 45</li>"
    html += "<li>Restart the app and try again</li></ol>"
    html += f"<p><a href='/'>Back to site</a></p></div>"
    return html


def _migrate_db():
    """Add any columns that exist in the model but not yet in the DB."""
    from sqlalchemy import text
    with db.engine.connect() as conn:
        result = conn.execute(text("PRAGMA table_info(users)"))
        existing = {row[1] for row in result}
        migrations = [
            ("is_verified", "BOOLEAN NOT NULL DEFAULT 0"),
            ("is_admin",    "BOOLEAN NOT NULL DEFAULT 0"),
        ]
        for col, definition in migrations:
            if col not in existing:
                conn.execute(text(f"ALTER TABLE users ADD COLUMN {col} {definition}"))
                print(f"✓ DB migration: added column users.{col}")
        conn.commit()


with app.app_context():
    db.create_all()
    _migrate_db()

if __name__ == "__main__":
    # Startup diagnostic
    print("\n" + "=" * 50)
    print("✂  Aura Studio.co")
    print("=" * 50)
    if check_mail_configured():
        print(f"📧 Email: CONFIGURED ({app.config['MAIL_USERNAME']})")
        print(f"   Server: {app.config['MAIL_SERVER']}:{app.config['MAIL_PORT']}")
        print(f"   Sender: {app.config['MAIL_DEFAULT_SENDER']}")
    else:
        print("⚠  Email: NOT CONFIGURED")
        print("   Set MAIL_USERNAME and MAIL_PASSWORD env vars.")
        print("   Visit /test-email after starting to diagnose.")
    pf_live = not PAYFAST_SANDBOX
    print(f"💳 PayFast: {'LIVE' if pf_live else 'SANDBOX (test mode)'}")
    print(f"📞 Contact: {CONTACT_PHONE}")
    print(f"✉  Contact: {CONTACT_EMAIL}")
    print(f"🔗 Open: http://127.0.0.1:5000")
    print(f"🔗 Test email: http://127.0.0.1:5000/test-email")
    print("=" * 50 + "\n")
    app.run(debug=True, port=5000)
