use std::{
    env, fs,
    path::{Path, PathBuf},
    process,
    time::{SystemTime, UNIX_EPOCH},
};

use safeclaw_core::{
    effect_ledger::{
        EffectAction, EffectActor, EffectRecord, EffectReversibility, EffectTier,
        ProbeMode,
    },
    scheduler::{OrchestratorClaim, OrchestratorSnapshot, OrchestratorTask},
    InMemoryTaskRuntime, PreflightDecision, ScheduleIntent,
};
use safeclaw_sqlite::{SandboxCommand, SqliteOpenOptions, SqliteWorkerService};

const DEFAULT_CONTENT: &str = "safeclaw mvp entry\n";
const DEFAULT_OWNER_ID: &str = "safeclaw-mvp";

fn main() -> Result<(), String> {
    let raw_args = env::args().skip(1).collect::<Vec<_>>();
    if raw_args.iter().any(|arg| arg == "--help" || arg == "-h") {
        print_usage();
        return Ok(());
    }

    let args = CliArgs::parse(raw_args)?;
    match args.action {
        CliAction::Run => run_action(&args),
        CliAction::Report => report_action(&args),
    }
}

fn run_action(args: &CliArgs) -> Result<(), String> {
    ensure_parent_dir(&args.db_path)?;
    ensure_parent_dir(&args.output_path)?;
    if args.reset {
        reset_session_artifacts(&args.db_path, &args.output_path);
    }

    let effect_id = args.effect_id();
    let mut service = SqliteWorkerService::open(
        &args.db_path,
        SqliteOpenOptions::default(),
        args.owner_id.clone(),
    )
    .map_err(|error| format!("{error:?}"))?
    .with_lease_ttl_ms(60_000)
    .with_poll_interval_ms(5);

    service.filesystem_probe_mut().register_expected_blake3(
        effect_id.clone(),
        blake3::hash(args.content.as_bytes()).to_hex().to_string(),
    );
    service
        .enqueue_task(OrchestratorTask::new(
            &args.task_id,
            ScheduleIntent::write(format!("scope:{}", args.output_path.display())),
            0,
        ))
        .map_err(|error| format!("{error:?}"))?;

    println!("[mvp] accepted task => task={} effect={}", args.task_id, effect_id);
    print_snapshot("after-enqueue", service.queue_snapshot());

    let output_path = args.output_path.clone();
    let content = args.content.clone();
    let effect_id_for_service = effect_id.clone();
    let report = service
        .run_dispatch_until_idle(
            0,
            2,
            PreflightDecision::Permit,
            {
                let effect_id = effect_id_for_service.clone();
                move |_| Ok(effect_id.clone())
            },
            {
                let effect_id = effect_id_for_service.clone();
                let output_path = output_path.clone();
                let content = content.clone();
                move |claim| {
                    Ok((
                        build_runtime(claim, &effect_id),
                        sandbox_write_command(&output_path, content.as_bytes()),
                    ))
                }
            },
            {
                let output_path = output_path.clone();
                let content = content.clone();
                move |_, _| Ok(sandbox_write_command(&output_path, content.as_bytes()))
            },
        )
        .map_err(|error| format!("{error:?}"))?;

    println!(
        "[mvp] run report => polls={} idle={} executed={} probed={} parked={}",
        report.poll_count,
        report.consecutive_idle_polls,
        report.executed_count(),
        report.probed_count(),
        report.parked_count()
    );

    let governance = service
        .governance_report_for_report(&report)
        .map_err(|error| format!("{error:?}"))?;
    for line in governance.render_lines() {
        println!("[mvp] governance {line}");
    }

    print_snapshot("after-run", service.queue_snapshot());
    println!("[mvp] output exists => {}", args.output_path.exists());
    let rendered = fs::read_to_string(&args.output_path).map_err(|error| error.to_string())?;
    println!(
        "[mvp] output content => {}",
        rendered.replace('\r', "\\r").replace('\n', "\\n")
    );
    println!("[mvp] db: {}", args.db_path.display());
    println!("[mvp] output: {}", args.output_path.display());
    println!("[mvp] owner: {}", args.owner_id);

    println!(
        "[mvp] next report => cargo run -p safeclaw-sqlite --example safeclaw_mvp_entry -- report --db \"{}\" --output \"{}\" --task-id {} --effect-id {}",
        args.db_path.display(),
        args.output_path.display(),
        args.task_id,
        effect_id
    );
    Ok(())
}

