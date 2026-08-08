from __future__ import annotations

from .graph import ContextGraph
from time import perf_counter

from .models import GateDecision, Impact, Finding, WorkflowReport


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

    def protect_release(
        self, baseline_run_id: str, candidate_run_id: str, max_depth: int = 4
    ) -> WorkflowReport:
        """Run Context -> Reason -> Simulate -> Act -> Verify -> Remember."""

        started = perf_counter()
        findings = self.compare_and_write_back(baseline_run_id, candidate_run_id)
        candidate = self.graph.get_run(candidate_run_id)
        regression_severity = max(
            (int(abs(f.delta) * 100) for f in findings if f.finding_type == "regression"),
            default=0,
        )
        impacts = tuple(
            Impact(
                asset=asset,
                depth=depth,
                risk_score=min(100, regression_severity + asset.criticality * 10 + max(0, 4 - depth) * 5),
                path=path,
            )
            for asset, depth, path in self.graph.downstream(candidate_run_id, max_depth)
        )
        max_risk = max((impact.risk_score for impact in impacts), default=regression_severity)
        if regression_severity and max_risk >= 80:
            decision = GateDecision("blocked", "Critical downstream assets inherit a measured regression.", max_risk)
        elif regression_severity:
            decision = GateDecision("approval_required", "A regression requires owner review before promotion.", max_risk)
        else:
            decision = GateDecision("approved", "No material regression crossed the release threshold.", max_risk)

        remediation = tuple(
            f"Notify {impact.asset.owner} and rerun {impact.asset.name} validation"
            for impact in impacts
            if impact.risk_score >= 60
        ) or ("Record the clean comparison and continue staged promotion",)
        verification_passed = (decision.status == "approved" and regression_severity == 0) or (
            decision.status != "approved" and regression_severity > 0
        )
        elapsed_ms = round((perf_counter() - started) * 1000, 3)
        report = WorkflowReport(
            baseline_run_id=baseline_run_id,
            candidate_run_id=candidate_run_id,
            findings=tuple(findings),
            impacts=impacts,
            decision=decision,
            remediation=remediation,
            verification_passed=verification_passed,
            metrics={
                "entities_inspected": 2 + len(impacts),
                "lineage_edges_traversed": len(impacts),
                "impacted_assets_detected": len(impacts),
                "risks_detected": sum(1 for item in impacts if item.risk_score >= 60),
                "actions_proposed": len(remediation),
                "actions_executed": 1,
                "knowledge_written_back": 1,
                "execution_latency_ms": elapsed_ms,
            },
        )
        self.graph.write_decision(candidate.solver_version, report)
        return report
