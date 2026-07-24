import unittest

from arc_lineage_agent import (
    ExperimentRun,
    InMemoryContextGraph,
    ResearchLineageAgent,
)


class ResearchLineageAgentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.graph = InMemoryContextGraph()
        self.graph.add_run(
            ExperimentRun("base", "v1", {"a": 1.0, "b": 0.0, "stable": 0.5})
        )
        self.graph.add_run(
            ExperimentRun("next", "v2", {"a": 0.5, "b": 0.5, "stable": 0.5})
        )

    def test_detects_and_writes_regression_and_improvement(self) -> None:
        findings = ResearchLineageAgent(self.graph).compare_and_write_back(
            "base", "next"
        )

        self.assertEqual(["regression", "improvement"], [f.finding_type for f in findings])
        self.assertEqual(
            {"arc-regression", "arc-improvement", "needs-review"},
            self.graph.tags["v2"],
        )

    def test_ignores_small_changes(self) -> None:
        agent = ResearchLineageAgent(self.graph, regression_threshold=0.75)

        self.assertEqual([], agent.compare_and_write_back("base", "next"))

    def test_rejects_duplicate_runs(self) -> None:
        with self.assertRaisesRegex(ValueError, "run already exists"):
            self.graph.add_run(ExperimentRun("base", "v3", {}))


if __name__ == "__main__":
    unittest.main()