fn report_action(args: &CliArgs) -> Result<(), String> {
    let effect_id = args.effect_id();
    let service = SqliteWorkerService::open(
        &args.db_path,
        SqliteOpenOptions::default(),
        args.owner_id.clone(),
    )
    .map_err(|error| format!("{error:?}"))?;

    println!("[mvp] report target => task={} effect={}", args.task_id, effect_id);

    let governance = service
        .governance_view(&args.task_id, &effect_id)
        .map_err(|error| format!("{error:?}"))?
        .ok_or_else(|| format!("missing governance view for task={} effect={effect_id}", args.task_id))?;

    println!(
        "[mvp] governance view => disposition={:?} worker={:?} effect={:?} attempts={}",
        governance.disposition,
        governance.worker_state,
        governance.effect_status,
        governance.attempt_count
    );

    let snapshot = service
        .diagnostic_snapshot(&args.task_id, &effect_id)
        .map_err(|error| format!("{error:?}"))?
        .ok_or_else(|| format!("missing diagnostic snapshot for task={} effect={effect_id}", args.task_id))?;
    println!("[mvp] diagnostic => {}", snapshot.render_line());
    print_snapshot("report", service.queue_snapshot());

    let output_exists = args.output_path.exists();
    println!("[mvp] output exists => {output_exists}");
    if output_exists {
        let rendered = fs::read_to_string(&args.output_path).map_err(|error| error.to_string())?;
        println!(
            "[mvp] output content => {}",
            rendered.replace('\r', "\\r").replace('\n', "\\n")
        );
    }

    println!("[mvp] db: {}", args.db_path.display());
    println!("[mvp] output: {}", args.output_path.display());
    println!("[mvp] owner: {}", args.owner_id);
    Ok(())
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum CliAction {
    Run,
    Report,
}

#[derive(Clone, Debug)]
struct CliArgs {
    action: CliAction,
    db_path: PathBuf,
    output_path: PathBuf,
    content: String,
    task_id: String,
    owner_id: String,
    effect_id: Option<String>,
    reset: bool,
}

impl CliArgs {
    fn parse(raw_args: Vec<String>) -> Result<Self, String> {
        let workspace = env::current_dir().map_err(|error| error.to_string())?;
        let unique = unique_suffix()?;
        let default_root = workspace.join("target").join(format!("safeclaw-mvp-entry-{unique}"));
        let default_output = default_root.join("output.txt");
        let default_db = default_root.join("session.db");

        let mut action = CliAction::Run;
        let mut action_set = false;
        let mut db_path = None;
        let mut output_path = None;
        let mut content = String::from(DEFAULT_CONTENT);
        let mut task_id = None;
        let mut owner_id = String::from(DEFAULT_OWNER_ID);
        let mut effect_id = None;
        let mut reset = false;

        let mut args = raw_args.into_iter();
        while let Some(arg) = args.next() {
            match arg.as_str() {
                "run" if !action_set => {
                    action = CliAction::Run;
                    action_set = true;
                }
                "report" if !action_set => {
                    action = CliAction::Report;
                    action_set = true;
                }
                "--db" => db_path = Some(PathBuf::from(next_value(&mut args, "--db")?)),
                "--output" => {
                    output_path = Some(PathBuf::from(next_value(&mut args, "--output")?))
                }
                "--content" => content = next_value(&mut args, "--content")?,
                "--task-id" => task_id = Some(next_value(&mut args, "--task-id")?),
                "--owner-id" => owner_id = next_value(&mut args, "--owner-id")?,
                "--effect-id" => effect_id = Some(next_value(&mut args, "--effect-id")?),
                "--reset" => reset = true,
                _ => return Err(format!("unknown argument: {arg}\n\n{}", usage_text())),
            }
        }

        let (db_path, output_path, task_id) = match action {
            CliAction::Run => {
                let output_path = output_path.unwrap_or(default_output);
                let db_path = db_path.unwrap_or(default_db);
                let task_id = task_id.unwrap_or(format!("task-safeclaw-mvp-{unique}"));
                (db_path, output_path, task_id)
            }
            CliAction::Report => {
                let db_path = db_path.ok_or_else(|| {
                    format!("report requires --db\n\n{}", usage_text())
                })?;
                let task_id = task_id.ok_or_else(|| {
                    format!("report requires --task-id\n\n{}", usage_text())
                })?;
                let output_path = output_path.unwrap_or_else(|| {
                    db_path
                        .parent()
                        .unwrap_or_else(|| Path::new("."))
                        .join("output.txt")
                });
                (db_path, output_path, task_id)
            }
        };

        Ok(Self {
            action,
            db_path,
            output_path,
            content,
            task_id,
            owner_id,
            effect_id,
            reset,
        })
    }

    fn effect_id(&self) -> String {
        self.effect_id
            .clone()
            .unwrap_or_else(|| format!("effect-{}", self.task_id))
    }
}

fn next_value(
    args: &mut impl Iterator<Item = String>,
    flag: &str,
) -> Result<String, String> {
    args.next()
        .ok_or_else(|| format!("missing value for {flag}\n\n{}", usage_text()))
}

fn usage_text() -> &'static str {
    "usage: cargo run -p safeclaw-sqlite --example safeclaw_mvp_entry -- [run [--reset] [--db <path>] [--output <path>] [--content <text>] [--task-id <id>] [--owner-id <id>] [--effect-id <id>] | report --db <path> --task-id <id> [--output <path>] [--owner-id <id>] [--effect-id <id>]]"
}

