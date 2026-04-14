use std::{
    collections::HashMap,
    fs,
    io::{Read, Write},
    net::{TcpStream, ToSocketAddrs},
    path::{Path, PathBuf},
    time::{Duration, SystemTime, UNIX_EPOCH},
};

use safeclaw_core::{
    effect_ledger::{EffectAction, EffectRecord, ProbeMode},
    ProbeAdapter, ProbeAdapterError, ProbeReceipt, ProbeReceiptStatus,
};

#[derive(Clone, Debug, Default)]
pub struct FileSystemProbeAdapter {
    expected_blake3_by_effect: HashMap<String, String>,
}

impl FileSystemProbeAdapter {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn register_expected_blake3(
        &mut self,
        effect_id: impl Into<String>,
        expected_blake3: impl Into<String>,
    ) {
        self.expected_blake3_by_effect
            .insert(effect_id.into(), expected_blake3.into());
    }
}

impl ProbeAdapter for FileSystemProbeAdapter {
    fn evaluate(&self, effect: &EffectRecord) -> Result<ProbeReceipt, ProbeAdapterError> {
        if effect.probe_mode == ProbeMode::None {
            return Err(ProbeAdapterError::ProbeDisabled {
                action: effect.action,
            });
        }

        let target_path =
            decode_target_path(&effect.target).ok_or(ProbeAdapterError::AdapterUnavailable {
                action: effect.action,
            })?;

        match effect.action {
            EffectAction::FileWrite => self.evaluate_file_write(effect, &target_path),
            EffectAction::FileDelete => self.evaluate_file_delete(&target_path),
            _ => Err(ProbeAdapterError::AdapterUnavailable {
                action: effect.action,
            }),
        }
    }
}

impl FileSystemProbeAdapter {
    fn evaluate_file_write(
        &self,
        effect: &EffectRecord,
        target_path: &Path,
    ) -> Result<ProbeReceipt, ProbeAdapterError> {
        let expected_blake3 = self
            .expected_blake3_by_effect
            .get(&effect.effect_id)
            .ok_or(ProbeAdapterError::AdapterUnavailable {
                action: effect.action,
            })?;

        match fs::read(target_path) {
            Ok(bytes) => {
                let actual_blake3 = blake3::hash(&bytes).to_hex().to_string();
                let status = if actual_blake3 == *expected_blake3 {
                    ProbeReceiptStatus::VerifiedExecuted
                } else {
                    ProbeReceiptStatus::VerifiedUnexecuted
                };
                Ok(ProbeReceipt::new(
                    status,
                    format!("file_hash={actual_blake3}"),
                    checked_at_now(),
                ))
            }
            Err(error) if error.kind() == std::io::ErrorKind::NotFound => Ok(ProbeReceipt::new(
                ProbeReceiptStatus::VerifiedUnexecuted,
                "file_not_found",
                checked_at_now(),
            )),
            Err(error) if error.kind() == std::io::ErrorKind::PermissionDenied => {
                Ok(ProbeReceipt::new(
                    ProbeReceiptStatus::Indeterminate,
                    "permission_denied",
                    checked_at_now(),
                ))
            }
            Err(_) => Err(ProbeAdapterError::AdapterUnavailable {
                action: effect.action,
            }),
        }
    }

    fn evaluate_file_delete(&self, target_path: &Path) -> Result<ProbeReceipt, ProbeAdapterError> {
        match fs::read(target_path) {
            Ok(bytes) => Ok(ProbeReceipt::new(
                ProbeReceiptStatus::VerifiedUnexecuted,
                format!("file_exists_hash={}", blake3::hash(&bytes).to_hex()),
                checked_at_now(),
            )),
            Err(error) if error.kind() == std::io::ErrorKind::NotFound => Ok(ProbeReceipt::new(
                ProbeReceiptStatus::VerifiedExecuted,
                "file_not_found",
                checked_at_now(),
            )),
            Err(error) if error.kind() == std::io::ErrorKind::PermissionDenied => {
                Ok(ProbeReceipt::new(
                    ProbeReceiptStatus::Indeterminate,
                    "permission_denied",
                    checked_at_now(),
                ))
            }
            Err(_) => Err(ProbeAdapterError::AdapterUnavailable {
                action: EffectAction::FileDelete,
            }),
        }
    }
}

#[derive(Clone, Debug)]
pub struct NetworkProbeAdapter {
    expected_pattern_by_effect: HashMap<String, String>,
    timeout_ms: u64,
}

