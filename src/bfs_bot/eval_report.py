"""Milestone evaluation sign-off — runs the pytest ``eval`` marker suite."""

from __future__ import annotations

import subprocess
import sys

from bfs_bot.demo_data.scenarios import load_scenarios, load_security_probes

_MATRIX_IDS = [s.customer_id or s.path for s in load_scenarios()]
_PROBE_IDS = [p.probe_id for p in load_security_probes()]


def _print_summary() -> None:
    lines = (
        "BFS Bot evaluation harness",
        f"  Scenario matrix (M2a, {len(_MATRIX_IDS)}): {', '.join(_MATRIX_IDS)}",
        f"  Security probes (M2b, {len(_PROBE_IDS)}): {', '.join(_PROBE_IDS)}",
        "",
        "Running: pytest -m eval -v",
        "",
    )
    sys.stdout.write("\n".join(lines) + "\n")
    sys.stdout.flush()


def main() -> None:
    _print_summary()
    code = subprocess.call([sys.executable, "-m", "pytest", "-m", "eval", "-v"])
    raise SystemExit(code)


if __name__ == "__main__":
    main()
