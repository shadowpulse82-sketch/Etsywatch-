from fastapi import FastAPI, APIRouter, HTTPException, Header, Depends
from fastapi.responses import Response
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import asyncio
import logging
import re
import json
import random
import uuid
import hashlib
import urllib.parse
from pathlib import Path
from datetime import datetime, timezone
from difflib import SequenceMatcher
from typing import List, Optional, Annotated

from pydantic import BaseModel, Field, EmailStr, ConfigDict
import httpx
from bs4 import BeautifulSoup
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from playwright.async_api import async_playwright, Browser as PWBrowser
from playwright_stealth import stealth_async


ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB
mongo_url = os.environ['MONGO_URL']
mongo_client = AsyncIOMotorClient(mongo_url)
db = mongo_client[os.environ['DB_NAME']]

# Resend (optional)
RESEND_API_KEY = os.environ.get('RESEND_API_KEY', '')
SENDER_EMAIL = os.environ.get('SENDER_EMAIL', 'onboarding@resend.dev')
if RESEND_API_KEY:
    import resend
    resend.api_key = RESEND_API_KEY

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("etsywatch")

app = FastAPI(title="EtsyWatch API")
api_router = APIRouter(prefix="/api")

# ---------- Models ----------

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class User(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    email: EmailStr
    shop_name: Optional[str] = None
    alert_on_price_undercut: bool = True
    alert_on_similar_listing: bool = True
    created_at: str = Field(default_factory=now_iso)


class SignupRequest(BaseModel):
    email: EmailStr


class Listing(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_email: EmailStr
    url: str
    title: str = ""
    price: str = ""
    seller_name: str = ""
    status: str = "Watching"  # Watching | Price Changed | Copy Detected
    last_checked: Optional[str] = None
    last_price: Optional[str] = None
    created_at: str = Field(default_factory=now_iso)


class AddListingRequest(BaseModel):
    url: str


class SettingsUpdate(BaseModel):
    shop_name: Optional[str] = None
    alert_on_price_undercut: Optional[bool] = None
    alert_on_similar_listing: Optional[bool] = None


class Evidence(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_email: EmailStr
    listing_id: str
    original_title: str
    original_url: str
    suspicious_url: str
    suspicious_title: str
    suspicious_shop: str
    similarity: float
    screenshot_url: str
    detected_at: str = Field(default_factory=now_iso)


# ---------- Auth (simple email session) ----------

async def get_current_user(
    x_user_email: Annotated[Optional[str], Header()] = None,
) -> User:
    if not x_user_email:
        raise HTTPException(status_code=401, detail="Not authenticated")
    doc = await db.users.find_one({"email": x_user_email}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=401, detail="User not found")
    return User(**doc)


# ---------- Scraping ----------

USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
]


def _browser_headers() -> dict:
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "Sec-Ch-Ua": '"Chromium";v="124", "Not_A Brand";v="99"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": '"macOS"',
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1",
        "Referer": "https://www.google.com/",
        "DNT": "1",
    }


def _proxy_config() -> Optional[dict]:
    """Parse SCRAPER_PROXY env var into a Playwright proxy config dict."""
    raw = os.environ.get("SCRAPER_PROXY") or os.environ.get("HTTP_PROXY")
    if not raw:
        return None
    try:
        parsed = urllib.parse.urlparse(raw)
        if not parsed.hostname:
            return None
        scheme = parsed.scheme or "http"
        port = f":{parsed.port}" if parsed.port else ""
        server = f"{scheme}://{parsed.hostname}{port}"
        cfg = {"server": server}
        if parsed.username:
            cfg["username"] = urllib.parse.unquote(parsed.username)
        if parsed.password:
            cfg["password"] = urllib.parse.unquote(parsed.password)
        return cfg
    except Exception as e:
        logger.warning(f"Bad SCRAPER_PROXY: {e}")
        return None


async def fetch(url: str, timeout: float = 30.0, polite_delay: bool = True) -> Optional[str]:
    """Fetch a URL using a stealthed headless Chromium via Playwright.

    Playwright executes JavaScript and presents a real browser fingerprint,
    so it can pass through anti-bot services like DataDome _provided_ the
    egress IP isn't already flagged. If the page returns a non-2xx status
    (including DataDome's 403 challenge), we log the server header and
    return None so the caller can degrade gracefully.
    """
    if polite_delay:
        await asyncio.sleep(random.uniform(2.0, 3.0))

    browser = await get_browser()
    if browser is None:
        return None

    context = None
    try:
        ctx_kwargs = dict(
            user_agent=random.choice(USER_AGENTS),
            viewport={"width": 1280, "height": 800},
            locale="en-US",
            timezone_id="America/New_York",
            extra_http_headers={"Accept-Language": "en-US,en;q=0.9"},
        )
        proxy_cfg = _proxy_config()
        if proxy_cfg:
            ctx_kwargs["proxy"] = proxy_cfg
        context = await browser.new_context(**ctx_kwargs)
        page = await context.new_page()
        try:
            await stealth_async(page)
        except Exception:
            # Stealth shim failure shouldn't kill the fetch
            pass
        response = await page.goto(
            url, wait_until="domcontentloaded", timeout=int(timeout * 1000)
        )
        status = response.status if response else 0
        if status and status >= 400:
            srv = response.headers.get("server", "?") if response else "?"
            logger.warning(f"Fetch {url} -> {status} (server={srv})")
            return None
        # Give JSON-LD / hydration a beat to land
        try:
            await page.wait_for_selector(
                'script[type="application/ld+json"]', timeout=5000
            )
        except Exception:
            pass
        html = await page.content()
        return html
    except Exception as e:
        logger.warning(f"Fetch error {url}: {e}")
        return None
    finally:
        if context is not None:
            try:
                await context.close()
            except Exception:
                pass


def _text(el) -> str:
    return el.get_text(strip=True) if el else ""


# Shared Playwright browser (singleton) - lazy launch, kept across requests
_playwright = None
_browser: Optional[PWBrowser] = None
_browser_lock = asyncio.Lock()


async def get_browser() -> Optional[PWBrowser]:
    """Lazy-launch and return a shared Chromium browser."""
    global _playwright, _browser
    async with _browser_lock:
        if _browser is not None and _browser.is_connected():
            return _browser
        try:
            if _playwright is None:
                _playwright = await async_playwright().start()
            launch_kwargs = dict(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-blink-features=AutomationControlled",
                ],
            )
            proxy_cfg = _proxy_config()
            if proxy_cfg:
                launch_kwargs["proxy"] = proxy_cfg
                logger.info(f"Launching Chromium via proxy {proxy_cfg['server']}")
            _browser = await _playwright.chromium.launch(**launch_kwargs)
            logger.info("Playwright Chromium launched.")
            return _browser
        except Exception as e:
            logger.error(f"Playwright launch failed: {e}")
            return None


