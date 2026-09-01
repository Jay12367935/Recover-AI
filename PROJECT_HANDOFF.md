# RecoverAI Project Handoff

This file is meant to be uploaded to another coding platform, AI assistant, teammate, or hackathon workspace so they can understand what has already been built and continue from the current state without guessing.

## Project Name

RecoverAI

## Hackathon / Buildathon Topic

Razorpay buildathon project under an AI Revenue Recovery theme.

The idea is to recover failed payments intelligently instead of blindly retrying every failed transaction.

## Core Concept

When a payment fails, RecoverAI:

1. Receives the failed-payment event.
2. Diagnoses the failure using deterministic error-code classification.
3. Predicts recovery probability for multiple possible actions.
4. Calculates expected recovered value in rupees.
5. Lets an AI-style recovery agent recommend the best action.
6. Sends the action through a deterministic policy engine.
7. Executes only safe actions through a Razorpay test-mode simulator.
8. Logs every decision, reason, policy result, and recovery attempt.
9. Shows a dashboard with recovered revenue and comparison against blind retry.

The important safety principle is:

```text
ML/Agent recommendation -> Policy engine -> Razorpay action
```

The model or agent should never directly control real money-moving APIs.

## Current Status

A complete runnable app has been built.

It includes:

- A backend server using only Python standard library by default.
- A pure-Python recovery probability model.
- Synthetic Razorpay-style payment data generation.
- Deterministic failure classification.
- Agentic recovery recommendation.
- Deterministic safety policy engine.
- Razorpay gateway simulator.
- SQLite persistence.
- Static dashboard frontend.
- API endpoints.
- Tests.
- Optional FastAPI entrypoint for teams that want to install dependencies.
- A pitch script for a 3-minute demo.
- Razorpay-style webhook endpoint with raw-body signature validation support.
- Demo reset endpoint.
- JSON and CSV recovery report export.
- Dashboard controls for webhook demo, new failure, report download, reset, and batch recovery.
- User-defined payment calculator with preview and save flows.
- Manual payment records persist to SQLite and appear in the report.
- Corrected metric definitions: payment recovery rate is recovered eligible payments divided by eligible opportunities; revenue recovery is shown separately.
- 10,000-payment batch simulation endpoint and dashboard section.
- Batch Simulation button now runs a real 10,000-payment synthetic simulation, completes each stage in the UI, and reveals actual generated results.
- Model card now shows ROC-AUC, precision, recall, and F1 instead of advertising raw accuracy.
- Merchant-level root-cause/degradation insights.
- AI recovery pipeline display: detect, diagnose, score, policy check, execute/measure.
- Policy gate and recovery guardrails screen.
- Stored audit trail on payment detail and report row click-through.
- Counterfactual hero metrics for RecoverAI versus blind retry.
- Simulator-created payments use `PAY_SIM_...`/`PAY_PREVIEW_...` IDs and carry the same customer history through Simulator -> Queue -> Decision -> Audit -> Report.
- Repeated decision logs are labeled as `Policy re-check before execution` so audit trails show deliberate revalidation instead of duplicate-looking agent decisions.

## Final Completion Update

The app has now moved beyond the first MVP. The final local version includes a working dashboard, synthetic ML model, agent decisioning, policy engine, Razorpay test-mode simulator, webhook ingestion, reset flow, report export, deployment files, API docs, and tests.

Verified final routes:

```text
GET  /
GET  /api/health
GET  /api/metrics
GET  /api/payments
GET  /api/payments/{payment_id}
GET  /api/report
GET  /api/report?format=csv
POST /api/payments/simulate-failure
POST /api/payments/{payment_id}/decide
POST /api/payments/{payment_id}/execute
POST /api/batch-run
POST /api/batch-simulation
POST /api/demo/reset
POST /api/webhooks/razorpay
```

The final smoke test confirmed:

