from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent import ResearchLineageAgent
from .graph import InMemoryContextGraph
from .models import ExperimentRun


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

    findings = ResearchLineageAgent(graph).compare_and_write_back(
        baseline.run_id, candidate.run_id
    )
    print("RuleCraft")
    for finding in findings:
        print(f"- [{finding.finding_type}] {finding.summary}")
    print(f"Written tags: {sorted(graph.tags[candidate.solver_version])}")

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
                },
                indent=2,
            ),
            encoding="utf-8",
        )


if __name__ == "__main__":
    main()
