from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent import ResearchLineageAgent
from .graph import InMemoryContextGraph
from .models import Asset, ExperimentRun


def load_runs(path: Path) -> tuple[ExperimentRun, ExperimentRun]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    runs = []
    for item in payload["runs"]:
        runs.append(
            ExperimentRun(
                run_id=item["run_id"],
                solver_version=item["solver_version"],
                task_scores=item["task_scores"],
                hypothesis=item.get("hypothesis", ""),
            )
        )
    if len(runs) != 2:
        raise ValueError("the demo input must contain exactly two runs")
    return runs[0], runs[1]


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the RuleCraft regression demo")
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("examples/arc_experiment_runs.json"),
        help="JSON file containing a baseline and candidate run",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="optional path for the generated findings JSON",
    )
    args = parser.parse_args()

    baseline, candidate = load_runs(args.input)
    graph = InMemoryContextGraph()
    graph.add_run(baseline)
    graph.add_run(candidate)

    # Reproducible mirror of the DataHub lineage used by the signature demo.
    assets = [
        Asset("benchmark:arc-hard", "ARC Hard Benchmark", "dataset", "eval-team", 3),
        Asset("model:solver-release", "Solver Production Release", "mlModel", "ml-platform", 3),
        Asset("dashboard:leaderboard", "Research Leaderboard", "dashboard", "research-ops", 2),
    ]
    for asset in assets:
        graph.add_asset(asset)
    graph.link_asset(candidate.run_id, assets[0].urn)
    graph.link_asset(assets[0].urn, assets[1].urn)
    graph.link_asset(assets[0].urn, assets[2].urn)

    report = ResearchLineageAgent(graph).protect_release(
        baseline.run_id, candidate.run_id
    )
    findings = list(report.findings)
    print("RuleCraft")
    for finding in findings:
        print(f"- [{finding.finding_type}] {finding.summary}")
    print(f"Written tags: {sorted(graph.tags[candidate.solver_version])}")
    print(f"Release gate: {report.decision.status} (risk {report.decision.max_risk}/100)")
    print(f"Impacted assets: {len(report.impacts)}; verification: {'PASS' if report.verification_passed else 'FAIL'}")

    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(
                {
                    "candidate_solver": candidate.solver_version,
                    "tags": sorted(graph.tags[candidate.solver_version]),
                    "findings": [
                        {
                            "task_id": finding.task_id,
                            "type": finding.finding_type,
                            "delta": finding.delta,
                            "summary": finding.summary,
                            "tags": list(finding.tags),
                        }
                        for finding in findings
                    ],
                    "signature_feature": "Counterfactual Experiment Blast-Radius Gate",
                    "decision": {
                        "status": report.decision.status,
                        "reason": report.decision.reason,
                        "max_risk": report.decision.max_risk,
                    },
                    "impacts": [
                        {
                            "urn": impact.asset.urn,
                            "name": impact.asset.name,
                            "type": impact.asset.asset_type,
                            "owner": impact.asset.owner,
                            "depth": impact.depth,
                            "risk_score": impact.risk_score,
                            "path": list(impact.path),
                        }
                        for impact in report.impacts
                    ],
                    "remediation": list(report.remediation),
                    "verification_passed": report.verification_passed,
                    "metrics": report.metrics,
                },
                indent=2,
            ),
            encoding="utf-8",
        )


if __name__ == "__main__":
    main()
