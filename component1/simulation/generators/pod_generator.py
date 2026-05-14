"""
pod_generator.py
Adds Gaussian noise to pod raw metrics each tick to simulate realistic drift.
Scenarios directly mutate ClusterState.pods before this runs.
"""
import numpy as np
from cluster_state import ClusterState, PodState


def _jitter(value: float, sigma_pct: float = 0.05, minimum: float = 0.0) -> float:
    """Add ±sigma_pct relative Gaussian noise."""
    noise = np.random.normal(0, abs(value) * sigma_pct)
    return max(minimum, value + noise)


def tick_pods(state: ClusterState) -> None:
    """Update raw pod metrics for one simulation tick (30s window)."""
    for pod in state.pods:
        if pod.phase != "Running":
            continue

        # --- CPU ---
        pod.cpu_usage_millicores = _jitter(pod.cpu_usage_millicores, sigma_pct=0.08, minimum=1.0)
        # throttle periods accumulate; scenario sets throttle rate via fault_intensity
        tick_periods = 100  # 100 CFS periods per 30s
        throttle_rate = pod._fault_intensity if hasattr(pod, '_fault_intensity') else 0.0
        new_throttled = int(tick_periods * throttle_rate * np.random.uniform(0.9, 1.1))
        pod.cpu_throttled_periods += new_throttled
        pod.cpu_total_periods += tick_periods

        # --- Memory ---
        pod.memory_working_set_bytes = max(
            1024 * 1024,
            int(_jitter(pod.memory_working_set_bytes, sigma_pct=0.03))
        )
        pod.memory_rss_bytes = min(pod.memory_working_set_bytes,
                                   int(_jitter(pod.memory_rss_bytes, sigma_pct=0.03, minimum=0)))

        # OOM events only increment if WSS > limit
        if pod.memory_working_set_bytes > pod.memory_limit_bytes:
            pod.memory_oom_events += 1
            pod.memory_failcnt += 1
            state.add_event("oom_kill", pod.pod_id, "error", "OOMKilling")

        # Major page faults: higher when memory is under pressure
        pressure_ratio = pod.memory_working_set_bytes / pod.memory_limit_bytes
        pod.memory_major_fault_rate = _jitter(
            max(0.0, (pressure_ratio - 0.7) * 500), sigma_pct=0.2, minimum=0.0
        )

        # --- Probes ---
        pod.probe_latency_ms = max(1, int(_jitter(pod.probe_latency_ms, sigma_pct=0.1)))
        # Probe succeeds if latency < 2000ms and pod not under severe pressure
        if pod.probe_latency_ms < 2000 and pod.memory_working_set_bytes < pod.memory_limit_bytes:
            pod.probe_last_succeeded = True
            pod.probe_consecutive_failures = 0
        else:
            pod.probe_last_succeeded = False
            pod.probe_consecutive_failures += 1
            pod.probe_failure_event_count += 1
            state.add_event("probe_failure", pod.pod_id, "warning", "Unhealthy")

        # kubelet kills pod after 3 consecutive probe failures
        if pod.probe_consecutive_failures >= 3:
            pod.restart_count_prev = pod.restart_count
            pod.restart_count += 1
            pod.probe_consecutive_failures = 0
            pod.memory_working_set_bytes = int(pod.memory_limit_bytes * 0.3)  # reset after restart
            pod.last_terminated_reason = "Error"
            state.add_event("pod_restart", pod.pod_id, "warning", "BackOff")

        if pod.restart_count >= 5:
            pod.crash_loop_active = True

        # --- Network ---
        base_rx = 1_000_000  # 1 MB/s baseline
        pod.net_rx_bytes_total += int(_jitter(base_rx * 30, sigma_pct=0.15, minimum=0))
        pod.net_tx_bytes_total += int(_jitter(base_rx * 20, sigma_pct=0.15, minimum=0))
        # Drops only if fault_intensity is high (set by grpc scenario)
        drop_rate = getattr(pod, '_net_drop_rate', 0.0)
        pod.net_rx_packets_dropped_total += int(np.random.poisson(max(0, drop_rate * 30)))

        # --- Storage ---
        pod.storage_used_bytes = min(
            pod.storage_capacity_bytes,
            int(_jitter(pod.storage_used_bytes, sigma_pct=0.01, minimum=0))
        )
