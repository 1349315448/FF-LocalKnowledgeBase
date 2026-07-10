from __future__ import annotations

import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from ff_local_knowledge.detection import detect_environment


class DetectionTests(unittest.TestCase):
    def test_detect_reports_runtime_without_writing_workspace(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            marker = root / "marker.txt"
            marker.write_text("unchanged", encoding="utf-8")
            before = set(root.rglob("*"))

            result = detect_environment(root)

            self.assertEqual("1.0", result["schema_version"])
            self.assertEqual(str(root.resolve()), result["workspace_root"])
            self.assertIn(result["os"]["value"], {"windows", "linux", "macos"})
            self.assertEqual("high", result["python"]["confidence"])
            self.assertEqual(before, set(root.rglob("*")))
            self.assertEqual("unchanged", marker.read_text(encoding="utf-8"))

    def test_detect_recognizes_agent_instruction_files(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "AGENTS.md").write_text("generic", encoding="utf-8")
            (root / "CLAUDE.md").write_text("claude", encoding="utf-8")

            result = detect_environment(root)

            adapters = {item["value"] for item in result["agents"]}
            self.assertIn("generic", adapters)
            self.assertIn("claude", adapters)

    def test_detect_recognizes_supported_agent_executables(self):
        with TemporaryDirectory() as directory:
            def fake_which(command: str) -> str | None:
                if command in {"git", "codex", "claude"}:
                    return f"/tools/{command}"
                return None

            with patch("ff_local_knowledge.detection.shutil.which", side_effect=fake_which):
                result = detect_environment(directory)

            adapters = {item["value"]: item for item in result["agents"]}
            self.assertIn("codex", adapters)
            self.assertIn("claude", adapters)
            self.assertIn("PATH:codex", adapters["codex"]["evidence"])

    def test_detect_recognizes_project_workbuddy_skill_directory(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".workbuddy-ai" / "skills").mkdir(parents=True)

            result = detect_environment(root)

            adapters = {item["value"]: item for item in result["agents"]}
            self.assertIn("workbuddy", adapters)
            self.assertIn(".workbuddy-ai/skills", adapters["workbuddy"]["evidence"])


if __name__ == "__main__":
    unittest.main()
