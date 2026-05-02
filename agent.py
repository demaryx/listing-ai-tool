from groq import Groq
import os
import base64
import requests
import json
import time
def _detect_image_type(data: bytes) -> str:
    """imghdr ki jagah magic bytes se image type detect karo (Python 3.13+ compatible)."""
    if data[:8] == b'\x89PNG\r\n\x1a\n':
        return "png"
    if data[:3] == b'\xff\xd8\xff':
        return "jpeg"
    if data[:6] in (b'GIF87a', b'GIF89a'):
        return "gif"
    if data[:4] == b'RIFF' and data[8:12] == b'WEBP':
        return "webp"
    return "jpeg"  # default fallback
from dotenv import load_dotenv
from urllib.parse import quote

load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# ─── MODELS ───────────────────────────────────────────────────
_LLM_MODEL    = "llama-3.3-70b-versatile"
_VISION_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"
_FALLBACK_MODEL = "llama3-70b-8192"


# ─── SHOPIFY API VERSION ──────────────────────────────────────
SHOPIFY_API_VERSION = "2024-10"


# ─────────────────────────────────────────────
# CORE LLM  (with retry on rate-limit)
# ─────────────────────────────────────────────
def llm_call(prompt: str, system: str = "", retries: int = 3) -> str:
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    models_to_try = [_LLM_MODEL, _FALLBACK_MODEL]
    for model in models_to_try:
        for attempt in range(retries):
            try:
                response = client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=0.7,
                    max_tokens=2048,
                )
                return response.choices[0].message.content.strip()
            except Exception as e:
                err = str(e).lower()
                if "rate_limit" in err and attempt < retries - 1:
                    time.sleep(2 ** attempt)
                    continue
                if attempt == retries - 1:
                    break   # try next model
                raise RuntimeError(f"LLM call failed: {e}") from e
    return ""


# ─────────────────────────────────────────────
# IMAGE ANALYSIS
# ─────────────────────────────────────────────
def analyze_image(image_bytes: bytes) -> str:
    """
    Analyze a product image and return structured metadata.
    Raises RuntimeError if the API call fails.
    """
    if not image_bytes:
        raise ValueError("image_bytes is empty.")

    image_base64 = base64.standard_b64encode(image_bytes).decode("utf-8")
    img_type = _detect_image_type(image_bytes)
    try:
        response = client.chat.completions.create(
            model=_VISION_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/{img_type};base64,{image_base64}"}
                        },
                        {
                            "type": "text",
                            "text": (
                                "Analyze this product image and return ONLY this exact format, "
                                "nothing else:\n\n"
                                "PRODUCT_NAME: (product name)\n"
                                "CATEGORY: (product category)\n"
                                "COLOR: (color/s)\n"
                                "CONDITION: (New/Used)\n"
                                "FEATURES: (comma separated visible features)\n"
                                "DESCRIPTION: (2-3 sentence product description)"
                            )
                        }
                    ]
                }
            ],
            max_tokens=512,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        raise RuntimeError(f"Image analysis failed: {e}") from e


# ─────────────────────────────────────────────
# AI IMAGE GENERATION  (Pollinations.ai — free)
# ─────────────────────────────────────────────
def generate_product_images(product_name: str, category: str, color: str, n: int = 3) -> list[bytes]:
    """
    Generate n product-style images.
    Returns a list of raw image bytes. Failed requests are skipped silently.
    """
    n = max(1, min(n, 5))
    prompts = [
        f"professional product photography, {product_name}, {color}, white background, studio lighting, 4k, commercial",
        f"lifestyle photo of {product_name} in use, natural light, minimalist background, high quality",
        f"e-commerce hero image, {product_name}, {category}, close-up detail, premium quality, sharp focus",
        f"flat lay product shot, {product_name}, {color}, clean aesthetic, overhead view, editorial style",
        f"packshot, {product_name}, transparent background, ultra-sharp, product catalogue style",
    ]

    images = []
    for i, prompt in enumerate(prompts[:n]):
        try:
            encoded = quote(prompt)
            url = (
                f"https://image.pollinations.ai/prompt/{encoded}"
                f"?width=800&height=800&seed={i + 42}&nologo=true&enhance=true"
            )
            resp = requests.get(url, timeout=45)
            if resp.status_code == 200 and len(resp.content) > 1000:
                images.append(resp.content)
        except Exception:
            pass
    return images


