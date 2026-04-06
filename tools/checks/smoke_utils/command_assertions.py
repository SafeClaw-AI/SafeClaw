"""Command and verification assertion functions for smoke tests."""


def assert_verify_json_result(
    result: dict[str, object] | None,
    errors: list[str],
    name: str,
) -> None:
    if result is None:
        return

    if result.get("exit_code") != 0:
        errors.append(f"{name} missing exit_code=0")

    elif result.get("script") != "tools/checks/check_mvp_operator_flow.py":
        errors.append(f"{name} missing verify script path")

    elif not result.get("python"):
        errors.append(f"{name} missing python path")

    elif "MVP operator flow check passed." not in str(
        result.get("captured_output", "")
    ):
        errors.append(f"{name} missing verify success output")


def assert_doctor_json_result(
    result: dict[str, object] | None,
    errors: list[str],
    name: str,
    *,
    expected_db_path: str,
    expected_output_path: str,
    expected_db_source: str = "flag",
    expected_output_source: str = "flag",
    expected_workspace_active: bool | None = None,
    expected_workspace_name: str | None = None,
) -> None:
    if result is None:
        return

    python_info = result.get("python") or {}

    workspace_info = result.get("workspace") or {}

    if result.get("status") != "ready":
        errors.append(f"{name} missing status=ready")

    elif result.get("failing_checks") != []:
        errors.append(f"{name} missing empty failing_checks")

    elif not isinstance(python_info, dict) or python_info.get("ok") is not True:
        errors.append(f"{name} missing python ok")

    elif not python_info.get("detail"):
        errors.append(f"{name} missing python detail")

    elif result.get("entrypoints", {}).get("cmd", {}).get("exists") is not True:
        errors.append(f"{name} missing cmd entry ok")

    elif result.get("entrypoints", {}).get("ps1", {}).get("exists") is not True:
        errors.append(f"{name} missing ps1 entry ok")

    elif result.get("entrypoints", {}).get("py", {}).get("exists") is not True:
        errors.append(f"{name} missing py entry ok")

    elif result.get("cargo", {}).get("ok") is not True:
        errors.append(f"{name} missing cargo ok")

    elif result.get("toolchain", {}).get("ok") is not True:
        errors.append(f"{name} missing toolchain ok")

    elif result.get("linker", {}).get("ok") is not True:
        errors.append(f"{name} missing linker ok")

    elif result.get("session_path") != "target\mvp\last_session.json":
        errors.append(f"{name} missing session_path")

    elif (
        not isinstance(workspace_info, dict)
        or workspace_info.get("path") != "target\mvp\workspace.json"
    ):
        errors.append(f"{name} missing workspace_path")

    elif (
        expected_workspace_active is not None
        and workspace_info.get("active") is not expected_workspace_active
    ):
        errors.append(f"{name} missing workspace active={expected_workspace_active}")

    elif (
        expected_workspace_name is None
        and expected_workspace_active is False
        and workspace_info.get("name") is not None
    ):
        errors.append(f"{name} unexpected workspace name")

    elif (
        expected_workspace_name is not None
        and workspace_info.get("name") != expected_workspace_name
    ):
        errors.append(f"{name} missing workspace name={expected_workspace_name}")

    elif result.get("db", {}).get("path") != expected_db_path:
        errors.append(f"{name} missing db path={expected_db_path}")

    elif result.get("db", {}).get("source") != expected_db_source:
        errors.append(f"{name} missing db source={expected_db_source}")

    elif result.get("output", {}).get("path") != expected_output_path:
        errors.append(f"{name} missing output path={expected_output_path}")

    elif result.get("output", {}).get("source") != expected_output_source:
        errors.append(f"{name} missing output source={expected_output_source}")

    else:
        runtime_profile = result.get("runtime_profile") or {}

        model_provider = result.get("model_provider") or {}

        sidecar = result.get("sidecar") or {}

        if not isinstance(runtime_profile, dict):
            errors.append(f"{name} missing runtime_profile")

        elif runtime_profile.get("mode") != "local_mvp":
            errors.append(f"{name} missing runtime_profile.mode=local_mvp")

        elif runtime_profile.get("offline_ready") is not True:
            errors.append(f"{name} missing runtime_profile.offline_ready=true")

        elif runtime_profile.get("llm_required") is not False:
            errors.append(f"{name} missing runtime_profile.llm_required=false")

        elif runtime_profile.get("sidecar_required") is not False:
            errors.append(f"{name} missing runtime_profile.sidecar_required=false")

        elif not isinstance(model_provider, dict):
            errors.append(f"{name} missing model_provider")

        elif model_provider.get("configured") is not False:
            errors.append(f"{name} missing model_provider.configured=false")

        elif model_provider.get("required") is not False:
            errors.append(f"{name} missing model_provider.required=false")

        elif model_provider.get("status") != "not-configured":
            errors.append(f"{name} missing model_provider.status=not-configured")

        elif model_provider.get("degradation_mode") != "local_only_ok":
            errors.append(
                f"{name} missing model_provider.degradation_mode=local_only_ok"
            )

        elif not model_provider.get("detail"):
            errors.append(f"{name} missing model_provider.detail")

        elif not isinstance(sidecar, dict):
            errors.append(f"{name} missing sidecar")

        elif sidecar.get("configured") is not False:
            errors.append(f"{name} missing sidecar.configured=false")

        elif sidecar.get("required") is not False:
            errors.append(f"{name} missing sidecar.required=false")

        elif sidecar.get("status") != "not-configured":
            errors.append(f"{name} missing sidecar.status=not-configured")

        elif not sidecar.get("detail"):
            errors.append(f"{name} missing sidecar.detail")


