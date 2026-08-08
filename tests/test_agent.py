import unittest

from arc_lineage_agent import (
    Asset,
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

    def test_blast_radius_blocks_regressed_candidate_and_remembers_decision(self) -> None:
        benchmark = Asset("benchmark:hard", "Hard benchmark", owner="eval", criticality=3)
        release = Asset("model:prod", "Production model", "mlModel", "platform", 3)
        self.graph.add_asset(benchmark)
        self.graph.add_asset(release)
        self.graph.link_asset("next", benchmark.urn)
        self.graph.link_asset(benchmark.urn, release.urn)

        report = ResearchLineageAgent(self.graph).protect_release("base", "next")

        self.assertEqual("blocked", report.decision.status)
        self.assertEqual(2, report.metrics["lineage_edges_traversed"])
        self.assertTrue(report.verification_passed)
        self.assertEqual(("next", "benchmark:hard", "model:prod"), report.impacts[1].path)
        self.assertEqual(report, self.graph.decisions["v2"][0])
        self.assertIn("rulecraft-blocked", self.graph.tags["v2"])

    def test_blast_radius_approves_candidate_without_regressions(self) -> None:
        graph = InMemoryContextGraph()
        graph.add_run(ExperimentRun("base", "v1", {"a": 0.5}))
        graph.add_run(ExperimentRun("next", "v2", {"a": 1.0}))

        report = ResearchLineageAgent(graph).protect_release("base", "next")

        self.assertEqual("approved", report.decision.status)
        self.assertTrue(report.verification_passed)


if __name__ == "__main__":
    unittest.main()
