# 🏷️ listing.ai

AI-powered e-commerce copy and Shopify listing tool built with Streamlit + Groq.

## Features

- **AI Copy Generation** — Title, description, 3 ad variations per product
- **Image Analysis** — Upload a product photo; AI fills in the details
- **Shopify Integration** — Push listings directly to your Shopify store
- **SEO Tags** — Auto-generated search tags for each product
- **PDF Export** — Download your copy as a formatted PDF
- **History** — All generations saved per user
- **Subscription System** — Free trial → Starter / Pro / Ultra ProMax

## Quick Start

```bash
# Install dependencies
pip install groq python-dotenv streamlit requests Pillow reportlab filelock

# Add your Groq API key to .env
GROQ_API_KEY=your_key_here

# Run
streamlit run app.py
```

Or on Windows, double-click `run.bat`.

## Setup Checklist Before Launch

- [ ] Add your real `GROQ_API_KEY` in `.env`
- [ ] Update `PAYPAL_ME_LINK` in `payments.py`
- [ ] Update `BANK_ACCOUNT` details in `payments.py`
- [ ] Update `CONTACT_WHATSAPP` in `payments.py`
- [ ] Update admin emails in `auth.py` → `ADMIN_EMAILS`

## Subscription Plans

| Plan | Price | Generations/day | Shopify/day |
|------|-------|----------------|-------------|
| Free Trial | Free (7 days) | 10 | 5 |
| Starter | $9.99/mo | 50 | 20 |
| Pro | $24.99/mo | 200 | 100 |
| Ultra ProMax | $59.99/mo | Unlimited | Unlimited |

## Tech Stack

- **Frontend:** Streamlit
- **AI:** Groq (llama-3.3-70b + llama-4-scout vision)
- **Shopify:** Admin REST API 2024-10
- **Auth:** Custom (SHA-256 + salt, JSON persistence)
- **PDF:** ReportLab