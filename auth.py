import json
import os
import hashlib
import secrets
import re
from datetime import datetime, timedelta

USERS_FILE = "users.json"

# ─── FILELOCK SETUP ───────────────────────────────────────────
# Lock file path is resolved to absolute at import time —
# stays consistent regardless of Streamlit launch directory.
_LOCK_PATH = os.path.abspath(USERS_FILE) + ".lock"
try:
    from filelock import FileLock as _FileLock, Timeout as _LockTimeout
    _LOCK = _FileLock(_LOCK_PATH, timeout=10)   # wait up to 10 s before raising
except ImportError:
    _LOCK        = None
    _LockTimeout = Exception   # fallback so except clauses still compile

# ─── ADMIN ACCOUNTS ───────────────────────────────────────────
ADMIN_EMAILS = {
    "muhammadsaadpopat76@gmail.com",
    "muhammadsaadayub.bmj@gmail.com",
}

# ─── SUBSCRIPTION PLANS ───────────────────────────────────────
PLANS = {
    "free_trial": {
        "name":           "Free Trial",
        "price_monthly":  0,
        "price_yearly":   0,
        "duration_days":  7,
        "generate_limit": 10,
        "shopify_limit":  5,
        "bulk_limit":     0,
        "description":    "7-day free trial — 10 generations/day",
    },
    "starter": {
        "name":           "Starter",
        "price_monthly":  9.99,
        "price_yearly":   89.99,
        "duration_days":  None,
        "generate_limit": 50,
        "shopify_limit":  20,
        "bulk_limit":     5,
        "description":    "50 generations/day, 20 Shopify listings/day",
    },
    "pro": {
        "name":           "Pro",
        "price_monthly":  24.99,
        "price_yearly":   199.99,
        "duration_days":  None,
        "generate_limit": 200,
        "shopify_limit":  100,
        "bulk_limit":     25,
        "description":    "200 generations/day, 100 Shopify listings/day",
    },
    "ultra_promax": {
        "name":           "Ultra ProMax",
        "price_monthly":  59.99,
        "price_yearly":   499.99,
        "duration_days":  None,
        "generate_limit": 9999,
        "shopify_limit":  9999,
        "bulk_limit":     9999,
        "description":    "Unlimited everything — priority support",
    },
}


# ─── INTERNALS ────────────────────────────────────────────────
def _hash_password(password: str, salt: str) -> str:
    return hashlib.sha256((salt + password).encode()).hexdigest()

def _validate_email(email: str) -> tuple[bool, str]:
    pattern = r"^[\w\.\+\-]+@[\w\-]+\.[a-zA-Z]{2,}$"
    if not re.match(pattern, email):
        return False, "Invalid email address."
    return True, ""

def _validate_password(password: str) -> tuple[bool, str]:
    if len(password) < 6:
        return False, "Password must be at least 6 characters."
    if len(password) > 128:
        return False, "Password too long (max 128 chars)."
    return True, ""

def _memory_filename(email: str) -> str:
    return f"memory_{email.replace('@', '_at_').replace('.', '_')}.json"


# ─── PERSISTENCE ──────────────────────────────────────────────
def _read_users_file() -> dict:
    """Raw read — caller must hold the lock."""
    path = os.path.abspath(USERS_FILE)
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def _write_users_file(users: dict) -> None:
    """Atomic write via temp file — caller must hold the lock."""
    path = os.path.abspath(USERS_FILE)
    tmp  = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(users, f, indent=2)
    os.replace(tmp, path)


def load_users() -> dict:
    """Thread-safe read."""
    if _LOCK:
        try:
            with _LOCK:
                return _read_users_file()
        except _LockTimeout:
            return _read_users_file()   # fallback — read without lock
    return _read_users_file()


def save_users(users: dict) -> None:
    """Thread-safe atomic write."""
    if _LOCK:
        try:
            with _LOCK:
                _write_users_file(users)
        except _LockTimeout:
            _write_users_file(users)    # fallback — write without lock
    else:
        _write_users_file(users)


# ─── SUBSCRIPTION HELPERS ─────────────────────────────────────
def _default_subscription(email: str) -> dict:
    if email in ADMIN_EMAILS:
        return {
            "plan":           "ultra_promax",
            "billing":        "admin",
            "status":         "active",
            "started_at":     datetime.now().isoformat(),
            "expires_at":     None,
            "payment_ref":    "ADMIN",
            "usage_date":     "",
            "usage_generate": 0,
            "usage_shopify":  0,
        }
    return {
        "plan":           "free_trial",
        "billing":        "trial",
        "status":         "active",
        "started_at":     datetime.now().isoformat(),
        "expires_at":     (datetime.now() + timedelta(days=7)).isoformat(),
        "payment_ref":    "",
        "usage_date":     "",
        "usage_generate": 0,
        "usage_shopify":  0,
    }


