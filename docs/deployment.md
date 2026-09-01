# RecoverAI Deployment Guide

## Local Demo

```bash
python backend/app.py
```

Open:

```text
http://127.0.0.1:8000
```

## Optional FastAPI Mode

Install dependencies:

```bash
pip install -r backend/requirements.txt
```

Run:

```bash
uvicorn backend.fastapi_app:app --host 0.0.0.0 --port 8000
```

## Environment Variables

```text
RECOVERAI_HOST=127.0.0.1
RECOVERAI_PORT=8000
RECOVERAI_DB_PATH=backend/data/recoverai.sqlite
RECOVERAI_MODEL_PATH=backend/data/recovery_model.json
RECOVERAI_SEED=42
RECOVERAI_RAZORPAY_DRY_RUN=true
RAZORPAY_KEY_ID=
RAZORPAY_KEY_SECRET=
RAZORPAY_WEBHOOK_SECRET=
```

Use `RECOVERAI_RAZORPAY_DRY_RUN=true` for demos.

## Render / Railway Style Deployment

Start command:

```bash
python backend/app.py
```

For most cloud hosts, set:

```text
RECOVERAI_HOST=0.0.0.0
RECOVERAI_PORT=<platform-provided-port>
```

If the platform provides a `PORT` variable only, either map it to `RECOVERAI_PORT` or update `backend/app.py` to read `PORT`.

## Webhook Deployment Notes

Razorpay production webhooks must use a public HTTPS URL. Configure:

```text
https://your-domain.com/api/webhooks/razorpay
```

Set `RAZORPAY_WEBHOOK_SECRET` in your deployment environment and use the same secret in the Razorpay dashboard.

The webhook endpoint validates signatures against the raw request body and tracks `x-razorpay-event-id` to avoid duplicate processing, following Razorpay webhook validation and idempotency guidance.

Reference: [Razorpay Webhook Best Practices](https://razorpay.com/docs/webhooks/best-practices/)

## Production Upgrade Path

The current MVP is deliberately dependency-light. For a production-like buildathon final:

1. Use FastAPI mode.
2. Move SQLite to PostgreSQL.
3. Add a background queue for webhook processing.
4. Replace the simulator in `backend/recoverai/razorpay_client.py` with Razorpay Test Mode SDK calls.
5. Keep the deterministic policy engine before any Razorpay API call.

