"""Contract tests for the portable skills, profiles, and agent adapters."""

from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL_NAMES = {
    "ff-bootstrap",
    "ff-kb-bridge",
    "ff-develop",
    "ff-knowledge",
    "ff-learn",
    "ff-plan",
    "ff-verify",
    "ff-review",
}
FORBIDDEN_TOKENS = (
    "D:\\Company\\Private",
    "Internal.Product",
    "internal-workflow",
    "CustomerSchema",
    "PrivateOrm",
)


class SkillContractTests(unittest.TestCase):
    """Verify that exported skills stay portable and progressively loaded."""

    def test_all_portable_skills_have_valid_frontmatter_and_codex_metadata(self) -> None:
        for name in SKILL_NAMES:
            skill_root = ROOT / "skills" / name
            skill_text = (skill_root / "SKILL.md").read_text(encoding="utf-8")
            self.assertTrue(skill_text.startswith("---\n"), name)
            self.assertRegex(skill_text, rf"(?m)^name:\s*{re.escape(name)}$")
            self.assertRegex(skill_text, r"(?m)^description:\s*\S.+$")
            self.assertLess(len(skill_text.splitlines()), 500, name)
            self.assertTrue((skill_root / "agents" / "openai.yaml").is_file(), name)

    def test_workbuddy_bridge_keeps_a_portable_skill_contract(self) -> None:
        skill = (ROOT / "skills" / "ff-kb-bridge" / "SKILL.md").read_text(encoding="utf-8")
        description = re.search(r"(?m)^description:\s*(.+)$", skill)

        self.assertIsNotNone(description)
        self.assertLessEqual(len(description.group(1)), 200)
        self.assertIn("## Principles", skill)
        self.assertIn("## Steps", skill)
        self.assertIn("## Commands", skill)
        self.assertIn("## Output Contract", skill)
        self.assertIn("## Boundaries", skill)
        self.assertNotIn("C:\\", skill)
        self.assertNotIn("~/.workbuddy-ai", skill)
        self.assertIn('skills/ff-kb-bridge/SKILL.md', (ROOT / "pyproject.toml").read_text(encoding="utf-8"))

    def test_public_templates_do_not_contain_private_workspace_coupling(self) -> None:
        public_roots = [ROOT / "skills", ROOT / "profiles", ROOT / "templates"]
        for public_root in public_roots:
            for path in public_root.rglob("*"):
                if not path.is_file():
                    continue
                text = path.read_text(encoding="utf-8")
                for token in FORBIDDEN_TOKENS:
                    self.assertNotIn(token, text, f"{token} leaked into {path}")

    def test_profiles_and_thin_agent_adapters_exist(self) -> None:
        for profile in ("generic", "dotnet", "node", "python"):
            self.assertTrue((ROOT / "profiles" / profile / "profile.json").is_file(), profile)

        adapters = {
            "generic": "AGENTS.md.tmpl",
            "codex": "AGENTS.md.tmpl",
            "claude": "CLAUDE.md.tmpl",
        }
        for adapter, filename in adapters.items():
            path = ROOT / "templates" / "adapters" / adapter / filename
            self.assertTrue(path.is_file(), str(path))
            self.assertLess(len(path.read_text(encoding="utf-8").splitlines()), 120)

    def test_knowledge_template_uses_machine_router_as_source(self) -> None:
        template = ROOT / "templates" / "knowledge"
        self.assertTrue((template / "knowledge.json").is_file())
        self.assertTrue((template / "router.json").is_file())
        index = (template / "INDEX.md").read_text(encoding="utf-8")
        self.assertIn("router.json", index)
        self.assertIn("display", index.casefold())
        self.assertTrue((template / "pages" / "standards" / "coding-standards.md").is_file())
        self.assertTrue((template / "graph" / "nodes.jsonl").is_file())
        self.assertTrue((template / "graph" / "edges.jsonl").is_file())


if __name__ == "__main__":
    unittest.main()
