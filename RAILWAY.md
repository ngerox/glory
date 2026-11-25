# Railway deploy (FF GLORY)

1. Push this folder to a **private** GitHub repo (it contains account/token files).
2. railway.com -> New Project -> Deploy from GitHub repo -> select it. Build/start are automatic (Procfile / railway.json).
3. Service -> Variables:
   - `ADMIN_USER` = NGANIL      `ADMIN_PASS` = (choose a strong password)
   - `DATA_DIR` = /data
   - `RBC_PAY_API_KEY` = your RBC PAY key (or paste it later in Admin -> Payments -> RBC PAY gateway)
4. Service -> Volumes -> Add Volume -> mount path `/data` (keeps users, coupons, settings after redeploy).
5. Settings -> Networking -> Generate Domain. Open `https://<domain>/` (users) and `https://<domain>/admin-x9k2` (admin).
6. Admin Panel -> Payments: set price, UPI ID, Gmail + App Password, press "Test mailbox".

7. RBC PAY dashboard -> Webhooks: set `https://<domain>/api/pay/webhook` (optional; the site also polls, so credits arrive even without it).


## FamPay/RBC PAY gateway (updated bundle)
Deploy `fampay_gateway/` as a **second Railway service** with Root Directory `fampay_gateway/`. Follow `FAMPAY_INTEGRATION.md` to configure the merchant UPI/Gmail verification and connect its API key + HTTPS URL in FF GLORY Admin → Payments. The gateway must be a separate service because the supplied gateway is Flask while FF GLORY runs aiohttp.
