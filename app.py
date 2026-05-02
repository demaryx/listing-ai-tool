import streamlit as st
from agent import analyze_image, generate_product_copy, list_on_shopify, generate_seo_tags
from auth import (
    register_user, login_user, get_memory_file, update_profile, get_user_info,
    is_admin, get_subscription, is_subscription_active, check_usage_limit,
    increment_usage, activate_subscription, cancel_subscription, PLANS, load_users,
    generate_reset_token, verify_reset_token, reset_password_with_token,
    change_password,
)
from payments import (
    PAYPAL_ME_LINK, BANK_ACCOUNT, CONTACT_EMAIL, CONTACT_WHATSAPP,
    PLAN_FEATURES, build_payment_email, get_paypal_link,
)
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image as RLImage
from reportlab.lib.units import cm
import tempfile
import os
import json
import base64
import random
from datetime import datetime
from io import BytesIO
from PIL import Image as PILImage
import requests
from concurrent.futures import ThreadPoolExecutor

# ─── PAGE CONFIG ──────────────────────────────────────────────
st.set_page_config(page_title="listing.ai — AI E-commerce Copy Tool", page_icon="🏷️", layout="wide")

# ─── GLOBAL CSS ───────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');
html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
.stApp { background: #ffffff; color: #111111; }
section[data-testid="stSidebar"] { background: #f9f9f9; }
.shopify-preview {
    background: #fafafa; border: 1.5px solid #e0e0e0;
    border-radius: 12px; padding: 24px; color: #111;
}
.shopify-preview h3 { color: #111; font-size: 20px; margin: 0 0 10px; }
.shopify-preview p  { color: #444; font-size: 14px; line-height: 1.7; }
.shopify-price { font-size: 26px; font-weight: 800; color: #111; }
.tag-pill {
    display: inline-block; background: #f0f0f0; color: #333;
    padding: 3px 10px; border-radius: 20px; font-size: 12px; margin: 2px;
}
.login-logo { text-align: center; padding: 48px 0 24px; }
.recaptcha-box {
    background: #f9f9f9; border: 1.5px solid #d0d0d0;
    border-radius: 8px; padding: 14px 18px; margin: 10px 0;
}
.stButton > button[kind="primary"] {
    background: #111111 !important; color: #ffffff !important;
    border: none !important; border-radius: 8px !important; font-weight: 600 !important;
}
.stButton > button[kind="primary"]:hover { background: #D97757 !important; }
.plan-card {
    border: 2px solid #e0e0e0; border-radius: 14px;
    padding: 22px 18px; text-align: center; background: #fafafa;
    transition: border-color 0.2s;
}
.plan-card.current { border-color: #111 !important; }
.plan-card h4 { margin: 0 0 6px; font-size: 18px; }
.plan-card .price { font-size: 28px; font-weight: 800; color: #111; }
.plan-card .desc  { color: #666; font-size: 13px; margin-top: 6px; }
.badge-admin { background:#111;color:#fff;padding:2px 10px;border-radius:20px;font-size:12px; }
.badge-active{ background:#22c55e;color:#fff;padding:2px 10px;border-radius:20px;font-size:12px; }
.badge-trial { background:#f59e0b;color:#fff;padding:2px 10px;border-radius:20px;font-size:12px; }
.badge-expired{ background:#ef4444;color:#fff;padding:2px 10px;border-radius:20px;font-size:12px; }
</style>
""", unsafe_allow_html=True)

# ─── CURRENCIES ───────────────────────────────────────────────
CURRENCIES = {
    "PKR (₨)": ("PKR", "₨"), "USD ($)": ("USD", "$"), "EUR (€)": ("EUR", "€"),
    "GBP (£)": ("GBP", "£"), "AED (د.إ)": ("AED", "د.إ"), "SAR (﷼)": ("SAR", "﷼"),
    "INR (₹)": ("INR", "₹"), "CAD (C$)": ("CAD", "C$"), "AUD (A$)": ("AUD", "A$"),
}

# ─── MEMORY ───────────────────────────────────────────────────
def load_memory(memory_file):
    if not os.path.exists(memory_file):
        return []
    with open(memory_file, "r") as f:
        return json.load(f)

def save_to_memory(memory_file, product_name, features, audience,
                   brand_name, platform, output, image_b64=None):
    memory = load_memory(memory_file)
    entry = {
        "date":         datetime.now().strftime("%d %b %Y - %I:%M %p"),
        "product_name": product_name,
        "brand_name":   brand_name,
        "features":     features,
        "audience":     audience,
        "platform":     platform,
        "output":       output,
    }
    if image_b64:
        entry["image_b64"] = image_b64
    memory.append(entry)
    if len(memory) > 500:          # cap at 500 entries to prevent file bloat
        memory = memory[-499:]
    with open(memory_file, "w") as f:
        json.dump(memory, f, indent=2)

# ─── PDF EXPORT ───────────────────────────────────────────────
def export_pdf(product_name, brand_name, platform, audience,
               features, benefits, output, image_bytes=None):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp_path = tmp.name
    doc = SimpleDocTemplate(tmp_path, pagesize=A4,
                            leftMargin=2*cm, rightMargin=2*cm,
                            topMargin=2*cm, bottomMargin=2*cm)
    styles = getSampleStyleSheet()
    story  = []
    h1 = styles["Heading1"]
    h1.fontSize = 20
    story.append(Paragraph(f"Product Copy: {product_name}", h1))
    story.append(Spacer(1, 0.4*cm))
    story.append(Paragraph(
        f"<b>Brand:</b> {brand_name} | <b>Platform:</b> {platform} | <b>Audience:</b> {audience}",
        styles["Normal"]))
    story.append(Spacer(1, 0.5*cm))
    if image_bytes:
        try:
            img     = PILImage.open(BytesIO(image_bytes)).convert("RGB")
            img_tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg")
            img_tmp_path = img_tmp.name
            img_tmp.close()
            img.save(img_tmp_path, "JPEG")
            story.append(RLImage(img_tmp_path, width=6*cm, height=6*cm))
            story.append(Spacer(1, 0.5*cm))
        except Exception:
            img_tmp_path = None
        finally:
            if 'img_tmp_path' in dir() and img_tmp_path and os.path.exists(img_tmp_path):
                try:
                    os.unlink(img_tmp_path)
                except OSError:
                    pass
    story.append(Paragraph("<b>Benefits:</b>", styles["Heading2"]))
    for line in benefits.split("\n"):
        if line.strip():
            story.append(Paragraph(line.strip(), styles["Normal"]))
    story.append(Spacer(1, 0.4*cm))
    story.append(Paragraph("<b>Generated Copy:</b>", styles["Heading2"]))
    for line in output.split("\n"):
        if line.strip():
            style = styles["Heading3"] if line.startswith("##") else styles["Normal"]
            story.append(Paragraph(line.replace("##", "").strip(), style))
    doc.build(story)
    with open(tmp_path, "rb") as f:
        pdf_bytes = f.read()
    os.unlink(tmp_path)
    return pdf_bytes

# ─── HELPERS ──────────────────────────────────────────────────
def _fetch_product_image(product_name: str) -> bytes | None:
    try:
        from urllib.parse import quote
        prompt  = f"professional product photography, {product_name}, white background, studio lighting, 4k"
        encoded = quote(prompt)
        url = (f"https://image.pollinations.ai/prompt/{encoded}"
               f"?width=600&height=600&seed={random.randint(1,999)}&nologo=true")
        r = requests.get(url, timeout=25)
        if r.status_code == 200 and len(r.content) > 1000:
            return r.content
    except Exception:
        pass
    return None

def _extract_description(output: str) -> str:
    if not output:
        return ""
    capturing, desc_lines = False, []
    for line in output.split("\n"):
        if "## PRODUCT DESCRIPTION" in line:
            capturing = True
            continue
        if capturing:
            if line.startswith("##"):
                break
            desc_lines.append(line)
    return " ".join(l.strip() for l in desc_lines if l.strip())

def _subscription_badge(sub: dict) -> str:
    plan  = sub.get("plan", "free_trial")
    billing = sub.get("billing", "")
    status  = sub.get("status", "")
    if billing == "admin":
        return '<span class="badge-admin">⭐ Admin</span>'
    if status != "active":
        return '<span class="badge-expired">Expired</span>'
    if plan == "free_trial":
        return '<span class="badge-trial">Free Trial</span>'
    return f'<span class="badge-active">{PLANS.get(plan,{}).get("name", plan)}</span>'

# ─── SESSION STATE ────────────────────────────────────────────
for key, default in [
    ("logged_in", False), ("user", {}),
    ("memory_file", "memory.json"), ("auth_mode", "login"),
    ("active_page", "Generate Copy"),
]:
    if key not in st.session_state:
        st.session_state[key] = default

# ─── AUTH ─────────────────────────────────────────────────────
def show_auth():
    col1, col2, col3 = st.columns([1, 1.2, 1])
    with col2:
        st.markdown('<div class="login-logo">', unsafe_allow_html=True)
        st.markdown("## 🏷️ listing.ai")
        st.markdown("*AI-powered e-commerce copy and Shopify listing tool*")
        st.markdown("</div>", unsafe_allow_html=True)

        mode = st.radio("", ["Login", "Register"], horizontal=True,
                        index=0 if st.session_state.auth_mode == "login" else 1,
                        label_visibility="collapsed")
        st.session_state.auth_mode = "login" if mode == "Login" else "register"

        # ── Forgot Password flow ───────────────────────────────
        if mode == "Login":
            if "forgot_step" not in st.session_state:
                st.session_state.forgot_step = 0   # 0=normal, 1=enter code, 2=new password

            if st.session_state.forgot_step == 1:
                st.info("A 6-digit reset code has been sent to your email. Enter it below.")
                fp_code = st.text_input("Reset Code", placeholder="123456", key="fp_code")
                fp_email_stored = st.session_state.get("fp_email", "")
                col_fp1, col_fp2 = st.columns(2)
                with col_fp1:
                    if st.button("Verify Code", type="primary", use_container_width=True):
                        ok, msg = verify_reset_token(fp_email_stored, fp_code)
                        if ok:
                            st.session_state.forgot_step = 2
                            st.rerun()
                        else:
                            st.error(msg)
                with col_fp2:
                    if st.button("Cancel", use_container_width=True):
                        st.session_state.forgot_step = 0
                        st.rerun()
                return

            if st.session_state.forgot_step == 2:
                st.info("Enter your new password.")
                fp_new  = st.text_input("New Password", type="password", key="fp_new")
                fp_new2 = st.text_input("Confirm Password", type="password", key="fp_new2")
                col_fp1, col_fp2 = st.columns(2)
                with col_fp1:
                    if st.button("Reset Password", type="primary", use_container_width=True):
                        if fp_new != fp_new2:
                            st.error("Passwords do not match.")
                        else:
                            fp_email_stored = st.session_state.get("fp_email", "")
                            fp_code_stored  = st.session_state.get("fp_code", "")
                            ok, msg = reset_password_with_token(fp_email_stored, fp_code_stored, fp_new)
                            if ok:
                                st.success(msg)
                                st.session_state.forgot_step = 0
                                st.rerun()
                            else:
                                st.error(msg)
                with col_fp2:
                    if st.button("Cancel", use_container_width=True):
                        st.session_state.forgot_step = 0
                        st.rerun()
                return

        email    = st.text_input("Email", placeholder="you@example.com")
        password = st.text_input("Password", type="password", placeholder="••••••••")

        if mode == "Register":
            confirm = st.text_input("Confirm Password", type="password", placeholder="••••••••")

        st.markdown('<div class="recaptcha-box">', unsafe_allow_html=True)
        recaptcha_ok = st.checkbox("I am not a robot", key=f"recaptcha_{mode}")
        st.markdown("</div>", unsafe_allow_html=True)

        if mode == "Register":
            if st.button("Create Account", type="primary", use_container_width=True):
                if not recaptcha_ok:
                    st.error("Please confirm you are not a robot.")
                elif not email or not password:
                    st.error("Please fill in all fields.")
                elif password != confirm:
                    st.error("Passwords do not match.")
                elif len(password) < 6:
                    st.error("Password must be at least 6 characters.")
                else:
                    ok, msg = register_user(email, password)
                    if ok:
                        st.success(msg + " Please login.")
                        st.session_state.auth_mode = "login"
                        st.rerun()
                    else:
                        st.error(msg)
        else:
            if st.button("Login", type="primary", use_container_width=True):
                if not recaptcha_ok:
                    st.error("Please confirm you are not a robot.")
                elif not email or not password:
                    st.error("Please fill in all fields.")
                else:
                    ok, msg, user = login_user(email, password)
                    if ok:
                        st.session_state.logged_in   = True
                        st.session_state.user        = user
                        st.session_state.memory_file = get_memory_file(user)
                        st.rerun()
                    else:
                        st.error(msg)

            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("Forgot Password?", use_container_width=True):
                if not email:
                    st.error("Enter your email address above first.")
                else:
                    ok, code = generate_reset_token(email)
                    if ok:
                        st.session_state.fp_email    = email
                        st.session_state.forgot_step = 1
                        # Security: code is stored server-side only.
                        # In production this is emailed. For now, check server logs.
                        import sys
                        print(f"[PASSWORD RESET] {email} → code: {code}", file=sys.stderr)
                        st.info("✅ A reset code has been sent to your email address. Please check your inbox (and spam folder).")
                        st.rerun()
                    else:
                        st.error(code)

# ─── MAIN APP ─────────────────────────────────────────────────
def show_app():
    memory_file = st.session_state.memory_file
    user        = st.session_state.user
    email       = user.get("email", "")
    admin       = is_admin(email)
    sub         = get_subscription(email)

    with st.sidebar:
        st.markdown("### 🏷️ listing.ai")
        st.markdown(f"**{user.get('display_name', '')}**")
        st.markdown(_subscription_badge(sub), unsafe_allow_html=True)
        st.markdown("---")
        pages = ["Generate Copy", "History", "List on Shopify", "Subscription", "Settings"]
        if admin:
            pages.append("Admin Panel")
        page = st.radio("Navigate", pages, label_visibility="collapsed",
                        index=pages.index(st.session_state.active_page)
                        if st.session_state.active_page in pages else 0)
        st.session_state.active_page = page
        st.markdown("---")
        if st.button("Logout", use_container_width=True):
            for k in ["logged_in","user","memory_file","last_copy","confirmed_tags"]:
                st.session_state.pop(k, None)
            st.rerun()

    # ══════════════════════════════════════════
    # PAGE: GENERATE COPY
    # ══════════════════════════════════════════
    if page == "Generate Copy":
        st.markdown("## Generate Product Copy")
        st.caption("Upload an image or fill in details — AI writes your Shopify listings.")

        # Subscription gate
        active, reason = is_subscription_active(email)
        if not active:
            st.error(f"🔒 {reason}")
            if st.button("View Plans", type="primary"):
                st.session_state.active_page = "Subscription"
                st.rerun()
            return

        uploaded_file = st.file_uploader(
            "Upload Product Image (optional)", type=["jpg","jpeg","png","webp"])
        image_bytes = uploaded_file.read() if uploaded_file else None

        analyzed = {}
        if image_bytes:
            col_img, col_info = st.columns([1, 2])
            with col_img:
                st.image(image_bytes, caption="Uploaded Image", use_column_width=True)
            with col_info:
                if st.button("Analyze Image", type="primary"):
                    with st.spinner("Analyzing image..."):
                        raw = analyze_image(image_bytes)
                    st.session_state["image_analysis"] = raw
                if "image_analysis" in st.session_state:
                    st.code(st.session_state["image_analysis"], language=None)
                    for line in st.session_state["image_analysis"].split("\n"):
                        if ":" in line:
                            k, _, v = line.partition(":")
                            analyzed[k.strip()] = v.strip()

        col1, col2 = st.columns(2)
        with col1:
            product_name = st.text_input("Product Name *", value=analyzed.get("PRODUCT_NAME",""))
            features     = st.text_area("Key Features *", value=analyzed.get("FEATURES",""),
                                        height=100, placeholder="e.g. waterproof, 30hr battery")
            audience     = st.text_input("Target Audience *", placeholder="e.g. gym-goers aged 20-35")
        with col2:
            brand_name   = st.text_input("Brand Name", placeholder="e.g. Nike, My Store")
            # Platform: Shopify only (fixed dropdown)
            platform     = st.selectbox("Platform", ["Shopify"])
            currency_key = st.selectbox("Currency", list(CURRENCIES.keys()))

        if st.button("Generate Copy", type="primary", use_container_width=True):
            if not product_name or not features or not audience:
                st.error("Please fill in Product Name, Features, and Target Audience.")
            else:
                allowed, limit_msg = check_usage_limit(email, "generate")
                if not allowed:
                    st.error(f"🔒 {limit_msg}")
                    st.session_state["goto_subscription"] = True
                else:
                    cat = analyzed.get("CATEGORY", "product")
                    with st.spinner("Generating copy, tags and image at the same time..."):
                        with ThreadPoolExecutor(max_workers=3) as executor:
                            f_copy = executor.submit(
                                generate_product_copy,
                                product_name, features, audience, brand_name, platform)
                            f_tags = executor.submit(
                                generate_seo_tags,
                                product_name, cat, features, platform)
                            f_img  = executor.submit(_fetch_product_image, product_name) \
                                     if not image_bytes else None

                        benefits, output = f_copy.result()
                        suggested_tags   = f_tags.result()
                        ai_image         = f_img.result() if f_img else None

                    increment_usage(email, "generate")
                    final_image = image_bytes or ai_image

                    st.session_state["last_copy"] = {
                        "product_name":   product_name,
                        "features":       features,
                        "audience":       audience,
                        "brand_name":     brand_name,
                        "platform":       platform,
                        "benefits":       benefits,
                        "output":         output,
                        "image_bytes":    final_image,
                        "currency_key":   currency_key,
                        "suggested_tags": suggested_tags,
                    }
                    st.session_state["confirmed_tags"] = ", ".join(suggested_tags)

                    img_b64 = base64.b64encode(final_image).decode() if final_image else None
                    save_to_memory(memory_file, product_name, features, audience,
                                   brand_name, platform, output, image_b64=img_b64)

        if st.session_state.pop("goto_subscription", False):
            st.session_state.active_page = "Subscription"
            st.rerun()

        if "last_copy" in st.session_state:
            c = st.session_state["last_copy"]
            st.markdown("---")

            st.markdown("### Benefits Identified")
            st.info(c["benefits"])

            st.markdown("### Generated Copy")
            st.markdown(c["output"])

            if c.get("image_bytes"):
                st.markdown("### Product Image")
                st.image(c["image_bytes"], width=280)

            st.markdown("---")

            col_a, col_b = st.columns(2)
            with col_a:
                pdf_bytes = export_pdf(
                    c["product_name"], c["brand_name"], c["platform"],
                    c["audience"], c["features"], c["benefits"],
                    c["output"], c.get("image_bytes")
                )
                st.download_button(
                    "Download PDF", data=pdf_bytes,
                    file_name=f"{c['product_name'].replace(' ','_')}_copy.pdf",
                    mime="application/pdf", use_container_width=True
                )
            with col_b:
                if st.button("Send to Shopify Tab", type="primary", use_container_width=True):
                    st.session_state.active_page = "List on Shopify"
                    st.rerun()

    # ══════════════════════════════════════════
    # PAGE: HISTORY
    # ══════════════════════════════════════════
    elif page == "History":
        st.markdown("## History")
        memory = load_memory(memory_file)
        if not memory:
            st.info("No history yet. Generate some copy first!")
        else:
            for i, entry in enumerate(reversed(memory)):
                label = (f"{entry.get('date','')}  —  "
                         f"**{entry.get('product_name','')}** ({entry.get('platform','')})")
                with st.expander(label):
                    col1, col2 = st.columns([2, 1])
                    with col1:
                        st.markdown(
                            f"**Brand:** {entry.get('brand_name','')} | "
                            f"**Audience:** {entry.get('audience','')}")
                        st.markdown(f"**Features:** {entry.get('features','')}")
                        st.markdown("---")
                        st.markdown(entry.get("output",""))

                        if st.button("Use in Shopify", key=f"use_{i}", type="primary"):
                            img_b = (base64.b64decode(entry["image_b64"])
                                     if entry.get("image_b64") else None)
                            st.session_state["last_copy"] = {
                                "product_name": entry.get("product_name",""),
                                "features":     entry.get("features",""),
                                "audience":     entry.get("audience",""),
                                "brand_name":   entry.get("brand_name",""),
                                "platform":     entry.get("platform",""),
                                "benefits":     "",
                                "output":       entry.get("output",""),
                                "image_bytes":  img_b,
                                "currency_key": "PKR (₨)",
                                "suggested_tags": [],
                            }
                            st.session_state["confirmed_tags"] = ""
                            st.session_state.active_page = "List on Shopify"
                            st.rerun()

                    with col2:
                        if entry.get("image_b64"):
                            st.image(base64.b64decode(entry["image_b64"]),
                                     use_column_width=True)

            st.markdown("---")
            if st.button("Clear All History", type="primary"):
                with open(memory_file, "w") as f:
                    json.dump([], f)
                st.success("History cleared.")
                st.rerun()

    # ══════════════════════════════════════════
    # PAGE: SHOPIFY
    # ══════════════════════════════════════════
    elif page == "List on Shopify":
        st.markdown("## List on Shopify")
        st.caption("Push a product directly to your Shopify store.")

        # Subscription gate
        active, reason = is_subscription_active(email)
        if not active:
            st.error(f"🔒 {reason}")
            if st.button("View Plans", type="primary"):
                st.session_state.active_page = "Subscription"
                st.rerun()
            return

        last      = st.session_state.get("last_copy", {})
        user_info = get_user_info(email) or {}

        # ── Credentials ───────────────────────────────────────
        st.markdown("### Store Credentials")
        st.caption("Saved to your account — fill once, reuse always.")
        c1, c2, c3 = st.columns(3)
        with c1:
            store_url = st.text_input("Store URL",
                value=user_info.get("shopify_store",""),
                placeholder="mystore.myshopify.com")
        with c2:
            client_id = st.text_input("Client ID",
                value=user_info.get("shopify_client_id",""),
                placeholder="Shopify App Client ID")
        with c3:
            # ← CHANGED: label is now "Client Secret" (was "Access Token")
            client_secret = st.text_input("Client Secret",
                value=user_info.get("shopify_client_secret",""),
                type="password", placeholder="shpss_xxxxxxxxxx")

        if st.button("Save Credentials"):
            update_profile(email,
                           shopify_store=store_url,
                           shopify_client_id=client_id,
                           shopify_client_secret=client_secret)
            st.success("Credentials saved!")

        st.markdown("---")

        # ── Product Details ───────────────────────────────────
        st.markdown("### Product Details")
        col1, col2 = st.columns(2)
        with col1:
            product_name = st.text_input("Product Name *", value=last.get("product_name",""))
            description  = st.text_area("Description *",
                value=_extract_description(last.get("output","")), height=120)
            vendor       = st.text_input("Vendor / Brand", value=last.get("brand_name",""))
            product_type = st.text_input("Product Type", placeholder="e.g. Electronics, Jewelry")
        with col2:
            cur_keys     = list(CURRENCIES.keys())
            def_cur      = last.get("currency_key","PKR (₨)")
            currency_key = st.selectbox("Currency", cur_keys,
                index=cur_keys.index(def_cur) if def_cur in cur_keys else 0)
            _, sym       = CURRENCIES[currency_key]
            price        = st.number_input(f"Price ({sym})", min_value=0.0, value=0.0, step=0.5)
            stock_qty    = st.number_input("Stock Quantity", min_value=0, value=10)
            sku          = st.text_input("SKU (optional)")
            default_tags = st.session_state.get("confirmed_tags","")
            tags         = st.text_input("Tags (comma separated)", value=default_tags,
                                         placeholder="gift, bracelet, protection")
            status       = st.selectbox("Status", ["draft","active","archived"])

        # ── Image ─────────────────────────────────────────────
        img_bytes = last.get("image_bytes")
        if img_bytes:
            st.markdown("#### Product Image (from Generate tab)")
            st.image(img_bytes, width=180)
        else:
            img_file  = st.file_uploader("Main Product Image",
                type=["jpg","jpeg","png","webp"], key="shopify_img_upload")
            img_bytes = img_file.read() if img_file else None

        # ── Live Preview ──────────────────────────────────────
        if product_name and description:
            st.markdown("---")
            st.markdown("#### Shopify Preview")
            _, sym2   = CURRENCIES[currency_key]
            tags_html = "".join(
                f'<span class="tag-pill">{t.strip()}</span>'
                for t in tags.split(",") if t.strip()
            )
            st.markdown(f"""
            <div class="shopify-preview">
                <h3>{product_name}</h3>
                <div class="shopify-price">{sym2}{price:,.2f}</div>
                <p>{description}</p>
                <p><b>Vendor:</b> {vendor or 'My Store'} &nbsp;|&nbsp;
                   <b>Type:</b> {product_type or 'General'} &nbsp;|&nbsp;
                   <b>Stock:</b> {int(stock_qty)}</p>
                <div style="margin-top:10px">{tags_html}</div>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("---")

        if st.button("List on Shopify", type="primary", use_container_width=True):
            allowed, limit_msg = check_usage_limit(email, "shopify")
            if not allowed:
                st.error(f"🔒 {limit_msg}")
            else:
                token = client_secret.strip() if client_secret else ""
                if not store_url or not token:
                    st.error("Store URL and Client Secret are required.")
                elif not product_name or not description or price <= 0:
                    st.error("Product Name, Description, and Price > 0 are required.")
                else:
                    with st.spinner("Listing on Shopify..."):
                        ok, result = list_on_shopify(
                            store_url, token, product_name, description, price,
                            image_bytes=img_bytes,
                            vendor=vendor, product_type=product_type,
                            sku=sku or None, stock_qty=int(stock_qty),
                            tags=tags, status=status,
                        )
                    if ok:
                        increment_usage(email, "shopify")
                        st.success("Product listed successfully!")
                        st.markdown(f"[View on Shopify Admin]({result})")
                    else:
                        st.error(f"Failed: {result}")

        with st.expander("How to get Shopify Client Secret (2026)"):
            st.markdown("""
**Step 1** — Shopify Admin → Settings → Apps and sales channels

**Step 2** — Click **Develop apps** → **Create an app**

**Step 3** — Configure Admin API scopes:
- write_products, read_products
- write_inventory, read_locations

**Step 4** — Save → Install app → Reveal token → Copy `shpss_xxxxx`

**Step 5** — Paste in **Client Secret** field above

Store URL format: `your-store.myshopify.com` (no https://)
            """)

    # ══════════════════════════════════════════
    # PAGE: SUBSCRIPTION
    # ══════════════════════════════════════════
    elif page == "Subscription":
        st.markdown("## Subscription & Plans")

        sub    = get_subscription(email)
        plan   = sub.get("plan", "free_trial")
        status = sub.get("status", "active")
        exp    = sub.get("expires_at")
        billing = sub.get("billing","")

        # Current plan info
        st.markdown("### Your Current Plan")
        col_a, col_b, col_c = st.columns(3)
        with col_a:
            st.metric("Plan", PLANS.get(plan,{}).get("name", plan))
        with col_b:
            st.metric("Status", status.capitalize())
        with col_c:
            if exp:
                try:
                    exp_dt  = datetime.fromisoformat(exp)
                    days_left = (exp_dt - datetime.now()).days
                    st.metric("Days Left", max(0, days_left))
                except Exception:
                    st.metric("Expires", "—")
            else:
                st.metric("Expires", "Never" if billing == "admin" else "Monthly")

        # Usage today
        today = datetime.now().strftime("%Y-%m-%d")
        if sub.get("usage_date") == today:
            gen_used  = sub.get("usage_generate", 0)
            shop_used = sub.get("usage_shopify", 0)
        else:
            gen_used = shop_used = 0

        plan_info = PLANS.get(plan, PLANS["free_trial"])
        g_limit   = plan_info["generate_limit"]
        s_limit   = plan_info["shopify_limit"]

        st.markdown("### Today's Usage")
        col1, col2 = st.columns(2)
        with col1:
            lbl = "Unlimited" if g_limit >= 9999 else str(g_limit)
            st.progress(min(gen_used / max(g_limit, 1), 1.0),
                        text=f"Generations: {gen_used} / {lbl}")
        with col2:
            lbl2 = "Unlimited" if s_limit >= 9999 else str(s_limit)
            st.progress(min(shop_used / max(s_limit, 1), 1.0),
                        text=f"Shopify Listings: {shop_used} / {lbl2}")

        st.markdown("---")
        st.markdown("### Available Plans")

        # ── Billing toggle ─────────────────────────────────
        billing_choice = st.radio("Billing Period", ["Monthly", "Yearly (save ~30%)"],
                                  horizontal=True)
        yearly = billing_choice.startswith("Yearly")

        cols = st.columns(4)
        plan_keys = ["free_trial", "starter", "pro", "ultra_promax"]

        for col, pk in zip(cols, plan_keys):
            p = PLANS[pk]
            price_disp = p["price_yearly"] if yearly else p["price_monthly"]
            period     = "/yr" if yearly else "/mo"
            is_current = (pk == plan and status == "active")
            border_style = "border: 2px solid #111; border-radius:14px; padding:22px 16px; text-align:center; background:#f0f0f0;" if is_current else "border: 2px solid #e0e0e0; border-radius:14px; padding:22px 16px; text-align:center; background:#fafafa;"
            price_str  = "Free" if price_disp == 0 else f"${price_disp}{period}"
            col.markdown(f"""
<div style="{border_style}">
  <h4 style="margin:0 0 6px;font-size:17px">{p['name']}</h4>
  <div style="font-size:26px;font-weight:800;color:#111">{price_str}</div>
  <div style="color:#666;font-size:12px;margin-top:6px">{p['description']}</div>
  {'<div style="margin-top:8px;background:#111;color:#fff;border-radius:8px;padding:3px 0;font-size:12px">Current Plan</div>' if is_current else ''}
</div>
""", unsafe_allow_html=True)

        st.markdown("---")

        # ── Payment instructions ───────────────────────────
        st.markdown("### How to Upgrade")
        st.info("""
**To subscribe or upgrade, please make a payment and then contact us:**

1. **Send payment** via PayPal or bank transfer:
   - **PayPal:** [paypal.me/YourPayPalUsername](https://paypal.me/YourPayPalUsername)
   - **Bank Transfer:** Contact us on WhatsApp for account details

2. **Contact us after payment** with:
   - Your registered email address
   - Plan name & billing period (monthly / yearly)
   - Payment screenshot or transaction ID

3. **Reach us at:**
   - 📧 muhammadsaadpopat76@gmail.com
   - 📱 WhatsApp: [+92-300-0000000](https://wa.me/923000000000)

⚡ Subscriptions activated **within a few hours** of payment confirmation.
        """)

        if plan != "free_trial" and status == "active" and billing != "admin":
            st.markdown("---")
            if st.button("Cancel Subscription", type="primary"):
                cancel_subscription(email)
                st.warning("Subscription cancelled. You can still use the app until the period ends.")
                st.rerun()

    # ══════════════════════════════════════════
    # PAGE: ADMIN PANEL
    # ══════════════════════════════════════════
    elif page == "Admin Panel" and admin:
        st.markdown("## 🔐 Admin Panel")
        st.caption("Manage all user accounts and subscriptions.")

        users_data = load_users()

        # ── Stats ─────────────────────────────────────────
        total      = len(users_data)
        active_cnt = sum(1 for u in users_data.values()
                         if u.get("subscription",{}).get("status") == "active")
        trial_cnt  = sum(1 for u in users_data.values()
                         if u.get("subscription",{}).get("plan") == "free_trial")
        paid_cnt   = sum(1 for u in users_data.values()
                         if u.get("subscription",{}).get("plan") not in ("free_trial",)
                         and u.get("subscription",{}).get("billing") != "admin")

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total Users", total)
        c2.metric("Active", active_cnt)
        c3.metric("On Trial", trial_cnt)
        c4.metric("Paid", paid_cnt)

        st.markdown("---")

        # ── Admin Tabs ────────────────────────────────────
        admin_tab1, admin_tab2 = st.tabs(["👥 All Users", "⬆️ Upgrade / Change Plan"])

        # ── Tab 1: All Users ──────────────────────────────
        with admin_tab1:
            st.markdown("### All Users")
            for em, u in users_data.items():
                sub_u    = u.get("subscription", {})
                plan_u   = sub_u.get("plan", "—")
                status_u = sub_u.get("status", "—")
                exp_u    = sub_u.get("expires_at", "")
                with st.expander(f"{em}  —  {PLANS.get(plan_u,{}).get('name', plan_u)}  [{status_u}]"):
                    col1, col2 = st.columns(2)
                    with col1:
                        st.write(f"**Display Name:** {u.get('display_name','')}")
                        st.write(f"**Joined:** {u.get('created','')}")
                        st.write(f"**Plan:** {plan_u}")
                        st.write(f"**Billing:** {sub_u.get('billing','')}")
                        st.write(f"**Status:** {status_u}")
                        st.write(f"**Expires:** {exp_u or 'Never'}")
                        st.write(f"**Payment Ref:** {sub_u.get('payment_ref','—')}")
                    with col2:
                        st.markdown("**Activate / Change Plan**")
                        new_plan    = st.selectbox("Plan", list(PLANS.keys()),
                                                   key=f"plan_{em}",
                                                   index=list(PLANS.keys()).index(plan_u)
                                                   if plan_u in PLANS else 0)
                        new_billing = st.selectbox("Billing", ["monthly","yearly","admin"],
                                                   key=f"bill_{em}")
                        new_ref     = st.text_input("Payment Reference", key=f"ref_{em}",
                                                    value=sub_u.get("payment_ref",""))
                        if st.button("Activate", key=f"act_{em}", type="primary"):
                            ok, msg = activate_subscription(em, new_plan, new_billing, new_ref)
                            if ok:
                                st.success(msg)
                                st.rerun()
                            else:
                                st.error(msg)
                        if st.button("Cancel", key=f"cancel_{em}"):
                            cancel_subscription(em)
                            st.warning(f"Subscription cancelled for {em}")
                            st.rerun()

        # ── Tab 2: Upgrade / Change Plan ──────────────────
        with admin_tab2:
            st.markdown("### ⬆️ Upgrade or Change a User's Plan")
            st.caption("Search any user and change their plan instantly — with or without payment.")

            all_emails = list(users_data.keys())
            selected_email = st.selectbox("Select User", ["— select —"] + all_emails,
                                          key="upgrade_select_email")

            if selected_email and selected_email != "— select —":
                sel_user = users_data[selected_email]
                sel_sub  = sel_user.get("subscription", {})
                cur_plan    = sel_sub.get("plan", "free_trial")
                cur_billing = sel_sub.get("billing", "monthly")
                cur_status  = sel_sub.get("status", "—")
                cur_expires = sel_sub.get("expires_at", "Never")
                cur_ref     = sel_sub.get("payment_ref", "")

                st.markdown(f"""
<div style="background:#f5f5f5;border-radius:10px;padding:14px 18px;margin-bottom:16px">
  <b>User:</b> {selected_email}<br>
  <b>Display Name:</b> {sel_user.get('display_name','')}<br>
  <b>Current Plan:</b> {PLANS.get(cur_plan,{}).get('name', cur_plan)} &nbsp;|&nbsp;
  <b>Billing:</b> {cur_billing} &nbsp;|&nbsp;
  <b>Status:</b> {cur_status}<br>
  <b>Expires:</b> {cur_expires or 'Never'}
</div>
""", unsafe_allow_html=True)

                col_a, col_b = st.columns(2)
                with col_a:
                    up_plan = st.selectbox(
                        "New Plan",
                        list(PLANS.keys()),
                        index=list(PLANS.keys()).index(cur_plan) if cur_plan in PLANS else 0,
                        format_func=lambda k: PLANS[k]["name"],
                        key="upgrade_plan"
                    )
                with col_b:
                    up_billing = st.selectbox(
                        "Billing Period",
                        ["monthly", "yearly", "admin"],
                        index=["monthly","yearly","admin"].index(cur_billing)
                              if cur_billing in ["monthly","yearly","admin"] else 0,
                        key="upgrade_billing"
                    )

                up_ref = st.text_input(
                    "Payment Reference (optional)",
                    value=cur_ref,
                    placeholder="PayPal TxID / Payoneer Ref / manual",
                    key="upgrade_ref"
                )

                st.markdown(f"""
<div style="background:#fffbe6;border:1px solid #f0d060;border-radius:8px;padding:10px 14px;margin:8px 0">
  Changing <b>{PLANS.get(cur_plan,{}).get('name', cur_plan)}</b> →
  <b>{PLANS.get(up_plan,{}).get('name', up_plan)}</b>
  ({up_billing})
</div>
""", unsafe_allow_html=True)

                if st.button("✅ Apply Plan Change", type="primary", key="upgrade_apply"):
                    ok, msg = activate_subscription(selected_email, up_plan, up_billing, up_ref)
                    if ok:
                        st.success(f"✅ Done! {selected_email} is now on **{PLANS[up_plan]['name']}** ({up_billing}).")
                        st.rerun()
                    else:
                        st.error(msg)

    # ══════════════════════════════════════════
    # PAGE: SETTINGS
    # ══════════════════════════════════════════
    elif page == "Settings":
        st.markdown("## Settings")
        user_info = get_user_info(email) or {}
        st.markdown("### Account Info")
        st.info(f"**Email:** {email}  \n**Joined:** {user_info.get('created','')}")

        st.markdown("---")
        st.markdown("### Change Password")
        with st.expander("Change my password"):
            cp_old  = st.text_input("Current Password", type="password", key="cp_old")
            cp_new  = st.text_input("New Password",     type="password", key="cp_new")
            cp_new2 = st.text_input("Confirm New Password", type="password", key="cp_new2")
            if st.button("Update Password", type="primary"):
                if not cp_old or not cp_new:
                    st.error("Please fill in all fields.")
                elif cp_new != cp_new2:
                    st.error("New passwords do not match.")
                else:
                    ok, msg = change_password(email, cp_old, cp_new)
                    if ok:
                        st.success(msg)
                    else:
                        st.error(msg)

        st.markdown("---")
        st.markdown("### Clear My History")
        if st.button("Clear All History", type="primary"):
            with open(memory_file, "w") as f:
                json.dump([], f)
            st.success("History cleared!")

# ─── ENTRY POINT ──────────────────────────────────────────────
if st.session_state.logged_in:
    show_app()
else:
    show_auth()