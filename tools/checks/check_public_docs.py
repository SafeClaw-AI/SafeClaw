from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.checks.check_ledger_alignment import collect_ledger_errors
from tools.checks.ledger_index_manifest import load_ledger_index_manifest

LEDGER_MANIFEST = load_ledger_index_manifest()
README_FILE = REPO_ROOT / "README.md"
STATUS_FILE = REPO_ROOT / "STATUS.md"
CHANGELOG_FILE = REPO_ROOT / "CHANGELOG.md"
DECISIONS_FILE = REPO_ROOT / "DECISIONS.md"
ROOT_ARCHITECTURE_FILE = REPO_ROOT / "ARCHITECTURE.md"
DEV_PLAN_FILE = LEDGER_MANIFEST.resolve_existing_path("dev-plan")
MVP_PROGRESS_FILE = LEDGER_MANIFEST.resolve_existing_path("mvp-progress")
PUSH_LOG_FILE = LEDGER_MANIFEST.resolve_existing_path("push-log")
SCOPE_FILE = REPO_ROOT / "docs" / "V1_SCOPE.md"
TRIAGE_FILE = REPO_ROOT / "docs" / "V1_TASK_TRIAGE.md"
DEVLOG_FILE = REPO_ROOT / "docs" / "DEVLOG.md"
IMPLEMENTATION_STRATEGY_FILE = REPO_ROOT / "docs" / "IMPLEMENTATION_STRATEGY.md"
REFERENCE_HYGIENE_FILE = REPO_ROOT / "docs" / "reference" / "01-反屎山工程规范.md"
SPECS_README_FILE = REPO_ROOT / "specs" / "README.md"
CONTRACTS_README_FILE = REPO_ROOT / "tests" / "contracts" / "README.md"
CODEGEN_README_FILE = REPO_ROOT / "tools" / "codegen" / "README.md"
SCHEMA_DIFF_README_FILE = REPO_ROOT / "tools" / "schema_diff" / "README.md"
DOCS_README_FILE = REPO_ROOT / "docs" / "README.md"
CHANCELLOR_ENTRY_BASELINE_FILE = (
    REPO_ROOT / "docs" / "chancellor-mode" / "v2" / "01-m1b-exit-and-m2-panel-entry.md"
)
CHANCELLOR_PANEL_TRUTH_FILE = (
    REPO_ROOT / "docs" / "chancellor-mode" / "v2" / "02-m2-panel-command-truth-source.md"
)
CHANCELLOR_PRODUCT_REBASELINE_FILE = (
    REPO_ROOT / "docs" / "chancellor-mode" / "v2" / "03-m2-product-value-rebaseline.md"
)
DIRECTORY_LOCK_FILE = REPO_ROOT / "docs" / "30-方案" / "02-V4-目录锁定清单.md"
REFERENCE_REBASELINE_FILE = REPO_ROOT / "docs" / "30-方案" / "20-V4-reference-compliance-rebaseline-record-20260329_030242.md"
TOOLS_README_FILE = REPO_ROOT / "tools" / "README.md"
CHECKS_README_FILE = REPO_ROOT / "tools" / "checks" / "README.md"
TESTS_README_FILE = REPO_ROOT / "tests" / "README.md"
OPERATOR_PLAYBOOK_FILE = REPO_ROOT / "tools" / "mvp" / "OPERATOR_PLAYBOOK.md"
MVP_README_FILE = REPO_ROOT / "tools" / "mvp" / "README.md"
LINT_README_FILE = REPO_ROOT / "tools" / "lint" / "README.md"
VERSION_FILE = REPO_ROOT / "VERSION"
BOUNDARY_NOTE_TITLE = "当前边界说明（2026-04-04）"
BOUNDARY_NOTE_DECISION = "SafeClaw 当前不单独开发丞相模式/大都督模式等外部解释层功能。"
BOUNDARY_NOTE_FUSION = "若后续需要接入，只做外部程序拼接融合，不在 SafeClaw 仓内继续扩写独立模式功能。"
BOUNDARY_NOTE_SCOPE = "不作为 SafeClaw 当前主线功能承诺"
CURRENT_CLOSEOUT_OVERVIEW_TITLE = "当前收口总览（2026-04-04）"
CURRENT_SUBMISSION_EXECUTION_SUMMARY_TITLE = "当前提交执行摘要（2026-04-04）"
BATCH_ONE_PRE_SUBMIT_CHECKLIST_TITLE = "批次一提交前验证清单（边界治理 13）"
BATCH_TWO_PRE_SUBMIT_CHECKLIST_TITLE = "批次二提交前验证清单（自检治理 8）"
BATCH_THREE_PRE_SUBMIT_CHECKLIST_TITLE = "批次三提交前验证清单（个人部署链 3）"
CURRENT_SUBMISSION_CLOSEOUT_TABLE_TITLE = "当前提交/归档收口表（2026-04-04）"
CURRENT_SUBMISSION_READINESS_TABLE_TITLE = "当前提交前就绪核对（2026-04-04）"

