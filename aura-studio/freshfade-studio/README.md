# ✂ Aura Studio.co — Hair Salon Web App

> **"It's nicer when you get out."**

Full-stack hair salon booking app built with Flask, SQLite, and HTML/CSS/JS.

---

## Features

### Client
- **Register** with email verification (must verify before booking)
- **Strong password** enforcement + one-click "Suggest" generator
- **Forgot password** — reset link sent to email (1-hour expiry)
- **Services page** — 29 hairstyles, each with "Book This Style" button (redirects to login if not signed in)
- **Booking** — interactive calendar, 45-min time slots, blocked-slot detection
- **Payment** — PayFast (Card, EFT, Capitec Pay, SnapScan, Zapper) or Cash on arrival
- **Dashboard** — upcoming/past appointments, cancel bookings, view ratings

### Admin (`/admin/login`)
- **Availability toggle** — shown on homepage to clients
- **Block time slots** — mark specific hours unavailable on any date
- **Mark appointment complete** → triggers review email to client (rate 1–10)
- **Stats** — bookings, clients, revenue, average rating

### Payment Flow
- **PayFast**: Creates appointment → redirects to PayFast hosted page → PayFast handles Card/EFT/Capitec Pay/SnapScan/Zapper → ITN callback confirms payment → confirmation email sent
- **Cash**: Booking confirmed immediately, pay on arrival

---

## Tech Stack

| Layer    | Tech                |
|----------|---------------------|
| Backend  | Flask (Python)      |
| Frontend | HTML / CSS / JS     |
| Database | SQLite (`csas.db`)  |
| Email    | Flask-Mail (SMTP)   |
| Payments | PayFast API         |

---

## Setup (VS Code)

### 1. Open project & create virtual environment
```bash
code aurastudio-studio

# Windows
python -m venv venv
venv\Scripts\activate

# Mac/Linux
python3 -m venv venv
source venv/bin/activate
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure environment variables

**Email (required for verification, reset, booking confirmation):**
```bash
# Windows PowerShell
$env:MAIL_SERVER="smtp.gmail.com"
$env:MAIL_PORT="587"
$env:MAIL_USERNAME="your-email@gmail.com"
$env:MAIL_PASSWORD="your-app-password"
$env:MAIL_DEFAULT_SENDER="your-email@gmail.com"

# Mac/Linux
export MAIL_SERVER="smtp.gmail.com"
export MAIL_PORT="587"
export MAIL_USERNAME="your-email@gmail.com"
export MAIL_PASSWORD="your-app-password"
export MAIL_DEFAULT_SENDER="your-email@gmail.com"
```
> Gmail: Generate an App Password at https://myaccount.google.com/apppasswords

**PayFast (for online payments):**
```bash
# Sandbox defaults are pre-filled for testing.
# For LIVE payments, set these:
$env:PAYFAST_MERCHANT_ID="your_merchant_id"
$env:PAYFAST_MERCHANT_KEY="your_merchant_key"
$env:PAYFAST_PASSPHRASE="your_passphrase"
$env:PAYFAST_SANDBOX="false"
```
> Sign up at https://www.payfast.co.za
> Link your Capitec account (2208645495) in the PayFast merchant dashboard under Payout Settings.

### 4. Run
```bash
python app.py
```
Open: **http://127.0.0.1:5000**

---

## Admin Credentials

| Field    | Value           |
|----------|-----------------|
| Username | `admin`         |
| Password | `aurastudio2024` |

Admin panel: **http://127.0.0.1:5000/admin/login**

---

## Contact (configured in app)

| Channel | Detail                  |
|---------|-------------------------|
| Phone   | +27 79 909 7678         |
| Email   | aurastudio.co6@gmail.com |

---

## Project Structure

```
aurastudio-studio/
├── app.py                      # Flask app (routes, models, PayFast integration)
├── requirements.txt
├── static/
│   ├── css/style.css           # Dark luxury barbershop theme
│   └── js/main.js              # Calendar, slots, UI
└── templates/
    ├── base.html               # Navbar, footer, flash messages
    ├── index.html              # Homepage (hero, status, info)
    ├── services.html           # All hairstyles + book buttons
    ├── about.html              # About page
    ├── contact.html            # Contact page
    ├── register.html           # Sign up (strong password + suggest)
    ├── login.html              # Login (forgot password link)
    ├── forgot_password.html    # Request reset link
    ├── reset_password.html     # Set new password
    ├── unverified.html         # Email verification holding page
    ├── dashboard.html          # Client dashboard
    ├── book.html               # Booking (calendar + PayFast/Cash)
    ├── payment_redirect.html   # Auto-redirect to PayFast
    ├── payment_success.html    # Payment confirmation
    ├── review.html             # Rate 1-10
    ├── admin_login.html
    ├── admin_dashboard.html    # Toggle, block time, stats
    ├── email_verify.html       # Verification email
    ├── email_reset.html        # Password reset email
    ├── email_confirmation.html # Booking confirmation email
    └── email_review.html       # Review request email
```

---

## Notes

- Delete `instance/csas.db` if upgrading from an earlier version (schema changed)
- PayFast sandbox credentials are pre-filled for testing — switch to live when ready
- Password must be 8+ chars with uppercase, lowercase, digit, and special character
- Email verification link expires in 24 hours; password reset link expires in 1 hour