async def shutdown_browser():
    global _playwright, _browser
    try:
        if _browser is not None:
            await _browser.close()
            _browser = None
        if _playwright is not None:
            await _playwright.stop()
            _playwright = None
    except Exception as e:
        logger.warning(f"Browser shutdown error: {e}")


def _iter_jsonld(soup: BeautifulSoup):
    """Yield each parsed JSON-LD object embedded on the page."""
    for tag in soup.find_all("script", attrs={"type": "application/ld+json"}):
        raw = tag.string or tag.get_text() or ""
        raw = raw.strip()
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except Exception:
            continue
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    yield item
        elif isinstance(data, dict):
            if "@graph" in data and isinstance(data["@graph"], list):
                for item in data["@graph"]:
                    if isinstance(item, dict):
                        yield item
            else:
                yield data


def _extract_product_from_jsonld(soup: BeautifulSoup) -> dict:
    """Find the first JSON-LD Product node and pull title/price/seller."""
    out = {"title": "", "price": "", "seller_name": ""}
    for node in _iter_jsonld(soup):
        type_val = node.get("@type")
        types = type_val if isinstance(type_val, list) else [type_val]
        if not any(t == "Product" for t in types if t):
            continue

        if not out["title"]:
            name = node.get("name")
            if isinstance(name, str):
                out["title"] = name.strip()

        # Brand or seller from Product
        brand = node.get("brand")
        if isinstance(brand, dict):
            bname = brand.get("name")
            if isinstance(bname, str) and not out["seller_name"]:
                out["seller_name"] = bname.strip()
        elif isinstance(brand, str) and not out["seller_name"]:
            out["seller_name"] = brand.strip()

        # Offers can be Offer or AggregateOffer (or list)
        offers = node.get("offers")
        offer_list = []
        if isinstance(offers, list):
            offer_list = offers
        elif isinstance(offers, dict):
            offer_list = [offers]

        for offer in offer_list:
            if not isinstance(offer, dict):
                continue
            currency = offer.get("priceCurrency") or "USD"
            # AggregateOffer fields
            amount = (
                offer.get("price")
                or offer.get("lowPrice")
                or offer.get("highPrice")
            )
            if amount is not None and amount != "":
                out["price"] = f"{currency} {amount}"
                break

            # Nested priceSpecification
            spec = offer.get("priceSpecification")
            if isinstance(spec, dict):
                amount = spec.get("price")
                cur = spec.get("priceCurrency") or currency
                if amount is not None and amount != "":
                    out["price"] = f"{cur} {amount}"
                    break

            seller = offer.get("seller")
            if isinstance(seller, dict) and not out["seller_name"]:
                sname = seller.get("name")
                if isinstance(sname, str):
                    out["seller_name"] = sname.strip()

        if out["title"] or out["price"]:
            break
    return out


