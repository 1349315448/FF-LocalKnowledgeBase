"""Command-line interface for FF Local Knowledge Base."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .detection import detect_environment
from .knowledge import compact, lint, query, search
from .planning import create_install_plan
from .resources import ResourceUnavailableError
from .scanning import render_markdown_report, scan_workspace, write_scan_reports
from .transaction import InstallationError, apply_plan, doctor, rollback, uninstall


def _read_json(path: str | Path) -> dict | list:
    """Load a CLI JSON input file."""
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _emit(value: dict | list) -> None:
    """Write stable machine-readable output to stdout."""
    print(json.dumps(value, indent=2, ensure_ascii=False))


def build_parser() -> argparse.ArgumentParser:
    """Build the complete public CLI grammar."""
    parser = argparse.ArgumentParser(prog="ffkb", description="Local knowledge tools for coding agents")
    parser.add_argument("--version", action="version", version="ffkb 0.1.0")
    commands = parser.add_subparsers(dest="command", required=True)

    detect_parser = commands.add_parser("detect", help="Detect the local runtime without writing files")
    detect_parser.add_argument("root", nargs="?", default=".")

    scan_parser = commands.add_parser("scan", help="Scan project architecture without executing project code")
    scan_parser.add_argument("root", nargs="?", default=".")
    scan_parser.add_argument("--json-output")
    scan_parser.add_argument("--markdown-output")
    scan_parser.add_argument("--markdown", action="store_true", help="Print the human report instead of JSON")

    plan_parser = commands.add_parser("plan", help="Create a confirmed installation plan")
    plan_parser.add_argument("report")
    plan_parser.add_argument("--answers", required=True)
    plan_parser.add_argument("--operations", help="Advanced JSON operation override; defaults use confirmed resources")
    plan_parser.add_argument("--output")

    apply_parser = commands.add_parser("apply", help="Apply a plan transactionally")
    apply_parser.add_argument("plan")

    for name, help_text in (
        ("doctor", "Check managed file integrity"),
        ("rollback", "Restore the latest transaction"),
        ("uninstall", "Remove unchanged managed installation files"),
    ):
        command_parser = commands.add_parser(name, help=help_text)
        command_parser.add_argument("root", nargs="?", default=".")

    query_parser = commands.add_parser("query", help="Query compiled project knowledge")
    query_parser.add_argument("root_pos", nargs="?")
    query_parser.add_argument("intent_pos", nargs="?")
    query_parser.add_argument("--root", dest="root_option")
    query_parser.add_argument("--intent", dest="intent_option")
    query_parser.add_argument("--budget", type=int, default=800)
    query_parser.add_argument("--limit", type=int, default=3)

    search_parser = commands.add_parser("search", help="Search routed project knowledge")
    search_parser.add_argument("root")
    search_parser.add_argument("text")
    search_parser.add_argument("--limit", type=int, default=20)

    compact_parser = commands.add_parser("compact", help="Build replaceable derived caches")
    compact_parser.add_argument("root")
    compact_parser.add_argument("--cache-root")

    lint_parser = commands.add_parser("lint", help="Validate router, pages and graph")
    lint_parser.add_argument("root")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Dispatch one CLI command and return a process status code."""
    parser = build_parser()
    arguments = parser.parse_args(argv)
    try:
        if arguments.command == "detect":
            _emit(detect_environment(arguments.root))
        elif arguments.command == "scan":
            report = scan_workspace(arguments.root)
            write_scan_reports(
                report,
                Path(arguments.json_output) if arguments.json_output else None,
                Path(arguments.markdown_output) if arguments.markdown_output else None,
            )
            print(render_markdown_report(report) if arguments.markdown else json.dumps(report, indent=2, ensure_ascii=False))
        elif arguments.command == "plan":
            operations = _read_json(arguments.operations) if arguments.operations else None
            plan = create_install_plan(_read_json(arguments.report), _read_json(arguments.answers), operations)
            if arguments.output:
                output_path = Path(arguments.output)
                output_path.parent.mkdir(parents=True, exist_ok=True)
                output_path.write_text(json.dumps(plan, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            _emit(plan)
        elif arguments.command == "apply":
            _emit(apply_plan(_read_json(arguments.plan)))
        elif arguments.command == "doctor":
            _emit(doctor(arguments.root))
        elif arguments.command == "rollback":
            _emit(rollback(arguments.root))
        elif arguments.command == "uninstall":
            _emit(uninstall(arguments.root))
        elif arguments.command == "query":
            root = arguments.root_option or arguments.root_pos
            intent = arguments.intent_option or arguments.intent_pos
            if not root or not intent:
                raise ValueError("query requires --root and --intent (or positional equivalents)")
            _emit(query(root, intent, arguments.budget, arguments.limit))
        elif arguments.command == "search":
            _emit(search(arguments.root, arguments.text, arguments.limit))
        elif arguments.command == "compact":
            _emit(compact(arguments.root, arguments.cache_root))
        elif arguments.command == "lint":
            result = lint(arguments.root)
            _emit(result)
            return 1 if result["status"] == "error" else 0
    except (ValueError, OSError, json.JSONDecodeError, InstallationError, ResourceUnavailableError) as exc:
        print(json.dumps({"status": "error", "message": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
