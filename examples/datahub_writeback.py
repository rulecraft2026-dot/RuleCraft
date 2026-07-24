"""Run RuleCraft against a local or remote DataHub instance."""

from __future__ import annotations

import json
import os
from pathlib import Path

from arc_lineage_agent import DataHubContextGraph, ExperimentRun, ResearchLineageAgent


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
        findings = ResearchLineageAgent(graph).compare_and_write_back(
            runs[0].run_id, runs[1].run_id
        )
    finally:
        graph.close()

    print(f"Wrote {len(findings)} findings to DataHub at {server}")
    for finding in findings:
        print(f"- {finding.summary}")


if __name__ == "__main__":
    main()
