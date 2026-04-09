from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT_PATH = REPO_ROOT / "target" / "mvp" / "provider-smoke" / "claude_generated_smoke.py"


@dataclass(frozen=True)
class ProviderSmokeResult:
    version_text: str
    output_path: Path
    prompt_text: str
    generated_code: str


def build_provider_smoke_prompt() -> str:
    return (
        "Generate a tiny valid Python module for a provider smoke test. "
        "Output only the code, with no markdown fences or prose. "
        "The module must define def add(a, b): return a + b "
        "and include a __main__ guard that prints add(1, 2)."
    )


def strip_markdown_code_fences(payload: str) -> str:
    stripped = payload.strip()
    if not stripped.startswith("```"):
        return payload
    lines = stripped.splitlines()
    if len(lines) >= 2 and lines[-1].strip() == "```":
        first_line = lines[0].strip()
        body_lines = lines[1:-1]
        if first_line == "```" and body_lines:
            return "\n".join(body_lines) + "\n"
        if first_line.startswith("```") and body_lines:
            return "\n".join(body_lines) + "\n"
    return payload


def resolve_executable_candidate(candidate: str) -> str | None:
    path = Path(candidate).expanduser()
    if path.exists():
        return str(path)
    resolved = shutil.which(candidate)
    if resolved is not None:
        return resolved
    return None


def resolve_powershell_host() -> str:
    for candidate in ("pwsh", "powershell", "powershell.exe"):
        resolved = resolve_executable_candidate(candidate)
        if resolved is not None:
            return resolved
    return "powershell"


def resolve_claude_command(command: Sequence[str]) -> list[str]:
    if not command:
        raise ValueError("claude command must not be empty")
    executable = command[0]
    resolved_executable = resolve_executable_candidate(executable)
    if resolved_executable is None and executable == "claude":
        resolved_executable = resolve_executable_candidate("claude.ps1")
    final_executable = resolved_executable or executable
    if final_executable.lower().endswith(".ps1"):
        return [
            resolve_powershell_host(),
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            final_executable,
            *command[1:],
        ]
    return [final_executable, *command[1:]]


def extract_generated_code(payload: str) -> str:
    stripped_payload = payload.strip()
    if not stripped_payload:
        return ""
    try:
        decoded_payload = json.loads(stripped_payload)
    except json.JSONDecodeError as error:
        if stripped_payload.startswith(("{", "[")):
            raise ValueError(f"provider returned invalid json payload: {error}") from error
        return strip_markdown_code_fences(payload).strip()
    if isinstance(decoded_payload, dict):
        structured_output = decoded_payload.get("structured_output")
        if isinstance(structured_output, str) and structured_output.strip():
            return strip_markdown_code_fences(structured_output).strip()
        result_text = decoded_payload.get("result")
        if isinstance(result_text, str) and result_text.strip():
            return strip_markdown_code_fences(result_text).strip()
        return ""
    return ""


def run_checked_command(command: Sequence[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(command),
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=True,
    )


def run_provider_smoke(
    *,
    claude_command: Sequence[str] = ("claude",),
    output_path: Path = DEFAULT_OUTPUT_PATH,
    prompt_text: str | None = None,
) -> ProviderSmokeResult:
    resolved_prompt = prompt_text or build_provider_smoke_prompt()
    resolved_claude_command = resolve_claude_command(claude_command)
    version_completed = run_checked_command([*resolved_claude_command, "--version"])
    prompt_completed = run_checked_command(
        [*resolved_claude_command, "-p", resolved_prompt, "--output-format", "json"]
    )
    version_text = (version_completed.stdout or version_completed.stderr or "").strip()
    generated_code = extract_generated_code(prompt_completed.stdout or "")
    if not generated_code:
        raise ValueError("provider returned empty code payload")
    final_code = generated_code + "\n"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(final_code, encoding="utf-8")
    subprocess.run(
        ["python", "-m", "py_compile", str(output_path)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=True,
    )
    return ProviderSmokeResult(
        version_text=version_text,
        output_path=output_path,
        prompt_text=resolved_prompt,
        generated_code=final_code,
    )


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run a real Claude provider smoke prompt and write the returned code to disk."
    )
    parser.add_argument(
        "--output",
        default=str(DEFAULT_OUTPUT_PATH),
        help="Where to write the generated Python module.",
    )
    parser.add_argument(
        "--prompt",
        default="",
        help="Override the default provider smoke prompt.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_argument_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    result = run_provider_smoke(
        output_path=Path(args.output),
        prompt_text=args.prompt or None,
    )
    print(f"[provider-smoke] claude => {result.version_text}")
    print(f"[provider-smoke] output => {result.output_path}")
    print("[provider-smoke] status => wrote generated code and passed py_compile")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
