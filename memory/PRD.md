# EtsyWatch — PRD

## Original Problem Statement
Full-stack web app for Etsy sellers to monitor their listings 24/7 for price changes and copies. Users paste Etsy listing URLs; app scrapes title/price/seller, runs daily checks, searches Etsy for similar listings, flags potential copies (>=70% title similarity), saves evidence screenshots, and emails alerts with cease-and-desist text and a link to Etsy's IP report form.

## User Personas
- Independent Etsy sellers worried about copycats and price wars
- Small craft/handmade businesses without legal/IP resources

## Core Requirements (static)
- Email-based session auth (no password)
- Daily scheduled job (24h) + manual "Check Now"
- Real Etsy scraping (httpx + BeautifulSoup, best-effort)
- Title similarity via difflib.SequenceMatcher; copy flagged at >=0.70
- Evidence vault with placeholder screenshots
- Resend email integration (currently MOCKED — key empty, logs only)
- Free plan: 3 listings; Pro: unlimited ($9/mo, no payment yet)

## Architecture
- Backend: FastAPI + Motor (Mongo) + APScheduler + httpx + BeautifulSoup + Resend SDK
- Frontend: React + react-router + Shadcn/UI + sonner + Outfit/Plus Jakarta Sans
- Auth: header `X-User-Email`, axios interceptor adds it from `localStorage["etsywatch_email"]`

## Implemented (2026-06-06)
- Landing page (hero, signup form, features strip, pricing Free/Pro)
- Dashboard (URL input, add, listings table, status badges, delete row, Check Now)
- Alert Settings (email read-only, shop_name editable, two toggles, save)
- Evidence Vault (grid of screenshots with similarity %, download)
- Backend routes: /api/auth/signup, /api/auth/me, /api/listings (CRUD), /api/listings/check-now, /api/settings (GET/PUT), /api/evidence, /api/evidence/{id}/download
- Scheduler: 24h interval AsyncIOScheduler
- Price-change detection, copy-detection with deduped evidence, alert email rendering (price-change + copy + cease-and-desist)
- 100% backend pytest pass (17/17); UI flows verified

## Backlog (P0/P1/P2)
- P0 (deferred): Plug in real Resend API key when provided by user
- P1: Real screenshot capture (Playwright) instead of placeholder image
- P1: Replace difflib with rapidfuzz token-set ratio for better robustness
- P1: Mongo indexes (users.email, listings.user_email, evidence.listing_id)
- P2: Lifespan context manager (replace deprecated on_event)
- P2: Stripe integration for Pro plan
- P2: Rate-limit signup; magic-link verification
- P2: Local caching of evidence screenshot bytes
- P2: Tighten CORS for production