# ─────────────────────────────────────────────
# COPY GENERATION
# ─────────────────────────────────────────────
def generate_product_copy(
    product_name: str,
    features: str,
    audience: str,
    brand_name: str,
    platform: str,
) -> tuple[str, str]:
    """
    Two-step copy generation:
      1. Features → emotional benefits
      2. Benefits → full platform-optimised copy
    Returns (benefits, full_copy).
    """
    # Step 1 — features to benefits
    benefits = llm_call(
        prompt=(
            f"Product: {product_name}\n"
            f"Features: {features}\n"
            f"Target Audience: {audience}\n\n"
            "Convert the features above into a concise bullet list of emotional customer benefits. "
            "No intro, no extra text — only the bullet list."
        ),
        system="You are a senior product analyst who translates product specs into customer value.",
    )

    # Step 2 — platform-optimised copy
    platform_hints = {
        "shopify":   "Include SEO-rich title, benefit-led description, and 3 ad variations.",
        "instagram": "Use casual tone, emojis where natural, short punchy copy, 5–8 relevant hashtags.",
        "amazon":    "Lead with the top benefit in title, use keyword-rich bullet points, backend search terms.",
        "daraz":     "Highlight value, free delivery, easy returns. Urdu/English mix is acceptable.",
        "facebook":  "Conversational, story-driven, include a clear CTA, keep under 150 words per variation.",
        "tiktok shop": "Ultra-short hooks (≤15 words), trending language, strong visual CTA.",
    }
    hint = platform_hints.get(platform.lower(), "Keep tone professional and conversion-focused.")

    full_copy = llm_call(
        prompt=(
            f"Brand: {brand_name or 'Generic'}\n"
            f"Product: {product_name}\n"
            f"Customer Benefits:\n{benefits}\n"
            f"Target Audience: {audience}\n"
            f"Platform: {platform}\n\n"
            f"Platform guidance: {hint}\n\n"
            "Generate the following in clean structured markdown:\n\n"
            "## PRODUCT TITLE\n"
            "One high-converting title optimised for this platform.\n\n"
            "## PRODUCT DESCRIPTION\n"
            "3–4 sentences, benefit- and emotion-led.\n\n"
            "## AD COPY VARIATIONS\n"
            "- **Variation 1 – Benefit-focused:** ...\n"
            "- **Variation 2 – Emotion-focused:** ...\n"
            "- **Variation 3 – Direct & Urgent:** ..."
        ),
        system=f"You are an expert e-commerce copywriter specialising in {platform}.",
    )

    return benefits, full_copy


# ─────────────────────────────────────────────
# SEO TAGS GENERATOR
# ─────────────────────────────────────────────
def generate_seo_tags(product_name: str, category: str, features: str, platform: str) -> list[str]:
    """
    Generate a list of SEO / search tags for the product.
    Returns a plain Python list of strings.
    """
    raw = llm_call(
        prompt=(
            f"Product: {product_name}\n"
            f"Category: {category}\n"
            f"Features: {features}\n"
            f"Platform: {platform}\n\n"
            "Generate 10–15 high-traffic search tags/keywords for this product on the given platform. "
            "Return ONLY a comma-separated list — no numbering, no extra text."
        ),
        system="You are an SEO specialist for e-commerce marketplaces.",
    )
    tags = [t.strip().lower() for t in raw.split(",") if t.strip()]
    return tags[:15]


# ─────────────────────────────────────────────
# PRICE SUGGESTION
# ─────────────────────────────────────────────
def suggest_price(product_name: str, category: str, features: str, currency: str = "PKR") -> dict:
    """
    Returns a dict: {min_price, suggested_price, max_price, reasoning}
    """
    raw = llm_call(
        prompt=(
            f"Product: {product_name}\n"
            f"Category: {category}\n"
            f"Features: {features}\n"
            f"Currency: {currency}\n\n"
            "Suggest a competitive retail price range for this product based on typical "
            f"{currency} market pricing. Return ONLY valid JSON in this exact format:\n"
            '{"min_price": <number>, "suggested_price": <number>, "max_price": <number>, '
            '"reasoning": "<one sentence>"}'
        ),
        system="You are a pricing analyst with expertise in South Asian and global e-commerce markets.",
    )
    try:
        # Strip markdown fences if present
        clean = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        data  = json.loads(clean)
        return {
            "min_price":       float(data.get("min_price", 0)),
            "suggested_price": float(data.get("suggested_price", 0)),
            "max_price":       float(data.get("max_price", 0)),
            "reasoning":       str(data.get("reasoning", "")),
        }
    except Exception:
        return {"min_price": 0, "suggested_price": 0, "max_price": 0, "reasoning": raw}


