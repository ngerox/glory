# FF GLORY + FamPay/RBC PAY integration

This bundle contains two deployable services:

- **FF GLORY** (project root): existing aiohttp dashboard and game automation service.
- **FamPay/RBC PAY gateway** (`fampay_gateway/`): the Flask payment gateway from the supplied `fampay.zip`.

## Payment flow

1. Deploy `fampay_gateway/` as a separate Railway service (set its Root Directory to `fampay_gateway/`).
2. Configure the gateway's admin panel and create/activate a merchant account.
3. In the gateway merchant Integrations page, configure the receiving UPI ID and Gmail App Password used by the supplied gateway's mailbox verification.
4. Copy that merchant's API key.
5. In FF GLORY Admin → Payments → RBC PAY gateway, set:
   - Gateway base URL = the public HTTPS URL of the deployed gateway service
   - Gateway API key = the merchant API key
   Save and use **Test gateway**.
6. In gateway dashboard → Webhooks, optionally set `https://YOUR-FF-GLORY-DOMAIN/api/pay/webhook`.

FF GLORY's existing order flow already calls `/api/create_order.php`, polls `/api/verify.php`, and credits the user's account only after the gateway reports `SUCCESS`. The older direct Gmail UTR form is automatically hidden in the user UI when the gateway is enabled.

## FamPay ID / UTR verification

The supplied gateway supports QR checkout and verifies the submitted UTR/transaction reference against the merchant's incoming payment email. A 10-digit FamPay ID by itself is not proof that money was received, and this gateway does not expose an independent official FamPay-ID verification API. Do not credit accounts from a user-entered ID alone. The trusted gateway's verified order status is the source of truth.

## Deployment notes

- Deploy the root FF GLORY service as before (`Procfile`: `python main.py`).
- Deploy the gateway as a second service from the `fampay_gateway/` directory (`Procfile`: Gunicorn + `wsgi:app`).
- Set `RBC_PAY_GATEWAY_URL` and `RBC_PAY_API_KEY` on the FF GLORY service, or enter them in Admin → Payments.
- Set the gateway's required environment values using `fampay_gateway/.env.example`. Do not copy the old `instance/` database, secret keys, or `.env` file from the source archive; a fresh gateway creates its own secrets and database.
- Keep both services on HTTPS. Use a persistent volume for each service's data/database.

## Important

The source archives included runtime account/token data and local gateway secrets. Those transient files were deliberately excluded from this updated ZIP. Configure your own credentials and restore any runtime data from your own secure backup if required.


## Verification behavior in this revision

- FamPay and FamApp wording is treated as the same sender-filter family, fixing the screenshot case where the email subject says "FamApp" but the configured filter says "fampay".
- The hosted checkout accepts an optional 10-digit FamPay ID alongside the required UTR / Transaction ID. A successful FamPay ID is recorded and cannot be used for a second successful order. The UTR also remains single-use: the gateway has a unique database index on successful UTRs, and the FF GLORY legacy checker rejects already-recorded UTRs.
- The FamPay ID is an additional reference and duplicate-use guard, not standalone proof of payment. Credits are still issued only after the gateway confirms the matching amount and UTR from the merchant's incoming payment email.
- The QR is generated from the order's UPI URI, which includes that order's exact INR amount and order reference. A different order amount therefore produces a different QR payload.
- "Test mailbox" only checks that Gmail IMAP login works. It does not simulate a payment or prove that a live transaction has arrived. Real verification can remain pending briefly while FamApp/FamPay's payment email reaches the merchant inbox; retry after it arrives.
