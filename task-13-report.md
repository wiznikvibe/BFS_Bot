# Task 13 Report — UI rewrite + README

## Goal

Demo UI surfaces hybrid RAG outputs for personas **C001–C007**: route, data/policy citations, escalate banner, and agent trace. README and `.env.example` document the payments + policy PoC workflow.

## UI changes

| Area | Change |
|------|--------|
| Branding | Payments + Policy Q&A; session-scoped messaging |
| Personas | Chips filtered to C001–C007 with name, plan, status; sample question per persona |
| Answer panel | Route badge, confidence, resolved customer meta |
| Citations | Separate **Data citations** and **Policy citations** lists |
| Escalate | Visible banner when `escalate: true` (C003, C006) |
| Trace | Full-width agent trace panel |

Files: `src/bfs_bot/static/index.html`, `app.js`, `styles.css`.

## Docs

- `README.md` — quick start (`seed` / `ingest` / `api`), demo login table, suggested demo order, `pytest -m eval`
- `.env.example` — Postgres URL, seed count, session secret, optional LLM vars

## API contract tests

- `tests/test_api_contract.py` — `answer_response_to_dict` keys + `/api/ask` JSON shape with stub supervisor

## Tests

```
pytest -q                 → 119 passed
pytest -m eval -q         → 13 passed (matrix + security probes)
```

## Acceptance

- [x] C001–C007 persona chips and demo login table documented
- [x] UI shows route, data/policy citations, escalate banner, trace
- [x] README covers seed, ingest, api, eval command
- [x] AnswerResponse contract covered in tests
