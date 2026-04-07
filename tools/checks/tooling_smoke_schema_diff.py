from __future__ import annotations

import json
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


JsonPayloadLoader = Callable[[Path, list[str], str], dict[str, object] | None]

_SCHEMA_DIFF_SCRIPT = "tools/schema_diff/main.py"
_OLD_JSON_NAME = "old.json"
_NEW_JSON_NAME = "new.json"
_DIFF_JSON_NAME = "diff.json"
_JSON_OUTPUT_LABEL = "schema-diff JSON 输出"
_FAIL_ON_DIFF_ERROR = "schema-diff 在存在差异时未按预期返回非 0"


@dataclass(frozen=True)
class SchemaDiffContext:
    repo_root: Path
    python_executable: str
    subprocess_module: Any
    load_json_file_payload: JsonPayloadLoader


def _schema_diff_command(
    python_executable: str,
    *args: str,
) -> list[str]:
    return [python_executable, _SCHEMA_DIFF_SCRIPT, *args]


def append_schema_diff_errors(
    errors: list[str],
    *,
    repo_root: Path,
    python_executable: str,
    subprocess_module: Any,
    load_json_file_payload: JsonPayloadLoader,
) -> None:
    ctx = SchemaDiffContext(
        repo_root=repo_root,
        python_executable=python_executable,
        subprocess_module=subprocess_module,
        load_json_file_payload=load_json_file_payload,
    )

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_root = Path(temp_dir)
        old_path = temp_root / _OLD_JSON_NAME
        new_path = temp_root / _NEW_JSON_NAME
        json_out = temp_root / _DIFF_JSON_NAME

        old_path.write_text(json.dumps({"version": "0.1.1", "a": 1}), encoding="utf-8")
        new_path.write_text(
            json.dumps({"version": "0.1.2", "a": 2, "b": 3}),
            encoding="utf-8",
        )

        json_run = ctx.subprocess_module.run(
            _schema_diff_command(
                ctx.python_executable,
                str(old_path),
                str(new_path),
                "--json-out",
                str(json_out),
            ),
            cwd=ctx.repo_root,
            capture_output=True,
            text=True,
        )
        if json_run.returncode != 0:
            errors.append(f"schema-diff json 输出执行失败: exit={json_run.returncode}")
        elif not json_out.exists():
            errors.append("schema-diff 未生成 JSON 输出文件")
        else:
            payload = ctx.load_json_file_payload(json_out, errors, _JSON_OUTPUT_LABEL)
            if payload is not None:
                if payload.get("mode") != "file":
                    errors.append("schema-diff JSON 输出 mode 不正确")
                if "added_keys" not in payload or "changed_keys" not in payload:
                    errors.append("schema-diff JSON 输出缺少关键字段")

        fail_run = ctx.subprocess_module.run(
            _schema_diff_command(
                ctx.python_executable,
                str(old_path),
                str(new_path),
                "--fail-on-diff",
            ),
            cwd=ctx.repo_root,
            capture_output=True,
            text=True,
        )
        if fail_run.returncode == 0:
            errors.append(_FAIL_ON_DIFF_ERROR)