- `/api/demo/reset` reseeds a clean demo.
- `/api/report?format=csv` exports a recovery report.
- `/api/webhooks/razorpay` processes a Razorpay-style `payment.failed` payload.
- The sample webhook payment recovers `₹4,999` for a smooth demo.
- `pay_showcase_18000` routes to human review for the safety story.
- `/api/batch-simulation` processes 10,000 synthetic failed payments without mutating the live database.
- The Batch Simulation UI shows `Analyzing`, `Classifying`, `Scoring`, `Applying policies`, and `Recovery actions` as completed counts, then reveals revenue/risk/recovery results.
- `/api/payments/{payment_id}` returns persisted audit-trail events for the decision and recovery timeline.
- The dashboard opens at `http://127.0.0.1:8000`.

## Important Environment Note

On the original machine:

- `node` exists.
- `npm` was broken.
- `python` was not on PATH.
- Codex bundled Python worked at:

```powershell
& "C:\Users\jayta\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" backend\app.py
```

The project was therefore built so the main demo does not require npm, React build tooling, FastAPI, scikit-learn, pandas, or external downloads.

On a normal machine with Python installed, run:

```bash
python backend/app.py
```

Then open:

```text
http://127.0.0.1:8000
```

## Verification Completed

Tests were run successfully:

```powershell
& "C:\Users\jayta\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m unittest discover -s tests
```

Result:

```text
........
----------------------------------------------------------------------
Ran 8 tests

OK
```

The server was also smoke-tested:

- `GET /`
- `GET /styles.css`
- `GET /app.js`
- `GET /api/health`
- `GET /api/metrics`
- `GET /api/payments`
- `GET /api/payments/pay_showcase_4999`
- `POST /api/batch-run`
- `POST /api/batch-simulation`
- `POST /api/payments/manual`
- `POST /api/predict-recovery`

A real bug was found and fixed during testing: SQLite was originally shared across threaded HTTP requests. The fix added `check_same_thread=False` plus a service-level `RLock`.

## Repository Structure

```text
.
├── README.md
├── PROJECT_HANDOFF.md
├── .env.example
├── .gitignore
├── package.json
├── backend
│   ├── app.py
│   ├── fastapi_app.py
│   ├── requirements.txt
│   └── recoverai
│       ├── __init__.py
│       ├── agent.py
│       ├── analyzer.py
│       ├── constants.py
│       ├── data.py
│       ├── db.py
│       ├── features.py
│       ├── ml.py
│       ├── policy.py
│       ├── razorpay_client.py
│       └── service.py
├── frontend
│   ├── index.html
│   ├── styles.css
│   └── app.js
├── tests
│   └── test_recoverai.py
└── docs
    └── pitch.md
```

Generated runtime files are intentionally ignored by git:

```text
backend/data/recoverai.sqlite
backend/data/recovery_model.json
backend/data/*.sqlite-*
```

The app regenerates those files on first run.

## File-by-File Summary

### `README.md`

Main project overview, architecture, quick start, API list, and Razorpay integration notes.

### `.env.example`

Environment variables for host, port, database path, model path, seed, and Razorpay test credentials.

### `.gitignore`

Ignores Python caches, Node artifacts, local env files, and generated model/database state.

### `package.json`

Lightweight metadata and convenience scripts:

```json
{
  "start": "python backend/app.py",
  "test": "python -m unittest discover -s tests"
}
```

This is mostly for platforms that expect a `package.json`. The default app itself does not require npm.

## Backend Details

### `backend/app.py`

Default runnable server.

It uses:

- `http.server.ThreadingHTTPServer`
- static file serving from `frontend/`
- JSON API endpoints
- no third-party dependencies

Run:

```bash
python backend/app.py
```

API routes:

```text
GET  /api/health
GET  /api/metrics
GET  /api/payments
GET  /api/payments/{payment_id}
POST /api/payments/simulate-failure
POST /api/payments/{payment_id}/decide
POST /api/payments/{payment_id}/execute
POST /api/batch-run
```

