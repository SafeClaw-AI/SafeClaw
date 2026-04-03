# SafeClaw Personal MVP Playbook

只给当前仓库主人自己用的最小闭环。

## 目的
- 只保留 `archive-note -> 可读账单 -> undo`
- 不混入丞相模式
- 不混入大都督模式
- 不等待大 GUI、商业化、安全包、多人协作；当前只补一层中文小面板

## 入口
### 明早直接用（已部署生产入口）
- `%USERPROFILE%\.safeclaw-personal-production\safeclaw-personal-panel.cmd`
- `%USERPROFILE%\.safeclaw-personal-production\safeclaw-personal-panel.ps1`
- 备份 CLI：`%USERPROFILE%\.safeclaw-personal-production\safeclaw-personal.cmd` / `%USERPROFILE%\.safeclaw-personal-production\safeclaw-personal.ps1`
- 如果你只是要直接用，先不要回到仓库内入口。

### 维护层入口（仓库内）
- `tools\mvp\safeclaw_personal_mvp.cmd`
- `tools\mvp\safeclaw_personal_mvp.ps1`
- `tools/mvp/safeclaw_personal_mvp.py`

## 默认数据位置
- 个人根目录：`%USERPROFILE%\.safeclaw-personal`
- 状态库：`%USERPROFILE%\.safeclaw-personal\state\session.db`
- 最近一次任务：`%USERPROFILE%\.safeclaw-personal\state\last_note.json`
- 归档目录：`%USERPROFILE%\.safeclaw-personal\archive`

可用 `SAFECLAW_PERSONAL_ROOT` 覆盖默认根目录，方便测试或迁移。

## 生产部署（维护层动作）
- 部署命令：`python -X utf8 tools/mvp/safeclaw_personal_deploy.py deploy`
- 面板入口：`%USERPROFILE%\\.safeclaw-personal-production\\safeclaw-personal-panel.cmd`
- 备份 CLI：`%USERPROFILE%\\.safeclaw-personal-production\\safeclaw-personal.cmd`
- 查看部署态：`python -X utf8 tools/mvp/safeclaw_personal_deploy.py status`
- 回滚上一版：`python -X utf8 tools/mvp/safeclaw_personal_deploy.py rollback`
- 可用 `SAFECLAW_PERSONAL_DEPLOY_ROOT` 覆盖默认部署根目录，方便测试或迁移。

## 最短循环
1. 先点开个人中文小面板
2. 写一条笔记
3. 看当前状态
4. 需要时点“撤销上一步”

## 命令
### 1) 写入归档笔记（生产位）
```bat
%USERPROFILE%\.safeclaw-personal-production\safeclaw-personal.cmd archive-note --name "Daily Note" --content "今天先把最小版跑通"
```

### 2) 查看当前状态（生产位）
```bat
%USERPROFILE%\.safeclaw-personal-production\safeclaw-personal.cmd status
```

### 3) 撤销最近一次归档（生产位）
```bat
%USERPROFILE%\.safeclaw-personal-production\safeclaw-personal.cmd undo
```

### 4) 仓库内维护入口（只在维护时用）
```bat
tools\mvp\safeclaw_personal_mvp.cmd status
```

## 当前边界
- 这是维护层最小生产版，不是假装已经做完正式产品
- 当前只服务一个人自己快速使用、快速提意见、快速回改
- 当前不承担丞相解释层，也不承担大都督调度层