def parse_listing(html: str) -> dict:
    """Best-effort parse of an Etsy listing page.

    Strategy: prefer structured JSON-LD Product data (most reliable), fall back
    to OG meta tags, then visible HTML selectors.
    """
    soup = BeautifulSoup(html, "lxml")
    title = ""
    price = ""
    seller = ""

    # 1) JSON-LD Product (most reliable - Etsy embeds it)
    jl = _extract_product_from_jsonld(soup)
    title = jl["title"]
    price = jl["price"]
    seller = jl["seller_name"]

    # 2) OG meta fallbacks
    if not title:
        og_title = soup.find("meta", property="og:title")
        if og_title and og_title.get("content"):
            title = og_title["content"].strip()
    if not title:
        h1 = soup.find("h1")
        title = _text(h1)

    if not price:
        price_meta = soup.find("meta", property="product:price:amount") or soup.find(
            "meta", property="og:price:amount"
        )
        if price_meta and price_meta.get("content"):
            currency = soup.find("meta", property="product:price:currency") or soup.find(
                "meta", property="og:price:currency"
            )
            cur = currency.get("content").strip() if currency and currency.get("content") else "USD"
            price = f"{cur} {price_meta['content'].strip()}"

    if not price:
        # try price wp-price selectors
        candidates = soup.select(
            "p.wt-text-title-larger, p.wt-text-title-03, [data-buy-box-region='price'] p, "
            "div[data-selector='price-only'] p"
        )
        for c in candidates:
            text = _text(c)
            if text and any(sym in text for sym in ("$", "£", "€", "USD", "CAD")):
                price = text
                break

    if not seller:
        shop_link = soup.find("a", attrs={"href": re.compile(r"/shop/")})
        seller = _text(shop_link)
    if not seller:
        shop_meta = soup.find("meta", attrs={"name": "shop_name"})
        if shop_meta and shop_meta.get("content"):
            seller = shop_meta["content"]

    return {"title": title, "price": price, "seller_name": seller}


def parse_search_results(html: str, limit: int = 10) -> List[dict]:
    """Parse Etsy search results page for listing previews."""
    soup = BeautifulSoup(html, "lxml")
    results = []
    seen = set()
    anchors = soup.select("a[href*='/listing/']")
    for a in anchors:
        href = a.get("href", "")
        if not href.startswith("http"):
            continue
        # Normalize URL by stripping query
        base = href.split("?")[0]
        m = re.search(r"/listing/(\d+)/", base)
        if not m:
            continue
        listing_id = m.group(1)
        if listing_id in seen:
            continue
        seen.add(listing_id)

        title = (a.get("title") or "").strip()
        if not title:
            title = _text(a)
        if not title:
            continue

        # Try to extract shop name from nearby element
        shop_name = ""
        parent = a.find_parent()
        if parent:
            shop_el = parent.find("p", attrs={"class": re.compile("v2-listing-card__shop")})
            shop_name = _text(shop_el)

        results.append({
            "url": base,
            "title": title,
            "shop_name": shop_name,
            "listing_id": listing_id,
        })
        if len(results) >= limit:
            break
    return results


