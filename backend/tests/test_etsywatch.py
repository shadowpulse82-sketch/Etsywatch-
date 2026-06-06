"""EtsyWatch backend API tests."""
import os
import uuid
import time
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL")
if not BASE_URL:
    # Fallback: read from frontend .env
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = line.split("=", 1)[1].strip()
                break
BASE_URL = BASE_URL.rstrip("/")
API = f"{BASE_URL}/api"

UNIQUE = uuid.uuid4().hex[:8]
USER_A = f"test_a_{UNIQUE}@example.com"
USER_B = f"test_b_{UNIQUE}@example.com"

VALID_URL = "https://www.etsy.com/listing/1234567890/test"


def h(email):
    return {"X-User-Email": email, "Content-Type": "application/json"}


# ---- Auth ----
def test_root():
    r = requests.get(f"{API}/")
    assert r.status_code == 200
    assert r.json().get("service") == "EtsyWatch"


def test_signup_new_user():
    r = requests.post(f"{API}/auth/signup", json={"email": USER_A})
    assert r.status_code == 200
    data = r.json()
    assert data["new"] is True
    assert data["email"] == USER_A.lower()
    assert "user" in data and data["user"]["email"] == USER_A.lower()


def test_signup_existing_returns_new_false():
    r = requests.post(f"{API}/auth/signup", json={"email": USER_A})
    assert r.status_code == 200
    assert r.json()["new"] is False


def test_me_with_header():
    r = requests.get(f"{API}/auth/me", headers=h(USER_A))
    assert r.status_code == 200
    assert r.json()["email"] == USER_A.lower()


def test_me_without_header():
    r = requests.get(f"{API}/auth/me")
    assert r.status_code == 401


# ---- Listings ----
listing_ids = []


def test_add_valid_etsy_listing():
    r = requests.post(f"{API}/listings", json={"url": VALID_URL}, headers=h(USER_A), timeout=30)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["url"] == VALID_URL
    assert data["title"]  # fallback to 'Etsy Listing'
    assert data["last_checked"] is not None
    assert "id" in data
    listing_ids.append(data["id"])


def test_add_non_etsy_rejected():
    r = requests.post(f"{API}/listings", json={"url": "https://www.amazon.com/dp/B0001"}, headers=h(USER_A))
    assert r.status_code == 400


def test_get_listings_user_a():
    r = requests.get(f"{API}/listings", headers=h(USER_A))
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    assert any(l["id"] == listing_ids[0] for l in data)


def test_free_plan_limit():
    # Add 2 more (total 3)
    for i in range(2):
        url = f"https://www.etsy.com/listing/{2000000000+i}/extra-{i}-{UNIQUE}"
        r = requests.post(f"{API}/listings", json={"url": url}, headers=h(USER_A), timeout=30)
        assert r.status_code == 200, r.text
        listing_ids.append(r.json()["id"])
    # 4th should fail with 402
    r = requests.post(
        f"{API}/listings",
        json={"url": f"https://www.etsy.com/listing/9999999999/over-limit-{UNIQUE}"},
        headers=h(USER_A),
        timeout=30,
    )
    assert r.status_code == 402, f"Expected 402, got {r.status_code}: {r.text}"


def test_multitenancy_user_b_cannot_see_user_a_listings():
    # Signup user B
    r = requests.post(f"{API}/auth/signup", json={"email": USER_B})
    assert r.status_code == 200
    r = requests.get(f"{API}/listings", headers=h(USER_B))
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    for l in data:
        assert l["user_email"] == USER_B.lower()
    # User B has 0 listings
    assert len(data) == 0


def test_check_now():
    r = requests.post(f"{API}/listings/check-now", headers=h(USER_A), timeout=60)
    assert r.status_code == 200
    data = r.json()
    assert "checked" in data
    assert data["checked"] >= 1


def test_delete_listing_cascades():
    lid = listing_ids[0]
    r = requests.delete(f"{API}/listings/{lid}", headers=h(USER_A))
    assert r.status_code == 200
    assert r.json()["deleted"] is True
    # Verify gone
    r2 = requests.get(f"{API}/listings", headers=h(USER_A))
    assert all(l["id"] != lid for l in r2.json())
    # Delete again -> 404
    r3 = requests.delete(f"{API}/listings/{lid}", headers=h(USER_A))
    assert r3.status_code == 404


# ---- Settings ----
def test_get_settings():
    r = requests.get(f"{API}/settings", headers=h(USER_A))
    assert r.status_code == 200
    data = r.json()
    assert data["email"] == USER_A.lower()
    assert "shop_name" in data
    assert data["alert_on_price_undercut"] is True
    assert data["alert_on_similar_listing"] is True


def test_update_settings():
    payload = {
        "shop_name": "MyTestShop",
        "alert_on_price_undercut": False,
        "alert_on_similar_listing": False,
    }
    r = requests.put(f"{API}/settings", json=payload, headers=h(USER_A))
    assert r.status_code == 200
    data = r.json()
    assert data["shop_name"] == "MyTestShop"
    assert data["alert_on_price_undercut"] is False
    assert data["alert_on_similar_listing"] is False
    # Verify persisted
    r2 = requests.get(f"{API}/settings", headers=h(USER_A))
    assert r2.json()["shop_name"] == "MyTestShop"
    assert r2.json()["alert_on_price_undercut"] is False


# ---- Evidence ----
def test_evidence_empty_for_user_b():
    r = requests.get(f"{API}/evidence", headers=h(USER_B))
    assert r.status_code == 200
    assert r.json() == []


def test_evidence_download_404():
    r = requests.get(f"{API}/evidence/nonexistent-id/download", headers=h(USER_A))
    assert r.status_code == 404


# ---- Cleanup ----
def test_cleanup():
    # Delete remaining listings
    r = requests.get(f"{API}/listings", headers=h(USER_A))
    for l in r.json():
        requests.delete(f"{API}/listings/{l['id']}", headers=h(USER_A))
