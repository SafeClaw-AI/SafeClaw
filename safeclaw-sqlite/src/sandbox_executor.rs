use std::{
    path::PathBuf,
    process::{Command, Stdio},
    thread,
    time::{Duration, Instant},
};

use safeclaw_core::{effect_ledger::AttemptResultStatus, ExecutionDisposition, ExecutionInterruption};

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct SandboxCommand {
    pub program: String,
    pub args: Vec<String>,
    pub current_dir: Option<PathBuf>,
    pub timeout_ms: u64,
}

impl SandboxCommand {
    pub fn new(program: impl Into<String>, args: impl IntoIterator<Item = impl Into<String>>, timeout_ms: u64) -> Self {
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
}

#[derive(Debug)]
pub enum SandboxExecutorError {
    Spawn(std::io::Error),
    Capture(std::io::Error),
    Kill(std::io::Error),
}

pub struct LocalSandboxExecutor;

impl LocalSandboxExecutor {
    pub fn new() -> Self {
        Self
    }

    pub fn run(&self, command: &SandboxCommand) -> Result<SandboxExecutionReport, SandboxExecutorError> {
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

        let output = child.wait_with_output().map_err(SandboxExecutorError::Capture)?;
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
        LocalSandboxExecutor, RuntimeExecutionDirective, SandboxCommand,
    };
    use safeclaw_core::{effect_ledger::AttemptResultStatus, ExecutionDisposition, ExecutionInterruption};

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
        assert_eq!(report.execution_disposition(), Some(ExecutionDisposition::Commit));
        assert_eq!(report.runtime_directive(), RuntimeExecutionDirective::Commit);
    }

    #[test]
    fn executor_captures_stderr_and_maps_non_zero_exit_to_exec_error() {
        let executor = LocalSandboxExecutor::new();
        let command = if cfg!(windows) {
            SandboxCommand::new(
                "cmd",
                ["/C", "echo boom 1>&2 && exit /b 7"],
                2_000,
            )
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
        assert_eq!(report.execution_disposition(), Some(ExecutionDisposition::Crash));
        assert_eq!(report.runtime_directive(), RuntimeExecutionDirective::Crash);
    }
}