def get_subscription(email: str) -> dict:
    users = load_users()
    email = email.strip().lower()
    if email not in users:
        return {}
    return users[email].get("subscription", _default_subscription(email))


def is_subscription_active(email: str) -> tuple[bool, str]:
    email = email.strip().lower()
    if email in ADMIN_EMAILS:
        return True, "admin"
    sub = get_subscription(email)
    if not sub:
        return False, "No subscription found."
    if sub.get("status") != "active":
        return False, "Subscription is not active."
    expires = sub.get("expires_at")
    if expires:
        try:
            if datetime.fromisoformat(expires) < datetime.now():
                return False, "Your free trial has expired. Please upgrade to continue — contact us on WhatsApp or email."
        except Exception:
            pass
    return True, "active"


def check_usage_limit(email: str, action: str) -> tuple[bool, str]:
    email = email.strip().lower()
    if email in ADMIN_EMAILS:
        return True, ""
    active, reason = is_subscription_active(email)
    if not active:
        return False, reason
    users = load_users()
    sub   = users[email].get("subscription", _default_subscription(email))
    plan  = PLANS.get(sub.get("plan", "free_trial"), PLANS["free_trial"])
    today = datetime.now().strftime("%Y-%m-%d")
    if sub.get("usage_date") != today:
        sub["usage_date"]     = today
        sub["usage_generate"] = 0
        sub["usage_shopify"]  = 0
    current = sub.get(f"usage_{action}", 0)
    limit   = plan.get(f"{action}_limit", 0)
    if current >= limit:
        return False, (
            f"Daily limit reached ({limit} {action}s/day on **{plan['name']}** plan). "
            "Please upgrade your plan."
        )
    return True, ""


def increment_usage(email: str, action: str) -> None:
    email = email.strip().lower()
    if email in ADMIN_EMAILS:
        return
    users = load_users()
    if email not in users:
        return
    sub   = users[email].get("subscription", _default_subscription(email))
    today = datetime.now().strftime("%Y-%m-%d")
    if sub.get("usage_date") != today:
        sub["usage_date"]     = today
        sub["usage_generate"] = 0
        sub["usage_shopify"]  = 0
    sub[f"usage_{action}"] = sub.get(f"usage_{action}", 0) + 1
    users[email]["subscription"] = sub
    save_users(users)


def activate_subscription(email: str, plan: str, billing: str,
                           payment_ref: str = "") -> tuple[bool, str]:
    email = email.strip().lower()
    users = load_users()
    if email not in users:
        return False, "Account not found."
    if plan not in PLANS:
        return False, f"Unknown plan: {plan}"
    if billing == "yearly":
        expires = (datetime.now() + timedelta(days=365)).isoformat()
    elif billing == "monthly":
        expires = (datetime.now() + timedelta(days=30)).isoformat()
    else:
        expires = None
    users[email]["subscription"] = {
        "plan":           plan,
        "billing":        billing,
        "status":         "active",
        "started_at":     datetime.now().isoformat(),
        "expires_at":     expires,
        "payment_ref":    payment_ref,
        "usage_date":     "",
        "usage_generate": 0,
        "usage_shopify":  0,
    }
    save_users(users)
    return True, f"Subscription activated: {plan} ({billing})"


def cancel_subscription(email: str) -> tuple[bool, str]:
    email = email.strip().lower()
    users = load_users()
    if email not in users:
        return False, "Account not found."
    sub = users[email].get("subscription", {})
    sub["status"] = "cancelled"
    users[email]["subscription"] = sub
    save_users(users)
    return True, "Subscription cancelled."


def is_admin(email: str) -> bool:
    return email.strip().lower() in ADMIN_EMAILS


# ─── PUBLIC API ───────────────────────────────────────────────
def register_user(email: str, password: str, display_name: str = "") -> tuple[bool, str]:
    email = email.strip().lower()
    ok, msg = _validate_email(email)
    if not ok:
        return False, msg
    ok, msg = _validate_password(password)
    if not ok:
        return False, msg
    users = load_users()
    if email in users:
        return False, "An account with this email already exists."
    salt   = secrets.token_hex(16)
    hashed = _hash_password(password, salt)
    users[email] = {
        "salt":                  salt,
        "password":              hashed,
        "display_name":          display_name.strip() or email.split("@")[0],
        "created":               datetime.now().strftime("%d %b %Y %I:%M %p"),
        "memory_file":           _memory_filename(email),
        "shopify_store":         "",
        "shopify_client_id":     "",
        "shopify_client_secret": "",
        "subscription":          _default_subscription(email),
    }
    save_users(users)
    return True, "Account created successfully!"


