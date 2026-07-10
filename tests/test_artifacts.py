from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from sec_capsules.core.artifacts import ArtifactStore, artifact_ref


class ArtifactStoreTest(unittest.TestCase):
    def test_reads_bounded_snippet_from_artifact_reference(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = ArtifactStore(Path(tmp))
            store.write_text(
                run_id="run_test",
                produced_by="nuclei",
                name="output.jsonl",
                content="one\ntwo\nthree\n",
            )
            snippet = store.read_ref(artifact_ref("run_test", "output.jsonl", 2))
            self.assertEqual("two", snippet["content"])
            self.assertEqual(2, snippet["start_line"])

    def test_rejects_path_traversal(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = ArtifactStore(Path(tmp))
            with self.assertRaises(ValueError):
                store.read_ref("artifact://run_test/artifacts/../../secret.txt")


if __name__ == "__main__":
    unittest.main()
