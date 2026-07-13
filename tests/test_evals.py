from __future__ import annotations

import unittest
from pathlib import Path

from sec_capsules.evals.harness import benchmark_planner, grade_candidate, load_data


class EvalHarnessTest(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(__file__).resolve().parents[1]

    def test_reference_candidate_passes_provider_neutral_scenario(self) -> None:
        scenario = load_data(self.root / "evals" / "scenarios" / "katana-shallow.yml")
        candidate = load_data(
            self.root / "evals" / "candidates" / "reference" / "katana-shallow.json"
        )
        result = grade_candidate(scenario, candidate)
        self.assertTrue(result["passed"], result)
        self.assertLess(
            result["context_metrics"]["progressive_estimated_tokens"],
            result["context_metrics"]["raw_full_estimated_tokens"],
        )

    def test_invalid_or_over_privileged_candidate_is_scored_without_execution(self) -> None:
        scenario = load_data(self.root / "evals" / "scenarios" / "katana-shallow.yml")
        candidate = {
            "capsule_id": "katana",
            "target": "https://example.com",
            "profile": "safe",
            "arguments": {"depth": 5, "requests_per_second": 10},
        }
        result = grade_candidate(scenario, candidate)
        self.assertFalse(result["passed"])
        self.assertFalse(result["checks"]["argument_constraints"])

        malformed = {**candidate, "arguments": {"depth": "deep", "requests_per_second": "fast"}}
        malformed_result = grade_candidate(scenario, malformed)
        self.assertFalse(malformed_result["passed"])
        self.assertTrue(malformed_result["errors"])

    def test_planner_benchmark_reports_overhead_without_a_timing_gate(self) -> None:
        result = benchmark_planner(
            "katana",
            target="https://example.com",
            arguments={"depth": 1},
            iterations=20,
        )
        self.assertEqual(20, result["iterations"])
        self.assertGreaterEqual(result["p95_ms"], 0)


if __name__ == "__main__":
    unittest.main()
