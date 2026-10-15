# Task 9 Report — Thin E2E supervisor slice (C001 hybrid)

## M1 gate: C001 scenario

| Check | Result |
|-------|--------|
| Question | Why no 10% loyalty discount? |
| route | `hybrid` |
| data citation | `INV-1001` |
| policy citation | `loyalty-discount-policy` / `v3` |
| membership | ~9 months (signup 2026-01-15, as_of 2026-10-15) |
| requirement | 12 months (Loyalty v3) |
| eligible_from | 2027-01-15 |
| escalate | false |
| **M1 gate** | **PASS** |

## Tests

```
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src python3 -m pytest tests/test_supervisor_c001.py tests/ -q
98 passed
```

## Deliverables

- `src/bfs_bot/agents/supervisor.py` — routing, parallel structured + policy for loyalty hybrid, `/api/ask` path
- `src/bfs_bot/agents/reasoner.py` — criterion-by-criterion loyalty compare (tenure vs policy vs invoice)
- `src/bfs_bot/schemas.py` — `AnswerResponse` with route, confidence, data/policy citations, escalate, trace
- `src/bfs_bot/api.py` — `/api/ask` wired to `Supervisor` (session customer only)
- `tests/test_supervisor_c001.py` — sqlite seed + ingested policies

## Notes

- `llm.py` unchanged; C001 answer is deterministic via reasoner (offline M1 slice).
- Cross-customer mentions in questions return scope refusal without 500.
