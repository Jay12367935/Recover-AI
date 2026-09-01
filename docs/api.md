# RecoverAI API

Base URL for local demo:

```text
http://127.0.0.1:8000
```

## Health

```http
GET /api/health
```

Returns model status, gateway mode, and whether webhook signatures are required.

## Metrics

```http
GET /api/metrics
```

Returns:

- total failed-payment exposure
- recovered amount
- recovery rate
- review queue count
- webhook count
- AI versus blind retry comparison
- model evaluation metadata

## Payments

```http
GET /api/payments?limit=80
GET /api/payments/{payment_id}
```

Payment detail includes a fresh agent decision with:

- failure analysis
- probabilities per recovery action
- expected values
- final policy-bounded action
- customer message

## Decide

```http
POST /api/payments/{payment_id}/decide
```

Creates an audit log entry for the latest agent decision without executing the recovery action.

## Execute

```http
POST /api/payments/{payment_id}/execute
```

Runs:

```text
failure analyzer -> model -> agent -> policy engine -> gateway simulator
```

Returns the decision, gateway payload, result, and recovered amount.

## Batch Run

```http
POST /api/batch-run
Content-Type: application/json

{
  "limit": 40
}
```

Processes a batch of currently failed payments.

## Batch Simulation

```http
POST /api/batch-simulation
Content-Type: application/json

{
  "count": 10000
}
```

Runs a synthetic batch simulation without changing the live database.

Returns:

- analyzed/classified/scored/policy-checked counts
- recovery-action evaluation count
- revenue at risk
- recoverable amount
- expected recovery opportunity
- realized recovery
- incremental revenue versus blind retry
- unnecessary-attempt reduction
- human escalations
- blocked actions

## Simulate Failed Payment

```http
POST /api/payments/simulate-failure
```

Adds one new synthetic failed payment to the live queue.

## User-Defined Payment Calculator

Preview a recovery decision without saving:

```http
POST /api/predict-recovery
Content-Type: application/json
```

Save a user-defined failed payment and calculate the decision:

```http
POST /api/payments/manual
Content-Type: application/json
```

Example body:

```json
{
  "customer_name": "Rahul S.",
  "amount": 4999,
  "method": "upi",
  "bank": "HDFC",
  "failure_code": "BANK_ERROR",
  "merchant_category": "ecommerce",
  "customer_previous_success": 8,
  "customer_previous_failures": 1,
  "attempt_number": 1,
  "time_since_last_attempt": 20,
  "hour": 22,
  "risk_score": 0.09
}
```

The saved payment is inserted into SQLite, logged in `agent_logs`, shown on the dashboard, and included in the report.

## Reset Demo

```http
POST /api/demo/reset
```

Clears customers, payments, recovery attempts, agent logs, and webhook events, then reseeds the demo.

## Report

```http
GET /api/report
GET /api/report?format=csv
```

Exports the recovery report as JSON or CSV.

## Razorpay Webhook

```http
POST /api/webhooks/razorpay
X-Razorpay-Signature: <signature>
x-razorpay-event-id: <event-id>
Content-Type: application/json
```

RecoverAI currently acts on:

```text
payment.failed
```

It accepts other events but marks them ignored.

Signature behavior:

- If `RAZORPAY_WEBHOOK_SECRET` is configured, the endpoint validates `X-Razorpay-Signature` using HMAC SHA256 over the raw body.
- If no secret is configured, the endpoint accepts requests in local demo mode.

Idempotency behavior:

- Duplicate `x-razorpay-event-id` values are ignored safely.

Reference: [Razorpay Validate and Test Webhooks](https://razorpay.com/docs/webhooks/validate-test/)
