# BFS Bot SME Credit Assistant PoC

A Python-first proof of concept for a multi-agent SME credit assistant. It answers questions by combining dummy PostgreSQL customer data with policy-document retrieval, while enforcing PII redaction before any LLM call.

## What It Demonstrates

- Synthetic SME BNPL/trade-credit customer data in PostgreSQL.
- Policy ingestion from the configured ePayLater privacy, terms, grievance, and collection-agency sources.
- A redaction gate that replaces customer PII before response generation.
- A multi-agent flow: router, customer retrieval, redaction, policy retrieval, compliance guard, response generation.
- A simple browser UI showing the answer, policy citations, redacted customer context, and agent trace.

## Quick Start

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

Open `http://localhost:8000`.

If `LLM_API_KEY` and `LLM_BASE_URL` are not set, the app uses a deterministic offline LLM adapter so the redaction and orchestration flow can be demonstrated without API spend.

## Useful Commands

```bash
python3 -m pytest
bfs-bot-seed
bfs-bot-ingest
bfs-bot-api
```

## Security Notes

- Users identify customers by synthetic IDs such as `SME-10023`; v1 does not support lookup by name, phone, PAN, GSTIN, or email.
- Raw PII disclosure requests are blocked before retrieval.
- Retrieved customer rows are redacted before prompt construction.
- The LLM adapter receives only redacted customer facts and retrieved policy chunks.
- Real `.env` files are ignored by git; keep API keys out of source control.

## Main Modules

- `bfs_bot.agents`: deterministic multi-agent orchestration and redaction gate.
- `bfs_bot.redaction`: field and pattern-based PII redaction.
- `bfs_bot.models`: PostgreSQL schema, including policy chunks and audit events.
- `bfs_bot.seed`: dummy SME customer data generator.
- `bfs_bot.ingestion`: policy-document fetch, extraction, chunking, and vector storage.
- `bfs_bot.api`: FastAPI app and demo UI.