### `backend/fastapi_app.py`

Optional FastAPI version of the same API.

Use this only after installing:

```bash
pip install -r backend/requirements.txt
```

Then run:

```bash
uvicorn backend.fastapi_app:app --reload
```

### `backend/requirements.txt`

Optional dependencies:

- FastAPI
- Uvicorn
- Razorpay SDK
- python-dotenv

The current default demo does not need these.

### `backend/recoverai/constants.py`

Shared constants:

- recovery actions
- action labels
- action costs
- payment methods
- banks
- failure codes
- merchant categories
- failure-code group mappings

Recovery actions currently include:

```text
retry_immediate
retry_30m
payment_link
alternate_method
human_review
no_retry
```

### `backend/recoverai/data.py`

Synthetic data generator.

It creates:

- Indian-style customer names
- Razorpay-like failed payments
- payment methods
- banks
- failure codes
- customer history
- risk scores
- recovery labels

Important functions:

```python
generate_customers()
generate_historical_attempts()
generate_demo_failed_payments()
true_recovery_probability()
choose_historical_action()
```

`true_recovery_probability()` acts as the hidden simulation function used to generate labels and demo outcomes.

Showcase payments include:

- `pay_showcase_4999`: a `₹4,999` UPI `BANK_ERROR` case for the main recovery demo.
- `pay_showcase_18000`: a `₹18,000` high-risk card case for the safety/human-review demo.

### `backend/recoverai/features.py`

Feature engineering for the ML model.

Numeric features include:

- amount
- hour
- day of week
- previous successes
- previous failures
- attempt number
- time since last attempt
- customer age
- previous recovery success
- risk score

Categorical features include:

- payment method
- bank
- failure code
- merchant category
- recovery action

### `backend/recoverai/ml.py`

Pure-Python logistic regression model.

No scikit-learn dependency is required.

Capabilities:

- train from synthetic historical rows
- predict probability for one payment/action pair
- predict all recovery action probabilities
- evaluate accuracy, Brier score, and log loss
- save/load model as JSON

Class:

```python
RecoveryModel
```

### `backend/recoverai/analyzer.py`

Deterministic failure intelligence.

Maps failure codes such as:

```text
BANK_ERROR
NETWORK_ERROR
INSUFFICIENT_FUNDS
USER_CANCELLED
AUTHENTICATION_FAILED
PAYMENT_METHOD_ISSUE
RISK_CHECK_FAILED
UNKNOWN
```

into:

- category
- issue type
- severity
- human-readable summary
- evidence list

This intentionally does not use an LLM because payment failure codes should be deterministic.

### `backend/recoverai/agent.py`

Recovery agent.

It:

1. Calls the failure analyzer.
2. Gets probabilities from the model.
3. Computes expected value:

```text
expected value = amount * probability - action cost
```

4. Chooses an action.
5. Routes risky issues to human review.
6. Calls policy engine.
7. Produces:

- recommended action
- final policy-bounded action
- confidence
- expected recovery
- explanation
- personalized customer messages in English and Hinglish

Important safety behavior:

- `RISK_CHECK_FAILED` and risky issues go to `human_review`.
- The final action may differ from the model recommendation if policy blocks automation.

### `backend/recoverai/policy.py`

Deterministic safety gate.

Rules include:

- high-risk payment requires human review
- `RISK_CHECK_FAILED` requires human review
- amount above `₹10,000` requires human review
- retry limit blocks automated retries
- payment links and alternate-method flows are allowed only because customer completion is required
- `no_retry` has zero financial side effect

The policy returns:

```python
{
    "allowed": bool,
    "final_action": str,
    "status": "allowed" | "blocked" | "review",
    "reason": str,
    "controls": list[str]
}
```

### `backend/recoverai/razorpay_client.py`

Safe Razorpay gateway boundary.

