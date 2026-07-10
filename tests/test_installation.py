import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from ff_local_knowledge import transaction
from ff_local_knowledge.planning import create_install_plan
from ff_local_knowledge.scanning import scan_workspace
from ff_local_knowledge.knowledge import lint, query
from ff_local_knowledge.transaction import (
    InstallationError,
    apply_plan,
    doctor,
    rollback,
    uninstall,
)


class InstallationTests(unittest.TestCase):
    def _project(self, directory: str) -> Path:
        root = Path(directory)
        (root / "pyproject.toml").write_text('[project]\nname="sample"\n', encoding="utf-8")
        return root

    def test_plan_apply_doctor_and_repeat_apply_are_transactional(self):
        with TemporaryDirectory() as directory:
            root = self._project(directory)
            report = scan_workspace(root)
            plan = create_install_plan(
                report,
                answers={"standards_confirmed": True},
                operations=[{"path": ".ff-knowledge/config.json", "content": '{"version":1}\n'}],
            )

            first = apply_plan(plan)
            second = apply_plan(plan)
            health = doctor(root)

            self.assertEqual("applied", first["status"])
            self.assertEqual("already_applied", second["status"])
            self.assertEqual("healthy", health["status"])
            self.assertTrue((root / ".ff-knowledge" / "config.json").exists())
            self.assertTrue((root / ".ffkb" / "runtime" / "journal" / f'{first["transaction_id"]}.json').exists())

    def test_apply_rejects_a_different_plan_while_an_installation_is_active(self):
        with TemporaryDirectory() as directory:
            root = self._project(directory)
            first_plan = create_install_plan(
                scan_workspace(root),
                answers={"standards_confirmed": True},
                operations=[{"path": ".ff-knowledge/config.json", "content": '{"version":1}\n'}],
            )
            apply_plan(first_plan)
            second_plan = create_install_plan(
                scan_workspace(root),
                answers={"standards_confirmed": True},
                operations=[{"path": ".ff-knowledge/config.json", "content": '{"version":2}\n'}],
            )

            with self.assertRaisesRegex(InstallationError, "different installation is already active"):
                apply_plan(second_plan)

    def test_apply_rejects_workspace_change_and_path_escape(self):
        with TemporaryDirectory() as directory:
            root = self._project(directory)
            report = scan_workspace(root)
            plan = create_install_plan(
                report,
                answers={"standards_confirmed": True},
                operations=[{"path": "AGENTS.md", "content": "managed\n"}],
            )
            (root / "pyproject.toml").write_text('[project]\nname="changed"\n', encoding="utf-8")

            with self.assertRaisesRegex(InstallationError, "snapshot"):
                apply_plan(plan)

            with self.assertRaisesRegex(ValueError, "allowed root"):
                create_install_plan(
                    scan_workspace(root),
                    answers={"standards_confirmed": True},
                    operations=[{"path": "../escape.txt", "content": "bad"}],
                )

    def test_plan_rejects_changes_made_after_scan(self):
        with TemporaryDirectory() as directory:
            root = self._project(directory)
            report = scan_workspace(root)
            (root / "new-source.py").write_text("VALUE = 2\n", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "scan snapshot"):
                create_install_plan(
                    report,
                    answers={"standards_confirmed": True},
                    operations=[{"path": "AGENTS.md", "content": "managed\n"}],
                )

    def test_plan_rejects_invalid_confirmation_and_operation_shapes(self):
        with TemporaryDirectory() as directory:
            root = self._project(directory)
            report = scan_workspace(root)

            invalid_cases = (
                ({"standards_confirmed": "yes"}, None, "standards_confirmed must be true"),
                ({"standards_confirmed": True, "adapters": "codex"}, None, "adapters must be a non-empty array"),
                ({"standards_confirmed": True, "standards": "one rule"}, None, "standards must be an array"),
                ({"standards_confirmed": True, "profile": "../secret"}, None, "profile must be one of"),
                ({"standards_confirmed": True, "locale": []}, None, "locale must be a string"),
                ({"standards_confirmed": True}, {"path": "AGENTS.md"}, "operations must be an array"),
                ({"standards_confirmed": True}, ["AGENTS.md"], "operation must be an object"),
            )
            for answers, operations, message in invalid_cases:
                with self.subTest(message=message), self.assertRaisesRegex(ValueError, message):
                    create_install_plan(report, answers=answers, operations=operations)

    def test_plan_rejects_sensitive_install_targets(self):
        with TemporaryDirectory() as directory:
            root = self._project(directory)
            report = scan_workspace(root)

            for target in (".env", ".ssh/config", "certificate.pem"):
                with self.subTest(target=target), self.assertRaisesRegex(ValueError, "sensitive path"):
                    create_install_plan(
                        report,
                        answers={"standards_confirmed": True},
                        operations=[{"path": target, "content": "unsafe"}],
                    )

    def test_managed_block_preserves_user_content_and_uninstall_reports_conflict(self):
        with TemporaryDirectory() as directory:
            root = self._project(directory)
            agents = root / "AGENTS.md"
            agents.write_text("user instructions\n", encoding="utf-8")
            plan = create_install_plan(
                scan_workspace(root),
                answers={"standards_confirmed": True},
                operations=[{
                    "path": "AGENTS.md",
                    "content": "Use ffkb query before changes.",
                    "mode": "managed_block",
                    "marker": "ffkb",
                }],
            )
            apply_plan(plan)
            installed = agents.read_text(encoding="utf-8")
            self.assertIn("user instructions", installed)
            self.assertIn("BEGIN ffkb", installed)

            agents.write_text(installed + "user changed after install\n", encoding="utf-8")
            result = uninstall(root)

            self.assertEqual("conflict", result["status"])
            self.assertTrue(agents.exists())
            self.assertIn("user changed after install", agents.read_text(encoding="utf-8"))

    def test_rollback_restores_preimage(self):
        with TemporaryDirectory() as directory:
            root = self._project(directory)
            target = root / "AGENTS.md"
            target.write_text("original\n", encoding="utf-8")
            plan = create_install_plan(
                scan_workspace(root),
                answers={"standards_confirmed": True},
                operations=[{"path": "AGENTS.md", "content": "installed\n"}],
            )
            apply_plan(plan)

            result = rollback(root)

            self.assertEqual("rolled_back", result["status"])
            self.assertEqual("original\n", target.read_text(encoding="utf-8"))

    def test_apply_restores_preimages_when_manifest_commit_fails(self):
        with TemporaryDirectory() as directory:
            root = self._project(directory)
            target = root / "AGENTS.md"
            target.write_text("original\n", encoding="utf-8")
            plan = create_install_plan(
                scan_workspace(root),
                answers={"standards_confirmed": True},
                operations=[{"path": "AGENTS.md", "content": "installed\n"}],
            )
            write_json = transaction._write_json

            def fail_manifest(path: Path, value: dict) -> None:
                if path.name == "install-manifest.json":
                    raise OSError("simulated manifest failure")
                write_json(path, value)

            with patch("ff_local_knowledge.transaction._write_json", side_effect=fail_manifest):
                with self.assertRaisesRegex(OSError, "simulated manifest failure"):
                    apply_plan(plan)

            self.assertEqual("original\n", target.read_text(encoding="utf-8"))
            self.assertFalse((root / ".ffkb" / "runtime" / "install-manifest.json").exists())
            journals = list((root / ".ffkb" / "runtime" / "journal").glob("*.json"))
            self.assertEqual(1, len(journals))
            self.assertIn("rolled_back_after_error", journals[0].read_text(encoding="utf-8"))

    def test_default_plan_uses_confirmed_profile_knowledge_and_adapter_resources(self):
        with TemporaryDirectory() as directory, TemporaryDirectory() as resources_directory:
            root = self._project(directory)
            resources = Path(resources_directory)
            (resources / "templates" / "knowledge" / "pages").mkdir(parents=True)
            (resources / "templates" / "knowledge" / "router.json").write_text(
                '{"project_id":"{{PROJECT_ID}}"}\n', encoding="utf-8"
            )
            (resources / "templates" / "knowledge" / "pages" / "overview.md").write_text(
                "# {{PROJECT_NAME}}\n", encoding="utf-8"
            )
            (resources / "templates" / "knowledge" / "pages" / "standards").mkdir()
            (resources / "templates" / "knowledge" / "pages" / "standards" / "coding-standards.md").write_text(
                "## compiled_truth\n\n{{CONFIRMED_STANDARDS}}\n", encoding="utf-8"
            )
            (resources / "templates" / "adapters" / "generic").mkdir(parents=True)
            (resources / "templates" / "adapters" / "generic" / "AGENTS.md.tmpl").write_text(
                "Query {{KNOWLEDGE_ROOT}}", encoding="utf-8"
            )
            (resources / "profiles" / "python").mkdir(parents=True)
            (resources / "profiles" / "python" / "profile.json").write_text(
                '{"id":"python"}\n', encoding="utf-8"
            )
            (resources / "skills" / "ff-bootstrap").mkdir(parents=True)
            (resources / "skills" / "ff-bootstrap" / "SKILL.md").write_text(
                "---\nname: ff-bootstrap\ndescription: Bootstrap FF.\n---\n", encoding="utf-8"
            )
            old_resource_root = os.environ.get("FFKB_RESOURCE_ROOT")
            os.environ["FFKB_RESOURCE_ROOT"] = str(resources)
            try:
                plan = create_install_plan(
                    scan_workspace(root),
                    answers={
                        "standards_confirmed": True,
                        "project_id": "sample",
                        "project_name": "Sample Project",
                        "locale": "en",
                        "profile": "python",
                        "adapters": ["generic"],
                    },
                )
            finally:
                if old_resource_root is None:
                    os.environ.pop("FFKB_RESOURCE_ROOT", None)
                else:
                    os.environ["FFKB_RESOURCE_ROOT"] = old_resource_root

            by_path = {item["path"]: item for item in plan["operations"]}
            self.assertIn(".ff-knowledge/router.json", by_path)
            self.assertIn(".ff-knowledge/profile.json", by_path)
            self.assertIn("AGENTS.md", by_path)
            self.assertIn(".agents/skills/ff-bootstrap/SKILL.md", by_path)
            self.assertEqual("managed_block", by_path["AGENTS.md"]["mode"])
            self.assertIn("sample", by_path[".ff-knowledge/router.json"]["content"])
            self.assertIn(".ff-knowledge", by_path["AGENTS.md"]["content"])
            self.assertEqual("applied", apply_plan(plan)["status"])
            self.assertEqual("healthy", doctor(root)["status"])

    def test_repository_resources_install_and_query_end_to_end(self):
        with TemporaryDirectory() as directory:
            root = self._project(directory)
            plan = create_install_plan(
                scan_workspace(root),
                answers={
                    "standards_confirmed": True,
                    "project_id": "end-to-end",
                    "project_name": "End to End",
                    "locale": "en",
                    "profile": "python",
                    "adapters": ["generic", "claude"],
                },
            )

            applied = apply_plan(plan)
            knowledge_root = root / ".ff-knowledge"
            result = query(knowledge_root, "verify standards", budget=120)

            self.assertEqual("applied", applied["status"])
            self.assertEqual("healthy", doctor(root)["status"])
            self.assertEqual("ok", lint(knowledge_root)["status"])
            self.assertEqual("page:standards/coding-standards", result["pages"][0]["id"])
            self.assertTrue((root / "AGENTS.md").is_file())
            self.assertTrue((root / "CLAUDE.md").is_file())
            self.assertTrue((root / ".agents" / "skills" / "ff-bootstrap" / "SKILL.md").is_file())
            self.assertTrue((root / ".claude" / "skills" / "ff-bootstrap" / "SKILL.md").is_file())

    def test_default_plan_applies_confirmed_chinese_locale_templates(self):
        with TemporaryDirectory() as directory:
            root = self._project(directory)
            plan = create_install_plan(
                scan_workspace(root),
                answers={
                    "standards_confirmed": True,
                    "locale": "zh-CN",
                    "profile": "python",
                    "adapters": ["generic"],
                },
            )
            by_path = {item["path"]: item for item in plan["operations"]}

            standards = by_path[".ff-knowledge/pages/standards/coding-standards.md"]["content"]
            overview = by_path[".ff-knowledge/pages/projects/project-overview.md"]["content"]
            index = by_path[".ff-knowledge/INDEX.md"]["content"]
            self.assertIn("修改前", standards)
            self.assertIn("项目概览", overview)
            self.assertIn("机器路由真相源", index)

    def test_workbuddy_adapter_installs_only_project_workbuddy_skills(self):
        with TemporaryDirectory() as directory:
            root = self._project(directory)
            plan = create_install_plan(
                scan_workspace(root),
                answers={
                    "standards_confirmed": True,
                    "profile": "python",
                    "adapters": ["workbuddy"],
                },
            )
            paths = {item["path"] for item in plan["operations"]}

            self.assertIn(".workbuddy-ai/skills/ff-kb-bridge/SKILL.md", paths)
            self.assertFalse(any(path.startswith(".agents/skills/") for path in paths))
            self.assertFalse(any(path.startswith(".claude/skills/") for path in paths))
            self.assertNotIn("AGENTS.md", paths)
            self.assertNotIn("CLAUDE.md", paths)
            self.assertEqual("applied", apply_plan(plan)["status"])
            self.assertEqual("healthy", doctor(root)["status"])

    def test_confirmed_standards_are_written_to_the_canonical_page(self):
        with TemporaryDirectory() as directory:
            root = self._project(directory)
            plan = create_install_plan(
                scan_workspace(root),
                answers={
                    "standards_confirmed": True,
                    "standards": [
                        "Use domain services for business rules.",
                        "Run focused tests before the full suite.",
                    ],
                    "adapters": ["generic"],
                },
            )
            by_path = {item["path"]: item for item in plan["operations"]}
            standards = by_path[".ff-knowledge/pages/standards/coding-standards.md"]["content"]

            self.assertIn("- Use domain services for business rules.", standards)
            self.assertIn("- Run focused tests before the full suite.", standards)
            self.assertNotIn("{{CONFIRMED_STANDARDS}}", standards)
            self.assertEqual("user_confirmation", plan["resolved_standards"]["source"])


if __name__ == "__main__":
    unittest.main()
