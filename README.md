# SellerShield backend

Member 3's single-merchant sandbox backend: normalized capture ingestion, dispatch queue data, parsed label intake, deterministic verdicts, and audit history. Customer messages, label parsing, and seeded captures are simulated until teammates connect their modules. `PROTECTED` is a local rule result, not a PayPal guarantee.

## Run locally

Use Python 3.12 and Docker Desktop. In PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
docker compose up -d --wait
$env:DATABASE_URL='postgresql+psycopg://sellershield:local-only@localhost:5432/sellershield'
$env:MERCHANT_USERNAME='merchant'
$env:MERCHANT_PASSWORD='choose-a-long-random-password'
$env:CORS_ORIGINS='http://localhost:5173'
alembic upgrade head
python -m app.seed
uvicorn app.main:app --no-access-log
```

Environment variables are read from the process; `.env.example` documents them but is not automatically loaded. Use HTTPS when accessed remotely. Open `/docs` for schemas and interactive requests; authorize using the merchant credentials. `/health/ready` is public and checks database connectivity. Readiness assumes the release migration has run successfully.

Seed data contains three repeatable scenarios: `DEMO-CLEAN`, `DEMO-MISMATCH`, and `DEMO-UNCERTAIN`. Existing orders are never overwritten. Fixtures live in `fixtures/scenarios.py`, which also supplies example request bodies for teammates.

## Team integration

**PP:** mount your verified `/webhooks/paypal` router in this FastAPI app. After signature verification and trusted PayPal order retrieval, validate the normalized record with `Capture` and call the shared function within a transaction:

```python
from app.db import session_factory
from app.schemas import Capture
from app.service import Conflict, ingest_capture

sessions = session_factory()  # create once when your module initializes
with sessions.begin() as db:
    order = ingest_capture(db, Capture.model_validate(normalized_record))
```

Set `source` to `sandbox` for actual sandbox captures. The helper flushes but does not commit. Identical retries return the existing order; conflicting IDs or payloads raise `Conflict`. The app maps that exception to HTTP 409. Never expose this helper through an unverified capture intake endpoint. PayPal webhook routes need signature verification rather than merchant Basic auth.

**AI:** `POST /messages` accepts `{order_id, id, text, ai_analysis?}`. Analysis includes intent, confidence, an exact source quote, and optional US proposed address. Quotes must occur in the message. A message can arrive without analysis and later receive it using the same ID and unchanged text; conflicting replacements return 409. `POST /labels` accepts `{order_id, address, tracking_number, carrier, confidence}` as parsed JSON, not an image. Omitted confidence routes to REVIEW. The AI module owns uploads and vision calls.

**FE:** use HTTP Basic credentials at runtime, never committed or embedded in a production build. `GET /orders` returns newest-first full order views; `GET /orders/{id}` returns the same shape. Every merchant endpoint requires auth. CORS permits configured origins and Authorization headers. Store auth only for the demo session. Monetary values are decimal strings. Before evaluation, verdict/action/comparison match are null. Each order has a `source` marker. Requests use the shared contract fields; unknown fields are rejected.

## Decisions and persistence

Label evaluation and new message analysis update the current order and append an input snapshot/result with timestamp and rule version in one transaction. Postgres row locks serialize message and label changes per order. Audit history is persisted in `verdicts`; there is no mutation or public history endpoint in this slice.

US-only normalization preserves street numbers, unit identifiers, state, and full ZIP code. State input uses two-letter codes. Exact equality produces MATCH; normalized formatting equivalence produces NEAR_MATCH. Confirmed differences produce MISMATCH. Similar street/city spelling requires REVIEW rather than trusting fuzzy similarity. Missing fields, unparseable addresses, confidence below 0.90, ambiguous intent, or unconfirmed eligibility take precedence and produce REVIEW, even when comparison is MISMATCH. An absent AI analysis permits label-only evaluation. The signature rule is deferred.

Auth and CORS are deliberately for a single-merchant demo. No tenant isolation, real payments, refunds, tracking submission, dispute submission, or merchant override is implemented. Do not connect real customer data to a public demo.

## Verify

```powershell
python -m pytest -q
```

This runs rule tests and SQLite API checks. Postgres variants skip unless `TEST_DATABASE_URL` is set. Use a **separate, disposable database**: the test fixture applies migrations and deletes all rows in the four application tables after each test. Never use a shared or deployed database.

```powershell
# Create a separate database using your local Postgres administrator.
docker compose exec postgres createdb -U sellershield sellershield_test
$env:TEST_DATABASE_URL='postgresql+psycopg://sellershield:local-only@localhost:5432/sellershield_test'
python -m pytest -q
```

Tests cover address equivalence and mismatch, uncertainty precedence, retry conflicts, validation, authentication, rollback, immutable verdict snapshots, seed repeatability, and persistence across app recreation. SQLite checks do not prove Postgres locking behavior.

## Render

Connect this repository as a Render Blueprint using `render.yaml`. It provisions a paid web service and Postgres in the same region and injects the private connection string. Supply merchant credentials and the actual frontend origin when prompted. Migration runs as a pre-deploy command; the service starts only afterward. No secrets belong in the repository.

After deployment, check `/health/ready`, confirm `/orders` returns 401 without credentials, then authenticate and confirm queue access. Seed the database from the service shell only when synthetic scenarios are wanted. The readiness endpoint and Swagger schema do not expose buyer records. Request logs use route templates and omit bodies and rejected field values; server access logs are disabled to avoid logging identifiers in paths.

Deployment references: [Render FastAPI](https://render.com/docs/deploy-fastapi), [Render Postgres](https://render.com/docs/postgresql-creating-connecting).