Currently a simulator named `RazorpayGateway`.

It returns fake Razorpay-style references:

- retry references
- payment links
- alternate checkout links
- review case IDs
- no-retry skip IDs

This is where real Razorpay Test Mode integration should be added later.

Important: keep policy in front of this adapter.

### `backend/recoverai/db.py`

SQLite schema and persistence.

Tables:

```text
customers
payments
recovery_attempts
agent_logs
```

Important functions:

```python
init_db()
insert_payment()
get_payment()
list_payments()
log_decision()
log_attempt()
latest_decision()
latest_attempt()
payment_audit_trail()
metrics()
root_cause_insights()
seed_demo_data()
```

`metrics()` also computes the counterfactual comparison:

```text
Traditional blind retry vs RecoverAI
```

The dashboard definitions are now:

```text
Recovery Rate = recovered eligible payments / eligible recovery opportunities
Revenue Recovery = realized recovered rupees / recoverable rupees
Expected Recovery = model probability-weighted rupee opportunity
Realized Recovery = actually recovered amount in the simulation
```

### `backend/recoverai/service.py`

Application service layer.

Coordinates:

- model loading/training
- database initialization
- demo data seeding
- failure simulation
- decision generation
- execution
- batch run
- metrics

Important class:

```python
RecoverAIService
```

This class uses an `RLock` because the default server is threaded and SQLite access must be protected.

## Frontend Details

### `frontend/index.html`

Static dashboard shell.

Sections:

- sidebar navigation
- model status
- top metrics
- recovery simulator
- root-cause/degradation insights
- failed payment queue
- agent decision panel
- AI recovery pipeline
- probability bars
- policy gate
- recovery strategy timeline
- audit and safety guardrails
- report filters
- customer message
- safe execution button
- batch simulation
- counterfactual comparison

### `frontend/styles.css`

Responsive dashboard styling.

Design direction:

- operational fintech dashboard
- restrained and professional
- no marketing landing page
- no heavy framework dependency
- works on desktop and mobile

### `frontend/app.js`

Frontend logic.

It:

- fetches metrics and payments
- renders metric cards
- renders root-cause insights
- renders payment queue
- selects a payment
- renders fresh model decision
- shows probability bars
- shows expected rupee value for each recovery action
- shows why alternatives were not selected
- renders persisted audit trail events when available
- executes a safe action
- simulates a new failure
- runs AI batch recovery
- previews and saves user-defined failed payments
- filters and exports recovery reports

Important API calls:

```javascript
GET /api/metrics
GET /api/payments?limit=80
GET /api/payments/{id}
POST /api/payments/{id}/execute
POST /api/payments/simulate-failure
POST /api/batch-run
```

## Tests

### `tests/test_recoverai.py`

Coverage includes:

- model probability prediction
- policy block for high-risk action
- agent policy-bounded decision
- end-to-end service flow
- persisted payment audit trail
- Razorpay-style webhook processing and duplicate protection
- manual payment preview/save
- batch simulation metric consistency

Run:

```bash
python -m unittest discover -s tests
```

## Pitch Material

### `docs/pitch.md`

A 3-minute demo script.

Suggested demo order:

1. Explain that every failed payment is not the same.
2. Show the `₹4,999` UPI `BANK_ERROR` transaction.
3. Show probabilities for all actions.
4. Show the personalized message.
5. Execute the safe action.
6. Run batch recovery.
7. Show counterfactual comparison.
8. Select the `₹18,000` high-risk payment.
9. Show policy/human-review safety.

## Current Demo Story

The dashboard is designed to tell this story:

```text
Blind retry:
Retry everything.
Waste attempts.
Miss context.

RecoverAI:
Diagnose failure.
Predict action-level recovery odds.
Choose highest expected rupee value.
Apply deterministic safety policy.
Recover more revenue with fewer unnecessary attempts.
```

The main judge-facing line:

