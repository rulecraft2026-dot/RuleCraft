from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


@dataclass(frozen=True)
class ExperimentRun:
    """A reproducible ARC solver evaluation."""

    run_id: str
    solver_version: str
    task_scores: dict[str, float]
    hypothesis: str = ""


@dataclass(frozen=True)
class Finding:
    """An agent finding that can be written back to DataHub."""

    task_id: str
    finding_type: str
    delta: float
    summary: str
    tags: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class Asset:
    """A DataHub entity that can be affected by an experiment decision."""

    urn: str
    name: str
    asset_type: str = "dataset"
    owner: str = "unassigned"
    criticality: int = 1


@dataclass(frozen=True)
class Impact:
    asset: Asset
    depth: int
    risk_score: int
    path: tuple[str, ...]


@dataclass(frozen=True)
class GateDecision:
    status: Literal["approved", "approval_required", "blocked"]
    reason: str
    max_risk: int


@dataclass(frozen=True)
class WorkflowReport:
    baseline_run_id: str
    candidate_run_id: str
    findings: tuple[Finding, ...]
    impacts: tuple[Impact, ...]
    decision: GateDecision
    remediation: tuple[str, ...]
    verification_passed: bool
    metrics: dict[str, int | float]
