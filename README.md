# FF GLORY — Updated with FamPay/RBC PAY gateway

See [FAMPAY_INTEGRATION.md](FAMPAY_INTEGRATION.md) for the two-service deployment and payment setup.

# FF GLORY — Admin Command Center (Pro)

Owner: **@NG_RAXX** (full access, always)

## Files
- `admin.html`  – admin panel (~507 KB, fully self-contained: icons/fonts inline, works offline)
- `index.html`  – user dashboard (SEO meta, favicon, Google login button, footer)
- `dashboard_server.py` – server + Google auth + roles + `/admin` route

## Google Login setup
1. console.cloud.google.com → APIs & Services → Credentials → OAuth Client ID (Web).
   Authorized JavaScript origins: your site URL (e.g. https://your-app.onrender.com)
2. Set env vars on server:
   `GOOGLE_CLIENT_ID=xxxxx.apps.googleusercontent.com`
   `OWNER_EMAILS=your_owner_gmail@gmail.com`
3. Open `https://your-site/admin` → Sign in with Google. (Server fills the client ID into admin.html.)
   For user dashboard also set `BG_PUB.GOOGLE_CLIENT_ID` in index.html.
4. Setup mode shows "Owner demo access" button — it disappears automatically once GOOGLE_CLIENT_ID is set.
   If you host admin.html statically, edit `BG_CONFIG` at the top: set `ALLOW_DEMO:false`.

## Roles
| Role | Access |
|---|---|
| Owner | Everything incl. Team & Roles, Backup |
| Admin | All except Team & Roles, Backup |
| Moderator | Overview, Bots, Instances, Users, Orders, Logs, Audit |
Owner adds members (Google email) in **Team & Roles**; saved in `team.json` on the server.

## Features
Google login · RBAC · Analytics chart · Broadcast banner · Team & Roles · Audit trail · JSON/CSV backup · 5 accent themes · Ctrl/⌘+K quick jump · mobile menu · demo data when backend is not connected.

## Note
`/api/overview, /api/users, /api/coupons, /api/orders, /api/instances, /api/settings` ke endpoints aapke main backend me hone chahiye (original admin.html wahi use karta tha). Unke bina panel demo data dikhata hai.

## v7 — New (screenshots + SaaS reference)
- **Command Chat** – assistant-style panel: `/start <guild_id> [region]`, `/stop <group_key>`, `/restart <group_key>`, `/status`, `/list`, `/stats`, `/guild <id>` (uses your existing server APIs)
- **Guild Members** – member list like in-game (this-week glory, ONLINE / IN TEAM status, x/20 counter, search)
- **Bot Lobby** – RBC bot accounts as friend-list cards (level, status, BATTLE)
- **Spectate** – squad HUD with prev/next bot, glory bar, time left
- **Light / Dark** toggle (bottom-right button), softer SaaS cards
- Live data comes from `/api/groups`; demo data shows when backend is not connected.


## FF GLORY update
- Font: **Orbitron** (both pages) · UI: pure black theme (light mode removed)
- Admin login (`/admin-x9k2` or `/admin`): user `NGANIL` / pass `NG1988` (override: env `ADMIN_USER`, `ADMIN_PASS`)
- Admin can generate **unlimited** coupons, format `FF-XXX-XXX-XXX`


## Deploy on Railway
See RAILWAY.md

- Buy credits (FamPay/UPI): users pay the QR, enter 12-digit UTR, server checks the payment mail in Gmail (IMAP App Password) and adds credits = amount / price. Each UTR works once. Admin -> Payments tab sets price, UPI ID, Gmail.

- RBC PAY gateway: Admin -> Payments -> RBC PAY gateway (API key). When set, users pay by QR and credits are added automatically (amount match, no UTR). Remove key = old UTR/Gmail mode.
