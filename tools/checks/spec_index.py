from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
SPECS_ROOT = REPO_ROOT / "specs"


@dataclass(frozen=True)
class SpecDocument:
    relpath: str
    path: Path
    data: dict[str, Any]

    @property
    def version(self) -> str | None:
        value = self.data.get("version")
        return value if isinstance(value, str) else None

    @property
    def title(self) -> str:
        value = self.data.get("title")
        return value if isinstance(value, str) else self.relpath


class SpecIndex:
    def __init__(self, documents: list[SpecDocument]) -> None:
        self.documents = documents
        self.by_relpath = {doc.relpath: doc for doc in documents}

    def require(self, relpath: str) -> SpecDocument:
        try:
            return self.by_relpath[relpath]
        except KeyError as exc:
            raise KeyError(f"缺少 spec 文件: {relpath}") from exc


def iter_spec_paths() -> list[Path]:
    return sorted(SPECS_ROOT.rglob("*.json"))


def load_spec_document(path: Path) -> SpecDocument:
    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)
    relpath = path.relative_to(REPO_ROOT).as_posix()
    if not isinstance(data, dict):
        raise TypeError(f"Spec 顶层必须是 object: {relpath}")
    return SpecDocument(relpath=relpath, path=path, data=data)


def build_spec_index() -> SpecIndex:
    documents = [load_spec_document(path) for path in iter_spec_paths()]
    return SpecIndex(documents)


def main() -> int:
    index = build_spec_index()
    print(f"Loaded {len(index.documents)} spec files from {SPECS_ROOT}")
    for doc in index.documents:
        version = doc.version or "<missing>"
        print(f"- {doc.relpath} :: {version} :: {doc.title}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
