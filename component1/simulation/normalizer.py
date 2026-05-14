"""
normalizer.py
Maps raw ClusterState values -> canonical NormalizedObservation dict.
Field names match shared/SCHEMA.md exactly.
This is the core of Component 1's job.
"""
import time
from typing import Any, Dict, List
from cluster_state import ClusterState, PodState, NodeState, ServiceState, PVCState, SimEvent


def _pod_to_canonical(pod: PodState, interval_s: int = 30) -> Dict[str, Any]:
    """Map one PodState -> pod canonical fields."""
    throttle_ratio = (
        pod.cpu_throttled_periods / pod.cpu_total_periods
        if pod.cpu_total_periods > 0 else 0.0
    )
    cpu_pct = min(100.0, (pod.cpu_usage_millicores / pod.cpu_limit_millicores) * 100)
    mem_pct = min(100.0, (pod.memory_working_set_bytes / pod.memory_limit_bytes) * 100)
    storage_pct = (
        (pod.storage_used_bytes / pod.storage_capacity_bytes) * 100
        if pod.storage_capacity_bytes > 0 else 0.0
    )
    return {
        # Identity
        "pod.id":                         pod.pod_id,
        "pod.namespace":                  pod.namespace,
        "pod.node_name":                  pod.node_name,
        "pod.phase":                      pod.phase,
        "pod.labels":                     pod.labels,
        "pod.last_terminated_reason":     pod.last_terminated_reason,
        # Restart
        "pod.restart_count":              pod.restart_count,
        "pod.restart_delta":              max(0, pod.restart_count - pod.restart_count_prev),
        "pod.crash_loop_active":          pod.crash_loop_active,
        # CPU
        "pod.cpu.usage_percent":          round(cpu_pct, 2),
        "pod.cpu.throttle_ratio":         round(throttle_ratio, 4),
        "pod.cpu.throttle_ms":            round(throttle_ratio * interval_s * 1000, 1),
        # Memory
        "pod.memory.working_set_bytes":   pod.memory_working_set_bytes,
        "pod.memory.working_set_pct":     round(mem_pct, 2),
        "pod.memory.rss_bytes":           pod.memory_rss_bytes,
        "pod.memory.limit_hit_count":     pod.memory_failcnt,
        "pod.memory.oom_events":          pod.memory_oom_events,
        "pod.memory.major_fault_rate":    round(pod.memory_major_fault_rate, 3),
        # Probes
        "pod.probe.type":                 pod.probe_type,
        "pod.probe.latency_ms":           pod.probe_latency_ms,
        "pod.probe.consecutive_failures": pod.probe_consecutive_failures,
        "pod.probe.last_succeeded":       pod.probe_last_succeeded,
        "pod.probe.failure_event_count":  pod.probe_failure_event_count,
        # Network (rate over interval)
        "pod.net.rx_bytes_rate":          round(pod.net_rx_bytes_total / interval_s, 2),
        "pod.net.tx_bytes_rate":          round(pod.net_tx_bytes_total / interval_s, 2),
        "pod.net.rx_drop_rate":           round(pod.net_rx_packets_dropped_total / interval_s, 4),
        # Storage
        "pod.storage.used_bytes":         pod.storage_used_bytes,
        "pod.storage.capacity_bytes":     pod.storage_capacity_bytes,
        "pod.storage.used_pct":           round(storage_pct, 2),
    }


def _node_to_canonical(node: NodeState, out_segs_prev: int, retrans_prev: int,
                        interval_s: int = 30) -> Dict[str, Any]:
    """Map NodeState -> node canonical fields."""
    delta_out = max(1, node.tcp_out_segs - out_segs_prev)
    delta_retrans = node.tcp_retrans_segs - retrans_prev
    retrans_ratio = round(delta_retrans / delta_out, 6)
    mem_avail_pct = round(
        (node.memory_available_bytes / node.memory_total_bytes) * 100, 2
    )
    conntrack_util = round(node.conntrack_entries / node.conntrack_limit, 4)

    return {
        "node.name":                          node.name,
        "node.conditions":                    node.conditions,
        "node.schedulable":                   node.schedulable,
        # CPU
        "node.cpu.usage_percent":             round(node.cpu_usage_percent, 2),
        "node.cpu.pressure_waiting_rate":     round(node.cpu_pressure_waiting_rate, 4),
        "node.cpu.sched_wait_ratio":          round(node.cpu_sched_wait_ratio, 4),
        "node.cpu.load1":                     round(node.cpu_load1, 3),
        # Memory
        "node.memory.available_bytes":        node.memory_available_bytes,
        "node.memory.available_pct":          mem_avail_pct,
        "node.memory.pressure_waiting_rate":  round(node.memory_pressure_waiting_rate, 4),
        # Storage / IO
        "node.storage.disk_io_weighted_rate": round(node.disk_io_weighted_rate, 4),
        "node.storage.io_pressure_waiting_rate": round(node.io_pressure_waiting_rate, 4),
        "node.storage.fs_available_bytes":    node.fs_available_bytes,
        "node.storage.csi_attach_latency_ms": node.csi_attach_latency_ms,
        # Network
        "node.net.tcp_retrans_rate":          retrans_ratio,
        "node.net.tcp_syn_retrans_rate":      round(node.tcp_syn_retrans_rate, 6),
        "node.net.conntrack_utilization":     conntrack_util,
        "node.net.dns_latency_p99_ms":        node.dns_latency_p99_ms,
        "node.net.dns_servfail_rate":         round(node.dns_servfail_rate, 4),
    }