impl Default for NetworkProbeAdapter {
    fn default() -> Self {
        Self {
            expected_pattern_by_effect: HashMap::new(),
            timeout_ms: 10_000,
        }
    }
}

impl NetworkProbeAdapter {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn with_timeout_ms(mut self, timeout_ms: u64) -> Self {
        self.timeout_ms = timeout_ms;
        self
    }

    pub fn register_expected_response(
        &mut self,
        effect_id: impl Into<String>,
        expected_pattern: impl Into<String>,
    ) {
        self.expected_pattern_by_effect
            .insert(effect_id.into(), expected_pattern.into());
    }

    fn evaluate_network_request(
        &self,
        effect: &EffectRecord,
        target_url: &str,
    ) -> Result<ProbeReceipt, ProbeAdapterError> {
        let expected_pattern = self
            .expected_pattern_by_effect
            .get(&effect.effect_id)
            .ok_or(ProbeAdapterError::AdapterUnavailable {
                action: effect.action,
            })?;
        let (host, port, path) =
            parse_http_url(target_url).ok_or(ProbeAdapterError::AdapterUnavailable {
                action: effect.action,
            })?;

        match issue_http_get(&host, port, &path, self.timeout_ms) {
            Ok((status_code, body)) => {
                let status = if status_code == 200 && body.contains(expected_pattern) {
                    ProbeReceiptStatus::VerifiedExecuted
                } else if status_code == 404 || status_code == 410 || status_code == 200 {
                    ProbeReceiptStatus::VerifiedUnexecuted
                } else {
                    ProbeReceiptStatus::Indeterminate
                };
                Ok(ProbeReceipt::new(
                    status,
                    format!("http_status={status_code}"),
                    checked_at_now(),
                ))
            }
            Err(HttpProbeError::ConnectionRefused) => Ok(ProbeReceipt::new(
                ProbeReceiptStatus::VerifiedUnexecuted,
                "connection_refused",
                checked_at_now(),
            )),
            Err(HttpProbeError::Timeout) => Ok(ProbeReceipt::new(
                ProbeReceiptStatus::Indeterminate,
                "timeout",
                checked_at_now(),
            )),
            Err(HttpProbeError::Unsupported) => Err(ProbeAdapterError::AdapterUnavailable {
                action: effect.action,
            }),
            Err(HttpProbeError::Io) => Err(ProbeAdapterError::AdapterUnavailable {
                action: effect.action,
            }),
        }
    }
}

