"""
payments.py — Payment configuration and email notification helpers
All payment info is defined here. Import into app.py only for the Subscription page.
"""

# ─── YOUR PAYMENT DETAILS ─────────────────────────────────────
PAYPAL_ME_LINK  = "https://paypal.me/YourPayPalUsername"   # ← REQUIRED: update before launch
BANK_ACCOUNT    = {
    "bank_name":      "MCB / HBL",                         # ← update
    "account_title":  "Muhammad Saad Popat",
    "account_number": "XXXX-XXXX-XXXX",                    # ← REQUIRED: update before launch
    "iban":           "PK00XXXX0000000000000000",           # ← REQUIRED: update before launch
}
CONTACT_EMAIL   = "muhammadsaadpopat76@gmail.com"
CONTACT_WHATSAPP = "+92-300-0000000"                       # ← REQUIRED: update before launch

# ─── PLAN DISPLAY CONFIG ──────────────────────────────────────
PLAN_FEATURES = {
    "free_trial": [
        "10 AI generations per day",
        "5 Shopify listings per day",
        "PDF export",
        "7 days only",
    ],
    "starter": [
        "50 AI generations per day",
        "20 Shopify listings per day",
        "PDF export",
        "History & bulk tools",
        "Email support",
    ],
    "pro": [
        "200 AI generations per day",
        "100 Shopify listings per day",
        "Everything in Starter",
        "25 bulk listings/day",
        "Priority support",
    ],
    "ultra_promax": [
        "Unlimited AI generations",
        "Unlimited Shopify listings",
        "Everything in Pro",
        "Unlimited bulk listings",
        "Dedicated support",
        "Early access to new features",
    ],
}


def build_payment_email(user_email: str, plan: str, billing: str,
                        method: str, reference: str) -> str:
    """
    Build a mailto: URL that opens the user's email client
    with a pre-filled payment request to the owner.
    """
    import urllib.parse
    subject = f"listing.ai — Payment Request: {plan.replace('_',' ').title()} ({billing})"
    body = f"""Hi,

I have made a payment for listing.ai and would like my subscription activated.

--- PAYMENT DETAILS ---
User Email   : {user_email}
Plan         : {plan.replace('_',' ').title()}
Billing      : {billing.capitalize()}
Payment Method: {method}
Reference / TxID: {reference}

Please activate my subscription.

Thank you."""
    encoded = urllib.parse.quote(body)
    return f"mailto:{CONTACT_EMAIL}?subject={urllib.parse.quote(subject)}&body={encoded}"


def get_paypal_link(plan: str, billing: str) -> str:
    """Return a PayPal.Me link. Amount note is appended."""
    note = f"listing.ai {plan.replace('_',' ').title()} {billing}"
    import urllib.parse
    return f"{PAYPAL_ME_LINK}?country.x=PK&locale.x=en_US"