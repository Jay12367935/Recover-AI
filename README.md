# RecoverAI

RecoverAI is a Razorpay buildathon project for intelligent failed-payment recovery. It diagnoses payment failures, predicts the best recovery action, routes the action through deterministic safety policies, and shows business impact against blind retry.

## What It Does

- Generates synthetic Razorpay-style failed-payment history.
- Trains a lightweight recovery probability model from scratch.
- Classifies failures using deterministic payment/error-code intelligence.
- Recommends recovery actions with expected rupee value.
- Enforces policy before any recovery action can execute.
- Simulates Razorpay recovery workflows in test/demo mode.
- Shows a live dashboard with recovered revenue, recovery rate, human-review queue, activity, and counterfactual comparison.
- Accepts Razorpay-style `payment.failed` webhooks with signature validation support.
- Exports a JSON or CSV recovery report for judging and merchant review.
- Lets a user enter their own failed-payment values and calculate recovery probabilities.
- Saves user-defined payments into SQLite and includes them in the report.

## Quick Start

Use the bundled Codex Python runtime on this machine:

```powershell
& "C:\Users\jayta\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" backend\app.py
```

Then open:

```text
http://127.0.0.1:8000
```

If you have Python on PATH, this also works:

```powershell
python backend\app.py
```

## Demo Flow

1. Open the dashboard and point to failed payments at risk.
2. Use the calculator form to enter your own failed payment.
3. Click **Calculate only** to preview the model decision without saving.
4. Click **Save and calculate** to store the payment in the database.
5. Show the predicted probability for retry, delayed retry, payment link, alternate method, human review, and no retry.
6. Show the policy result before execution.
7. Execute the approved action and watch recovered revenue update.
8. Open the report section and export CSV.
9. Try the webhook demo to show how Razorpay failed-payment events enter the system.
10. Run batch recovery and show AI recovery versus blind retry.
11. Select a risky high-value payment and show deterministic human-review blocking.

## Metric Definitions

RecoverAI separates payment-count metrics from rupee metrics so the dashboard remains financially defensible:

- **Revenue At Risk:** total value of failed-payment opportunities in the database.
- **Recoverable:** value of opportunities where policy allows an automated recovery action.
- **Expected Recovery Opportunity:** model-estimated rupee recovery for eligible actions.
- **Realized Recovery:** money actually recovered by executed recovery attempts in the simulation.
- **Recovery Rate:** recovered payments divided by eligible recovery opportunities.
- **Revenue Recovery:** realized recovery divided by recoverable value.
- **Incremental Revenue:** RecoverAI realized recovery minus the blind-retry baseline.

## Architecture

```text
Failed Payment Event
        |
        v
Failure Analyzer
        |
        v
Recovery Probability Model
        |
        v
Agent Recommendation
        |
        v
Policy Engine
   /            \
Allowed      Review/Block
   |
   v
Razorpay Gateway Adapter
        |
        v
Recovered Revenue + Audit Log
```

## Project Structure

```text
backend/
  app.py                    Stdlib HTTP API + static file server
  fastapi_app.py            Optional FastAPI entrypoint
  requirements.txt          Optional FastAPI/Razorpay dependencies
  recoverai/
    agent.py                Recovery decision logic
    analyzer.py             Deterministic failure classification
    data.py                 Synthetic data generation
    db.py                   SQLite schema and metrics
    features.py             Model feature engineering
    ml.py                   Pure-Python logistic model
    policy.py               Safety controls
    razorpay_client.py      Test-mode gateway adapter
frontend/
  index.html                Dashboard shell
  styles.css                Polished responsive UI
  app.js                    Dashboard interactivity
tests/
  test_recoverai.py         Core model/agent/policy checks
docs/
  api.md                    API reference
  deployment.md             Deployment notes
  pitch.md                  3-minute demo script
  sample_razorpay_webhook.json
```

## API Highlights

- `GET /api/metrics`
- `GET /api/payments`
- `GET /api/payments/{payment_id}`
- `POST /api/payments/simulate-failure`
- `POST /api/payments/manual`
- `POST /api/predict-recovery`
- `POST /api/payments/{payment_id}/decide`
- `POST /api/payments/{payment_id}/execute`
- `POST /api/batch-run`
- `POST /api/batch-simulation`
- `POST /api/demo/reset`
- `POST /api/webhooks/razorpay`
- `GET /api/report`
- `GET /api/report?format=csv`

See [docs/api.md](docs/api.md) for request/response details.

## Razorpay Integration Notes

The project runs in safe simulated mode by default. For a real Razorpay Test Mode demo, replace `recoverai/razorpay_client.py` internals with the official Razorpay SDK or REST calls and keep the same policy boundary:

```text
Model/Agent recommendation -> Policy decision -> Razorpay API call
```

Never let an LLM or free-form agent directly call money-moving APIs.

Webhook handling follows Razorpay's raw-body HMAC SHA256 validation pattern when `RAZORPAY_WEBHOOK_SECRET` is configured, and uses `x-razorpay-event-id` for duplicate-event protection.

Reference: [Razorpay webhook validation docs](https://razorpay.com/docs/webhooks/validate-test/)

## Deployment

For simple platforms:

```bash
python backend/app.py
```

Set:

```text
RECOVERAI_HOST=0.0.0.0
RECOVERAI_RAZORPAY_DRY_RUN=true
```

The app reads `RECOVERAI_PORT` or the platform's `PORT` variable.
