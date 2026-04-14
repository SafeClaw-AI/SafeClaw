use std::time::{Duration, Instant};

#[derive(Clone, Debug)]
pub struct HeartbeatRecord {
    pub worker_id: String,
    pub last_heartbeat: Instant,
    pub task_id: Option<String>,
    pub effect_id: Option<String>,
}

#[derive(Clone, Debug)]
pub struct HeartbeatManager {
    workers: Vec<HeartbeatRecord>,
    heartbeat_timeout: Duration,
}

impl HeartbeatManager {
    pub fn new(heartbeat_timeout_ms: u64) -> Self {
        Self {
            workers: Vec::new(),
            heartbeat_timeout: Duration::from_millis(heartbeat_timeout_ms),
        }
    }

    pub fn register(&mut self, worker_id: impl Into<String>) {
        let worker_id = worker_id.into();
        self.workers.retain(|w| w.worker_id != worker_id);
        self.workers.push(HeartbeatRecord {
            worker_id,
            last_heartbeat: Instant::now(),
            task_id: None,
            effect_id: None,
        });
    }

    pub fn heartbeat(
        &mut self,
        worker_id: &str,
        task_id: Option<String>,
        effect_id: Option<String>,
    ) -> bool {
        if let Some(record) = self.workers.iter_mut().find(|w| w.worker_id == worker_id) {
            record.last_heartbeat = Instant::now();
            record.task_id = task_id;
            record.effect_id = effect_id;
            true
        } else {
            false
        }
    }

    pub fn is_alive(&self, worker_id: &str) -> bool {
        self.workers
            .iter()
            .find(|w| w.worker_id == worker_id)
            .map(|w| w.last_heartbeat.elapsed() < self.heartbeat_timeout)
            .unwrap_or(false)
    }

    pub fn reap_stale(&mut self) -> Vec<String> {
        let now = Instant::now();
        let stale: Vec<String> = self
            .workers
            .iter()
            .filter(|w| now.duration_since(w.last_heartbeat) >= self.heartbeat_timeout)
            .map(|w| w.worker_id.clone())
            .collect();
        self.workers.retain(|w| !stale.contains(&w.worker_id));
        stale
    }

    pub fn active_workers(&self) -> usize {
        self.workers
            .iter()
            .filter(|w| w.last_heartbeat.elapsed() < self.heartbeat_timeout)
            .count()
    }
}

#[derive(Clone, Debug)]
pub struct SidecarQuota {
    pub max_tasks_per_sidecar: usize,
    pub task_count: usize,
    pub graceful_restart_threshold: usize,
}

impl SidecarQuota {
    pub fn new(max_tasks: usize, graceful_restart_threshold: usize) -> Self {
        Self {
            max_tasks_per_sidecar: max_tasks,
            task_count: 0,
            graceful_restart_threshold,
        }
    }

    pub fn can_accept_task(&self) -> bool {
        self.task_count < self.max_tasks_per_sidecar
    }

    pub fn task_started(&mut self) {
        self.task_count += 1;
    }

    pub fn task_completed(&mut self) {
        self.task_count = self.task_count.saturating_sub(1);
    }

    pub fn needs_restart(&self) -> bool {
        self.task_count >= self.graceful_restart_threshold
    }

    pub fn reset(&mut self) {
        self.task_count = 0;
    }
}

#[cfg(test)]
mod tests {
    use super::{HeartbeatManager, SidecarQuota};
    use std::thread;
    use std::time::Duration;

    #[test]
    fn heartbeat_register_and_check_alive() {
        let mut hm = HeartbeatManager::new(100);
        hm.register("worker-1");
        assert!(hm.is_alive("worker-1"));
        assert!(!hm.is_alive("worker-2"));
    }

    #[test]
    fn heartbeat_update_refreshes_alive() {
        let mut hm = HeartbeatManager::new(100);
        hm.register("worker-1");
        thread::sleep(Duration::from_millis(50));
        assert!(hm.is_alive("worker-1"));
        hm.heartbeat("worker-1", None, None);
        thread::sleep(Duration::from_millis(80));
        assert!(hm.is_alive("worker-1"));
        thread::sleep(Duration::from_millis(50));
        assert!(!hm.is_alive("worker-1"));
    }

    #[test]
    fn reap_stale_removes_expired_workers() {
        let mut hm = HeartbeatManager::new(50);
        hm.register("worker-1");
        hm.register("worker-2");
        thread::sleep(Duration::from_millis(60));
        let stale = hm.reap_stale();
        assert_eq!(stale.len(), 2);
        assert_eq!(hm.active_workers(), 0);
    }

    #[test]
    fn sidecar_quota_limits_tasks() {
        let mut quota = SidecarQuota::new(5, 3);
        assert!(quota.can_accept_task());
        for _ in 0..5 {
            quota.task_started();
        }
        assert!(!quota.can_accept_task());
        quota.task_completed();
        assert!(quota.can_accept_task());
    }

    #[test]
    fn sidecar_quota_needs_restart() {
        let mut quota = SidecarQuota::new(10, 3);
        assert!(!quota.needs_restart());
        quota.task_started();
        quota.task_started();
        quota.task_started();
        assert!(quota.needs_restart());
        quota.reset();
        assert!(!quota.needs_restart());
    }
}
