from __future__ import annotations

import unittest

from sec_capsules.core.observation import build_observation_packet


class ObservationTest(unittest.TestCase):
    def test_observation_respects_small_budget(self) -> None:
        structured = {
            "assets": [{"type": "asset.v1", "value": "example.com"}],
            "findings": [
                {
                    "title": f"Finding {idx}",
                    "severity": "medium",
                    "confidence": "high",
                    "affected": f"https://example.com/{idx}",
                    "evidence_refs": [f"artifact://run/a.jsonl#L{idx}"],
                }
                for idx in range(20)
            ],
            "services": [],
            "endpoints": [{"url": f"https://example.com/{idx}"} for idx in range(50)],
        }
        packet = build_observation_packet(
            run_id="run_test",
            tool="nuclei",
            structured=structured,
            token_budget=120,
        )
        self.assertLessEqual(packet["budget"]["estimated_tokens"], 120)
        self.assertTrue(packet["hidden_from_model"]["raw_output"])
        self.assertFalse(packet["hidden_from_model"]["secrets_redacted"])
        self.assertEqual(50, packet["result_counts"]["endpoints"]["total"])
        self.assertEqual(
            50,
            packet["result_counts"]["endpoints"]["retained"]
            + packet["result_counts"]["endpoints"]["omitted"],
        )

    def test_observation_exposes_parser_diagnostics_when_budget_allows(self) -> None:
        packet = build_observation_packet(
            run_id="run_ffuf",
            tool="ffuf",
            structured={
                "assets": [],
                "services": [],
                "endpoints": [{"url": f"https://example.com/{idx}"} for idx in range(30)],
                "findings": [],
                "parse_diagnostics": {
                    "input_records": 32,
                    "parsed_records": 31,
                    "invalid_records": 1,
                    "duplicate_records": 1,
                    "emitted_records": 30,
                    "partial": True,
                },
            },
            token_budget=800,
        )
        self.assertEqual(32, packet["parse_diagnostics"]["input_records"])
        self.assertEqual(30, packet["result_counts"]["endpoints"]["total"])
        self.assertEqual(12, packet["result_counts"]["endpoints"]["retained"])
        self.assertEqual(18, packet["result_counts"]["endpoints"]["omitted"])


if __name__ == "__main__":
    unittest.main()
