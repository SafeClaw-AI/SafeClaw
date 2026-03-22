use std::{
    env, fs,
    path::{Path, PathBuf},
    process,
    time::{SystemTime, UNIX_EPOCH},
};

use safeclaw_core::{OrchestratorSnapshot, PreflightDecision};
use safeclaw_sqlite::{SqliteOpenOptions, SqliteSingleWorkerLoop};

fn main() -> Result<(), String> {
    let workspace = into_demo(env::current_dir())?;
    let temp = DemoArtifacts::new(&workspace)?;

    let mut worker = into_demo(SqliteSingleWorkerLoop::open(
        temp.db_path(),
        SqliteOpenOptions::default(),
    ))?;
    print_snapshot("initial", worker.queue_snapshot());

    let claimed = into_demo(worker.claim_and_drive_once(
        "worker-a",
        0,
        PreflightDecision::Permit,
        |_| unreachable!(),
    ))?;
    assert!(claimed.is_none());
    println!("[demo] claim_and_drive_once on empty queue => none={}", claimed.is_none());
    print_snapshot("after-empty-claim", worker.queue_snapshot());

    let drained = into_demo(worker.claim_and_drive_until_empty(
        "worker-a",
        1,
        PreflightDecision::Permit,
        |_| unreachable!(),
    ))?;
    assert!(drained.is_empty());
    println!("[demo] claim_and_drive_until_empty on empty queue => count={}", drained.len());
    print_snapshot("after-empty-drain", worker.queue_snapshot());

    let dispatched = into_demo(worker.claim_and_dispatch_until_empty(
        "worker-a",
        2,
        PreflightDecision::Permit,
        |_| unreachable!(),
        |_| unreachable!(),
        |_, _| unreachable!(),
    ))?;
    assert!(dispatched.is_empty());
    println!(
        "[demo] claim_and_dispatch_until_empty on empty queue => count={}",
        dispatched.len()
    );
    print_snapshot("after-empty-dispatch-drain", worker.queue_snapshot());

    println!("[demo] db: {}", temp.db_path().display());
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
    db_path: PathBuf,
}

impl DemoArtifacts {
    fn new(workspace: &Path) -> Result<Self, String> {
        let unique = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .map_err(|error| error.to_string())?
            .as_nanos();
        let root = workspace.join("target").join(format!(
            "worker-loop-empty-queue-demo-{}-{unique}",
            process::id()
        ));
        fs::create_dir_all(&root).map_err(|error| error.to_string())?;
        Ok(Self {
            db_path: root.join("worker-loop-empty-queue.db"),
            root,
        })
    }

    fn db_path(&self) -> &Path {
        &self.db_path
    }
}

impl Drop for DemoArtifacts {
    fn drop(&mut self) {
        let _ = fs::remove_dir_all(&self.root);
    }
}
