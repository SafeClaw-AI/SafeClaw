from __future__ import annotations

import argparse
import ast
import json
import re
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SMOKE_CHECK_PATH = REPO_ROOT / "tools" / "checks" / "check_tooling_smoke.py"
DEFAULT_CONTRACT_TEST = (
    REPO_ROOT / "tests" / "contracts" / "test_tooling_smoke_check.py"
)
LABEL_PATTERN = re.compile(r"[a-z0-9]+(?:[-_][a-z0-9.]+){2,}")


@dataclass(frozen=True)
class RefactorBlock:
    kind: str
    label: str
    start_line: int
    end_line: int
    statement_count: int


def _is_helper_call(statement: ast.stmt) -> bool:
    if not isinstance(statement, ast.Expr):
        return False
    call = statement.value
    if not isinstance(call, ast.Call):
        return False
    if not isinstance(call.func, ast.Name):
        return False
    if not call.func.id.startswith("append_") or not call.func.id.endswith("_errors"):
        return False
    if len(call.args) != 1:
        return False
    arg = call.args[0]
    return isinstance(arg, ast.Name) and arg.id == "errors"


def _extract_label_from_node(node: ast.AST) -> str | None:
    for child in ast.walk(node):
        if isinstance(child, ast.Name):
            if child.id.startswith("append_") and child.id.endswith("_errors"):
                return child.id
        if isinstance(child, ast.Constant) and isinstance(child.value, str):
            value = child.value.strip()
            matched = LABEL_PATTERN.search(value)
            if matched is not None:
                return matched.group(0)
    return None


def _extract_label_from_statements(statements: list[ast.stmt]) -> str | None:
    for statement in statements:
        label = _extract_label_from_node(statement)
        if label is not None:
            return label
    return None


def _statement_end_line(statement: ast.stmt) -> int:
    end_line = getattr(statement, "end_lineno", None)
    if end_line is None:
        return statement.lineno
    return end_line


def _build_helper_block(statement: ast.stmt) -> RefactorBlock:
    assert isinstance(statement, ast.Expr)
    call = statement.value
    assert isinstance(call, ast.Call)
    assert isinstance(call.func, ast.Name)
    return RefactorBlock(
        kind="helper",
        label=call.func.id,
        start_line=statement.lineno,
        end_line=_statement_end_line(statement),
        statement_count=1,
    )


def _build_inline_block(statements: list[ast.stmt]) -> RefactorBlock:
    label = _extract_label_from_statements(statements)
    if label is None:
        first_statement = statements[0]
        if (
            isinstance(first_statement, ast.Assign)
            and len(first_statement.targets) == 1
            and isinstance(first_statement.targets[0], ast.Name)
            and first_statement.targets[0].id == "errors"
        ) or (
            isinstance(first_statement, ast.AnnAssign)
            and isinstance(first_statement.target, ast.Name)
            and first_statement.target.id == "errors"
        ):
            label = "collect-errors-setup"
        else:
            label = f"inline-{statements[0].lineno}"
    return RefactorBlock(
        kind="inline",
        label=label,
        start_line=statements[0].lineno,
        end_line=_statement_end_line(statements[-1]),
        statement_count=len(statements),
    )


def collect_refactor_blocks(source: str) -> list[RefactorBlock]:
    module = ast.parse(source)
    collect_errors = next(
        (
            node
            for node in module.body
            if isinstance(node, ast.FunctionDef) and node.name == "collect_errors"
        ),
        None,
    )
    if collect_errors is None:
        raise ValueError("collect_errors() not found")

    blocks: list[RefactorBlock] = []
    inline_group: list[ast.stmt] = []
    inline_label: str | None = None
    for statement in collect_errors.body:
        if _is_helper_call(statement):
            if inline_group:
                blocks.append(_build_inline_block(inline_group))
                inline_group = []
                inline_label = None
            blocks.append(_build_helper_block(statement))
            continue
        statement_label = _extract_label_from_node(statement)
        if (
            inline_group
            and inline_label is not None
            and statement_label is not None
            and statement_label != inline_label
        ):
            blocks.append(_build_inline_block(inline_group))
            inline_group = []
            inline_label = None
        inline_group.append(statement)
        if inline_label is None and statement_label is not None:
            inline_label = statement_label

    if inline_group:
        blocks.append(_build_inline_block(inline_group))
    return blocks


