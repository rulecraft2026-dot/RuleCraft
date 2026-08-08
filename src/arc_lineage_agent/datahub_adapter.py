from __future__ import annotations

from collections import defaultdict
from typing import Any

from .models import Asset, ExperimentRun, Finding, WorkflowReport


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
                from datahub.ingestion.graph.client import DataHubGraph
                from datahub.ingestion.graph.config import DatahubClientConfig
            except ImportError as error:
                raise RuntimeError(
                    'DataHub support requires: pip install -e ".[datahub]"'
                ) from error
            emitter = DataHubGraph(DatahubClientConfig(server=server, token=token))

        self.emitter = emitter
        self.runs: dict[str, ExperimentRun] = {}
        self.tags: dict[str, set[str]] = defaultdict(set)
        self.notes: dict[str, list[str]] = defaultdict(list)
        self.decision_reports: dict[str, list[WorkflowReport]] = defaultdict(list)

    def _emit_aspect(self, entity_urn: str, aspect: Any) -> None:
        """Wrap an aspect using the current DataHub SDK MCP contract."""

        from datahub.emitter.mcp import MetadataChangeProposalWrapper

        proposal = MetadataChangeProposalWrapper(
            entityUrn=entity_urn,
            aspect=aspect,
        )
        self.emitter.emit_mcp(proposal)

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
        self._emit_aspect(self.run_urn(run.run_id), properties)
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
        self._emit_aspect(self.run_urn(candidate.run_id), lineage)

    def add_asset(self, asset: Asset) -> None:
        """Seed a reproducible downstream demo asset in DataHub."""

        from datahub.metadata.schema_classes import DatasetPropertiesClass

        self._emit_aspect(
            asset.urn,
            DatasetPropertiesClass(
                name=asset.name,
                description=f"RuleCraft demo dependency owned by {asset.owner}.",
                customProperties={
                    "asset_type": asset.asset_type,
                    "owner": asset.owner,
                    "criticality": str(asset.criticality),
                },
            ),
        )

    def link_asset(self, upstream_urn: str, downstream_urn: str) -> None:
        from datahub.metadata.schema_classes import (
            DatasetLineageTypeClass,
            UpstreamClass,
            UpstreamLineageClass,
        )

        self._emit_aspect(
            downstream_urn,
            UpstreamLineageClass(
                upstreams=[UpstreamClass(dataset=upstream_urn, type=DatasetLineageTypeClass.TRANSFORMED)]
            ),
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
        self._emit_aspect(urn, tag_aspect)
        self._emit_aspect(urn, note_aspect)

    def downstream(
        self, run_id: str, max_depth: int = 4
    ) -> list[tuple[Asset, int, tuple[str, ...]]]:
        """Read transitive downstream lineage from DataHub's OpenAPI graph."""

        from datahub.ingestion.graph.openapi import LineageDirection

        start = self.run_urn(run_id)
        queue: list[tuple[str, int, tuple[str, ...]]] = [(start, 0, (start,))]
        visited = {start}
        result: list[tuple[Asset, int, tuple[str, ...]]] = []
        while queue:
            current, depth, path = queue.pop(0)
            if depth >= max_depth:
                continue
            scroll_id = None
            while True:
                page = self.emitter.scroll_lineage(
                    urns=[current],
                    direction=LineageDirection.DOWNSTREAM,
                    count=100,
                    scroll_id=scroll_id,
                )
                for relationship in page.relationships:
                    urn = relationship.downstream_urn
                    if urn in visited or urn == current:
                        continue
                    visited.add(urn)
                    next_path = path + (urn,)
                    asset = self._read_asset(urn, relationship.destination_entity_type)
                    result.append((asset, depth + 1, next_path))
                    queue.append((urn, depth + 1, next_path))
                scroll_id = getattr(page, "scroll_id", None)
                if not scroll_id:
                    break
        return result

    def write_decision(self, solver_version: str, report: WorkflowReport) -> None:
        """Remember the safety decision as inspectable DataHub metadata."""

        from datahub.emitter.mce_builder import make_tag_urn
        from datahub.metadata.schema_classes import (
            DatasetPropertiesClass,
            GlobalTagsClass,
            TagAssociationClass,
        )

        run = self._run_for_solver(solver_version)
        self.decision_reports[solver_version].append(report)
        self.tags[solver_version].add(f"rulecraft-{report.decision.status}")
        urn = self.run_urn(run.run_id)
        self._emit_aspect(
            urn,
            GlobalTagsClass(
                tags=[TagAssociationClass(tag=make_tag_urn(tag)) for tag in sorted(self.tags[solver_version])]
            ),
        )
        self._emit_aspect(
            urn,
            DatasetPropertiesClass(
                name=run.run_id,
                description=(
                    f"# RuleCraft release memory `{run.run_id}`\n\n"
                    f"**Decision:** {report.decision.status}\n\n"
                    f"**Reason:** {report.decision.reason}\n\n"
                    f"**Verification:** {'PASS' if report.verification_passed else 'FAIL'}\n\n"
                    "## Remediation\n\n" + "\n".join(f"- {item}" for item in report.remediation)
                ),
                customProperties={
                    "rulecraft_decision": report.decision.status,
                    "rulecraft_max_risk": str(report.decision.max_risk),
                    "rulecraft_impacted_assets": str(len(report.impacts)),
                    "rulecraft_verification": "pass" if report.verification_passed else "fail",
                },
            ),
        )

    def _read_asset(self, urn: str, entity_type: str) -> Asset:
        """Resolve useful display context while degrading safely on old DataHub servers."""

        name = urn.rsplit(",", 2)[-2] if "," in urn else urn
        owner = "unassigned"
        criticality = 1
        try:
            from datahub.metadata.schema_classes import DatasetPropertiesClass, GlobalTagsClass

            properties = self.emitter.get_aspect(urn, DatasetPropertiesClass)
            if properties is not None:
                if getattr(properties, "name", None):
                    name = properties.name
                custom = getattr(properties, "customProperties", {}) or {}
                owner = custom.get("owner", owner)
                entity_type = custom.get("asset_type", entity_type)
                try:
                    criticality = max(1, min(3, int(custom.get("criticality", criticality))))
                except (TypeError, ValueError):
                    pass
            tags = self.emitter.get_aspect(urn, GlobalTagsClass)
            tag_names = [tag.tag.lower() for tag in getattr(tags, "tags", [])]
            if any("critical" in tag or "tier_1" in tag for tag in tag_names):
                criticality = 3
            elif any("tier_2" in tag for tag in tag_names):
                criticality = 2
        except Exception:
            pass
        return Asset(urn=urn, name=name, asset_type=entity_type, owner=owner, criticality=criticality)

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