def _service_to_canonical(svc: ServiceState) -> Dict[str, Any]:
    return {
        "service.id":                   svc.service_id,
        "service.ready_replicas":       svc.ready_replicas,
        "service.unavailable_replicas": svc.unavailable_replicas,
        "service.hpa_current_replicas": svc.hpa_current_replicas,
        "service.hpa_desired_replicas": svc.hpa_desired_replicas,
        "service.latency_p50_ms":       svc.latency_p50_ms,
        "service.latency_p99_ms":       svc.latency_p99_ms,
        "service.error_rate":           round(svc.error_rate, 6),
        "service.qps":                  round(svc.qps, 2),
    }


def _pvc_to_canonical(pvc: PVCState, ts_ms: int) -> Dict[str, Any]:
    pending_ms = (ts_ms - pvc.phase_changed_at_ms) if (
        pvc.phase == "Pending" and pvc.phase_changed_at_ms
    ) else 0
    return {
        "pvc.id":                  pvc.pvc_id,
        "pvc.phase":               pvc.phase,
        "pvc.pending_duration_ms": pending_ms,
    }


def _event_to_canonical(evt: SimEvent) -> Dict[str, Any]:
    return {
        "event.type":         evt.event_type,
        "event.affected_id":  evt.affected_id,
        "event.severity":     evt.severity,
        "event.timestamp_ms": evt.timestamp_ms,
        "event.count":        evt.count,
        "event.reason":       evt.reason,
    }


# ---------------------------------------------------------------------------
# Main normalization entry point
# ---------------------------------------------------------------------------
class Normalizer:
    def __init__(self):
        self._prev_tcp_out: int = 0
        self._prev_tcp_retrans: int = 0

    def normalize(self, state: ClusterState, events: List[SimEvent]) -> Dict[str, Any]:
        """
        Convert raw ClusterState -> canonical NormalizedObservation dict.
        This is the single place where all raw metric names are translated
        to canonical field names from shared/SCHEMA.md.
        """
        ts_ms = state.timestamp_ms()

        obs: Dict[str, Any] = {
            # A1 Envelope
            "tenant_id":    state.tenant_id,
            "cluster_name": state.cluster_name,
            "timestamp_ms": ts_ms,

            # A2 Capability flags
            "capability": {
                "capability.has_kubernetes_api":  state.has_kubernetes_api,
                "capability.has_prometheus":       state.has_prometheus,
                "capability.has_kubelet_metrics":  state.has_kubelet_metrics,
                "capability.has_logs":             state.has_logs,
                "capability.has_service_mesh":     state.has_service_mesh,
                "capability.degraded_playbooks":   {
                    "grpc-degradation": "partial" if not state.has_service_mesh else "full"
                },
            },

            # A3 Pod features
            "pod_metrics": [
                _pod_to_canonical(pod, state.tick_interval_s)
                for pod in state.pods
            ],

            # A4 Node features
            "node_metrics": [
                _node_to_canonical(
                    state.node,
                    self._prev_tcp_out,
                    self._prev_tcp_retrans,
                    state.tick_interval_s,
                )
            ],

            # A5 Service features
            "service_metrics": [
                _service_to_canonical(svc) for svc in state.services
            ],

            # A6 PVC features
            "pvc_metrics": [
                _pvc_to_canonical(pvc, ts_ms) for pvc in state.pvcs
            ],

            # A7 Events
            "events": [_event_to_canonical(e) for e in events],

            # Simulation metadata (not in schema — for debugging only)
            "_sim_tick": state.tick,
        }

        # Update TCP counters for next tick's rate calculation
        self._prev_tcp_out = state.node.tcp_out_segs
        self._prev_tcp_retrans = state.node.tcp_retrans_segs

        # Reset per-tick counters on pods
        for pod in state.pods:
            pod.restart_count_prev = pod.restart_count
            pod.probe_failure_event_count = 0
            pod.net_rx_bytes_total = 0
            pod.net_tx_bytes_total = 0
            pod.net_rx_packets_dropped_total = 0

        return obs
