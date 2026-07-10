from __future__ import annotations

import unittest
from pathlib import Path

from sec_capsules.core.parsers import parse_capsule_output
from sec_capsules.core.registry import CapsuleRegistry


class ParserTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = CapsuleRegistry()

    def read_fixture(self, capsule_id: str) -> str:
        capsule = self.registry.get(capsule_id)
        return (capsule.root / "fixtures" / "sample.jsonl").read_text(encoding="utf-8")

    def test_httpx_parser_outputs_services(self) -> None:
        capsule = self.registry.get("httpx")
        structured = parse_capsule_output(
            capsule,
            self.read_fixture("httpx"),
            run_id="run_test",
            artifact_name="httpx.jsonl",
        )
        self.assertEqual(2, len(structured["services"]))
        self.assertEqual(2, len(structured["endpoints"]))

    def test_katana_parser_outputs_deduped_endpoints(self) -> None:
        capsule = self.registry.get("katana")
        structured = parse_capsule_output(
            capsule,
            self.read_fixture("katana"),
            run_id="run_test",
            artifact_name="katana.jsonl",
        )
        self.assertEqual(3, len(structured["endpoints"]))

    def test_nuclei_parser_outputs_findings(self) -> None:
        capsule = self.registry.get("nuclei")
        structured = parse_capsule_output(
            capsule,
            self.read_fixture("nuclei"),
            run_id="run_test",
            artifact_name="nuclei.jsonl",
        )
        self.assertEqual(2, len(structured["findings"]))
        self.assertTrue(structured["findings"][0]["evidence_refs"][0].endswith("#L1"))


if __name__ == "__main__":
    unittest.main()

