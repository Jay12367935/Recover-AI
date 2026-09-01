from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi import Header, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from recoverai.service import create_service


service = create_service()
app = FastAPI(title="RecoverAI", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict:
    return service.health()


@app.get("/api/metrics")
def get_metrics() -> dict:
    return service.metrics()


@app.get("/api/options")
def get_options() -> dict:
    from recoverai.constants import BANKS, FAILURE_CODES, MERCHANT_CATEGORIES, PAYMENT_METHODS

    return {
        "payment_methods": PAYMENT_METHODS,
        "banks": BANKS,
        "failure_codes": FAILURE_CODES,
        "merchant_categories": MERCHANT_CATEGORIES,
    }


@app.get("/api/payments")
def get_payments(limit: int = 80) -> dict:
    return {"payments": service.payments(limit=limit)}


@app.get("/api/payments/{payment_id}")
def get_payment(payment_id: str) -> dict:
    payment = service.payment_detail(payment_id)
    if not payment:
        raise HTTPException(status_code=404, detail="payment_not_found")
    return payment


@app.post("/api/payments/simulate-failure")
def simulate_failure() -> dict:
    return service.simulate_failure()


@app.post("/api/payments/manual")
def create_manual_payment(payload: dict) -> dict:
    try:
        return service.create_manual_payment(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/predict-recovery")
def predict_recovery(payload: dict) -> dict:
    try:
        return service.preview_manual_payment(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/demo/reset")
def reset_demo() -> dict:
    return service.reset_demo()


@app.post("/api/payments/{payment_id}/decide")
def decide(payment_id: str) -> dict:
    try:
        return service.decide(payment_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="payment_not_found") from exc


@app.post("/api/payments/{payment_id}/execute")
def execute(payment_id: str) -> dict:
    try:
        return service.execute(payment_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="payment_not_found") from exc


@app.post("/api/batch-run")
def batch_run(payload: dict | None = None) -> dict:
    limit = int((payload or {}).get("limit", 40))
    return service.batch_run(limit=limit)


@app.post("/api/batch-simulation")
def batch_simulation(payload: dict | None = None) -> dict:
    count = int((payload or {}).get("count", 10000))
    return service.batch_simulation(count=count)


@app.get("/api/report")
def report() -> dict:
    return service.report()


@app.post("/api/webhooks/razorpay")
async def razorpay_webhook(
    request: Request,
    x_razorpay_signature: str | None = Header(default=None),
    x_razorpay_event_id: str | None = Header(default=None),
) -> dict:
    raw_body = await request.body()
    result = service.ingest_razorpay_webhook(
        raw_body,
        {
            "x-razorpay-signature": x_razorpay_signature or "",
            "x-razorpay-event-id": x_razorpay_event_id or "",
        },
    )
    if not result.get("accepted"):
        raise HTTPException(status_code=401, detail=result)
    return result


app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")
