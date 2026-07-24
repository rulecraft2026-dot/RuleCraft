import unittest

from arc_lineage_agent.datahub_adapter import DataHubContextGraph
from arc_lineage_agent.models import ExperimentRun


class DataHubContextGraphHelpersTests(unittest.TestCase):
    def test_mean_score(self) -> None:
        run = ExperimentRun("run-1", "v1", {"a": 1.0, "b": 0.5})
        self.assertEqual(0.75, DataHubContextGraph._mean_score(run))

    def test_empty_mean_score(self) -> None:
        run = ExperimentRun("run-1", "v1", {})
        self.assertEqual(0.0, DataHubContextGraph._mean_score(run))


if __name__ == "__main__":
    unittest.main()
