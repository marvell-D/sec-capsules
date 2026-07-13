from __future__ import annotations

import json
import os
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.request import Request

from sec_capsules.evals.harness import load_data
from sec_capsules.evals.providers.siliconflow import SiliconFlowClient, evaluate_scenario


class FakeTransport:
    def __init__(self) -> None:
        self.requests: list[Request] = []
        self.chat_responses = [
            {"capsule_id": "nmap"},
            {
                "capsule_id": "nmap",
                "target": "127.0.0.1",
                "profile": "service",
                "arguments": {
                    "ports": [5500, 8025, 8443, 8888],
                    "packets_per_second": 20,
                },
            },
        ]

    def __call__(self, request: Request, timeout: float) -> dict:
        self.requests.append(request)
        if "/models?" in request.full_url:
            return {
                "object": "list",
                "data": [
                    {"id": "Qwen/Qwen3.6-27B"},
                    {"id": "another/chat-model"},
                ],
            }
        response = self.chat_responses.pop(0)
        return {
            "choices": [{"message": {"content": json.dumps(response)}}],
            "usage": {"prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120},
        }


class SiliconFlowProviderTest(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(__file__).resolve().parents[1]

    def test_two_stage_evaluation_uses_progressive_cards_and_grades_candidate(self) -> None:
        transport = FakeTransport()
        client = SiliconFlowClient(api_key="test-key", transport=transport)
        scenario = load_data(self.root / "evals" / "scenarios" / "nmap-crapi-services.yml")
        result = evaluate_scenario(scenario, client=client)

        self.assertEqual("Qwen/Qwen3.6-27B", result["model"])
        self.assertTrue(result["grade"]["passed"], result["grade"])
        self.assertEqual(
            ["select_capsule", "generate_arguments"],
            [item["stage"] for item in result["calls"]],
        )
        self.assertTrue(
            all(
                request.get_header("Authorization") == "Bearer test-key"
                for request in transport.requests
            )
        )

        selection_payload = json.loads(transport.requests[1].data.decode("utf-8"))
        parameter_payload = json.loads(transport.requests[2].data.decode("utf-8"))
        self.assertNotIn("command", selection_payload["messages"][1]["content"])
        self.assertNotIn("command", parameter_payload["messages"][1]["content"])
        self.assertIn("input_schema", parameter_payload["messages"][1]["content"])

    def test_requested_model_must_exist_in_live_account_list(self) -> None:
        client = SiliconFlowClient(api_key="test-key", transport=FakeTransport())
        with self.assertRaisesRegex(ValueError, "not available"):
            client.choose_model("missing/model")

    def test_api_key_has_no_cli_argument_or_implicit_fallback(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(ValueError, "SILICONFLOW_API_KEY"):
                SiliconFlowClient()


if __name__ == "__main__":
    unittest.main()