def login_user(email: str, password: str) -> tuple[bool, str, dict]:
    email = email.strip().lower()
    users = load_users()
    if email not in users:
        return False, "No account found with this email.", {}
    user   = users[email]
    hashed = _hash_password(password, user["salt"])
    if hashed != user["password"]:
        return False, "Incorrect password.", {}
    if "subscription" not in user:
        user["subscription"] = _default_subscription(email)
        users[email]         = user
        save_users(users)
    safe = {k: v for k, v in user.items() if k not in ("salt", "password")}
    safe["email"] = email
    return True, "Login successful!", safe


def update_profile(email: str, display_name: str = None,
                   shopify_store: str = None,
                   shopify_client_id: str = None,
                   shopify_client_secret: str = None) -> tuple[bool, str]:
    email = email.strip().lower()
    users = load_users()
    if email not in users:
        return False, "Account not found."
    if display_name          is not None:
        users[email]["display_name"]          = display_name.strip()
    if shopify_store         is not None:
        users[email]["shopify_store"]         = shopify_store.strip().lower()
    if shopify_client_id     is not None:
        users[email]["shopify_client_id"]     = shopify_client_id.strip()
    if shopify_client_secret is not None:
        users[email]["shopify_client_secret"] = shopify_client_secret.strip()
    save_users(users)
    return True, "Profile updated."


def get_user_info(email: str) -> dict | None:
    email = email.strip().lower()
    users = load_users()
    if email not in users:
        return None
    user = users[email]
    safe = {k: v for k, v in user.items() if k not in ("salt", "password")}
    safe["email"] = email
    return safe


def get_memory_file(user: dict) -> str:
    return user.get("memory_file", "memory.json")


def change_password(email: str, old_password: str, new_password: str) -> tuple[bool, str]:
    email = email.strip().lower()
    users = load_users()
    if email not in users:
        return False, "Account not found."
    user   = users[email]
    hashed = _hash_password(old_password, user["salt"])
    if hashed != user["password"]:
        return False, "Current password is incorrect."
    ok, msg = _validate_password(new_password)
    if not ok:
        return False, msg
    new_salt             = secrets.token_hex(16)
    users[email]["salt"]     = new_salt
    users[email]["password"] = _hash_password(new_password, new_salt)
    save_users(users)
    return True, "Password changed successfully!"


def delete_account(email: str, password: str) -> tuple[bool, str]:
    email = email.strip().lower()
    users = load_users()
    if email not in users:
        return False, "Account not found."
    hashed = _hash_password(password, users[email]["salt"])
    if hashed != users[email]["password"]:
        return False, "Incorrect password."
    mem = users[email].get("memory_file", "")
    if mem and os.path.exists(mem):
        try:
            os.remove(mem)
        except OSError:
            pass
    del users[email]
    save_users(users)
    return True, "Account deleted."

# ─── FORGOT PASSWORD (token-based reset) ──────────────────────
_RESET_TOKENS: dict = {}   # in-memory store: {token: {email, expires}}

def generate_reset_token(email: str) -> tuple[bool, str]:
    email = email.strip().lower()
    users = load_users()
    if email not in users:
        return False, "No account found with this email."
    code    = str(secrets.randbelow(900000) + 100000)
    expires = datetime.now() + timedelta(minutes=15)
    _RESET_TOKENS[email] = {"code": code, "expires": expires}
    return True, code


def verify_reset_token(email: str, code: str) -> tuple[bool, str]:
    email = email.strip().lower()
    entry = _RESET_TOKENS.get(email)
    if not entry:
        return False, "No reset request found. Please start over."
    if datetime.now() > entry["expires"]:
        _RESET_TOKENS.pop(email, None)
        return False, "Code has expired. Please request a new one."
    if entry["code"] != code.strip():
        return False, "Incorrect code."
    return True, ""


def reset_password_with_token(email: str, code: str,
                               new_password: str) -> tuple[bool, str]:
    email = email.strip().lower()
    ok, msg = verify_reset_token(email, code)
    if not ok:
        return False, msg
    ok, msg = _validate_password(new_password)
    if not ok:
        return False, msg
    users = load_users()
    if email not in users:
        return False, "Account not found."
    new_salt                 = secrets.token_hex(16)
    users[email]["salt"]     = new_salt
    users[email]["password"] = _hash_password(new_password, new_salt)
    save_users(users)
    _RESET_TOKENS.pop(email, None)
    return True, "Password reset successfully! Please login."