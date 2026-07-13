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


if __name__ == "__main__":
    unittest.main()
