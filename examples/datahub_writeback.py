"""Run RuleCraft against a local or remote DataHub instance."""

from __future__ import annotations

import json
import os
from pathlib import Path

from arc_lineage_agent import Asset, DataHubContextGraph, ExperimentRun, ResearchLineageAgent


def load_runs(path: Path) -> list[ExperimentRun]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return [
        ExperimentRun(
            run_id=item["run_id"],
            solver_version=item["solver_version"],
            task_scores=item["task_scores"],
            hypothesis=item.get("hypothesis", ""),
        )
        for item in payload["runs"]
    ]


def main() -> None:
    server = os.getenv("DATAHUB_GMS_URL", "http://localhost:8080")
    token = os.getenv("DATAHUB_TOKEN")
    runs = load_runs(Path(__file__).with_name("arc_experiment_runs.json"))
    if len(runs) != 2:
        raise ValueError("expected one baseline and one candidate run")

    graph = DataHubContextGraph(server=server, token=token)
    try:
        for run in runs:
            graph.add_run(run)
        graph.link_runs(runs[0].run_id, runs[1].run_id)
        assets = [
            Asset(graph.run_urn("arc-hard-benchmark"), "ARC Hard Benchmark", owner="eval-team", criticality=3),
            Asset(graph.run_urn("solver-production-release"), "Solver Production Release", "mlModel", "ml-platform", 3),
            Asset(graph.run_urn("research-leaderboard"), "Research Leaderboard", "dashboard", "research-ops", 2),
        ]
        for asset in assets:
            graph.add_asset(asset)
        graph.link_asset(graph.run_urn(runs[1].run_id), assets[0].urn)
        graph.link_asset(assets[0].urn, assets[1].urn)
        graph.link_asset(assets[0].urn, assets[2].urn)
        report = ResearchLineageAgent(graph).protect_release(
            runs[0].run_id, runs[1].run_id
        )
    finally:
        graph.close()

    print(f"Wrote {len(report.findings)} findings to DataHub at {server}")
    for finding in report.findings:
        print(f"- {finding.summary}")
    print(f"Release gate: {report.decision.status} (risk {report.decision.max_risk}/100)")
    print(f"DataHub lineage edges traversed: {report.metrics['lineage_edges_traversed']}")
    print(f"Verification: {'PASS' if report.verification_passed else 'FAIL'}")


if __name__ == "__main__":
    main()
