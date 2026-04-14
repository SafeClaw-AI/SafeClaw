use std::{
    path::PathBuf,
    process::{Command, Stdio},
    thread,
    time::{Duration, Instant},
};

use safeclaw_core::{
    effect_ledger::AttemptResultStatus, ExecutionDisposition, ExecutionInterruption,
    InMemoryTaskRuntime, RunSummary, RuntimeError,
};

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct SandboxCommand {
    pub program: String,
    pub args: Vec<String>,
    pub current_dir: Option<PathBuf>,
    pub timeout_ms: u64,
}

impl SandboxCommand {
    pub fn new(
        program: impl Into<String>,
        args: impl IntoIterator<Item = impl Into<String>>,
        timeout_ms: u64,
    ) -> Self {
        Self {
            program: program.into(),
            args: args.into_iter().map(Into::into).collect(),
            current_dir: None,
            timeout_ms,
        }
    }

    pub fn with_current_dir(mut self, current_dir: impl Into<PathBuf>) -> Self {
        self.current_dir = Some(current_dir.into());
        self
    }
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct SandboxExecutionReport {
    pub exit_code: Option<i32>,
    pub stdout: String,
    pub stderr: String,
    pub timed_out: bool,
    pub duration_ms: u64,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum RuntimeExecutionDirective {
    Commit,
    Crash,
    Interrupt(ExecutionInterruption),
}

impl SandboxExecutionReport {
    pub fn attempt_result_status(&self) -> AttemptResultStatus {
        if self.timed_out {
            AttemptResultStatus::Timeout
        } else if self.exit_code == Some(0) {
            AttemptResultStatus::Success
        } else if self.exit_code.is_some() {
            AttemptResultStatus::Failure
        } else {
            AttemptResultStatus::Crash
        }
    }

    pub fn runtime_directive(&self) -> RuntimeExecutionDirective {
        if self.exit_code == Some(0) && !self.timed_out {
            RuntimeExecutionDirective::Commit
        } else if self.timed_out || self.exit_code.is_none() {
            RuntimeExecutionDirective::Crash
        } else {
            RuntimeExecutionDirective::Interrupt(ExecutionInterruption::ExecError)
        }
    }

    pub fn execution_disposition(&self) -> Option<ExecutionDisposition> {
        match self.runtime_directive() {
            RuntimeExecutionDirective::Commit => Some(ExecutionDisposition::Commit),
            RuntimeExecutionDirective::Crash => Some(ExecutionDisposition::Crash),
            RuntimeExecutionDirective::Interrupt(_) => None,
        }
    }

    pub fn apply_to_runtime(
        &self,
        runtime: &mut InMemoryTaskRuntime,
    ) -> Result<RunSummary, RuntimeError> {
        match self.runtime_directive() {
            RuntimeExecutionDirective::Commit => {
                runtime.continue_execution(ExecutionDisposition::Commit)
            }
            RuntimeExecutionDirective::Crash => {
                runtime.continue_execution(ExecutionDisposition::Crash)
            }
            RuntimeExecutionDirective::Interrupt(interruption) => {
                runtime.interrupt_execution(interruption)
            }
        }
    }
}

#[derive(Debug)]
pub enum SandboxExecutorError {
    Spawn(std::io::Error),
    Capture(std::io::Error),
    Kill(std::io::Error),
}

#[derive(Debug)]
pub enum SandboxRuntimeError {
    Executor(SandboxExecutorError),
    Runtime(RuntimeError),
}

pub struct LocalSandboxExecutor;

impl LocalSandboxExecutor {
    pub fn new() -> Self {
        Self
    }

    pub fn run_and_apply(
        &self,
        runtime: &mut InMemoryTaskRuntime,
        command: &SandboxCommand,
    ) -> Result<(SandboxExecutionReport, RunSummary), SandboxRuntimeError> {
        let report = self.run(command).map_err(SandboxRuntimeError::Executor)?;
        let summary = report
            .apply_to_runtime(runtime)
            .map_err(SandboxRuntimeError::Runtime)?;
        Ok((report, summary))
    }

    pub fn run(
        &self,
        command: &SandboxCommand,
    ) -> Result<SandboxExecutionReport, SandboxExecutorError> {
        let mut process = Command::new(&command.program);
        process
            .args(&command.args)
            .stdout(Stdio::piped())
            .stderr(Stdio::piped());
        if let Some(current_dir) = &command.current_dir {
            process.current_dir(current_dir);
        }

        let mut child = process.spawn().map_err(SandboxExecutorError::Spawn)?;
        let started_at = Instant::now();
        let timeout = Duration::from_millis(command.timeout_ms);
        let poll_interval = Duration::from_millis(10);
        let mut timed_out = false;

        loop {
            match child.try_wait() {
                Ok(Some(_)) => break,
                Ok(None) if started_at.elapsed() >= timeout => {
                    timed_out = true;
                    child.kill().map_err(SandboxExecutorError::Kill)?;
                    break;
                }
                Ok(None) => thread::sleep(poll_interval),
                Err(error) => return Err(SandboxExecutorError::Capture(error)),
            }
        }

        let output = child
            .wait_with_output()
            .map_err(SandboxExecutorError::Capture)?;
        let duration_ms = started_at.elapsed().as_millis() as u64;

        Ok(SandboxExecutionReport {
            exit_code: output.status.code(),
            stdout: String::from_utf8_lossy(&output.stdout).to_string(),
            stderr: String::from_utf8_lossy(&output.stderr).to_string(),
            timed_out,
            duration_ms,
        })
    }
}

#[cfg(test)]
mod tests {
    use super::{
        LocalSandboxExecutor, RuntimeExecutionDirective, SandboxCommand, SandboxExecutionReport,
        SandboxExecutorError, SandboxRuntimeError,
    };
    use safeclaw_core::{
        effect_ledger::{
            AttemptResultStatus, EffectAction, EffectActor, EffectRecord, EffectReversibility,
            EffectStatus, EffectTier, ProbeMode,
        },
        worker_lifecycle::WorkerState,
        ExecutionDisposition, ExecutionInterruption, InMemoryTaskRuntime, PreflightDecision,
    };

    #[test]
    fn executor_captures_stdout_and_commits_on_zero_exit() {
        let executor = LocalSandboxExecutor::new();
        let command = if cfg!(windows) {
            SandboxCommand::new("cmd", ["/C", "echo hello-safeclaw"], 2_000)
        } else {
            SandboxCommand::new("sh", ["-c", "printf hello-safeclaw"], 2_000)
        };

        let report = executor.run(&command).unwrap();
        assert_eq!(report.exit_code, Some(0));
        assert!(report.stdout.contains("hello-safeclaw"));
        assert_eq!(report.attempt_result_status(), AttemptResultStatus::Success);
        assert_eq!(
            report.execution_disposition(),
            Some(ExecutionDisposition::Commit)
        );
        assert_eq!(
            report.runtime_directive(),
            RuntimeExecutionDirective::Commit
        );
    }

    #[test]
    fn executor_captures_stderr_and_maps_non_zero_exit_to_exec_error() {
        let executor = LocalSandboxExecutor::new();
        let command = if cfg!(windows) {
            SandboxCommand::new("cmd", ["/C", "echo boom 1>&2 && exit /b 7"], 2_000)
        } else {
            SandboxCommand::new("sh", ["-c", "echo boom >&2; exit 7"], 2_000)
        };

        let report = executor.run(&command).unwrap();
        assert_eq!(report.exit_code, Some(7));
        assert!(report.stderr.contains("boom"));
        assert_eq!(report.attempt_result_status(), AttemptResultStatus::Failure);
        assert_eq!(
            report.runtime_directive(),
            RuntimeExecutionDirective::Interrupt(ExecutionInterruption::ExecError)
        );
    }

    #[test]
    fn executor_kills_timeout_and_maps_to_crash_path() {
        let executor = LocalSandboxExecutor::new();
        let command = if cfg!(windows) {
            SandboxCommand::new(
                "powershell",
                ["-Command", "Start-Sleep -Milliseconds 250"],
                50,
            )
        } else {
            SandboxCommand::new("sh", ["-c", "sleep 1"], 50)
        };

        let report = executor.run(&command).unwrap();
        assert!(report.timed_out);
        assert_eq!(report.attempt_result_status(), AttemptResultStatus::Timeout);
        assert_eq!(
            report.execution_disposition(),
            Some(ExecutionDisposition::Crash)
        );
        assert_eq!(report.runtime_directive(), RuntimeExecutionDirective::Crash);
    }

    #[test]
    fn report_apply_to_runtime_commits_executing_runtime() {
        let mut runtime = demo_runtime();
        runtime.begin_execution(PreflightDecision::Permit).unwrap();

        let report = SandboxExecutionReport {
            exit_code: Some(0),
            stdout: String::new(),
            stderr: String::new(),
            timed_out: false,
            duration_ms: 5,
        };

        let summary = report.apply_to_runtime(&mut runtime).unwrap();
        assert_eq!(summary.worker_state, WorkerState::Succeeded);
        assert_eq!(summary.effect_status, EffectStatus::Executed);
        assert_eq!(runtime.attempts.len(), 1);
    }

    #[test]
    fn report_apply_to_runtime_crashes_into_uncertain_runtime() {
        let mut runtime = demo_runtime();
        runtime.begin_execution(PreflightDecision::Permit).unwrap();

        let report = SandboxExecutionReport {
            exit_code: None,
            stdout: String::new(),
            stderr: String::new(),
            timed_out: true,
            duration_ms: 50,
        };

        let summary = report.apply_to_runtime(&mut runtime).unwrap();
        assert_eq!(summary.worker_state, WorkerState::Uncertain);
        assert_eq!(summary.effect_status, EffectStatus::Uncertain);
        assert_eq!(runtime.attempts.len(), 1);
    }

    #[test]
    fn report_apply_to_runtime_interrupts_with_exec_error() {
        let mut runtime = demo_runtime();
        runtime.begin_execution(PreflightDecision::Permit).unwrap();

        let report = SandboxExecutionReport {
            exit_code: Some(7),
            stdout: String::new(),
            stderr: String::from("boom"),
            timed_out: false,
            duration_ms: 8,
        };

        let summary = report.apply_to_runtime(&mut runtime).unwrap();
        assert_eq!(summary.worker_state, WorkerState::Failed);
        assert_eq!(summary.effect_status, EffectStatus::Prepared);
        assert!(runtime.attempts.is_empty());
    }

    #[test]
    fn executor_run_and_apply_commits_runtime_on_zero_exit() {
        let executor = LocalSandboxExecutor::new();
        let command = if cfg!(windows) {
            SandboxCommand::new("cmd", ["/C", "echo happy-safeclaw"], 2_000)
        } else {
            SandboxCommand::new("sh", ["-c", "printf happy-safeclaw"], 2_000)
        };
        let mut runtime = demo_runtime();
        runtime.begin_execution(PreflightDecision::Permit).unwrap();

        let (report, summary) = executor.run_and_apply(&mut runtime, &command).unwrap();
        assert_eq!(
            report.runtime_directive(),
            RuntimeExecutionDirective::Commit
        );
        assert!(report.stdout.contains("happy-safeclaw"));
        assert_eq!(summary.worker_state, WorkerState::Succeeded);
        assert_eq!(summary.effect_status, EffectStatus::Executed);
    }

    #[test]
    fn executor_run_and_apply_surfaces_runtime_state_errors() {
        let executor = LocalSandboxExecutor::new();
        let command = if cfg!(windows) {
            SandboxCommand::new("cmd", ["/C", "echo stale-safeclaw"], 2_000)
        } else {
            SandboxCommand::new("sh", ["-c", "printf stale-safeclaw"], 2_000)
        };
        let mut runtime = demo_runtime();

        let error = executor.run_and_apply(&mut runtime, &command).unwrap_err();
        assert!(matches!(error, SandboxRuntimeError::Runtime(_)));
    }

    #[test]
    fn executor_run_and_apply_surfaces_spawn_failures() {
        let executor = LocalSandboxExecutor::new();
        let command = SandboxCommand::new(
            "safeclaw-command-does-not-exist",
            std::iter::empty::<&str>(),
            2_000,
        );
        let mut runtime = demo_runtime();
        runtime.begin_execution(PreflightDecision::Permit).unwrap();

        let error = executor.run_and_apply(&mut runtime, &command).unwrap_err();
        assert!(matches!(
            error,
            SandboxRuntimeError::Executor(SandboxExecutorError::Spawn(_))
        ));
        assert_eq!(runtime.worker_state, WorkerState::Executing);
        assert_eq!(runtime.effect.status, EffectStatus::Prepared);
        assert!(runtime.attempts.is_empty());
    }

    fn demo_runtime() -> InMemoryTaskRuntime {
        InMemoryTaskRuntime::new(EffectRecord::new(
            "effect-sandbox",
            "task-sandbox",
            "trace-sandbox",
            "intent-sandbox",
            EffectActor::Worker,
            EffectAction::FileWrite,
            "scope:/tmp/sandbox.txt",
            EffectTier::Tier1,
            EffectReversibility::Rollbackable,
            ProbeMode::Auto,
        ))
    }
}
