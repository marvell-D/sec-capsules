from __future__ import annotations

import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

import yaml

from benchmarks.adapters import CapsuleToolAdapter, RawToolAdapter
from benchmarks.agent import run_reference_agent
from benchmarks.providers import ScriptedProvider
from benchmarks.reporting import build_report, render_markdown
from benchmarks.scoring import score_trace


ROOT = Path(__file__).resolve().parents[1]
SCENARIO_PATH = ROOT / "benchmarks" / "scenarios" / "crapi-recon-replay.yml"


class AgentBenchmarkTest(unittest.TestCase):
    def setUp(self) -> None:
        self.scenario = yaml.safe_load(SCENARIO_PATH.read_text(encoding="utf-8"))
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.work = Path(self.temp_dir.name)

    def test_raw_and_capsule_replay_pass_the_same_hidden_milestones(self) -> None:
        raw_adapter = RawToolAdapter(
            self.scenario,
            scenario_path=SCENARIO_PATH,
            runs_dir=self.work / "raw",
        )
        raw_trace = run_reference_agent(
            self.scenario,
            adapter=raw_adapter,
            provider=ScriptedProvider(_raw_script(raw_adapter.wordlist)),
            model="scripted-model",
            max_turns=8,
        )
        raw_trace["score"] = score_trace(raw_trace, self.scenario)

        capsule_adapter = CapsuleToolAdapter(
            self.scenario,
            scenario_path=SCENARIO_PATH,
            runs_dir=self.work / "capsule",
        )
        capsule_trace = run_reference_agent(
            self.scenario,
            adapter=capsule_adapter,
            provider=ScriptedProvider(_capsule_script()),
            model="scripted-model",
            max_turns=8,
        )
        capsule_trace["score"] = score_trace(capsule_trace, self.scenario)

        self.assertTrue(raw_trace["score"]["passed"])
        self.assertTrue(capsule_trace["score"]["passed"])
        self.assertEqual(4, raw_trace["score"]["milestones_passed"])
        self.assertEqual(4, capsule_trace["score"]["milestones_passed"])
        self.assertEqual(0, raw_trace["totals"]["policy_denials"])
        self.assertEqual(0, capsule_trace["totals"]["policy_denials"])

    def test_capsule_context_does_not_scale_with_repeated_raw_ffuf_records(self) -> None:
        scenario = deepcopy(self.scenario)
        source = ROOT / "src" / "sec_capsules" / "capsules" / "ffuf" / "fixtures" / "sample.jsonl"
        amplified = self.work / "ffuf-amplified.jsonl"
        amplified.write_text(source.read_text(encoding="utf-8") * 100, encoding="utf-8")
        scenario["fixtures"] = {
            "nmap": str(
                ROOT / "src" / "sec_capsules" / "capsules" / "nmap" / "fixtures" / "sample.xml"
            ),
            "ffuf": str(amplified),
        }
        scenario["scope_file"] = str(
            ROOT / "benchmarks" / "scenarios" / "crapi-scope.yml"
        )
        scenario["approval_file"] = str(
            ROOT / "benchmarks" / "scenarios" / "crapi-approval.yml"
        )

        raw_adapter = RawToolAdapter(
            scenario,
            scenario_path=SCENARIO_PATH,
            runs_dir=self.work / "raw-amplified",
        )
        raw_trace = run_reference_agent(
            scenario,
            adapter=raw_adapter,
            provider=ScriptedProvider(_raw_script(raw_adapter.wordlist)),
            model="scripted-model",
            max_turns=8,
        )
        capsule_trace = run_reference_agent(
            scenario,
            adapter=CapsuleToolAdapter(
                scenario,
                scenario_path=SCENARIO_PATH,
                runs_dir=self.work / "capsule-amplified",
            ),
            provider=ScriptedProvider(_capsule_script()),
            model="scripted-model",
            max_turns=8,
        )

        self.assertGreater(raw_trace["totals"]["raw_tool_output_bytes"], 300_000)
        self.assertLess(
            capsule_trace["totals"]["model_visible_tool_bytes"],
            raw_trace["totals"]["model_visible_tool_bytes"] * 0.1,
        )
        ffuf_calls = [
            call
            for call in capsule_trace["tool_calls"]
            if call["tool"] == "run_capsule" and call["input"].get("capsule_id") == "ffuf"
        ]
        diagnostics = ffuf_calls[0]["model_output"]["parse_diagnostics"]
        self.assertEqual(1800, diagnostics["input_records"])
        self.assertEqual(15, ffuf_calls[0]["model_output"]["result_counts"]["endpoints"]["total"])

    def test_raw_adapter_reports_policy_denial_separately(self) -> None:
        adapter = RawToolAdapter(
            self.scenario,
            scenario_path=SCENARIO_PATH,
            runs_dir=self.work / "denied",
        )
        result = adapter.invoke(
            {
                "type": "tool",
                "tool": "run_command",
                "input": {"argv": ["nmap", "--script", "vuln", "127.0.0.1"]},
            }
        )
        self.assertEqual("denied", result.status)
        self.assertFalse(result.policy["allowed"])

    def test_report_uses_provider_tokens_and_trace_schema_shape(self) -> None:
        adapter = RawToolAdapter(
            self.scenario,
            scenario_path=SCENARIO_PATH,
            runs_dir=self.work / "report",
        )
        trace = run_reference_agent(
            self.scenario,
            adapter=adapter,
            provider=ScriptedProvider(
                _raw_script(adapter.wordlist),
                usage_per_call={
                    "prompt_tokens": 123,
                    "completion_tokens": 17,
                    "total_tokens": 140,
                },
            ),
            model="scripted-model",
            max_turns=8,
        )
        trace["score"] = score_trace(trace, self.scenario)
        report = build_report([trace])
        self.assertEqual(420, trace["totals"]["total_tokens"])
        self.assertEqual(420, report["variants"]["raw"]["median_total_tokens"])
        self.assertIn("Safety denials", render_markdown(report))

        schema = json.loads(
            (ROOT / "benchmarks" / "schemas" / "agent_trace.v1.json").read_text(encoding="utf-8")
        )
        self.assertTrue(set(schema["required"]) <= set(trace))


