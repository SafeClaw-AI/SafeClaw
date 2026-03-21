use std::{
    collections::HashMap,
    fs,
    path::{Path, PathBuf},
    time::{SystemTime, UNIX_EPOCH},
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

        let target_path = decode_target_path(&effect.target).ok_or(
            ProbeAdapterError::AdapterUnavailable {
                action: effect.action,
            },
        )?;

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
            Err(error)
                if error.kind() == std::io::ErrorKind::PermissionDenied =>
            {
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

    fn evaluate_file_delete(
        &self,
        target_path: &Path,
    ) -> Result<ProbeReceipt, ProbeAdapterError> {
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
            Err(error)
                if error.kind() == std::io::ErrorKind::PermissionDenied =>
            {
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

fn decode_target_path(target: &str) -> Option<PathBuf> {
    target.strip_prefix("scope:").map(PathBuf::from)
}

fn checked_at_now() -> String {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|duration| duration.as_secs().to_string())
        .unwrap_or_else(|_| String::from("0"))
}

#[cfg(test)]
mod tests {
    use super::FileSystemProbeAdapter;
    use safeclaw_core::{
        effect_ledger::{
            EffectAction, EffectActor, EffectRecord, EffectReversibility,
            EffectTier, ProbeMode,
        },
        ProbeAdapter, ProbeAdapterError, ProbeReceiptStatus,
    };
    use std::{
        env, fs,
        path::{Path, PathBuf},
        process,
        time::{SystemTime, UNIX_EPOCH},
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
