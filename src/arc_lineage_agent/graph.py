from __future__ import annotations

from collections import defaultdict
from typing import Protocol

from .models import Asset, ExperimentRun, Finding, WorkflowReport


class ContextGraph(Protocol):
    """Boundary implemented by the in-memory graph and DataHub adapters."""

    def add_run(self, run: ExperimentRun) -> None: ...

    def get_run(self, run_id: str) -> ExperimentRun: ...

    def write_finding(self, solver_version: str, finding: Finding) -> None: ...

    def downstream(self, run_id: str, max_depth: int = 4) -> list[tuple[Asset, int, tuple[str, ...]]]: ...

    def write_decision(self, solver_version: str, report: WorkflowReport) -> None: ...


class InMemoryContextGraph:
    """Infrastructure-free adapter used by the demo and unit tests."""

    def __init__(self) -> None:
        self.runs: dict[str, ExperimentRun] = {}
        self.findings: dict[str, list[Finding]] = defaultdict(list)
        self.tags: dict[str, set[str]] = defaultdict(set)
        self.assets: dict[str, Asset] = {}
        self.edges: dict[str, set[str]] = defaultdict(set)
        self.decisions: dict[str, list[WorkflowReport]] = defaultdict(list)

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

    def add_asset(self, asset: Asset) -> None:
        self.assets[asset.urn] = asset

    def link_asset(self, upstream_urn: str, downstream_urn: str) -> None:
        if downstream_urn not in self.assets:
            raise KeyError(f"unknown downstream asset: {downstream_urn}")
        self.edges[upstream_urn].add(downstream_urn)

    def downstream(
        self, run_id: str, max_depth: int = 4
    ) -> list[tuple[Asset, int, tuple[str, ...]]]:
        start = run_id
        queue: list[tuple[str, int, tuple[str, ...]]] = [(start, 0, (start,))]
        visited = {start}
        result: list[tuple[Asset, int, tuple[str, ...]]] = []
        while queue:
            current, depth, path = queue.pop(0)
            if depth >= max_depth:
                continue
            for urn in sorted(self.edges[current]):
                if urn in visited:
                    continue
                visited.add(urn)
                next_path = path + (urn,)
                result.append((self.assets[urn], depth + 1, next_path))
                queue.append((urn, depth + 1, next_path))
        return result

    def write_decision(self, solver_version: str, report: WorkflowReport) -> None:
        self.decisions[solver_version].append(report)
        self.tags[solver_version].add(f"rulecraft-{report.decision.status}")
