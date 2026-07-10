import hashlib
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from ff_local_knowledge.scanning import render_markdown_report, scan_workspace


def tree_hash(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


class ScanningTests(unittest.TestCase):
    def test_scan_finds_stack_rules_and_evidence_without_mutation(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "pyproject.toml").write_text(
                '[project]\nname = "synthetic"\nrequires-python = ">=3.11"\n',
                encoding="utf-8",
            )
            (root / ".editorconfig").write_text("root = true\n", encoding="utf-8")
            (root / "AGENTS.md").write_text("# Instructions\n", encoding="utf-8")
            (root / "package.json").write_text(
                '{"name":"synthetic","scripts":{"test":"node --test","lint":"eslint ."}}',
                encoding="utf-8",
            )
            (root / "tests").mkdir()
            (root / "tests" / "test_sample.py").write_text("pass\n", encoding="utf-8")
            (root / ".github" / "workflows").mkdir(parents=True)
            (root / ".github" / "workflows" / "ci.yml").write_text("name: ci\n", encoding="utf-8")
            before = tree_hash(root)

            report = scan_workspace(root)

            self.assertEqual(before, tree_hash(root))
            self.assertEqual("1.0", report["schema_version"])
            self.assertEqual(64, len(report["snapshot_hash"]))
            python_finding = next(item for item in report["findings"] if item["value"] == "python")
            self.assertEqual("high", python_finding["confidence"])
            self.assertEqual("manifest-detector", python_finding["source"])
            self.assertTrue(any("pyproject.toml" in evidence for evidence in python_finding["evidence"]))
            self.assertTrue(any(item["source"] == "repository-rules" for item in report["standards"]))
            self.assertIn("Confirmation required", render_markdown_report(report))
            self.assertIn("generic", report["proposed_adapters"])
            self.assertIn(".agents/skills/", report["proposed_writes"])
            self.assertIn("Proposed Installation", render_markdown_report(report))
            self.assertTrue(any(item["value"] == "tests" for item in report["architecture"]["test_containers"]))
            self.assertTrue(any(item["value"] == ".github/workflows/ci.yml" for item in report["architecture"]["ci"]))
            commands = {item["value"] for item in report["architecture"]["commands"]}
            self.assertIn("npm test", commands)
            self.assertIn("npm run lint", commands)

    def test_scan_ignores_secrets_dependencies_binary_and_large_files(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".env").write_text("TOKEN=secret-value", encoding="utf-8")
            (root / "node_modules").mkdir()
            (root / "node_modules" / "package.json").write_text('{"private": true}', encoding="utf-8")
            (root / ".agent" / "sdd").mkdir(parents=True)
            (root / ".agent" / "sdd" / "package.json").write_text('{"private": true}', encoding="utf-8")
            (root / ".agent" / "sdd" / "go.mod").write_text("module ignored\n", encoding="utf-8")
            (root / "image.png").write_bytes(b"\x89PNG\x00secret-value")
            (root / "large.txt").write_bytes(b"x" * 1_100_000)
            (root / "package.json").write_text('{"name":"safe"}', encoding="utf-8")

            report = scan_workspace(root)
            serialized = json.dumps(report)

            self.assertNotIn("secret-value", serialized)
            evidence = json.dumps([item["evidence"] for item in report["findings"]])
            self.assertNotIn("node_modules", evidence)
            self.assertNotIn(".agent", evidence)
            self.assertNotIn("image.png", evidence)
            self.assertNotIn("large.txt", evidence)
            self.assertIn("package.json", evidence)
            self.assertNotIn("go", {item["value"] for item in report["findings"]})


if __name__ == "__main__":
    unittest.main()
