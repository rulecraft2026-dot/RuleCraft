from __future__ import annotations

from collections import defaultdict
from typing import Protocol

from .models import ExperimentRun, Finding


class ContextGraph(Protocol):
    """Boundary implemented by the in-memory graph and DataHub adapters."""

    def add_run(self, run: ExperimentRun) -> None: ...

    def get_run(self, run_id: str) -> ExperimentRun: ...

    def write_finding(self, solver_version: str, finding: Finding) -> None: ...


class InMemoryContextGraph:
    """Infrastructure-free adapter used by the demo and unit tests."""

    def __init__(self) -> None:
        self.runs: dict[str, ExperimentRun] = {}
        self.findings: dict[str, list[Finding]] = defaultdict(list)
        self.tags: dict[str, set[str]] = defaultdict(set)

    def add_run(self, run: ExperimentRun) -> None:
        if run.run_id in self.runs:
            raise ValueError(f"run already exists: {run.run_id}")
        self.runs[run.run_id] = run

    def get_run(self, run_id: str) -> ExperimentRun:
        try:
            return self.runs[run_id]
        except KeyError as error:
            raise KeyError(f"unknown run: {run_id}") from error

    def write_finding(self, solver_version: str, finding: Finding) -> None:
        self.findings[solver_version].append(finding)
        self.tags[solver_version].update(finding.tags)