def _raw_script(wordlist: Path) -> list[dict]:
    return [
        {
            "type": "tool",
            "tool": "run_command",
            "input": {
                "argv": [
                    "nmap",
                    "-sT",
                    "-Pn",
                    "-n",
                    "--reason",
                    "--max-retries",
                    "2",
                    "--host-timeout",
                    "60s",
                    "--max-rate",
                    "30",
                    "-p",
                    "5500,8025,8443,8888",
                    "-oX",
                    "-",
                    "127.0.0.1",
                ]
            },
        },
        {
            "type": "tool",
            "tool": "run_command",
            "input": {
                "argv": [
                    "ffuf",
                    "-w",
                    str(wordlist),
                    "-u",
                    "http://127.0.0.1:8888/FUZZ",
                    "-json",
                    "-s",
                    "-noninteractive",
                    "-t",
                    "5",
                    "-rate",
                    "10",
                    "-timeout",
                    "5",
                    "-maxtime",
                    "60",
                    "-mc",
                    "200,204,301,302,307,401,403,405",
                ]
            },
        },
        _final_action(),
    ]


def _capsule_script() -> list[dict]:
    return [
        {"type": "tool", "tool": "search_capsules", "input": {"query": "discovery"}},
        {"type": "tool", "tool": "get_capsule", "input": {"capsule_id": "nmap"}},
        {
            "type": "tool",
            "tool": "run_capsule",
            "input": {
                "capsule_id": "nmap",
                "target": "127.0.0.1",
                "profile": "safe",
                "arguments": {
                    "ports": [5500, 8025, 8443, 8888],
                    "packets_per_second": 30,
                },
            },
        },
        {"type": "tool", "tool": "get_capsule", "input": {"capsule_id": "ffuf"}},
        {
            "type": "tool",
            "tool": "run_capsule",
            "input": {
                "capsule_id": "ffuf",
                "target": "http://127.0.0.1:8888",
                "profile": "safe",
                "arguments": {"requests_per_second": 10},
            },
        },
        _final_action(),
    ]


def _final_action() -> dict:
    return {
        "type": "final",
        "answer": {
            "assets": [{"value": "127.0.0.1"}],
            "services": [{"port": 8443}, {"port": 8888}],
            "endpoints": [
                "http://127.0.0.1:8888/api",
                "http://127.0.0.1:8888/openapi.json",
            ],
            "findings": [],
            "evidence_refs": ["artifact://run/nmap.xml#L1", "artifact://run/ffuf.jsonl#L1"],
        },
    }


if __name__ == "__main__":
    unittest.main()