fn print_usage() {
    println!("{}", usage_text());
}

fn unique_suffix() -> Result<String, String> {
    let nanos = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map_err(|error| error.to_string())?
        .as_nanos();
    Ok(format!("{}-{nanos}", process::id()))
}

fn ensure_parent_dir(path: &Path) -> Result<(), String> {
    if let Some(parent) = path.parent().filter(|parent| !parent.as_os_str().is_empty()) {
        fs::create_dir_all(parent).map_err(|error| error.to_string())?;
    }
    Ok(())
}

fn reset_session_artifacts(db_path: &Path, output_path: &Path) {
    let _ = fs::remove_file(output_path);
    for suffix in ["", "-wal", "-shm"] {
        let candidate = if suffix.is_empty() {
            db_path.to_path_buf()
        } else {
            PathBuf::from(format!("{}{}", db_path.display(), suffix))
        };
        let _ = fs::remove_file(candidate);
    }
}

fn build_runtime(claim: &OrchestratorClaim, effect_id: &str) -> InMemoryTaskRuntime {
    let effect = EffectRecord::new(
        effect_id,
        claim.task.task_id.clone(),
        format!("trace-{}", claim.task.task_id),
        format!("intent-{}", claim.task.task_id),
        EffectActor::Worker,
        EffectAction::FileWrite,
        claim.task.intent.target_scope.clone(),
        EffectTier::Tier1,
        EffectReversibility::Rollbackable,
        ProbeMode::Auto,
    );
    InMemoryTaskRuntime::new(effect)
}

fn print_snapshot(label: &str, snapshot: OrchestratorSnapshot) {
    println!(
        "[mvp] snapshot {label} => queued={}, active={}, completed={}",
        snapshot.queued_tasks.len(),
        snapshot.active_leases.len(),
        snapshot.completed_task_ids.len(),
    );
}

fn sandbox_write_command(output_path: &Path, output_bytes: &[u8]) -> SandboxCommand {
    let bytes_literal = output_bytes
        .iter()
        .map(u8::to_string)
        .collect::<Vec<_>>()
        .join(", ");
    if cfg!(windows) {
        SandboxCommand::new(
            "powershell",
            [
                "-Command",
                &format!(
                    "$bytes = [byte[]]({bytes_literal}); [System.IO.File]::WriteAllBytes('{}', $bytes)",
                    output_path.display()
                ),
            ],
            5_000,
        )
    } else {
        SandboxCommand::new(
            "python3",
            [
                "-c",
                &format!(
                    "from pathlib import Path; Path(r'''{}''').write_bytes(bytes([{}]))",
                    output_path.display(),
                    bytes_literal
                ),
            ],
            5_000,
        )
    }
}
