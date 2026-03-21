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
    ExecutionDisposition, InMemoryTaskRuntime, PreflightDecision,
};
use safeclaw_sqlite::{
    open_database, FileSystemProbeAdapter, LocalSandboxExecutor, SandboxCommand,
    SqliteOpenOptions, SqliteRuntimeStore,
};

fn main() -> Result<(), String> {
    let workspace = into_demo(env::current_dir())?;
    let temp = DemoArtifacts::new(&workspace)?;

    let output_bytes = b"safeclaw full lifecycle demo\n";
    let effect = EffectRecord::new(
        "effect-demo-1",
        "task-demo-1",
        "trace-demo-1",
        "intent-demo-1",
        EffectActor::Worker,
        EffectAction::FileWrite,
        format!("scope:{}", temp.output_path.display()),
        EffectTier::Tier1,
        EffectReversibility::Rollbackable,
        ProbeMode::Auto,
    );
    let mut runtime = InMemoryTaskRuntime::new(effect);
    into_demo(runtime.begin_execution(PreflightDecision::Permit))?;

    let executor = LocalSandboxExecutor::new();
    let command = sandbox_write_command(&temp.output_path, output_bytes)?;
    let execution = into_demo(executor.run(&command))?;
    println!("[demo] sandbox stdout: {}", execution.stdout.trim());
    println!("[demo] sandbox stderr: {}", execution.stderr.trim());
    println!("[demo] sandbox result: {:?}", execution.runtime_directive());

    into_demo(runtime.continue_execution(ExecutionDisposition::Crash))?;
    println!(
        "[demo] runtime after crash => worker={:?}, effect={:?}",
        runtime.worker_state, runtime.effect.status
    );

    let connection = into_demo(open_database(temp.db_path(), SqliteOpenOptions::default()))?;
    let mut store = SqliteRuntimeStore::new(connection);
    into_demo(store.persist_runtime(&runtime, "demo-state-1", "full-lifecycle-demo"))?;
    drop(store);

    let reopened = into_demo(open_database(temp.db_path(), SqliteOpenOptions::default()))?;
    let store = SqliteRuntimeStore::new(reopened);
    let mut restored = into_demo(store.load_runtime("task-demo-1", "effect-demo-1"))?
        .expect("persisted runtime must reload");
    println!(
        "[demo] restored runtime => worker={:?}, effect={:?}",
        restored.worker_state, restored.effect.status
    );

    let mut probe = FileSystemProbeAdapter::new();
    probe.register_expected_blake3(
        restored.effect.effect_id.clone(),
        blake3::hash(output_bytes).to_hex().to_string(),
    );
    let summary = into_demo(restored.run_probe_with(&probe))?;
    println!(
        "[demo] probe summary => worker={:?}, effect={:?}, attempts={}",
        summary.worker_state, summary.effect_status, summary.attempt_count
    );

    let final_connection = into_demo(open_database(temp.db_path(), SqliteOpenOptions::default()))?;
    let mut final_store = SqliteRuntimeStore::new(final_connection);
    into_demo(final_store.persist_runtime(&restored, "demo-state-2", "full-lifecycle-demo"))?;

    println!("[demo] db: {}", temp.db_path().display());
    println!("[demo] output: {}", temp.output_path.display());
    Ok(())
}

fn sandbox_write_command(output_path: &Path, output_bytes: &[u8]) -> Result<SandboxCommand, String> {
    let text = String::from_utf8(output_bytes.to_vec()).map_err(|error| error.to_string())?;
    let command = if cfg!(windows) {
        let bytes_literal = output_bytes
            .iter()
            .map(u8::to_string)
            .collect::<Vec<_>>()
            .join(", ");
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
            "sh",
            ["-c", &format!("printf '%s' '{}' > '{}'", text, output_path.display())],
            5_000,
        )
    };
    Ok(command)
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
        let root = workspace
            .join("target")
            .join(format!("full-lifecycle-demo-{}-{unique}", process::id()));
        fs::create_dir_all(&root).map_err(|error| error.to_string())?;
        Ok(Self {
            output_path: root.join("demo-output.txt"),
            db_path: root.join("demo.db"),
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

