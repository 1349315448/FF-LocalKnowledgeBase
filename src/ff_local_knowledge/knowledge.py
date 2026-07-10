"""Small, deterministic lexical knowledge engine backed by router.json."""

from __future__ import annotations

import json
import re
from pathlib import Path

from .filesystem import resolve_within


IDENTIFIER_PATTERN = re.compile(r"[A-Za-z0-9_+#.-]+")
CJK_PATTERN = re.compile(r"[\u3400-\u9fff]+")
COMPILED_TRUTH_HEADING = re.compile(r"^##\s+compiled(?:[ _-])truth\s*$", re.IGNORECASE | re.MULTILINE)


def _load_router(root: Path) -> dict:
    """Load the canonical routing source and reject unsupported shapes."""
    path = root / "router.json"
    if not path.is_file():
        raise ValueError(f"Missing router.json: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data.get("routes"), list) and not isinstance(data.get("rules"), list):
        raise ValueError("router.json must contain a rules or routes array")
    return data


def _read_jsonl(path: Path) -> list[dict]:
    """Read newline-delimited JSON events from an optional file."""
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _canonical_routes(root: Path, router: dict) -> list[dict]:
    """Resolve canonical rule page IDs to paths through graph nodes."""
    if isinstance(router.get("routes"), list):
        return router["routes"]
    nodes = {
        str(node.get("id")): node
        for node in _read_jsonl(root / "graph" / "nodes.jsonl")
        if node.get("id") and node.get("path")
    }
    routes: dict[str, dict] = {}
    for rule_index, rule in enumerate(router.get("rules", [])):
        keywords = [str(item) for item in rule.get("keywords", [])]
        for kind, page_ids, base_priority in (
            ("primary", rule.get("primary_pages", []), 100),
            ("optional", rule.get("optional_pages", []), 10),
        ):
            for page_id in page_ids:
                node = nodes.get(str(page_id))
                if not node:
                    continue
                route = routes.setdefault(str(page_id), {
                    "id": str(page_id),
                    "page": node["path"],
                    "keywords": [],
                    "priority": 0,
                })
                route["keywords"] = list(dict.fromkeys([*route["keywords"], *keywords]))
                route["priority"] = max(route["priority"], base_priority - rule_index)
                route["route_kind"] = kind
    return list(routes.values())


def _tokens(value: str) -> set[str]:
    """Tokenize identifiers and ordered CJK n-grams for dependency-free matching."""
    tokens = {token.casefold() for token in IDENTIFIER_PATTERN.findall(value)}
    for segment in CJK_PATTERN.findall(value):
        for size in range(1, min(4, len(segment)) + 1):
            for start in range(0, len(segment) - size + 1):
                tokens.add(segment[start:start + size])
    return tokens


def _compiled_truth(markdown: str) -> str | None:
    """Extract the compact canonical section from a Markdown page."""
    match = COMPILED_TRUTH_HEADING.search(markdown)
    if not match:
        return None
    remainder = markdown[match.end():].lstrip("\r\n")
    next_heading = re.search(r"^##\s+", remainder, re.MULTILINE)
    return remainder[:next_heading.start()].strip() if next_heading else remainder.strip()


def _frontmatter(markdown: str) -> dict[str, str]:
    """Parse the documented scalar frontmatter subset needed for schema checks."""
    lines = markdown.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    values: dict[str, str] = {}
    for line in lines[1:]:
        if line.strip() == "---":
            return values
        if ":" in line:
            key, value = line.split(":", 1)
            values[key.strip()] = value.strip().strip('"\'')
    return {}


def _route_score(route: dict, intent_tokens: set[str]) -> int:
    """Rank one router entry using exact lexical overlap and declared priority."""
    keywords = _tokens(" ".join(str(item) for item in route.get("keywords", [])))
    identifier = _tokens(str(route.get("id", "")))
    overlap = len(intent_tokens & keywords) * 100 + len(intent_tokens & identifier) * 20
    return overlap + int(route.get("priority", 0)) if overlap else 0


def _clip_to_budget(text: str, remaining: int) -> tuple[str, int]:
    """Clip text using a conservative four-character token approximation."""
    if remaining <= 0:
        return "", 0
    limit = remaining * 4
    clipped = text if len(text) <= limit else text[: max(0, limit - 1)].rstrip() + "…"
    used = min(remaining, max(1, (len(clipped) + 3) // 4)) if clipped else 0
    return clipped, used


def _graph_edges(root: Path) -> list[dict]:
    """Read valid graph edge events while tolerating an absent graph file."""
    canonical = _read_jsonl(root / "graph" / "edges.jsonl")
    if canonical:
        return [
            {**edge, "source": edge.get("from"), "target": edge.get("to")}
            for edge in canonical
        ]
    return [event for event in _read_jsonl(root / "graph.jsonl") if event.get("type") == "edge"]


def query(knowledge_root: str | Path, intent: str, budget: int = 800, limit: int = 3) -> dict:
    """Return the highest scoring compiled truths without mutating source or runtime state."""
    root = Path(knowledge_root).resolve()
    if budget <= 0:
        raise ValueError("Budget must be positive")
    routes = _canonical_routes(root, _load_router(root))
    intent_tokens = _tokens(intent)
    ranked = sorted(
        ((route, _route_score(route, intent_tokens)) for route in routes),
        key=lambda item: (-item[1], -int(item[0].get("priority", 0)), str(item[0].get("id", ""))),
    )
    ranked = [item for item in ranked if item[1] > 0][:limit]
    pages = []
    used = 0
    warnings = []
    selected_ids = set()
    for route, score in ranked:
        try:
            page_path = resolve_within(root, route["page"])
        except (KeyError, ValueError):
            warnings.append(f"Invalid page path for route {route.get('id', '<unknown>')}")
            continue
        if not page_path.is_file():
            warnings.append(f"Missing page: {route['page']}")
            continue
        truth = _compiled_truth(page_path.read_text(encoding="utf-8"))
        if truth is None:
            warnings.append(f"Missing Compiled Truth: {route['page']}")
            continue
        content, cost = _clip_to_budget(truth, budget - used)
        if not content:
            break
        route_id = str(route.get("id", route["page"]))
        pages.append({"id": route_id, "page": route["page"], "score": score, "compiled_truth": content})
        selected_ids.add(route_id)
        used += cost
    related_edges = [
        edge for edge in _graph_edges(root)
        if any(identifier in str(edge.get("source", "")) or identifier in str(edge.get("target", "")) for identifier in selected_ids)
    ][:10]
    return {
        "status": "ok" if pages else "no_match",
        "intent": intent,
        "pages": pages,
        "related_edges": related_edges,
        "used_budget": used,
        "budget": budget,
        "warnings": warnings,
        "next_actions": [] if pages else ["Refine the query or add router keywords."],
    }


def search(knowledge_root: str | Path, text: str, limit: int = 20) -> dict:
    """Search routed Markdown pages directly; cache is never required for correctness."""
    root = Path(knowledge_root).resolve()
    needle = text.casefold()
    matches = []
    for route in _canonical_routes(root, _load_router(root)):
        try:
            page = resolve_within(root, route["page"])
        except (KeyError, ValueError):
            continue
        if not page.is_file():
            continue
        content = page.read_text(encoding="utf-8")
        haystack = f"{route.get('id', '')} {' '.join(route.get('keywords', []))} {content}".casefold()
        if needle in haystack:
            matches.append({"id": route.get("id"), "page": route["page"]})
        if len(matches) >= limit:
            break
    return {"status": "ok", "query": text, "matches": matches}


def compact(knowledge_root: str | Path, cache_root: str | Path | None = None) -> dict:
    """Build replaceable router and search cache files outside canonical knowledge sources."""
    root = Path(knowledge_root).resolve()
    cache = Path(cache_root).resolve() if cache_root else root / ".runtime" / "cache"
    router = _load_router(root)
    routes = _canonical_routes(root, router)
    index = []
    for route in routes:
        try:
            page = resolve_within(root, route["page"])
        except (KeyError, ValueError):
            continue
        if page.is_file():
            truth = _compiled_truth(page.read_text(encoding="utf-8"))
            index.append({
                "id": route.get("id"),
                "page": route["page"],
                "keywords": route.get("keywords", []),
                "compiled_truth": truth,
            })
    cache.mkdir(parents=True, exist_ok=True)
    (cache / "router.compiled.json").write_text(
        json.dumps(router, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    (cache / "search-index.json").write_text(
        json.dumps({"schema_version": "1.0", "pages": index}, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return {"status": "compacted", "cache_root": str(cache), "pages": len(index)}


def lint(knowledge_root: str | Path) -> dict:
    """Validate router/page contracts and graph endpoint integrity."""
    root = Path(knowledge_root).resolve()
    diagnostics: list[dict] = []
    try:
        router = _load_router(root)
        routes = _canonical_routes(root, router)
    except (ValueError, json.JSONDecodeError) as exc:
        return {"status": "error", "diagnostics": [{"code": "invalid_router", "message": str(exc)}]}
    route_ids: set[str] = set()
    canonical_nodes = {
        str(node.get("id")): node
        for node in _read_jsonl(root / "graph" / "nodes.jsonl")
        if node.get("id")
    }
    if "rules" in router:
        for rule in router["rules"]:
            for field in ("primary_pages", "optional_pages"):
                for page_id in rule.get(field, []):
                    if str(page_id) not in canonical_nodes:
                        diagnostics.append({"code": "router_unknown_page", "message": str(page_id)})
    for route in routes:
        route_id = str(route.get("id", ""))
        if not route_id or route_id in route_ids:
            diagnostics.append({"code": "invalid_route_id", "message": f"Missing or duplicate route id: {route_id}"})
        route_ids.add(route_id)
        try:
            page = resolve_within(root, route["page"])
        except (KeyError, ValueError) as exc:
            diagnostics.append({"code": "invalid_page_path", "message": str(exc)})
            continue
        if not page.is_file():
            diagnostics.append({"code": "missing_page", "message": str(route.get("page"))})
        else:
            markdown = page.read_text(encoding="utf-8")
            if _compiled_truth(markdown) is None:
                diagnostics.append({"code": "missing_compiled_truth", "message": str(route.get("page"))})
            node = canonical_nodes.get(route_id)
            if node:
                metadata = _frontmatter(markdown)
                for field in ("id", "status", "updated_at"):
                    expected = str(node.get(field, ""))
                    actual = metadata.get(field, "")
                    if not actual or actual != expected:
                        diagnostics.append({
                            "code": "page_node_mismatch",
                            "message": f"{route_id}: {field} page={actual!r} node={expected!r}",
                        })

    nodes: set[str] = set()
    edges: list[dict] = []
    graph_files = [root / "graph" / "nodes.jsonl", root / "graph" / "edges.jsonl"]
    if not any(path.is_file() for path in graph_files):
        graph_files = [root / "graph.jsonl"]
    for graph in graph_files:
        if graph.is_file():
            for number, line in enumerate(graph.read_text(encoding="utf-8").splitlines(), start=1):
                if not line.strip():
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError as exc:
                    diagnostics.append({"code": "invalid_graph_json", "message": f"{graph.name} line {number}: {exc.msg}"})
                    continue
                is_canonical_node = graph.name == "nodes.jsonl" and "id" in event
                is_compatibility_node = event.get("type") == "node" or (
                    "id" in event and "path" in event
                )
                if is_canonical_node or is_compatibility_node:
                    nodes.add(str(event["id"]))
                elif "from" in event and "to" in event:
                    edges.append({**event, "source": event.get("from"), "target": event.get("to")})
                elif event.get("type") == "edge":
                    edges.append(event)
    for edge in edges:
        if edge.get("source") not in nodes:
            diagnostics.append({"code": "dangling_graph_source", "message": str(edge.get("source"))})
        if edge.get("target") not in nodes:
            diagnostics.append({"code": "dangling_graph_target", "message": str(edge.get("target"))})
    return {"status": "error" if diagnostics else "ok", "diagnostics": diagnostics}
