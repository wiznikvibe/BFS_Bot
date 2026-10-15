# BFS Bot — Hybrid RAG Payments + Policy Q&A PoC

Python proof of concept for a **read-only**, session-scoped assistant that answers billing and policy questions by combining structured PostgreSQL data (invoices, payments, loyalty tenure) with versioned policy retrieval. Demo personas **C001–C007** map to the developer brief scenario matrix.

## What it demonstrates

- Synthetic customers, invoices, payments, and discount codes seeded into PostgreSQL.
- Policy ingestion (loyalty, annual, late-fee, refund windows) with chunk embeddings for retrieval.
- Multi-agent supervisor: route classification (`hybrid` / `data` / `policy`), structured SQL tools, policy RAG, deterministic reasoners for brief scenarios.
- Session-bound demo auth — questions cannot switch to another customer’s data.
- Guardrails: PII lookup blocked, read-only tools, cross-customer refusal, security probes in eval.
- Browser UI showing **route**, **data & policy citations**, **escalate banner**, **agent trace**, and redacted context.

## Quick start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
docker compose up -d postgres
bfs-bot-seed
bfs-bot-ingest
bfs-bot-api
```

Open [http://localhost:8000](http://localhost:8000).

If `LLM_API_KEY` and `LLM_BASE_URL` are unset, the app uses a deterministic offline adapter so orchestration, citations, and escalation logic can be demoed without API spend.

### Demo login (password `demo123` for all)

| Username | Customer | Brief scenario |
|----------|----------|----------------|
| `asha`   | C001     | Loyalty not yet eligible (9 vs 12 months) |
| `ben`    | C002     | LOYALTY10 applied correctly |
| `carla`  | C003     | Eligible but no discount — **escalate** |
| `dev`    | C004     | November 2025 invoice under policy **v2** |
| `elena`  | C005     | Annual vs loyalty stacking conflict |
| `farid`  | C006     | Late fee inside grace — **escalate** |
| `gita`   | C007     | Refund outside 14-day window |

Sign in, pick a persona chip (optional), and ask. The **session customer always wins**; IDs embedded in the question or JSON body do not change scope.

### Suggested demo order

1. Sign in as `asha` (C001) — hybrid loyalty answer with invoice + policy citations.
2. `dev` (C004) — policy versioning for a historical invoice.
3. `carla` (C003) or `farid` (C006) — escalate banner for anomalies.
4. Security: as C001, ask about C002’s invoices — refusal without leaking existence.

## Commands

| Command | Purpose |
|---------|---------|
| `bfs-bot-seed` | Load C001–C007 named rows + filler customers/invoices |
| `bfs-bot-ingest` | Fetch/chunk/store policy documents |
| `bfs-bot-api` | FastAPI app + static UI |
| `pytest` | Unit/integration tests |
| `pytest -m eval -q` | Scenario matrix (C001–C007 + policy/data-only) + security probes |

## API sketch

- `POST /api/login` — `{ username, password }` → session cookie + `customer_id`
- `POST /api/ask` — `{ question, customer_id? }` (requires login) → `AnswerResponse` JSON plus `query_id` and `resolved_customer_id`
- `GET /api/session` — current session + public demo account hints
- `GET /api/demo-customers` — persona list for the UI chips

Core response fields: `answer`, `route`, `confidence`, `data_citations`, `policy_citations`, `escalate`, `trace`, `redacted_customer_context`, `redaction`.

## Security notes

- v1 does **not** support lookup by name, phone, PAN, GSTIN, or email.
- Tools are read-only; write/discount-apply requests are refused.
- Demo login uses signed cookies (`SESSION_SECRET`); not production identity.
- Keep real `.env` files out of git.

## Main modules

- `bfs_bot.agents.supervisor` — routing, hybrid orchestration, escalation
- `bfs_bot.agents.reasoner` — deterministic answers for matrix scenarios
- `bfs_bot.agents.structured` / `tools_sql` — scoped SQL retrieval
- `bfs_bot.demo_auth` — C001–C007 demo accounts
- `bfs_bot.ingestion` / `seed` — data and policy load
- `bfs_bot.api` — HTTP surface and static UI
