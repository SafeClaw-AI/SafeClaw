use std::{
    env, fs,
    path::{Path, PathBuf},
    process,
    time::{SystemTime, UNIX_EPOCH},
};

use safeclaw_core::{OrchestratorSnapshot, OrchestratorTask, ScheduleIntent, TaskOrchestrator};
use safeclaw_sqlite::{open_database, SqliteOpenOptions, SqliteTaskOrchestrator};

fn main() -> Result<(), String> {
    let workspace = into_demo(env::current_dir())?;
    let temp = DemoArtifacts::new(&workspace)?;
    let shared_scope = format!("scope:{}", temp.root.join("shared-write-under-reads.txt").display());

    let mut orchestrator = into_demo(open_database(
        temp.db_path(),
        SqliteOpenOptions::default(),
    ))
    .map(SqliteTaskOrchestrator::new)?
    .with_lease_ttl_ms(60_000);

    into_demo(orchestrator.enqueue(OrchestratorTask::new(
        "task-shared-read-1",
        ScheduleIntent::read(shared_scope.clone()),
        0,
    )))?;
    into_demo(orchestrator.enqueue(OrchestratorTask::new(
        "task-shared-read-2",
        ScheduleIntent::read(shared_scope.clone()),
        1,
    )))?;
    into_demo(orchestrator.enqueue(OrchestratorTask::new(
        "task-shared-write-after-reads",
        ScheduleIntent::write(shared_scope.clone()),
        2,
    )))?;
    print_snapshot("after-enqueue", orchestrator.queue_snapshot());

    let first = into_demo(orchestrator.claim_next("orch-a", 0))?
        .expect("first shared read must be claimable");
    println!(
        "[demo] first read claim => task={} lease={} fence={} owner={}",
        first.task.task_id,
        first.lease.lease_id,
        first.lease.fencing_token,
        first.lease.owner_id
    );
    assert!(!first.task.intent.requires_write);

    let second = into_demo(orchestrator.claim_next("orch-b", 1))?
        .expect("second shared read must remain claimable");
    println!(
        "[demo] second read claim => task={} lease={} fence={} owner={}",
        second.task.task_id,
        second.lease.lease_id,
        second.lease.fencing_token,
        second.lease.owner_id
    );
    assert!(!second.task.intent.requires_write);

    let third = into_demo(orchestrator.claim_next("orch-c", 2))?
        .expect("same-scope write must remain claimable under reads");
    println!(
        "[demo] write-under-reads claim => task={} lease={} fence={} owner={}",
        third.task.task_id,
        third.lease.lease_id,
        third.lease.fencing_token,
        third.lease.owner_id
    );
    assert!(third.task.intent.requires_write);

    let snapshot = orchestrator.queue_snapshot();
    print_snapshot("after-three-claims", snapshot.clone());
    assert!(snapshot.queued_tasks.is_empty());
    assert_eq!(snapshot.active_leases.len(), 3);
    assert_eq!(
        snapshot
            .active_leases
            .iter()
            .map(|lease| lease.task_id.as_str())
            .collect::<Vec<_>>(),
        vec![
            "task-shared-read-1",
            "task-shared-read-2",
            "task-shared-write-after-reads",
        ]
    );

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
        let root = workspace
            .join("target")
            .join(format!("orchestrator-scope-write-under-reads-demo-{}-{unique}", process::id()));
        fs::create_dir_all(&root).map_err(|error| error.to_string())?;
        Ok(Self {
            db_path: root.join("orchestrator-scope-write-under-reads.db"),
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
