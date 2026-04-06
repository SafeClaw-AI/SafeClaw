# SafeClaw 开发路线图

> 本路线图展示 SafeClaw 的分阶段开发计划。

Phase 0: Schema 共识（1 周）

specs/ 完整集合: Worker 状态机(含 Uncertain) + Effect 四阶段 + effect_attempts + probe_spec(**含 unprobable 声明**)(v3.2) + recovery_lease(**含 fencing_token + TTL**)(v3.2) + 并发/权限/心跳/Sidecar/记忆/财务 + Preflight/SPI/插件信任 + **Chaos Monkey failure_model.json**(v3.2)。


Phase 2

浏览器自动化 / DAG / 模型路由 / FTS5 / 记忆浓缩器 / Persona×Scope / 受控 system_exec(带 adapter+probe) / WASM / 团队化 / **外部模式映射接口**(支持 everything-codex 七模式等外部心智模型映射到 Tier/scope 组合; 模式定义在独立仓库,SafeClaw 只提供映射 API)。