impl ProbeAdapter for NetworkProbeAdapter {
    fn evaluate(&self, effect: &EffectRecord) -> Result<ProbeReceipt, ProbeAdapterError> {
        if effect.probe_mode == ProbeMode::None {
            return Err(ProbeAdapterError::ProbeDisabled {
                action: effect.action,
            });
        }
        if effect.action != EffectAction::NetworkRequest {
            return Err(ProbeAdapterError::AdapterUnavailable {
                action: effect.action,
            });
        }

        let target_url =
            decode_target_url(&effect.target).ok_or(ProbeAdapterError::AdapterUnavailable {
                action: effect.action,
            })?;
        self.evaluate_network_request(effect, target_url)
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum HttpProbeError {
    ConnectionRefused,
    Timeout,
    Unsupported,
    Io,
}

fn decode_target_path(target: &str) -> Option<PathBuf> {
    target.strip_prefix("scope:").map(PathBuf::from)
}

fn decode_target_url(target: &str) -> Option<&str> {
    target.strip_prefix("scope:")
}

fn parse_http_url(url: &str) -> Option<(String, u16, String)> {
    let without_scheme = url.strip_prefix("http://")?;
    let (host_port, path) = match without_scheme.split_once('/') {
        Some((host_port, path)) => (host_port, format!("/{path}")),
        None => (without_scheme, String::from("/")),
    };
    let (host, port) = match host_port.split_once(':') {
        Some((host, port)) => (host, port.parse().ok()?),
        None => (host_port, 80),
    };
    if host.is_empty() {
        return None;
    }
    Some((host.to_string(), port, path))
}

fn issue_http_get(
    host: &str,
    port: u16,
    path: &str,
    timeout_ms: u64,
) -> Result<(u16, String), HttpProbeError> {
    let timeout = Duration::from_millis(timeout_ms);
    let socket_addr = (host, port)
        .to_socket_addrs()
        .map_err(|_| HttpProbeError::Unsupported)?
        .next()
        .ok_or(HttpProbeError::Unsupported)?;
    let mut stream =
        TcpStream::connect_timeout(&socket_addr, timeout).map_err(map_http_io_error)?;
    stream
        .set_read_timeout(Some(timeout))
        .map_err(|_| HttpProbeError::Io)?;
    stream
        .set_write_timeout(Some(timeout))
        .map_err(|_| HttpProbeError::Io)?;

    let request = format!("GET {path} HTTP/1.1\r\nHost: {host}\r\nConnection: close\r\n\r\n");
    stream
        .write_all(request.as_bytes())
        .map_err(map_http_io_error)?;

    let mut response = String::new();
    stream
        .read_to_string(&mut response)
        .map_err(map_http_io_error)?;

    let mut lines = response.lines();
    let status_line = lines.next().ok_or(HttpProbeError::Io)?;
    let status_code = status_line
        .split_whitespace()
        .nth(1)
        .and_then(|value| value.parse::<u16>().ok())
        .ok_or(HttpProbeError::Io)?;
    let body = response
        .split_once("\r\n\r\n")
        .map(|(_, body)| body.to_string())
        .unwrap_or_default();
    Ok((status_code, body))
}

fn map_http_io_error(error: std::io::Error) -> HttpProbeError {
    match error.kind() {
        std::io::ErrorKind::ConnectionRefused => HttpProbeError::ConnectionRefused,
        std::io::ErrorKind::TimedOut | std::io::ErrorKind::WouldBlock => HttpProbeError::Timeout,
        _ => HttpProbeError::Io,
    }
}

fn checked_at_now() -> String {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|duration| duration.as_secs().to_string())
        .unwrap_or_else(|_| String::from("0"))
}

#[cfg(test)]
mod tests {
    use super::{FileSystemProbeAdapter, NetworkProbeAdapter};
    use safeclaw_core::{
        effect_ledger::{
            EffectAction, EffectActor, EffectRecord, EffectReversibility, EffectTier, ProbeMode,
        },
        ProbeAdapter, ProbeAdapterError, ProbeReceiptStatus,
    };
    use std::{
        env, fs,
        io::{Read, Write},
        net::TcpListener,
        path::{Path, PathBuf},
        process, thread,
        time::{Duration, SystemTime, UNIX_EPOCH},
    };

    struct TempFile {
        path: PathBuf,
    }

    impl TempFile {
        fn new(label: &str) -> Self {
            let unique = SystemTime::now()
                .duration_since(UNIX_EPOCH)
                .expect("system clock must be after epoch")
                .as_nanos();
            let path = env::temp_dir().join(format!(
                "safeclaw-probe-{label}-{}-{unique}.txt",
                process::id()
            ));
            Self { path }
        }

        fn path(&self) -> &Path {
            &self.path
        }
    }

    impl Drop for TempFile {
        fn drop(&mut self) {
            let _ = fs::remove_file(&self.path);
        }
    }

    #[test]
    fn file_write_probe_verifies_existing_file_with_expected_hash() {
        let temp = TempFile::new("write-match");
        let bytes = b"safeclaw-file-write";
        fs::write(temp.path(), bytes).unwrap();

        let effect = demo_effect(
            "effect-file-write",
            EffectAction::FileWrite,
            format!("scope:{}", temp.path().display()),
            ProbeMode::Auto,
        );
        let mut adapter = FileSystemProbeAdapter::new();
        adapter.register_expected_blake3(
            effect.effect_id.clone(),
            blake3::hash(bytes).to_hex().to_string(),
        );

        let receipt = adapter.evaluate(&effect).unwrap();
        assert_eq!(receipt.status, ProbeReceiptStatus::VerifiedExecuted);
        assert!(receipt.evidence.starts_with("file_hash="));
    }

    #[test]
    fn file_write_probe_reports_missing_file_as_unexecuted() {
        let temp = TempFile::new("write-missing");
        let effect = demo_effect(
            "effect-file-missing",
            EffectAction::FileWrite,
            format!("scope:{}", temp.path().display()),
            ProbeMode::Auto,
        );
        let mut adapter = FileSystemProbeAdapter::new();
        adapter.register_expected_blake3(effect.effect_id.clone(), "deadbeef");

        let receipt = adapter.evaluate(&effect).unwrap();
        assert_eq!(receipt.status, ProbeReceiptStatus::VerifiedUnexecuted);
        assert_eq!(receipt.evidence, "file_not_found");
    }

