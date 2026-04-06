#!/usr/bin/env python3
"""
从内部真源提取公开文档

用途：
- 从 .constitution/ 提取可公开的部分到 docs/
- 确保公开文档与内部真源保持同步
- 避免手动维护两份文档导致的不一致

使用：
    python tools/docs/sync_public_docs.py
    python tools/docs/sync_public_docs.py --dry-run  # 预览变更
"""

import json
import re
from pathlib import Path
from typing import List, Tuple


def extract_public_sections(constitution_path: Path) -> str:
    """从宪法中提取可公开的部分"""
    content = constitution_path.read_text(encoding="utf-8")

    # 提取核心原则（前言 + 10 条宪法）
    lines = content.split("\n")
    public_lines: List[str] = []

    # 保留标题和前言
    in_public_section = True
    for line in lines:
        # 跳过内部实现细节
        if "附录" in line or "Doctor Claw" in line:
            in_public_section = False

        if in_public_section:
            public_lines.append(line)

        # 只保留到第十条
        if line.startswith("## 第十条"):
            # 继续读取第十条的内容
            continue
        elif line.startswith("## 附录"):
            break

    return "\n".join(public_lines)


def sync_architecture_principles(constitution_dir: Path, docs_dir: Path, dry_run: bool = False) -> None:
    """同步架构原则文档"""
    source = constitution_dir / "01_宪法.md"
    target = docs_dir / "architecture" / "principles.md"

    if not source.exists():
        print(f"⚠️  源文件不存在: {source}")
        return

    public_content = extract_public_sections(source)

    # 添加公开文档的头部说明
    header = """# SafeClaw 核心原则

> 本文档从内部设计文档提取，介绍 SafeClaw 的核心设计原则。
> 完整的内部设计文档不对外公开。

---

"""

    footer = """

---

## 了解更多

- [协议层规范](../../specs/) - 完整的技术规范
- [API 文档](../api/) - 接口参考
- [使用指南](../guides/) - 快速上手

"""

    final_content = header + public_content + footer

    if dry_run:
        print(f"📄 将更新: {target}")
        print(f"   内容长度: {len(final_content)} 字符")
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(final_content, encoding="utf-8")
        print(f"✅ 已更新: {target}")


def sync_roadmap(constitution_dir: Path, docs_dir: Path, dry_run: bool = False) -> None:
    """同步开发路线图（简化版）"""
    source = constitution_dir / "03_开发蓝图.md"
    target = docs_dir / "roadmap.md"

    if not source.exists():
        print(f"⚠️  源文件不存在: {source}")
        return

    content = source.read_text(encoding="utf-8")

    # 提取 Phase 信息，隐藏内部细节
    phases = re.findall(r"## (Phase \d+[^#]*?)(?=\n##|\Z)", content, re.DOTALL)

    public_content = "# SafeClaw 开发路线图\n\n"
    public_content += "> 本路线图展示 SafeClaw 的分阶段开发计划。\n\n"

    for phase in phases:
        # 只保留 Phase 标题和目标，移除内部实现细节
        lines = phase.split("\n")
        public_lines = [lines[0]]  # Phase 标题

        for line in lines[1:]:
            # 跳过内部实现细节
            if "内部" in line or "TODO" in line or "待定" in line:
                continue
            if line.strip().startswith("-") and ("实现" in line or "代码" in line):
                continue
            public_lines.append(line)

        public_content += "\n".join(public_lines) + "\n\n"

    if dry_run:
        print(f"📄 将更新: {target}")
        print(f"   内容长度: {len(public_content)} 字符")
    else:
        target.write_text(public_content, encoding="utf-8")
        print(f"✅ 已更新: {target}")


def main(dry_run: bool = False) -> None:
    """主函数"""
    repo_root = Path(__file__).parent.parent.parent
    constitution_dir = repo_root / ".constitution"
    docs_dir = repo_root / "docs"

    print("🔄 开始同步公开文档...\n")

    if not constitution_dir.exists():
        print(f"❌ 内部真源目录不存在: {constitution_dir}")
        return

    # 同步各个文档
    sync_architecture_principles(constitution_dir, docs_dir, dry_run)
    sync_roadmap(constitution_dir, docs_dir, dry_run)

    print("\n✨ 同步完成！")

    if dry_run:
        print("\n💡 这是预览模式，未实际修改文件。")
        print("   移除 --dry-run 参数以执行实际同步。")


if __name__ == "__main__":
    import sys
    dry_run = "--dry-run" in sys.argv
    main(dry_run)
