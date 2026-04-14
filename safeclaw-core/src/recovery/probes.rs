use std::collections::HashMap;

use crate::effect_ledger::{EffectAction, EffectRecord, ProbeMode};

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum ProbeReceiptStatus {
    VerifiedExecuted,
    VerifiedUnexecuted,
    Indeterminate,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct ProbeReceipt {
    pub status: ProbeReceiptStatus,
    pub evidence: String,
    pub checked_at: String,
}

impl ProbeReceipt {
    pub fn new(
        status: ProbeReceiptStatus,
        evidence: impl Into<String>,
        checked_at: impl Into<String>,
    ) -> Self {
        Self {
            status,
            evidence: evidence.into(),
            checked_at: checked_at.into(),
        }
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct ProbeDefinition {
    pub action: EffectAction,
    pub default_mode: ProbeMode,
    pub method: &'static str,
    pub inputs: &'static [&'static str],
    pub timeout_ms: u64,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum ProbeAdapterError {
    UnsupportedAction { action: EffectAction },
    AdapterUnavailable { action: EffectAction },
    ProbeDisabled { action: EffectAction },
}

pub trait ProbeAdapter {
    fn evaluate(&self, effect: &EffectRecord) -> Result<ProbeReceipt, ProbeAdapterError>;
}

#[derive(Clone, Debug, Default)]
pub struct InMemoryProbeAdapter {
    receipts: HashMap<String, ProbeReceipt>,
}

pub type MockProbeAdapter = InMemoryProbeAdapter;

impl InMemoryProbeAdapter {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn register(&mut self, effect_id: impl Into<String>, receipt: ProbeReceipt) {
        self.receipts.insert(effect_id.into(), receipt);
    }
}

pub fn probe_definition_for(action: EffectAction) -> Option<ProbeDefinition> {
    match action {
        EffectAction::FileWrite => Some(ProbeDefinition {
            action,
            default_mode: ProbeMode::Auto,
            method: "检查目标文件是否存在 + blake3 哈希比对",
            inputs: &["target_path", "expected_blake3"],
            timeout_ms: 5_000,
        }),
        EffectAction::FileDelete => Some(ProbeDefinition {
            action,
            default_mode: ProbeMode::Auto,
            method: "检查目标文件是否已不存在",
            inputs: &["target_path"],
            timeout_ms: 5_000,
        }),
        EffectAction::NetworkRequest => Some(ProbeDefinition {
            action,
            default_mode: ProbeMode::Auto,
            method: "HTTP GET 状态查询端点(如有); 否则标记 indeterminate",
            inputs: &["target_url", "expected_response_pattern"],
            timeout_ms: 10_000,
        }),
        _ => None,
    }
}

impl ProbeAdapter for InMemoryProbeAdapter {
    fn evaluate(&self, effect: &EffectRecord) -> Result<ProbeReceipt, ProbeAdapterError> {
        if effect.probe_mode == ProbeMode::None {
            return Err(ProbeAdapterError::ProbeDisabled {
                action: effect.action,
            });
        }

        if probe_definition_for(effect.action).is_none() {
            return Err(ProbeAdapterError::UnsupportedAction {
                action: effect.action,
            });
        }

        self.receipts
            .get(&effect.effect_id)
            .cloned()
            .ok_or(ProbeAdapterError::AdapterUnavailable {
                action: effect.action,
            })
    }
}

#[cfg(test)]
mod tests {
    use super::{
        probe_definition_for, InMemoryProbeAdapter, ProbeAdapter, ProbeAdapterError, ProbeReceipt,
        ProbeReceiptStatus,
    };
    use crate::effect_ledger::{
        EffectAction, EffectActor, EffectRecord, EffectReversibility, EffectTier, ProbeMode,
    };

    fn demo_effect(action: EffectAction, probe_mode: ProbeMode) -> EffectRecord {
        EffectRecord::new(
            "effect-probe",
            "task-probe",
            "trace-probe",
            "intent-probe",
            EffectActor::Worker,
            action,
            "scope:/tmp/probe.txt",
            EffectTier::Tier1,
            EffectReversibility::Rollbackable,
            probe_mode,
        )
    }

    #[test]
    fn probe_catalog_matches_current_supported_specs() {
        let file_write = probe_definition_for(EffectAction::FileWrite).unwrap();
        assert_eq!(file_write.timeout_ms, 5_000);
        assert_eq!(file_write.inputs, &["target_path", "expected_blake3"]);

        let file_delete = probe_definition_for(EffectAction::FileDelete).unwrap();
        assert_eq!(file_delete.inputs, &["target_path"]);

        let network = probe_definition_for(EffectAction::NetworkRequest).unwrap();
        assert_eq!(network.timeout_ms, 10_000);
        assert_eq!(network.inputs, &["target_url", "expected_response_pattern"]);

        assert!(probe_definition_for(EffectAction::SystemExec).is_none());
    }

    #[test]
    fn in_memory_probe_adapter_returns_registered_receipt() {
        let effect = demo_effect(EffectAction::FileWrite, ProbeMode::Auto);
        let mut adapter = InMemoryProbeAdapter::new();
        adapter.register(
            effect.effect_id.clone(),
            ProbeReceipt::new(
                ProbeReceiptStatus::VerifiedExecuted,
                "file_hash=abc",
                "2026-03-21T00:00:00Z",
            ),
        );

        let receipt = adapter.evaluate(&effect).unwrap();
        assert_eq!(receipt.status, ProbeReceiptStatus::VerifiedExecuted);
        assert_eq!(receipt.evidence, "file_hash=abc");
    }

    #[test]
    fn in_memory_probe_adapter_rejects_disabled_or_unknown_probe_paths() {
        let disabled = demo_effect(EffectAction::FileWrite, ProbeMode::None);
        let adapter = InMemoryProbeAdapter::new();
        assert_eq!(
            adapter.evaluate(&disabled),
            Err(ProbeAdapterError::ProbeDisabled {
                action: EffectAction::FileWrite,
            })
        );

        let unsupported = demo_effect(EffectAction::SystemExec, ProbeMode::Auto);
        assert_eq!(
            adapter.evaluate(&unsupported),
            Err(ProbeAdapterError::UnsupportedAction {
                action: EffectAction::SystemExec,
            })
        );
    }
}