    #[test]
    fn file_delete_probe_uses_real_fs_state() {
        let temp = TempFile::new("delete-state");
        fs::write(temp.path(), b"safeclaw-delete").unwrap();
        let effect = demo_effect(
            "effect-file-delete",
            EffectAction::FileDelete,
            format!("scope:{}", temp.path().display()),
            ProbeMode::Auto,
        );
        let adapter = FileSystemProbeAdapter::new();

        let before = adapter.evaluate(&effect).unwrap();
        assert_eq!(before.status, ProbeReceiptStatus::VerifiedUnexecuted);
        assert!(before.evidence.starts_with("file_exists_hash="));

        fs::remove_file(temp.path()).unwrap();
        let after = adapter.evaluate(&effect).unwrap();
        assert_eq!(after.status, ProbeReceiptStatus::VerifiedExecuted);
        assert_eq!(after.evidence, "file_not_found");
    }

    #[test]
    fn file_write_probe_requires_expected_hash_registration() {
        let temp = TempFile::new("write-no-hash");
        fs::write(temp.path(), b"safeclaw-no-hash").unwrap();
        let effect = demo_effect(
            "effect-file-no-hash",
            EffectAction::FileWrite,
            format!("scope:{}", temp.path().display()),
            ProbeMode::Auto,
        );
        let adapter = FileSystemProbeAdapter::new();

        assert_eq!(
            adapter.evaluate(&effect),
            Err(ProbeAdapterError::AdapterUnavailable {
                action: EffectAction::FileWrite,
            })
        );
    }

    #[test]
    fn filesystem_probe_rejects_disabled_and_non_filesystem_actions() {
        let disabled = demo_effect(
            "effect-disabled",
            EffectAction::FileDelete,
            String::from("scope:C:/tmp/disabled.txt"),
            ProbeMode::None,
        );
        let adapter = FileSystemProbeAdapter::new();
        assert_eq!(
            adapter.evaluate(&disabled),
            Err(ProbeAdapterError::ProbeDisabled {
                action: EffectAction::FileDelete,
            })
        );

        let network = demo_effect(
            "effect-network",
            EffectAction::NetworkRequest,
            String::from("scope:https://example.com/status"),
            ProbeMode::Auto,
        );
        assert_eq!(
            adapter.evaluate(&network),
            Err(ProbeAdapterError::AdapterUnavailable {
                action: EffectAction::NetworkRequest,
            })
        );
    }

    #[test]
    fn filesystem_probe_rejects_malformed_scope_target() {
        let effect = demo_effect(
            "effect-file-malformed-target",
            EffectAction::FileWrite,
            String::from("not-a-scope-target"),
            ProbeMode::Auto,
        );
        let adapter = FileSystemProbeAdapter::new();

        assert_eq!(
            adapter.evaluate(&effect),
            Err(ProbeAdapterError::AdapterUnavailable {
                action: EffectAction::FileWrite,
            })
        );
    }

    #[test]
    fn network_probe_verifies_expected_response_pattern() {
        let server = TestHttpServer::spawn(
            "HTTP/1.1 200 OK\r\nContent-Length: 13\r\nConnection: close\r\n\r\nstatus=applied",
            0,
        );
        let effect = demo_effect(
            "effect-network-match",
            EffectAction::NetworkRequest,
            server.target(),
            ProbeMode::Auto,
        );
        let mut adapter = NetworkProbeAdapter::new();
        adapter.register_expected_response(effect.effect_id.clone(), "status=applied");

        let receipt = adapter.evaluate(&effect).unwrap();
        assert_eq!(receipt.status, ProbeReceiptStatus::VerifiedExecuted);
        assert_eq!(receipt.evidence, "http_status=200");
    }

    #[test]
    fn network_probe_reports_missing_pattern_as_unexecuted() {
        let server = TestHttpServer::spawn(
            "HTTP/1.1 200 OK\r\nContent-Length: 14\r\nConnection: close\r\n\r\nstatus=pending",
            0,
        );
        let effect = demo_effect(
            "effect-network-pending",
            EffectAction::NetworkRequest,
            server.target(),
            ProbeMode::Auto,
        );
        let mut adapter = NetworkProbeAdapter::new();
        adapter.register_expected_response(effect.effect_id.clone(), "status=applied");

        let receipt = adapter.evaluate(&effect).unwrap();
        assert_eq!(receipt.status, ProbeReceiptStatus::VerifiedUnexecuted);
        assert_eq!(receipt.evidence, "http_status=200");
    }

