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


if __name__ == "__main__":
    unittest.main()
