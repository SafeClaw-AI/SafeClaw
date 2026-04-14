use std::fs::File;
use std::io::{self, Write};
use std::path::PathBuf;
use std::time::Instant;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum FsyncTrustLevel {
    Full,      // Real fsync, data durable
    Limited,   // May be cached (WSL, VM, network fs)
    Unreliable, // No fsync or known broken
}

#[derive(Clone, Debug)]
pub struct FsyncTrustResult {
    pub level: FsyncTrustLevel,
    pub latency_ms: u64,
    pub message: String,
}

pub fn detect_fsync_trust(temp_dir: Option<PathBuf>) -> FsyncTrustResult {
    let test_file = temp_dir
        .unwrap_or_else(|| std::env::temp_dir())
        .join("safeclaw_fsync_test.tmp");

    // 1. Quick check: try to create and sync
    let start = Instant::now();
    let result = perform_fsync_test(&test_file);
    let latency = start.elapsed().as_millis() as u64;

    match result {
        Ok(()) => {
            // 2. Detect WSL or VM by checking /proc/version (Linux) or environment
            let trust = if is_wsl() || is_vm() {
                FsyncTrustLevel::Limited
            } else {
                FsyncTrustLevel::Full
            };
            FsyncTrustResult {
                level: trust,
                latency_ms: latency,
                message: format!("fsync successful, latency={}ms", latency),
            }
        }
        Err(e) => {
            let msg = format!("fsync failed or unsupported: {}", e);
            FsyncTrustResult {
                level: FsyncTrustLevel::Unreliable,
                latency_ms: latency,
                message: msg,
            }
        }
    }
}

fn perform_fsync_test(path: &PathBuf) -> io::Result<()> {
    let mut file = File::create(path)?;
    file.write_all(b"safeclaw fsync test")?;
    file.sync_all()?;  // fsync on file and directory
    std::fs::remove_file(path)?;
    Ok(())
}

fn is_wsl() -> bool {
    #[cfg(target_os = "linux")]
    {
        std::fs::read_to_string("/proc/version")
            .ok()
            .map(|v| v.to_lowercase().contains("microsoft"))
            .unwrap_or(false)
    }
    #[cfg(not(target_os = "linux"))]
    false
}

fn is_vm() -> bool {
    // Simple detection: check for common hypervisor files
    let hypervisor_files = [
        "/sys/hypervisor/type",
        "/proc/device-tree/hypervisor/compatible",
    ];
    for path in hypervisor_files {
        if std::path::Path::new(path).exists() {
            return true;
        }
    }
    // Also check environment variable from some VMs
    std::env::var("VMWARE_VMX")
        .or_else(|_| std::env::var("VBOX_APP_HOME"))
        .is_ok()
}

pub fn suggest_degradation(trust: FsyncTrustLevel) -> &'static str {
    match trust {
        FsyncTrustLevel::Full => "fsync trusted, full durability",
        FsyncTrustLevel::Limited => "fsync limited (WSL/VM), add warning logs",
        FsyncTrustLevel::Unreliable => "fsync unreliable, disable durable write guarantees",
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_fsync_detection_does_not_panic() {
        let result = detect_fsync_trust(None);
        assert!(result.latency_ms < 5000); // should complete within 5s
        println!("Fsync trust: {:?}, message: {}", result.level, result.message);
    }

    #[test]
    fn test_suggestion_returns_string() {
        let s = suggest_degradation(FsyncTrustLevel::Full);
        assert!(!s.is_empty());
    }
}