    #[test]
    fn network_probe_reports_connection_refused_as_unexecuted() {
        let listener = TcpListener::bind("127.0.0.1:0").unwrap();
        let addr = listener.local_addr().unwrap();
        drop(listener);
        let effect = demo_effect(
            "effect-network-refused",
            EffectAction::NetworkRequest,
            format!("scope:http://{addr}/status"),
            ProbeMode::Auto,
        );
        let mut adapter = NetworkProbeAdapter::new();
        adapter.register_expected_response(effect.effect_id.clone(), "status=applied");

        let receipt = adapter.evaluate(&effect).unwrap();
        assert_eq!(receipt.status, ProbeReceiptStatus::VerifiedUnexecuted);
        assert_eq!(receipt.evidence, "connection_refused");
    }

    #[test]
    fn network_probe_reports_timeout_as_indeterminate() {
        let server = TestHttpServer::spawn(
            "HTTP/1.1 200 OK\r\nContent-Length: 13\r\nConnection: close\r\n\r\nstatus=applied",
            100,
        );
        let effect = demo_effect(
            "effect-network-timeout",
            EffectAction::NetworkRequest,
            server.target(),
            ProbeMode::Auto,
        );
        let mut adapter = NetworkProbeAdapter::new().with_timeout_ms(20);
        adapter.register_expected_response(effect.effect_id.clone(), "status=applied");

        let receipt = adapter.evaluate(&effect).unwrap();
        assert_eq!(receipt.status, ProbeReceiptStatus::Indeterminate);
        assert_eq!(receipt.evidence, "timeout");
    }

    #[test]
    fn network_probe_rejects_disabled_or_missing_pattern_registration() {
        let disabled = demo_effect(
            "effect-network-disabled",
            EffectAction::NetworkRequest,
            String::from("scope:http://127.0.0.1:8080/status"),
            ProbeMode::None,
        );
        let adapter = NetworkProbeAdapter::new();
        assert_eq!(
            adapter.evaluate(&disabled),
            Err(ProbeAdapterError::ProbeDisabled {
                action: EffectAction::NetworkRequest,
            })
        );

        let unregistered = demo_effect(
            "effect-network-unregistered",
            EffectAction::NetworkRequest,
            String::from("scope:http://127.0.0.1:8080/status"),
            ProbeMode::Auto,
        );
        assert_eq!(
            adapter.evaluate(&unregistered),
            Err(ProbeAdapterError::AdapterUnavailable {
                action: EffectAction::NetworkRequest,
            })
        );
    }

    #[test]
    fn network_probe_rejects_malformed_scope_target() {
        let effect = demo_effect(
            "effect-network-malformed-target",
            EffectAction::NetworkRequest,
            String::from("scope:not-a-valid-http-url"),
            ProbeMode::Auto,
        );
        let mut adapter = NetworkProbeAdapter::new();
        adapter.register_expected_response(effect.effect_id.clone(), "status=applied");

        assert_eq!(
            adapter.evaluate(&effect),
            Err(ProbeAdapterError::AdapterUnavailable {
                action: EffectAction::NetworkRequest,
            })
        );
    }

    struct TestHttpServer {
        target: String,
        handle: Option<thread::JoinHandle<()>>,
    }

    impl TestHttpServer {
        fn spawn(response: &str, delay_ms: u64) -> Self {
            let listener = TcpListener::bind("127.0.0.1:0").unwrap();
            let addr = listener.local_addr().unwrap();
            let response = response.to_string();
            let handle = thread::spawn(move || {
                let (mut stream, _) = listener.accept().unwrap();
                let mut buffer = [0_u8; 1024];
                let _ = stream.read(&mut buffer);
                if delay_ms > 0 {
                    thread::sleep(Duration::from_millis(delay_ms));
                }
                let _ = stream.write_all(response.as_bytes());
            });
            Self {
                target: format!("scope:http://{addr}/status"),
                handle: Some(handle),
            }
        }

        fn target(&self) -> String {
            self.target.clone()
        }
    }

    impl Drop for TestHttpServer {
        fn drop(&mut self) {
            if let Some(handle) = self.handle.take() {
                let _ = handle.join();
            }
        }
    }

    fn demo_effect(
        effect_id: &str,
        action: EffectAction,
        target: String,
        probe_mode: ProbeMode,
    ) -> EffectRecord {
        EffectRecord::new(
            effect_id,
            format!("task-{effect_id}"),
            format!("trace-{effect_id}"),
            format!("intent-{effect_id}"),
            EffectActor::Worker,
            action,
            target,
            EffectTier::Tier1,
            EffectReversibility::Rollbackable,
            probe_mode,
        )
    }
}