REQUIRED_MARKERS = {
    README_FILE: [
        "specs/",
        "tests/contracts/",
        "tools/checks/",
        "tools/mvp/OPERATOR_PLAYBOOK.md",
        "local-only",
        "STATUS.md",
        "CHANGELOG.md",
        "DECISIONS.md",
        "ARCHITECTURE.md",
        "Python/Tkinter",
        "Tauri + React",
        "protocol-first",
        "模型路由矩阵（稳定边界）",
        "高层路线图",
        "成功指标",
        "English Summary",
        "The current stable operator path is still local-only",
    ],
    STATUS_FILE: [
        "当前状态（滚动更新）",
        "本周进度",
        "当前风险",
        "当前瓶颈",
        "下周计划",
        "README 主线",
        "specs/` → `tests/contracts/` → implementation",
        "local-only",
    ],
    CHANGELOG_FILE: [
        "更新日志",
        "SSOT 五件套",
        "README.md",
        "STATUS.md",
        "DECISIONS.md",
        "ARCHITECTURE.md",
        "check_public_docs.py",
    ],
    DECISIONS_FILE: [
        "架构与流程决策记录",
        "README.md",
        "STATUS.md",
        "CHANGELOG.md",
        "DECISIONS.md",
        "ARCHITECTURE.md",
        "specs/",
        "docs/reference/",
        "开发计划.md",
        "PUSH_LOG.md",
    ],
    ROOT_ARCHITECTURE_FILE: [
        "系统架构真源",
        "模块划分",
        "依赖关系",
        "不变量",
        "关键设计原则",
        "safeclaw-core/",
        "safeclaw-sqlite/",
        "tools/checks/",
        "tools/mvp/",
        "specs/",
    ],
    DEV_PLAN_FILE: [
        BOUNDARY_NOTE_TITLE,
        BOUNDARY_NOTE_DECISION,
        BOUNDARY_NOTE_FUSION,
        "docs/chancellor-mode/v2/",
        "docs/records/开发计划.md",
        "docs/records/MVP_PROGRESS.md",
        "docs/records/PUSH_LOG.md",
        "tools/mvp/",
        "archive-note -> undo",
    ],
    MVP_PROGRESS_FILE: [
        BOUNDARY_NOTE_TITLE,
        BOUNDARY_NOTE_DECISION,
        BOUNDARY_NOTE_FUSION,
        CURRENT_CLOSEOUT_OVERVIEW_TITLE,
        "边界治理",
        "自检治理",
        "个人部署链",
        "当前工作区已干净",
        "未归类改动：0 项",
        "只作为历史切片与后期拼接融合参考",
        "不作为当前主线真源",
        "`tools/mvp/chancellor_panel.py` 只保留快照消费与兼容检查",
        "`python -X utf8 tools/checks/check_public_docs.py` 必须继续全绿",
        "`python -X utf8 tools/checks/selfcheck.py` 继续作为唯一总验收入口",
        "`tools/checks/worktree_groups.py` 继续输出摘要优先、明细随后的人话收口视图",
        "`.gitattributes` 继续作为当前仓库的换行真源",
        "`tmp/` 只允许放临时验证产物",
        "`safeclaw-personal.cmd` / `safeclaw-personal.ps1` 继续只服务 `archive-note -> status -> undo` 个人金线",
        "`tools/mvp/safeclaw_personal_deploy.py` 只保留 `deploy / rollback / status`",
        "回滚只切 release 指针，不碰个人数据目录",
        "个人部署链继续与外部丞相模式隔离",
        "本轮已提交 `80fe243`",
        "本轮已提交 `f6ca6a1`",
        "本轮已提交 `7937fa4`",
        "当前这一轮三组治理已全部完成提交，工作区干净",
        "提交/归档顺序、批次清单与收口表统一以 `docs/records/PUSH_LOG.md` 为准，本表不再重复展开提交层细节",
        "若后续开启新一轮迭代，先刷新顶部摘要再新增改动，不沿用本轮旧数字",
        "docs/chancellor-mode/v2/",
        "历史切片",
    ],
    PUSH_LOG_FILE: [
        BOUNDARY_NOTE_TITLE,
        BOUNDARY_NOTE_DECISION,
        BOUNDARY_NOTE_FUSION,
        CURRENT_SUBMISSION_EXECUTION_SUMMARY_TITLE,
        CURRENT_SUBMISSION_CLOSEOUT_TABLE_TITLE,
        "当前工作区总改动：0；当前工作区已干净；未归类：0。",
        "本轮三批提交已完成：边界治理 13 / 自检治理 8 / 个人部署链 3。",
        "`7937fa4 feat: lock personal deploy governance closeout`",
        "`f6ca6a1 test: lock selfcheck governance closeout`",
        "`80fe243 docs: lock boundary governance closeout`",
        "下一步：若开启新一轮迭代，先刷新本摘要与分组表，再新增批次清单。",
        "| 边界治理 | 已提交 | `80fe243` |",
        "| 自检治理 | 已提交 | `f6ca6a1` |",
        "| 个人部署链 | 已提交 | `7937fa4` |",
        "当前三组已完成提交，工作区干净。",
        "若后续出现新改动，重新生成分组摘要和批次清单，不沿用本轮旧数字。",
        "历史流水",
    ],
    SCOPE_FILE: [
        "Phase 0",
        "specs/",
        "tests/contracts/",
        "tools/checks/",
        "tools/lint/",
        "selfcheck.py",
        "ledger_index_manifest.py",
        "check_ledger_alignment.py",
        "check_consistency.py",
        "check_versions.py",
        "check_structure.py",
        "check_scaffold.py",
        "check_public_docs.py",
        "Contract tests",
    ],
    TRIAGE_FILE: [
        "specs/",
        "CI",
        "codegen",
        "Frozen",
        "selfcheck.py",
        "ledger_index_manifest.py",
        "check_ledger_alignment.py",
        "check_consistency.py",
        "check_versions.py",
        "check_structure.py",
        "check_scaffold.py",
        "check_public_docs.py",
        "Contract tests",
    ],
    DEVLOG_FILE: [
        "README.md",
        "specs/",
        "Phase 0",
        "selfcheck.py",
        ".github/workflows/contracts.yml",
        "ledger_index_manifest.py",
        "check_ledger_alignment.py",
        "check_consistency.py",
        "check_versions.py",
        "check_structure.py",
        "check_scaffold.py",
        "check_public_docs.py",
        "Contract tests",
    ],
    IMPLEMENTATION_STRATEGY_FILE: [
        "README.md",
        "specs/",
        "tests/contracts/",
        "tools/checks/",
        "selfcheck.py",
        "ledger_index_manifest.py",
        "check_ledger_alignment.py",
        "check_consistency.py",
        "check_versions.py",
        "check_structure.py",
        "check_scaffold.py",
        "check_public_docs.py",
        "Contract tests",
    ],
    SPECS_README_FILE: [
        "specs/",
        "generated/index.json",
        "plugin_runner.template.jsonc",
        "ledger-first policy chain",
        "selfcheck.py",
        "ledger_index_manifest.py",
        "check_ledger_alignment.py",
        "check_consistency.py",
        "check_versions.py",
        "check_structure.py",
        "check_scaffold.py",
        "check_public_docs.py",
        "Contract tests",
    ],
    CONTRACTS_README_FILE: [
        "specs/",
        "tools/checks/",
        "generated/",
        "selfcheck.py",
        "ledger_index_manifest.py",
        "check_ledger_alignment.py",
        "check_consistency.py",
        "check_versions.py",
        "check_structure.py",
        "check_scaffold.py",
        "check_public_docs.py",
        "Contract tests",
    ],
    CODEGEN_README_FILE: [
        "regenerate_all.py",
        "generated/index.json",
        "stable_ids.json",
        "selfcheck.py",
        ".github/workflows/contracts.yml",
        "ledger_index_manifest.py",
        "check_ledger_alignment.py",
        "check_consistency.py",
        "check_versions.py",
        "check_structure.py",
        "check_scaffold.py",
        "check_public_docs.py",
        "Contract tests",
    ],
    SCHEMA_DIFF_README_FILE: [
        "--json-out",
        "--fail-on-diff",
        "schema",
        "selfcheck.py",
        ".github/workflows/contracts.yml",
        "ledger_index_manifest.py",
        "check_ledger_alignment.py",
        "check_consistency.py",
        "check_versions.py",
        "check_structure.py",
        "check_scaffold.py",
        "check_public_docs.py",
        "Contract tests",
    ],
    DOCS_README_FILE: [
        "README.md",
        "STATUS.md",
        "CHANGELOG.md",
        "DECISIONS.md",
        "ARCHITECTURE.md",
        "safeclaw-core/ARCHITECTURE.md",
        "L0",
        "L1",
        "L2",
        "L3",
        "DEVLOG.md",
        "V1_SCOPE.md",
        "V1_TASK_TRIAGE.md",
        "02-V4-目录锁定清单.md",
        "08-V4-ledger-index-manifest.json",
        "generated/index.json",
        "docs/records/",
        "docs/chancellor-mode/v2/",
        "selfcheck.py",
        "tests/contracts/",
    ],
    REFERENCE_HYGIENE_FILE: [
        "先分类,再落盘",
        "绝对红线禁令",
        "自动化门禁",
    ],
    CHANCELLOR_ENTRY_BASELINE_FILE: [
        BOUNDARY_NOTE_DECISION,
        BOUNDARY_NOTE_FUSION,
        BOUNDARY_NOTE_SCOPE,
        "官方 Codex 面板",
        "`丞相状态`",
        "`丞相检查`",
        "`丞相版本`",
        "`丞相验板`",
    ],
    CHANCELLOR_PANEL_TRUTH_FILE: [
        BOUNDARY_NOTE_DECISION,
        BOUNDARY_NOTE_FUSION,
        BOUNDARY_NOTE_SCOPE,
        "官方 Codex 面板",
        "`丞相状态`",
        "`丞相检查`",
        "`丞相版本`",
        "`丞相验板`",
        "`mode`",
        "`stability`",
        "`next_step`",
        "`checks_run`",
        "`version_source`",
        "`steps`",
    ],
    CHANCELLOR_PRODUCT_REBASELINE_FILE: [
        BOUNDARY_NOTE_DECISION,
        BOUNDARY_NOTE_FUSION,
        BOUNDARY_NOTE_SCOPE,
        "`M2-1` / `M2-2` 已经证明",
        "可读账单",
        "真实任务",
        "`undo`",
        "官方 Codex 面板",
        "终端仍只保留给维护",
        "M2-P0-1",
        "M2-P0-4",
    ],
    DIRECTORY_LOCK_FILE: [
        "当前仓库的目录锁定依据",
        "迁移前临时保留",
        "docs/round_logs/",
        "specs/spi/keystore/",
        "04-V4-repo-hygiene-migration-plan.md",
        "06-V4-ledger-compat-index-spec.md",
        "08-V4-ledger-index-manifest.json",
        "后期拼接融合预留资料",
        "不属于 SafeClaw 当前主线功能真源",
    ],
    TOOLS_README_FILE: [
        "tools/checks/",
        "tools/codegen/",
        "selfcheck.py",
        "Current selfcheck policy",
        "docs/reference/",
        "02-V4-目录锁定清单.md",
        "ledger_index_manifest.py",
        "check_ledger_alignment.py",
        "check_consistency.py",
        "check_versions.py",
        "check_structure.py",
        "check_scaffold.py",
        "check_public_docs.py",
        "check_reference_redlines.py",
        "Contract tests",
    ],
    CHECKS_README_FILE: [
        "迁移期优先链路",
        "docs/reference/",
        "02-V4-目录锁定清单.md",
        "ledger_index_manifest.py",
        "check_consistency.py",
        "check_versions.py",
        "check_structure.py",
        "check_scaffold.py",
        "check_public_docs.py",
        "check_reference_redlines.py",
        "Contract tests",
    ],
    TESTS_README_FILE: [
        "tests/contracts/",
        "tests/fixtures/",
        "合同测试",
        "selfcheck.py",
        "ledger_index_manifest.py",
        "check_ledger_alignment.py",
        "check_consistency.py",
        "check_versions.py",
        "check_structure.py",
        "check_scaffold.py",
        "check_public_docs.py",
    ],
    OPERATOR_PLAYBOOK_FILE: [
        "README.md",
        "workspace --name demo",
        "doctor",
        "service-run --report",
        "service-status --limit 5",
        "service-retry --report",
        "service-recover --report",
        "verify --json",
        "local-only",
        "ai-reason",
        "tools\\checks\\selfcheck.py",
        "ledger_index_manifest.py",
        "check_ledger_alignment.py",
        "check_consistency.py",
        "check_versions.py",
        "check_structure.py",
        "check_scaffold.py",
        "check_public_docs.py",
        "Contract tests",
    ],
    MVP_README_FILE: [
        "tools/mvp/README.md",
        ".github/workflows/contracts.yml",
        "ledger_index_manifest.py",
        "check_ledger_alignment.py",
        "check_consistency.py",
        "check_versions.py",
        "check_structure.py",
        "check_scaffold.py",
        "check_public_docs.py",
        "Contract tests",
    ],
    LINT_README_FILE: [
        "tools/lint/check_naming.py",
        ".github/workflows/contracts.yml",
        "ledger_index_manifest.py",
        "check_ledger_alignment.py",
        "check_consistency.py",
        "check_versions.py",
        "check_structure.py",
        "check_scaffold.py",
        "check_public_docs.py",
        "Contract tests",
    ],
}