def load_refactor_blocks(path: Path = DEFAULT_SMOKE_CHECK_PATH) -> list[RefactorBlock]:
    return collect_refactor_blocks(path.read_text(encoding="utf-8"))


def render_block_map(
    blocks: list[RefactorBlock],
    *,
    inline_only: bool = False,
    limit: int | None = None,
) -> str:
    filtered = [block for block in blocks if not inline_only or block.kind == "inline"]
    if limit is not None:
        filtered = filtered[:limit]
    lines = [
        f"total_blocks={len(blocks)} inline_blocks={sum(block.kind == 'inline' for block in blocks)}"
    ]
    for index, block in enumerate(filtered, start=1):
        lines.append(
            f"{index:02d}. kind={block.kind} lines={block.start_line}-{block.end_line} "
            f"statements={block.statement_count} label={block.label}"
        )
    return "\n".join(lines)


def build_refactor_check_commands(test_filter: str | None = None) -> list[list[str]]:
    commands: list[list[str]] = []
    if test_filter:
        commands.append(
            [
                sys.executable,
                "-m",
                "pytest",
                str(DEFAULT_CONTRACT_TEST.relative_to(REPO_ROOT)),
                "-q",
                "-k",
                test_filter,
            ]
        )
    commands.append(
        [
            sys.executable,
            "-m",
            "py_compile",
            str(DEFAULT_SMOKE_CHECK_PATH.relative_to(REPO_ROOT)),
            str(DEFAULT_CONTRACT_TEST.relative_to(REPO_ROOT)),
        ]
    )
    commands.append(
        [
            sys.executable,
            "-m",
            "pytest",
            str(DEFAULT_CONTRACT_TEST.relative_to(REPO_ROOT)),
            "-q",
        ]
    )
    return commands


def run_refactor_check(test_filter: str | None = None) -> int:
    commands = build_refactor_check_commands(test_filter)
    for index, command in enumerate(commands, start=1):
        print(
            f"[refactor-check {index}/{len(commands)}] running: {' '.join(command)}",
            flush=True,
        )
        completed = subprocess.run(command, cwd=REPO_ROOT)
        if completed.returncode != 0:
            print(
                f"[refactor-check {index}/{len(commands)}] failed: exit={completed.returncode}",
                flush=True,
            )
            return completed.returncode
        print(f"[refactor-check {index}/{len(commands)}] passed", flush=True)
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Accelerators for check_tooling_smoke.py refactor work."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    map_parser = subparsers.add_parser(
        "map",
        help="Print a collect_errors() block map for helper and inline segments.",
    )
    map_parser.add_argument(
        "--path",
        type=Path,
        default=DEFAULT_SMOKE_CHECK_PATH,
        help="Path to the smoke check file.",
    )
    map_parser.add_argument(
        "--inline-only",
        action="store_true",
        help="Only show inline blocks that are still candidates for extraction.",
    )
    map_parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Only print the first N matching blocks.",
    )
    map_parser.add_argument(
        "--json",
        action="store_true",
        help="Emit JSON instead of text output.",
    )

    verify_parser = subparsers.add_parser(
        "verify",
        help="Run the standard refactor verification loop for tooling smoke.",
    )
    verify_parser.add_argument(
        "--test-filter",
        default=None,
        help="Optional pytest -k filter for the targeted structure tests.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "map":
        blocks = load_refactor_blocks(args.path)
        if args.json:
            payload = [asdict(block) for block in blocks if not args.inline_only or block.kind == "inline"]
            if args.limit is not None:
                payload = payload[: args.limit]
            print(json.dumps(payload, ensure_ascii=False, indent=2))
            return 0
        print(
            render_block_map(
                blocks,
                inline_only=args.inline_only,
                limit=args.limit,
            )
        )
        return 0

    if args.command == "verify":
        return run_refactor_check(args.test_filter)

    parser.error(f"unsupported command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