```text
RecoverAI does not blindly retry payments. It decides when, how, and whether recovery is worth attempting, and every financial action is bounded by deterministic safety policies.
```

## Known Generated State

During development, a local SQLite database and model JSON were generated under:

```text
backend/data/
```

They are ignored by git. Another platform should regenerate them automatically on first run.

If someone wants a clean demo reset, delete:

```text
backend/data/recoverai.sqlite
backend/data/recovery_model.json
```

Then run:

```bash
python backend/app.py
```

The app will rebuild the model and reseed the demo database.

## Important Improvements Still To Do

These are recommended next steps for another platform or AI assistant:

1. Add real Razorpay Test Mode integration in `backend/recoverai/razorpay_client.py`.
2. Add `.env` loading using `python-dotenv` if using the FastAPI version.
3. Replace SQLite with PostgreSQL for a more production-like architecture.
4. Add a real ML pipeline using scikit-learn, XGBoost, or LightGBM if dependencies are available.
5. Add model explainability such as feature contribution summaries.
6. Add merchant-level filters to the dashboard.
7. Add human-review queue approve/reject actions.
8. Add CSV upload for failed-payment history.
9. Add authentication if deploying publicly.
10. Add a React + Tailwind frontend if npm/pnpm works in the target environment.

## Suggested Razorpay Integration Plan

Keep the current interface in `RazorpayGateway.execute()`, but replace simulator internals with official Razorpay Test Mode calls.

Suggested mapping:

```text
payment_link       -> Razorpay Payment Links API
alternate_method   -> Payment Link or Checkout link with method hint
retry_immediate    -> retry workflow in merchant backend, not direct duplicate charge
retry_30m          -> scheduled retry job
human_review       -> internal queue only
no_retry           -> no Razorpay API call
```

Never implement:

```text
LLM -> Razorpay API -> Money
```

Keep:

```text
Agent recommendation -> Policy engine -> Gateway adapter
```

## Suggested Webhook Endpoint

Add something like:

```text
POST /api/webhooks/razorpay
```

Expected flow:

```text
Razorpay payment.failed webhook
-> validate webhook signature
-> normalize payment fields
-> insert payment
-> decide recovery action
-> if policy allows, execute safe action
-> log decision and attempt
-> dashboard updates
```

## Suggested Next AI Prompt

Upload this repository and this handoff file, then give the next platform/assistant this prompt:

```text
You are continuing a Razorpay buildathon project named RecoverAI. Read PROJECT_HANDOFF.md first. The project already has a runnable Python stdlib backend, static dashboard, synthetic recovery model, agent, policy engine, SQLite DB, tests, and pitch docs.

Your task is to continue from the current code without rewriting from scratch. First run the tests. Then inspect the dashboard and API. Next, improve the project for hackathon submission by adding real Razorpay Test Mode integration, PostgreSQL support, CSV upload for historical failures, and human-review approve/reject actions. Preserve the safety boundary: model/agent recommendation -> deterministic policy engine -> Razorpay gateway adapter.
```

## Submission Checklist

Before final submission, make sure:

- The dashboard opens at `http://127.0.0.1:8000`.
- `GET /api/metrics` works.
- `POST /api/batch-run` works.
- The `₹4,999` showcase payment demonstrates intelligent recovery.
- The `₹18,000` risky payment demonstrates policy/human review.
- The counterfactual section shows AI recovery versus blind retry.
- Tests pass.
- The README explains how to run.
- Razorpay Test Mode credentials are not committed.
- Any generated `backend/data/` files are either intentionally ignored or explicitly included only if needed for demo.

## Final Notes

The MVP was intentionally built to be dependency-light because the original environment had broken npm and no normal Python on PATH. This makes the project portable and easy to demo. A future version can upgrade the same architecture to FastAPI, PostgreSQL, React, Tailwind, Razorpay SDK, and a production ML model without changing the core story.