# ─────────────────────────────────────────────
# BULK COPY GENERATION
# ─────────────────────────────────────────────
def bulk_generate_copy(
    products: list[dict],
    platform: str,
    brand_name: str = "",
) -> list[dict]:
    """
    Generate copy for multiple products in one call.
    Each item in `products` must have keys: name, features, audience.
    Returns list of dicts with keys: name, benefits, output, error.
    """
    results = []
    for product in products:
        name     = product.get("name", "")
        features = product.get("features", "")
        audience = product.get("audience", "")
        try:
            benefits, output = generate_product_copy(name, features, audience, brand_name, platform)
            results.append({"name": name, "benefits": benefits, "output": output, "error": None})
        except Exception as e:
            results.append({"name": name, "benefits": "", "output": "", "error": str(e)})
    return results


# ─────────────────────────────────────────────
# SHOPIFY LISTING
# ─────────────────────────────────────────────
def list_on_shopify(
    store_url: str,
    access_token: str,
    product_name: str,
    description: str,
    price: float,
    image_bytes: bytes | None = None,
    extra_images: list[bytes] | None = None,
    vendor: str = "My Store",
    product_type: str = "General",
    sku: str | None = None,
    stock_qty: int = 10,
    tags: str = "",
    status: str = "draft",
    compare_price: float | None = None,
) -> tuple[bool, str]:
    """
    Create a product on Shopify.
    Returns (True, product_admin_url) on success, (False, error_message) on failure.
    """
    store_url = store_url.replace("https://", "").replace("http://", "").strip("/")
    if not store_url or not access_token:
        return False, "Store URL and Access Token are required."

    headers = {
        "X-Shopify-Access-Token": access_token,
        "Content-Type": "application/json",
    }

    variant: dict = {
        "price":                str(price),
        "inventory_management": "shopify",
        "fulfillment_service":  "manual",
        "inventory_quantity":   int(stock_qty),
    }
    if compare_price and compare_price > price:
        variant["compare_at_price"] = str(compare_price)
    if sku:
        variant["sku"] = sku

    payload = {
        "product": {
            "title":        product_name,
            "body_html":    f"<p>{description}</p>",
            "vendor":       vendor       or "My Store",
            "product_type": product_type or "General",
            "status":       status if status in ("active", "draft", "archived") else "draft",
            "tags":         tags,
            "variants":     [variant],
        }
    }

    try:
        resp = requests.post(
            f"https://{store_url}/admin/api/{SHOPIFY_API_VERSION}/products.json",
            headers=headers,
            data=json.dumps(payload),
            timeout=20,
        )
    except requests.RequestException as e:
        return False, f"Network error: {e}"

    if resp.status_code != 201:
        return False, f"Shopify error {resp.status_code}: {resp.text[:400]}"

    product_json = resp.json()["product"]
    product_id   = product_json["id"]

    # ── Set inventory level ──────────────────
    try:
        inv_item_id = product_json["variants"][0]["inventory_item_id"]
        loc_resp    = requests.get(
            f"https://{store_url}/admin/api/{SHOPIFY_API_VERSION}/locations.json",
            headers=headers, timeout=10,
        )
        if loc_resp.status_code == 200:
            locations = loc_resp.json().get("locations", [])
            if locations:
                requests.post(
                    f"https://{store_url}/admin/api/{SHOPIFY_API_VERSION}/inventory_levels/set.json",
                    headers=headers,
                    data=json.dumps({
                        "location_id":       locations[0]["id"],
                        "inventory_item_id": inv_item_id,
                        "available":         int(stock_qty),
                    }),
                    timeout=10,
                )
    except Exception:
        pass   # inventory set failure is non-fatal

    # ── Upload images ────────────────────────
    all_images: list[bytes] = []
    if image_bytes:
        all_images.append(image_bytes)
    if extra_images:
        all_images.extend(extra_images)

    for pos, img_b in enumerate(all_images, start=1):
        try:
            requests.post(
                f"https://{store_url}/admin/api/{SHOPIFY_API_VERSION}/products/{product_id}/images.json",
                headers=headers,
                data=json.dumps({
                    "image": {
                        "attachment": base64.standard_b64encode(img_b).decode("utf-8"),
                        "position":   pos,
                    }
                }),
                timeout=20,
            )
        except Exception:
            pass   # image upload failure is non-fatal

    return True, f"https://{store_url}/admin/products/{product_id}"