def assert_preflight_json_result(
    result: dict[str, object] | None,
    errors: list[str],
    name: str,
    *,
    expected_requested_action: str,
    expected_known: bool,
    expected_action_class: str,
    expected_tier: str,
    expected_writes_state: bool,
    expected_permission_context_source: str,
    expected_target_scope: str,
    expected_requires_write: bool,
    expected_doctor_bypass: bool,
    expected_permission_context_applied: bool,
    expected_permission_tier: str,
    expected_permission_policy: str,
    expected_permission_reason: str,
    expected_permission_enforced: bool,
    expected_action_allowed: bool,
    expected_action_decision: str,
    expected_action_reason: str,
    expected_allowed: bool,
    expected_decision: str,
    expected_offline_ready: bool,
    expected_degradation_mode: str,
    expected_reason: str,
    expected_requires_model: bool = False,
    expected_requires_sidecar: bool = False,
    expected_error_code: str | None = None,
) -> None:
    if result is None:
        return

    runtime_profile = result.get("runtime_profile") or {}

    model_provider = result.get("model_provider") or {}

    sidecar = result.get("sidecar") or {}

    if result.get("requested_action") != expected_requested_action:
        errors.append(f"{name} missing requested_action={expected_requested_action}")

    elif result.get("known") is not expected_known:
        errors.append(f"{name} missing known={expected_known}")

    elif result.get("action_class") != expected_action_class:
        errors.append(f"{name} missing action_class={expected_action_class}")

    elif result.get("tier") != expected_tier:
        errors.append(f"{name} missing tier={expected_tier}")

    elif result.get("writes_state") is not expected_writes_state:
        errors.append(f"{name} missing writes_state={expected_writes_state}")

    elif result.get("permission_context_source") != expected_permission_context_source:
        errors.append(
            f"{name} missing permission_context_source={expected_permission_context_source}"
        )

    elif result.get("target_scope") != expected_target_scope:
        errors.append(f"{name} missing target_scope={expected_target_scope}")

    elif result.get("requires_write") is not expected_requires_write:
        errors.append(f"{name} missing requires_write={expected_requires_write}")

    elif result.get("doctor_bypass") is not expected_doctor_bypass:
        errors.append(f"{name} missing doctor_bypass={expected_doctor_bypass}")

    elif (
        result.get("permission_context_applied")
        is not expected_permission_context_applied
    ):
        errors.append(
            f"{name} missing permission_context_applied={expected_permission_context_applied}"
        )

    elif result.get("permission_tier") != expected_permission_tier:
        errors.append(f"{name} missing permission_tier={expected_permission_tier}")

    elif result.get("permission_policy") != expected_permission_policy:
        errors.append(f"{name} missing permission_policy={expected_permission_policy}")

    elif result.get("permission_reason") != expected_permission_reason:
        errors.append(f"{name} missing permission_reason={expected_permission_reason}")

    elif result.get("permission_enforced") is not expected_permission_enforced:
        errors.append(
            f"{name} missing permission_enforced={expected_permission_enforced}"
        )

    elif result.get("action_allowed") is not expected_action_allowed:
        errors.append(f"{name} missing action_allowed={expected_action_allowed}")

    elif result.get("action_decision") != expected_action_decision:
        errors.append(f"{name} missing action_decision={expected_action_decision}")

    elif result.get("action_reason") != expected_action_reason:
        errors.append(f"{name} missing action_reason={expected_action_reason}")

    elif result.get("allowed") is not expected_allowed:
        errors.append(f"{name} missing allowed={expected_allowed}")

    elif result.get("decision") != expected_decision:
        errors.append(f"{name} missing decision={expected_decision}")

    elif result.get("offline_ready") is not expected_offline_ready:
        errors.append(f"{name} missing offline_ready={expected_offline_ready}")

    elif result.get("requires_model") is not expected_requires_model:
        errors.append(f"{name} missing requires_model={expected_requires_model}")

    elif result.get("requires_sidecar") is not expected_requires_sidecar:
        errors.append(f"{name} missing requires_sidecar={expected_requires_sidecar}")

    elif result.get("degradation_mode") != expected_degradation_mode:
        errors.append(f"{name} missing degradation_mode={expected_degradation_mode}")

    elif result.get("reason") != expected_reason:
        errors.append(f"{name} missing reason={expected_reason}")

    elif (
        expected_error_code is not None
        and result.get("error_code") != expected_error_code
    ):
        errors.append(f"{name} missing error_code={expected_error_code}")

    elif not result.get("detail"):
        errors.append(f"{name} missing detail")

    elif (
        not isinstance(runtime_profile, dict)
        or runtime_profile.get("mode") != "local_mvp"
    ):
        errors.append(f"{name} missing runtime_profile.mode=local_mvp")

    elif runtime_profile.get("offline_ready") is not True:
        errors.append(f"{name} missing runtime_profile.offline_ready=true")

    elif (
        not isinstance(model_provider, dict)
        or model_provider.get("status") != "not-configured"
    ):
        errors.append(f"{name} missing model_provider.status=not-configured")

    elif model_provider.get("degradation_mode") != "local_only_ok":
        errors.append(f"{name} missing model_provider.degradation_mode=local_only_ok")

    elif not isinstance(sidecar, dict) or sidecar.get("status") != "not-configured":
        errors.append(f"{name} missing sidecar.status=not-configured")

    elif sidecar.get("required") is not False:
        errors.append(f"{name} missing sidecar.required=false")

    elif sidecar.get("configured") is not False:
        errors.append(f"{name} missing sidecar.configured=false")

    elif not sidecar.get("detail"):
        errors.append(f"{name} missing sidecar.detail")

    elif "budget" in result:
        errors.append(f"{name} unexpectedly exposed budget without runtime source")


def assert_workspace_json_result(
    result: dict[str, object] | None,
    errors: list[str],
    name: str,
    *,
    expected_active: bool,
    expected_name: str | None,
    expected_db_path: str,
    expected_output_path: str,
    expected_changed: bool | None = None,
) -> None:
    if result is None:
        return

    normalized_db = str(result.get("db") or "").replace("/", chr(92))

    normalized_output = str(result.get("output") or "").replace("/", chr(92))

    expected_db = expected_db_path.replace("/", chr(92))

    expected_output = expected_output_path.replace("/", chr(92))

    if result.get("active") is not expected_active:
        errors.append(f"{name} missing active={expected_active}")

    elif result.get("name") != expected_name:
        errors.append(f"{name} missing name={expected_name}")

    elif normalized_db != expected_db:
        errors.append(f"{name} missing db={expected_db_path}")

    elif normalized_output != expected_output:
        errors.append(f"{name} missing output={expected_output_path}")

    elif result.get("path") != "target\mvp\workspace.json":
        errors.append(f"{name} missing workspace path")

    elif expected_changed is not None and result.get("changed") is not expected_changed:
        errors.append(f"{name} missing changed={expected_changed}")


