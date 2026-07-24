from __future__ import annotations

from collections import defaultdict
from typing import Any

from .models import ExperimentRun, Finding


class DataHubContextGraph:
    """DataHub-backed graph with lazy SDK imports."""

    def __init__(
        self,
        server: str = "http://localhost:8080",
        token: str | None = None,
        emitter: Any | None = None,
    ) -> None:
        if emitter is None:
            try:
                from datahub.emitter.rest_emitter import DatahubRestEmitter
            except ImportError as error:
                raise RuntimeError(
                    'DataHub support requires: pip install -e ".[datahub]"'
                ) from error
            emitter = DatahubRestEmitter(gms_server=server, token=token)

        self.emitter = emitter
        self.runs: dict[str, ExperimentRun] = {}
        self.tags: dict[str, set[str]] = defaultdict(set)
        self.notes: dict[str, list[str]] = defaultdict(list)

    @staticmethod
    def run_urn(run_id: str) -> str:
        from datahub.emitter.mce_builder import make_dataset_urn

        return make_dataset_urn(
            platform="arc",
            name=f"rulecraft.experiment.{run_id}",
            env="PROD",
        )

    def add_run(self, run: ExperimentRun) -> None:
        if run.run_id in self.runs:
            raise ValueError(f"run already exists: {run.run_id}")

        from datahub.metadata.schema_classes import DatasetPropertiesClass

        properties = DatasetPropertiesClass(
            name=run.run_id,
            description=(
                f"# RuleCraft experiment `{run.run_id}`\n\n"
                f"Solver: `{run.solver_version}`\n\n"
                f"Hypothesis: {run.hypothesis or 'Not recorded'}"
            ),
            customProperties={
                "solver_version": run.solver_version,
                "task_count": str(len(run.task_scores)),
                "mean_score": f"{self._mean_score(run):.4f}",
            },
        )
        self.emitter.emit_mcp(
            entityUrn=self.run_urn(run.run_id),
            aspectName="datasetProperties",
            aspect=properties,
        )
        self.runs[run.run_id] = run

    def get_run(self, run_id: str) -> ExperimentRun:
        try:
            return self.runs[run_id]
        except KeyError as error:
            raise KeyError(f"unknown run: {run_id}") from error

    def link_runs(self, baseline_run_id: str, candidate_run_id: str) -> None:
        """Write baseline -> candidate lineage to DataHub."""

        from datahub.metadata.schema_classes import (
            DatasetLineageTypeClass,
            UpstreamClass,
            UpstreamLineageClass,
        )

        baseline = self.get_run(baseline_run_id)
        candidate = self.get_run(candidate_run_id)
        lineage = UpstreamLineageClass(
            upstreams=[
                UpstreamClass(
                    dataset=self.run_urn(baseline.run_id),
                    type=DatasetLineageTypeClass.TRANSFORMED,
                )
            ]
        )
        self.emitter.emit_mcp(
            entityUrn=self.run_urn(candidate.run_id),
            aspectName="upstreamLineage",
            aspect=lineage,
        )

    def write_finding(self, solver_version: str, finding: Finding) -> None:
        """Persist cumulative tags and a Markdown research note."""

        from datahub.emitter.mce_builder import make_tag_urn
        from datahub.metadata.schema_classes import (
            DatasetPropertiesClass,
            GlobalTagsClass,
            TagAssociationClass,
        )

        run = self._run_for_solver(solver_version)
        urn = self.run_urn(run.run_id)
        self.tags[solver_version].update(finding.tags)
        self.notes[solver_version].append(
            f"- **{finding.finding_type}** `{finding.task_id}` "
            f"(delta {finding.delta:+.2f}): {finding.summary}"
        )
        tag_aspect = GlobalTagsClass(
            tags=[
                TagAssociationClass(tag=make_tag_urn(tag))
                for tag in sorted(self.tags[solver_version])
            ]
        )
        note_aspect = DatasetPropertiesClass(
            name=run.run_id,
            description=(
                f"# RuleCraft experiment `{run.run_id}`\n\n"
                f"Solver: `{run.solver_version}`\n\n"
                "## Agent findings\n\n"
                + "\n".join(self.notes[solver_version])
            ),
            customProperties={
                "solver_version": run.solver_version,
                "finding_count": str(len(self.notes[solver_version])),
            },
        )
        self.emitter.emit_mcp(
            entityUrn=urn, aspectName="globalTags", aspect=tag_aspect
        )
        self.emitter.emit_mcp(
            entityUrn=urn, aspectName="datasetProperties", aspect=note_aspect
        )

    def close(self) -> None:
        close = getattr(self.emitter, "close", None)
        if close is not None:
            close()

    def _run_for_solver(self, solver_version: str) -> ExperimentRun:
        matches = [
            run for run in self.runs.values() if run.solver_version == solver_version
        ]
        if len(matches) != 1:
            raise ValueError(
                f"expected one run for solver {solver_version!r}, found {len(matches)}"
            )
        return matches[0]

    @staticmethod
    def _mean_score(run: ExperimentRun) -> float:
        if not run.task_scores:
            return 0.0
        return sum(run.task_scores.values()) / len(run.task_scores)