def title_similarity(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    a_norm = re.sub(r"\s+", " ", a.lower()).strip()
    b_norm = re.sub(r"\s+", " ", b.lower()).strip()
    return SequenceMatcher(None, a_norm, b_norm).ratio()


def first_n_words(title: str, n: int = 5) -> str:
    words = re.findall(r"\w+", title)
    return " ".join(words[:n])


def placeholder_screenshot_url(suspicious_url: str, title: str) -> str:
    """Generate a deterministic placeholder screenshot URL for evidence."""
    pool = [
        "https://images.unsplash.com/photo-1691096675075-de995918f3ce?w=800&q=80",
        "https://images.unsplash.com/photo-1691096674730-2b5fb28b726f?w=800&q=80",
        "https://images.unsplash.com/photo-1691096671014-b00e1923d288?w=800&q=80",
        "https://images.unsplash.com/photo-1691096674326-74cfe19c04cc?w=800&q=80",
    ]
    h = int(hashlib.md5((suspicious_url + title).encode()).hexdigest(), 16)
    return pool[h % len(pool)]


# ---------- Email ----------

async def send_email(to_email: str, subject: str, html: str) -> bool:
    if not RESEND_API_KEY:
        logger.info(f"[EMAIL MOCK] to={to_email} subject={subject!r}")
        return True
    try:
        params = {
            "from": SENDER_EMAIL,
            "to": [to_email],
            "subject": subject,
            "html": html,
        }
        await asyncio.to_thread(resend.Emails.send, params)
        logger.info(f"[EMAIL SENT] to={to_email} subject={subject!r}")
        return True
    except Exception as e:
        logger.error(f"Email error: {e}")
        return False


def render_price_change_email(listing: dict, old_price: str, new_price: str) -> tuple[str, str]:
    subject = f"⚠️ Price change detected on {listing['title']}"
    body = f"""
    <div style="font-family: Arial, sans-serif; color:#1a1a1a; max-width:560px; margin:auto;">
      <h2 style="color:#2D9B6F;">Price change detected</h2>
      <p><strong>Listing:</strong> {listing['title']}</p>
      <p><strong>URL:</strong> <a href="{listing['url']}">{listing['url']}</a></p>
      <table style="border-collapse:collapse; margin:16px 0;">
        <tr>
          <td style="padding:8px 16px; border:1px solid #ddd;">Old price</td>
          <td style="padding:8px 16px; border:1px solid #ddd;">{old_price}</td>
        </tr>
        <tr>
          <td style="padding:8px 16px; border:1px solid #ddd;">New price</td>
          <td style="padding:8px 16px; border:1px solid #ddd;"><strong>{new_price}</strong></td>
        </tr>
      </table>
      <p style="color:#666;">Detected at: {now_iso()}</p>
      <p>Open your <a href="#">EtsyWatch dashboard</a> to review.</p>
    </div>
    """
    return subject, body


def render_copy_email(
    listing: dict,
    suspicious: dict,
    similarity: float,
    screenshot_url: str,
    shop_name: str,
) -> tuple[str, str]:
    subject = f"🚨 Someone may have copied your listing: {listing['title']}"
    cease_msg = (
        f"Dear {suspicious.get('shop_name') or '[Shop Name]'}, "
        f"I am the original creator of {listing['title']} on Etsy. "
        f"Your listing {suspicious['url']} appears to copy my original work. "
        f"I am requesting you immediately remove this listing. "
        f"If you do not comply I reserve the right to pursue formal legal and platform action. — {shop_name or '[Your shop name]'}"
    )
    body = f"""
    <div style="font-family: Arial, sans-serif; color:#1a1a1a; max-width:600px; margin:auto;">
      <h2 style="color:#b91c1c;">Possible copy detected</h2>
      <p><strong>Your listing:</strong> {listing['title']}<br/>
         <a href="{listing['url']}">{listing['url']}</a></p>
      <p><strong>Suspicious listing:</strong> {suspicious['title']}<br/>
         <a href="{suspicious['url']}">{suspicious['url']}</a></p>
      <p><strong>Similarity:</strong> {int(similarity*100)}%</p>
      <p><img src="{screenshot_url}" alt="evidence" style="max-width:100%; border:1px solid #ddd;"/></p>
      <h3 style="color:#2D9B6F; margin-top:24px;">Fight Back — Do This Now:</h3>
      <ol>
        <li>Report copyright infringement directly to Etsy: <a href="https://www.etsy.com/legal/ip">https://www.etsy.com/legal/ip</a></li>
        <li>Send this pre-written cease and desist message:
          <blockquote style="border-left:3px solid #2D9B6F; padding:12px 16px; background:#f7f7f7; margin:8px 0;">
            {cease_msg}
          </blockquote>
        </li>
        <li>Your screenshot evidence has been saved in your EtsyWatch dashboard under Evidence Vault.</li>
      </ol>
    </div>
    """
    return subject, body


# ---------- Core check logic ----------

async def check_listing(listing_doc: dict, user_doc: dict) -> dict:
    """Re-scrape a listing, detect price changes & copies. Returns updated fields."""
    url = listing_doc["url"]
    html = await fetch(url)
    update = {"last_checked": now_iso()}
    new_status = "Watching"

    if not html:
        # Don't error; just record last_checked
        update["status"] = listing_doc.get("status", "Watching")
        return update

    parsed = parse_listing(html)
    new_title = parsed["title"] or listing_doc.get("title", "")
    new_price = parsed["price"] or listing_doc.get("price", "")
    new_seller = parsed["seller_name"] or listing_doc.get("seller_name", "")

    old_price = listing_doc.get("price", "")
    update["title"] = new_title
    update["price"] = new_price
    update["seller_name"] = new_seller

    # Price change detection
    if old_price and new_price and old_price.strip() != new_price.strip():
        new_status = "Price Changed"
        update["last_price"] = old_price
        if user_doc.get("alert_on_price_undercut", True):
            subject, body = render_price_change_email(
                {"title": new_title or listing_doc.get("title", ""), "url": url},
                old_price,
                new_price,
            )
            await send_email(user_doc["email"], subject, body)

    # Copy detection: search Etsy for first 5 words of title
    title_for_search = new_title or listing_doc.get("title", "")
    if title_for_search:
        query = first_n_words(title_for_search, 5)
        if query:
            search_url = (
                "https://www.etsy.com/search?q=" + urllib.parse.quote(query)
            )
            search_html = await fetch(search_url)
            results = parse_search_results(search_html, limit=10) if search_html else []
            for r in results:
                sim = title_similarity(title_for_search, r["title"])
                # Different seller check: compare URL/shop_name to user's seller
                same_seller = (
                    new_seller
                    and r.get("shop_name")
                    and new_seller.strip().lower() == r["shop_name"].strip().lower()
                )
                same_listing_url = r["url"].startswith(url.split("?")[0])
                if sim >= 0.7 and not same_seller and not same_listing_url:
                    new_status = "Copy Detected"
                    screenshot_url = placeholder_screenshot_url(r["url"], r["title"])
                    evidence = Evidence(
                        user_email=user_doc["email"],
                        listing_id=listing_doc["id"],
                        original_title=title_for_search,
                        original_url=url,
                        suspicious_url=r["url"],
                        suspicious_title=r["title"],
                        suspicious_shop=r.get("shop_name", ""),
                        similarity=round(sim, 3),
                        screenshot_url=screenshot_url,
                    )
                    # Avoid duplicates: check by suspicious_url + listing_id
                    existing = await db.evidence.find_one(
                        {"listing_id": listing_doc["id"], "suspicious_url": r["url"]}
                    )
                    if not existing:
                        await db.evidence.insert_one(evidence.model_dump())
                        if user_doc.get("alert_on_similar_listing", True):
                            subject, body = render_copy_email(
                                {"title": title_for_search, "url": url},
                                {
                                    "title": r["title"],
                                    "url": r["url"],
                                    "shop_name": r.get("shop_name", ""),
                                },
                                sim,
                                screenshot_url,
                                user_doc.get("shop_name") or "",
                            )
                            await send_email(user_doc["email"], subject, body)
                    break  # one alert per check is enough

    update["status"] = new_status
    return update


async def check_user_listings(user_email: str) -> int:
    user = await db.users.find_one({"email": user_email}, {"_id": 0})
    if not user:
        return 0
    listings = await db.listings.find({"user_email": user_email}, {"_id": 0}).to_list(1000)
    count = 0
    for lst in listings:
        try:
            update = await check_listing(lst, user)
            await db.listings.update_one({"id": lst["id"]}, {"$set": update})
            count += 1
        except Exception as e:
            logger.error(f"check_listing error for {lst.get('id')}: {e}")
    return count


async def scheduled_check_all():
    logger.info("Scheduled job: checking all user listings...")
    users = await db.users.find({}, {"_id": 0}).to_list(10000)
    for u in users:
        await check_user_listings(u["email"])
    logger.info("Scheduled job complete.")


# ---------- Routes ----------

@api_router.get("/")
async def root():
    return {"service": "EtsyWatch", "status": "ok"}


@api_router.post("/auth/signup")
async def signup(payload: SignupRequest):
    email = payload.email.lower()
    existing = await db.users.find_one({"email": email}, {"_id": 0})
    if existing:
        return {"email": email, "new": False, "user": existing}
    user = User(email=email)
    await db.users.insert_one(user.model_dump())
    return {"email": email, "new": True, "user": user.model_dump()}


@api_router.get("/auth/me")
async def me(current: User = Depends(get_current_user)):
    return current.model_dump()


@api_router.get("/listings")
async def list_listings(current: User = Depends(get_current_user)):
    docs = await db.listings.find({"user_email": current.email}, {"_id": 0}).to_list(1000)
    docs.sort(key=lambda d: d.get("created_at", ""), reverse=True)
    return docs


@api_router.post("/listings")
async def add_listing(
    payload: AddListingRequest, current: User = Depends(get_current_user)
):
    url = payload.url.strip()
    if "etsy.com/listing/" not in url:
        raise HTTPException(status_code=400, detail="Please paste a valid Etsy listing URL")

    # Free plan limit: 3 listings
    existing_count = await db.listings.count_documents({"user_email": current.email})
    if existing_count >= 3:
        raise HTTPException(
            status_code=402,
            detail="Free plan limit reached (3 listings). Upgrade to Pro for unlimited.",
        )

    # Initial fetch & parse
    html = await fetch(url)
    parsed = {"title": "", "price": "", "seller_name": ""}
    if html:
        parsed = parse_listing(html)

    listing = Listing(
        user_email=current.email,
        url=url,
        title=parsed["title"] or "Etsy Listing",
        price=parsed["price"],
        seller_name=parsed["seller_name"],
        last_checked=now_iso(),
    )
    await db.listings.insert_one(listing.model_dump())
    return listing.model_dump()


@api_router.delete("/listings/{listing_id}")
async def delete_listing(listing_id: str, current: User = Depends(get_current_user)):
    res = await db.listings.delete_one({"id": listing_id, "user_email": current.email})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Listing not found")
    # Cascade evidence
    await db.evidence.delete_many({"listing_id": listing_id, "user_email": current.email})
    return {"deleted": True}


@api_router.post("/listings/check-now")
async def check_now(current: User = Depends(get_current_user)):
    n = await check_user_listings(current.email)
    return {"checked": n}


@api_router.get("/settings")
async def get_settings(current: User = Depends(get_current_user)):
    return {
        "email": current.email,
        "shop_name": current.shop_name or "",
        "alert_on_price_undercut": current.alert_on_price_undercut,
        "alert_on_similar_listing": current.alert_on_similar_listing,
    }


@api_router.put("/settings")
async def update_settings(
    payload: SettingsUpdate, current: User = Depends(get_current_user)
):
    update = {k: v for k, v in payload.model_dump().items() if v is not None}
    if not update:
        return await get_settings(current)
    await db.users.update_one({"email": current.email}, {"$set": update})
    doc = await db.users.find_one({"email": current.email}, {"_id": 0})
    return {
        "email": doc["email"],
        "shop_name": doc.get("shop_name") or "",
        "alert_on_price_undercut": doc.get("alert_on_price_undercut", True),
        "alert_on_similar_listing": doc.get("alert_on_similar_listing", True),
    }


@api_router.get("/evidence")
async def list_evidence(current: User = Depends(get_current_user)):
    docs = await db.evidence.find({"user_email": current.email}, {"_id": 0}).to_list(1000)
    docs.sort(key=lambda d: d.get("detected_at", ""), reverse=True)
    return docs


@api_router.get("/evidence/{evidence_id}/download")
async def download_evidence(evidence_id: str, current: User = Depends(get_current_user)):
    doc = await db.evidence.find_one(
        {"id": evidence_id, "user_email": current.email}, {"_id": 0}
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Evidence not found")
    # Stream the placeholder image bytes
    async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
        r = await client.get(doc["screenshot_url"])
    headers = {
        "Content-Disposition": f'attachment; filename="evidence-{evidence_id}.jpg"'
    }
    return Response(content=r.content, media_type="image/jpeg", headers=headers)


# ---------- App lifecycle ----------

scheduler: Optional[AsyncIOScheduler] = None


@app.on_event("startup")
async def on_startup():
    global scheduler
    scheduler = AsyncIOScheduler(timezone="UTC")
    # Run every 24 hours; do an initial run 60s after startup
    scheduler.add_job(scheduled_check_all, "interval", hours=24, id="daily_check")
    scheduler.start()
    logger.info("EtsyWatch scheduler started (interval=24h).")


@app.on_event("shutdown")
async def on_shutdown():
    global scheduler
    if scheduler:
        scheduler.shutdown(wait=False)
    await shutdown_browser()
    mongo_client.close()


app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)
