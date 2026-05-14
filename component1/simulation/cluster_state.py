"""
cluster_state.py
Mutable world state for the simulated Kubernetes cluster.
All raw (un-normalized) values live here. The normalizer reads from this.
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional
import time


# ---------------------------------------------------------------------------
# Pod state — raw values as they would come from cAdvisor / Kubelet / KSM
# ---------------------------------------------------------------------------
@dataclass
class PodState:
    # Identity
    pod_id: str              # "namespace/pod-name"
    namespace: str
    pod_name: str
    node_name: str
    service: str             # which logical service this pod belongs to
    labels: Dict[str, str] = field(default_factory=dict)

    # Lifecycle
    phase: str = "Running"   # Running | Pending | Failed | Succeeded
    last_terminated_reason: str = "unknown"

    # Resource limits (set at start, don't change)
    cpu_limit_millicores: float = 500.0      # 500m
    memory_limit_bytes: int = 256 * 1024 * 1024  # 256 MiB

    # --- RAW CPU metrics (container_cpu_cfs_*) ---
    cpu_usage_millicores: float = 50.0       # current usage
    cpu_throttled_periods: int = 0           # cumulative counter
    cpu_total_periods: int = 1              # cumulative counter (always >= 1)

    # --- RAW Memory metrics (container_memory_*) ---
    memory_working_set_bytes: int = 80 * 1024 * 1024   # WSS ~80MiB baseline
    memory_rss_bytes: int = 60 * 1024 * 1024
    memory_failcnt: int = 0              # container_memory_failcnt
    memory_oom_events: int = 0           # container_oom_events_total
    memory_major_fault_rate: float = 0.0 # pgmajfault/s

    # --- RAW Probe metrics (Kubelet probe manager) ---
    probe_type: str = "liveness"
    probe_latency_ms: int = 5            # baseline: ~5ms
    probe_consecutive_failures: int = 0
    probe_last_succeeded: bool = True
    probe_failure_event_count: int = 0   # Unhealthy events in window

    # --- Restart info (kube_pod_container_status_restarts_total) ---
    restart_count: int = 0
    restart_count_prev: int = 0          # for computing delta
    crash_loop_active: bool = False

    # --- Network (container_network_*) ---
    net_rx_bytes_total: int = 0          # cumulative
    net_tx_bytes_total: int = 0
    net_rx_packets_dropped_total: int = 0

    # --- Storage (kubelet_volume_stats_*) ---
    storage_used_bytes: int = 10 * 1024 * 1024      # 10 MiB
    storage_capacity_bytes: int = 1024 * 1024 * 1024 # 1 GiB

    # --- Internal scenario tracking ---
    _fault_intensity: float = 0.0        # 0.0 = healthy, 1.0 = fully faulted


# ---------------------------------------------------------------------------
# Node state — raw values from node-exporter / Kubelet / K8s API
# ---------------------------------------------------------------------------
@dataclass
class NodeState:
    name: str = "node-1"
    schedulable: bool = True
    conditions: List[str] = field(default_factory=lambda: ["Ready"])

    # CPU (node_cpu_seconds_total, schedstat, PSI)
    cpu_usage_percent: float = 25.0
    cpu_pressure_waiting_rate: float = 0.02     # PSI cpu waiting
    cpu_sched_wait_ratio: float = 0.05          # waiting/(waiting+running)
    cpu_load1: float = 0.8

    # Memory (node_memory_*)
    memory_total_bytes: int = 8 * 1024 * 1024 * 1024   # 8 GiB
    memory_available_bytes: int = 6 * 1024 * 1024 * 1024
    memory_pressure_waiting_rate: float = 0.01

    # Storage/IO (node-exporter disk/PSI)
    disk_io_weighted_rate: float = 0.05
    io_pressure_waiting_rate: float = 0.01
    fs_available_bytes: int = 50 * 1024 * 1024 * 1024   # 50 GiB

    # Network (node_netstat_*)
    tcp_out_segs: int = 0       # cumulative
    tcp_retrans_segs: int = 0   # cumulative
    tcp_syn_retrans_rate: float = 0.0
    conntrack_entries: int = 500
    conntrack_limit: int = 65536

    # DNS (coredns metrics)
    dns_latency_p99_ms: int = 5
    dns_servfail_rate: float = 0.0

    # CSI
    csi_attach_latency_ms: int = 200


# ---------------------------------------------------------------------------
# Service state — aggregated from deployment/HPA
# ---------------------------------------------------------------------------
@dataclass
class ServiceState:
    service_id: str          # "namespace/service-name"
    namespace: str
    service_name: str

    ready_replicas: int = 3
    desired_replicas: int = 3
    unavailable_replicas: int = 0

    hpa_current_replicas: int = 3
    hpa_desired_replicas: int = 3

    # Latency (from Prometheus / service mesh)
    latency_p50_ms: int = 20
    latency_p99_ms: int = 80
    error_rate: float = 0.001   # 0.1%
    qps: float = 50.0


# ---------------------------------------------------------------------------
# PVC state
# ---------------------------------------------------------------------------
@dataclass
class PVCState:
    pvc_id: str              # "namespace/pvc-name"
    namespace: str
    pvc_name: str
    phase: str = "Bound"     # Bound | Pending | Lost
    phase_changed_at_ms: Optional[int] = None


# ---------------------------------------------------------------------------
# Event — maps to ClusterEvent in canonical schema
# ---------------------------------------------------------------------------
@dataclass
class SimEvent:
    event_type: str          # pod_restart | oom_kill | probe_failure | eviction | deploy | scale | node_condition | storage_error
    affected_id: str
    severity: str            # info | warning | error
    timestamp_ms: int
    count: int = 1
    reason: str = ""


# ---------------------------------------------------------------------------
# Top-level cluster state
# ---------------------------------------------------------------------------
@dataclass
class ClusterState:
    tenant_id: str = "tenant-sim-001"
    cluster_name: str = "sim-cluster"

    pods: List[PodState] = field(default_factory=list)
    node: NodeState = field(default_factory=NodeState)
    services: List[ServiceState] = field(default_factory=list)
    pvcs: List[PVCState] = field(default_factory=list)
    pending_events: List[SimEvent] = field(default_factory=list)

    tick: int = 0                        # current observation number
    tick_interval_s: int = 30            # seconds between observations

    # Capability flags (auto-set by simulation — all True for simulation)
    has_kubernetes_api: bool = True
    has_prometheus: bool = True
    has_kubelet_metrics: bool = True
    has_logs: bool = True
    has_service_mesh: bool = False       # not simulated in v1

    def timestamp_ms(self) -> int:
        """Wall-clock ms for the current tick."""
        base = int(time.time() * 1000)
        return base - (self.tick * self.tick_interval_s * 1000)

    def add_event(self, event_type: str, affected_id: str, severity: str, reason: str = ""):
        self.pending_events.append(SimEvent(
            event_type=event_type,
            affected_id=affected_id,
            severity=severity,
            timestamp_ms=self.timestamp_ms(),
            reason=reason,
        ))

    def flush_events(self) -> List[SimEvent]:
        evts = list(self.pending_events)
        self.pending_events.clear()
        return evts
