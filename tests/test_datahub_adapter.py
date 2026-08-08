import unittest
from types import ModuleType
from unittest.mock import patch

from arc_lineage_agent.datahub_adapter import DataHubContextGraph
from arc_lineage_agent.models import ExperimentRun


class DataHubContextGraphHelpersTests(unittest.TestCase):
    def test_emit_aspect_uses_metadata_change_proposal_wrapper(self) -> None:
        class FakeProposal:
            def __init__(self, **kwargs: object) -> None:
                self.entityUrn = kwargs["entityUrn"]
                self.aspect = kwargs["aspect"]

        class RecordingEmitter:
            def __init__(self) -> None:
                self.proposals: list[FakeProposal] = []

            def emit_mcp(self, proposal: FakeProposal) -> None:
                self.proposals.append(proposal)

        fake_mcp = ModuleType("datahub.emitter.mcp")
        fake_mcp.MetadataChangeProposalWrapper = FakeProposal  # type: ignore[attr-defined]
        emitter = RecordingEmitter()
        graph = DataHubContextGraph(emitter=emitter)
        aspect = object()

        with patch.dict("sys.modules", {"datahub.emitter.mcp": fake_mcp}):
            graph._emit_aspect("urn:li:dataset:test", aspect)

        self.assertEqual(1, len(emitter.proposals))
        self.assertEqual("urn:li:dataset:test", emitter.proposals[0].entityUrn)
        self.assertIs(aspect, emitter.proposals[0].aspect)

    def test_mean_score(self) -> None:
        run = ExperimentRun("run-1", "v1", {"a": 1.0, "b": 0.5})
        self.assertEqual(0.75, DataHubContextGraph._mean_score(run))

    def test_empty_mean_score(self) -> None:
        run = ExperimentRun("run-1", "v1", {})
        self.assertEqual(0.0, DataHubContextGraph._mean_score(run))

    def test_downstream_reads_transitive_datahub_lineage(self) -> None:
        class Relationship:
            def __init__(self, downstream_urn: str, entity_type: str) -> None:
                self.downstream_urn = downstream_urn
                self.destination_entity_type = entity_type

        class Page:
            def __init__(self, relationships: list[Relationship]) -> None:
                self.relationships = relationships

        class FakeEmitter:
            def scroll_lineage(self, *, urns: list[str], **_: object) -> Page:
                if urns[0].endswith("rulecraft.experiment.candidate,PROD)"):
                    return Page([Relationship("urn:li:dataset:(urn:li:dataPlatform:arc,benchmark,PROD)", "dataset")])
                if "benchmark" in urns[0]:
                    return Page([Relationship("urn:li:mlModel:(arc,release,PROD)", "mlModel")])
                return Page([])

            def get_aspect(self, *_: object) -> None:
                return None

        graph = DataHubContextGraph(emitter=FakeEmitter())
        graph.runs["candidate"] = ExperimentRun("candidate", "v2", {})

        impacts = graph.downstream("candidate")

        self.assertEqual([1, 2], [depth for _, depth, _ in impacts])
        self.assertEqual("mlModel", impacts[1][0].asset_type)

    def test_read_asset_uses_datahub_properties(self) -> None:
        class Properties:
            name = "Production release"
            customProperties = {"owner": "ml-platform", "criticality": "3", "asset_type": "mlModel"}

        class FakeEmitter:
            def get_aspect(self, _urn: str, aspect: type) -> object | None:
                return Properties() if aspect.__name__ == "DatasetPropertiesClass" else None

        asset = DataHubContextGraph(emitter=FakeEmitter())._read_asset("urn:test", "dataset")

        self.assertEqual("Production release", asset.name)
        self.assertEqual("ml-platform", asset.owner)
        self.assertEqual(3, asset.criticality)
        self.assertEqual("mlModel", asset.asset_type)


if __name__ == "__main__":
    unittest.main()