FORBIDDEN_MARKERS = {
    README_FILE: [
        "当前公开协议版本号为 `",
    ],
    DEV_PLAN_FILE: [
        "- 当前 SafeClaw 主线以 `README.md`、`开发计划.md`、`tools/mvp/` 现行最小闭环为准；`docs/chancellor-mode/v2/` 仅保留外部模式历史方案与后期拼接融合参考。",
        "- 每轮完成后必须同步：`MVP_PROGRESS.md`、`PUSH_LOG.md`、`开发计划.md`。",
        "- 若行为变化可见，必须同步 `MVP_PROGRESS.md`、`PUSH_LOG.md` 和 `开发计划.md`。",
        "- 台账写法要求：`MVP_PROGRESS.md`、`PUSH_LOG.md` 尽量使用中文、短句、小学生能懂；先写“做了什么”，再写“有什么用”。",
        "- 台账：`MVP_PROGRESS.md`、`PUSH_LOG.md`",
    ],
    MVP_PROGRESS_FILE: [
        "`MVP_PROGRESS.md`、`PUSH_LOG.md` 已接入公开文档检查",
        "提交/归档顺序、批次清单与收口表统一以 `PUSH_LOG.md` 为准，本表不再重复展开提交层细节",
    ],
}

def collect_reference_rebaseline_errors() -> list[str]:
    if not REFERENCE_REBASELINE_FILE.exists():
        return [f"缺少公开文档: {REFERENCE_REBASELINE_FILE.relative_to(REPO_ROOT).as_posix()}"]

    text = REFERENCE_REBASELINE_FILE.read_text(encoding="utf-8")
    errors: list[str] = []
    required_markers = [
        "已经过期的旧结论",
        "目录锁定清单",
        "公开文档门禁",
        "docs/round_logs/",
        "先止血、后迁移",
    ]
    for marker in required_markers:
        if marker not in text:
            errors.append(
                f"公开文档缺少关键标记: {REFERENCE_REBASELINE_FILE.relative_to(REPO_ROOT).as_posix()} -> {marker}"
            )

    return errors


def collect_errors() -> list[str]:
    repo_version = VERSION_FILE.read_text(encoding="utf-8").strip()
    errors: list[str] = []

    for path, markers in REQUIRED_MARKERS.items():
        if not path.exists():
            errors.append(f"缺少公开文档: {path.relative_to(REPO_ROOT).as_posix()}")
            continue

        text = path.read_text(encoding="utf-8")
        for marker in markers:
            current_marker = repo_version if marker == "0.1.1" else marker
            if current_marker not in text:
                errors.append(
                    f"公开文档缺少关键标记: {path.relative_to(REPO_ROOT).as_posix()} -> {current_marker}"
                )

        for marker in FORBIDDEN_MARKERS.get(path, []):
            if marker in text:
                errors.append(
                    f"公开文档仍含过期根路径口径: {path.relative_to(REPO_ROOT).as_posix()} -> {marker}"
                )

    errors.extend(collect_reference_rebaseline_errors())
    errors.extend(collect_ledger_errors())

    return errors


def main() -> int:
    errors = collect_errors()
    if errors:
        print("Public docs alignment check failed:")
        for item in errors:
            print(f"- {item}")
        return 1

    print("Public docs alignment check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
