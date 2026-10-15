"""Synthetic demo fixtures for the Hybrid RAG Payments POC."""

from bfs_bot.demo_data.generator import DemoDataset, generate_demo
from bfs_bot.demo_data.scenarios import (
    Scenario,
    SecurityProbe,
    load_scenarios,
    load_security_probes,
)

__all__ = [
    "DemoDataset",
    "Scenario",
    "SecurityProbe",
    "generate_demo",
    "load_scenarios",
    "load_security_probes",
]
