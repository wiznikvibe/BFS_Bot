# Task 10 Report — Audit log

## Acceptance

| Check | Result |
|-------|--------|
| C001 ask persists audit row | PASS |
| `route` | `hybrid` |
| Tool params include `customer_id=C001` | PASS |
| `policy_chunk_ids` overlap loyalty v3 chunks | PASS |
| Full answer text stored | PASS |

## Tests

```
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src python3 -m pytest tests/test_audit.py tests/ -q
100 passed
```

## Deliverables

- `src/bfs_bot/audit.py` — `AuditLogger.record(event) -> int`, JSON detail payload, chunk id resolution
- `src/bfs_bot/agents/supervisor.py` — optional `audit=`; emits on generic, loyalty hybrid, and blocked paths
- `tests/test_audit.py` — C001 hybrid audit assertions

## Notes

- Audit is opt-in via `Supervisor(..., audit=AuditLogger(session_factory))`; existing tests unchanged without logger.
- `created_at` on `AuditEvent` is DB server default; `as_of` is stored in JSON detail.
