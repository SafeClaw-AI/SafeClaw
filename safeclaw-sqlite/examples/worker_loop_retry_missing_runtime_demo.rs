use std::{
    env, fs,
    path::{Path, PathBuf},
    process,
    time::{SystemTime, UNIX_EPOCH},
};

use safeclaw_core::{OrchestratorSnapshot, OrchestratorTask, PreflightDecision, ScheduleIntent};
use safeclaw_sqlite::{SqliteOpenOptions, SqliteSingleWorkerLoop, WorkerLoopError};

fn main() -> Result<(), String> {
    let workspace = into_demo(env::current_dir())?;
    let temp = DemoArtifacts::new(&workspace)?;

    let mut worker = into_demo(SqliteSingleWorkerLoop::open(
        temp.db_path(),
        SqliteOpenOptions::default(),
    ))?;
    into_demo(worker.enqueue_task(OrchestratorTask::new(
        "task-worker-loop-missing-retry-demo",
        ScheduleIntent::write(format!("scope:{}", temp.output_path.display())),
        0,
    )))?;
    print_snapshot("after-enqueue", worker.queue_snapshot());

    let error = worker
        .claim_and_retry_failed_once(
            "worker-a",
            0,
            "effect-worker-loop-missing-retry-demo",
            PreflightDecision::Permit,
            |_, _| unreachable!(),
        )
        .expect_err("missing persisted runtime must surface explicit error");

    match &error {
        WorkerLoopError::PersistedRuntimeMissing { task_id, effect_id } => {
            assert_eq!(task_id, "task-worker-loop-missing-retry-demo");
            assert_eq!(effect_id, "effect-worker-loop-missing-retry-demo");
            println!(
                "[demo] missing persisted runtime => task={} effect={}",
                task_id, effect_id
            );
        }
        other => return Err(format!("unexpected error: {other:?}")),
    }

    let snapshot = worker.queue_snapshot();
    print_snapshot("after-missing-runtime-error", snapshot.clone());
    assert!(snapshot.completed_task_ids.is_empty());
    assert_eq!(snapshot.active_leases.len(), 1);
    assert_eq!(
        snapshot.active_leases[0].task_id,
        "task-worker-loop-missing-retry-demo"
    );

    println!("[demo] db: {}", temp.db_path().display());
    println!("[demo] output: {}", temp.output_path.display());
    Ok(())
}

fn print_snapshot(label: &str, snapshot: OrchestratorSnapshot) {
    println!(
        "[demo] snapshot {label} => queued={}, active={}, completed={}",
        snapshot.queued_tasks.len(),
        snapshot.active_leases.len(),
        snapshot.completed_task_ids.len(),
    );
}

fn into_demo<T, E: std::fmt::Debug>(result: Result<T, E>) -> Result<T, String> {
    result.map_err(|error| format!("{error:?}"))
}

struct DemoArtifacts {
    root: PathBuf,
    output_path: PathBuf,
    db_path: PathBuf,
}

impl DemoArtifacts {
    fn new(workspace: &Path) -> Result<Self, String> {
        let unique = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .map_err(|error| error.to_string())?
            .as_nanos();
        let root = workspace.join("target").join(format!(
            "worker-loop-missing-retry-demo-{}-{unique}",
            process::id()
        ));
        fs::create_dir_all(&root).map_err(|error| error.to_string())?;
        Ok(Self {
            output_path: root.join("worker-loop-missing-retry-output.txt"),
            db_path: root.join("worker-loop-missing-retry.db"),
            root,
        })
    }

    fn db_path(&self) -> &Path {
        &self.db_path
    }
}

impl Drop for DemoArtifacts {
    fn drop(&mut self) {
        let _ = fs::remove_file(&self.output_path);
        let _ = fs::remove_file(&self.db_path);
        let _ = fs::remove_file(PathBuf::from(format!("{}-wal", self.db_path.display())));
        let _ = fs::remove_file(PathBuf::from(format!("{}-shm", self.db_path.display())));
        let _ = fs::remove_dir(&self.root);
    }
}
