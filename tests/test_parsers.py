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
        artifact_name = str(capsule.raw.get("artifacts", {}).get("primary", "sample.jsonl"))
        fixture_name = f"sample{Path(artifact_name).suffix}"
        return (capsule.root / "fixtures" / fixture_name).read_text(encoding="utf-8")

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

    def test_nmap_parser_outputs_assets_services_and_line_evidence(self) -> None:
        capsule = self.registry.get("nmap")
        structured = parse_capsule_output(
            capsule,
            self.read_fixture("nmap"),
            run_id="run_test",
            artifact_name="nmap.xml",
        )
        self.assertEqual(1, len(structured["assets"]))
        self.assertEqual("127.0.0.1", structured["assets"][0]["value"])
        self.assertEqual(4, len(structured["services"]))
        self.assertEqual([5500, 8025, 8443, 8888], [item["port"] for item in structured["services"]])
        self.assertEqual("https://127.0.0.1:8443", structured["services"][2]["url"])
        self.assertRegex(structured["services"][0]["evidence_refs"][0], r"#L\d+$")

    def test_nmap_parser_salvages_hosts_completed_before_truncated_xml(self) -> None:
        capsule = self.registry.get("nmap")
        raw = self.read_fixture("nmap").replace("</nmaprun>", "<truncated")
        structured = parse_capsule_output(
            capsule,
            raw,
            run_id="run_test",
            artifact_name="nmap.xml",
        )
        self.assertEqual(1, len(structured["assets"]))
        self.assertEqual(4, len(structured["services"]))


if __name__ == "__main__":
    unittest.main()
