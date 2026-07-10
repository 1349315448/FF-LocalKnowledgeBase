import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from ff_local_knowledge.knowledge import compact, lint, query, search


class KnowledgeTests(unittest.TestCase):
    def _knowledge(self, directory: str) -> Path:
        root = Path(directory)
        (root / "pages").mkdir()
        (root / "pages" / "testing.md").write_text(
            "# Testing\n\n## Compiled Truth\n\nRun focused tests before the full suite. "
            "Verification evidence is required.\n\n## Details\n\nLong details.\n",
            encoding="utf-8",
        )
        (root / "router.json").write_text(json.dumps({
            "schema_version": "1.0",
            "routes": [{
                "id": "testing",
                "page": "pages/testing.md",
                "keywords": ["test", "testing", "verify"],
                "priority": 10,
            }],
        }), encoding="utf-8")
        (root / "graph.jsonl").write_text(
            json.dumps({"type": "node", "id": "page:testing"}) + "\n" +
            json.dumps({"type": "edge", "source": "page:testing", "target": "standard:missing"}) + "\n",
            encoding="utf-8",
        )
        return root

    def test_query_uses_router_respects_budget_and_has_no_side_effects(self):
        with TemporaryDirectory() as directory:
            root = self._knowledge(directory)
            before = {path.relative_to(root): path.read_bytes() for path in root.rglob("*") if path.is_file()}

            result = query(root, "how should I test and verify", budget=20)
            after = {path.relative_to(root): path.read_bytes() for path in root.rglob("*") if path.is_file()}

            self.assertEqual("ok", result["status"])
            self.assertEqual("testing", result["pages"][0]["id"])
            self.assertLessEqual(result["used_budget"], 20)
            self.assertEqual(before, after)
            self.assertFalse((root / "logs").exists())

    def test_search_and_compact_build_derived_cache(self):
        with TemporaryDirectory() as directory:
            root = self._knowledge(directory)
            cache = root.parent / "runtime-cache"

            found = search(root, "focused tests")
            result = compact(root, cache)

            self.assertEqual("testing", found["matches"][0]["id"])
            self.assertEqual("compacted", result["status"])
            self.assertTrue((cache / "search-index.json").exists())
            self.assertTrue((cache / "router.compiled.json").exists())

    def test_lint_reports_dangling_graph_and_missing_compiled_truth(self):
        with TemporaryDirectory() as directory:
            root = self._knowledge(directory)
            (root / "pages" / "bad.md").write_text("# Missing section\n", encoding="utf-8")
            router = json.loads((root / "router.json").read_text(encoding="utf-8"))
            router["routes"].append({"id": "bad", "page": "pages/bad.md", "keywords": ["bad"]})
            (root / "router.json").write_text(json.dumps(router), encoding="utf-8")

            result = lint(root)
            codes = {item["code"] for item in result["diagnostics"]}

            self.assertEqual("error", result["status"])
            self.assertIn("missing_compiled_truth", codes)
            self.assertIn("dangling_graph_target", codes)

    def test_query_supports_canonical_rules_nodes_and_edges_layout(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "pages" / "standards").mkdir(parents=True)
            (root / "graph").mkdir()
            (root / "pages" / "standards" / "coding.md").write_text(
                "---\nid: page:standards/coding\nstatus: active\nupdated_at: 1970-01-01\n---\n\n"
                "## compiled_truth\n\nAlways verify current evidence.\n",
                encoding="utf-8",
            )
            (root / "router.json").write_text(json.dumps({
                "schema_version": 1,
                "rules": [{
                    "keywords": ["verify", "standards"],
                    "primary_pages": ["page:standards/coding"],
                    "optional_pages": [],
                }],
            }), encoding="utf-8")
            (root / "graph" / "nodes.jsonl").write_text(
                json.dumps({
                    "id": "page:standards/coding",
                    "type": "page",
                    "path": "pages/standards/coding.md",
                    "status": "active",
                    "updated_at": "1970-01-01",
                }) + "\n",
                encoding="utf-8",
            )
            (root / "graph" / "edges.jsonl").write_text("", encoding="utf-8")

            result = query(root, "verify standards", budget=50)
            lint_result = lint(root)

            self.assertEqual("page:standards/coding", result["pages"][0]["id"])
            self.assertEqual("ok", lint_result["status"])

    def test_lint_accepts_canonical_non_page_graph_nodes(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "pages").mkdir()
            (root / "graph").mkdir()
            (root / "pages" / "overview.md").write_text(
                "---\nid: page:overview\nstatus: active\nupdated_at: 1970-01-01\n---\n\n"
                "## compiled_truth\n\nThe service owns the public workflow.\n",
                encoding="utf-8",
            )
            (root / "router.json").write_text(json.dumps({
                "schema_version": 1,
                "rules": [{
                    "keywords": ["service"],
                    "primary_pages": ["page:overview"],
                    "optional_pages": [],
                }],
            }), encoding="utf-8")
            (root / "graph" / "nodes.jsonl").write_text(
                json.dumps({
                    "id": "page:overview",
                    "type": "page",
                    "path": "pages/overview.md",
                    "status": "active",
                    "updated_at": "1970-01-01",
                }) + "\n" +
                json.dumps({"id": "service:example", "type": "service", "status": "active"}) + "\n",
                encoding="utf-8",
            )
            (root / "graph" / "edges.jsonl").write_text(
                json.dumps({"from": "page:overview", "to": "service:example", "type": "documents"}) + "\n",
                encoding="utf-8",
            )

            result = lint(root)

            self.assertEqual("ok", result["status"], result["diagnostics"])

    def test_query_uses_cjk_phrase_order_for_precise_routing(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "pages").mkdir()
            (root / "pages" / "correct.md").write_text(
                "## compiled_truth\n\n用户权限由服务端统一校验。\n", encoding="utf-8"
            )
            (root / "pages" / "wrong.md").write_text(
                "## compiled_truth\n\n这是不同的业务主题。\n", encoding="utf-8"
            )
            (root / "router.json").write_text(json.dumps({
                "schema_version": "1.0",
                "routes": [
                    {"id": "a-wrong", "page": "pages/wrong.md", "keywords": ["权限用户"], "priority": 10},
                    {"id": "z-correct", "page": "pages/correct.md", "keywords": ["用户权限"], "priority": 10},
                ],
            }), encoding="utf-8")

            result = query(root, "用户权限怎么处理", budget=50, limit=1)

            self.assertEqual("z-correct", result["pages"][0]["id"])


if __name__ == "__main__":
    unittest.main()
