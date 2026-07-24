from __future__ import annotations

from .graph import ContextGraph
from .models import Finding


class ResearchLineageAgent:
    """Compares two solver runs and persists actionable research findings."""

    def __init__(self, graph: ContextGraph, regression_threshold: float = 0.25):
        if regression_threshold <= 0:
            raise ValueError("regression_threshold must be positive")
        self.graph = graph
        self.regression_threshold = regression_threshold

    def compare_and_write_back(
        self, baseline_run_id: str, candidate_run_id: str
    ) -> list[Finding]:
        baseline = self.graph.get_run(baseline_run_id)
        candidate = self.graph.get_run(candidate_run_id)
        findings: list[Finding] = []

        task_ids = sorted(set(baseline.task_scores) | set(candidate.task_scores))
        for task_id in task_ids:
            old = baseline.task_scores.get(task_id, 0.0)
            new = candidate.task_scores.get(task_id, 0.0)
            delta = round(new - old, 4)

            if delta <= -self.regression_threshold:
                finding = Finding(
                    task_id=task_id,
                    finding_type="regression",
                    delta=delta,
                    summary=(
                        f"{task_id} regressed by {abs(delta):.2f} between "
                        f"{baseline.solver_version} and {candidate.solver_version}."
                    ),
                    tags=("arc-regression", "needs-review"),
                )
            elif delta >= self.regression_threshold:
                finding = Finding(
                    task_id=task_id,
                    finding_type="improvement",
                    delta=delta,
                    summary=(
                        f"{task_id} improved by {delta:.2f} between "
                        f"{baseline.solver_version} and {candidate.solver_version}."
                    ),
                    tags=("arc-improvement",),
                )
            else:
                continue

            self.graph.write_finding(candidate.solver_version, finding)
            findings.append(finding)

        return findings
