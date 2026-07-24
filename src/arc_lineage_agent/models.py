from __future__ import annotations

from dataclasses import dataclass, field


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
