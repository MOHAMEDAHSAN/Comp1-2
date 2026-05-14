"""
service_generator.py
Derives service-level metrics from pod states each tick.
"""
import numpy as np
from cluster_state import ClusterState


def _jitter(value: float, sigma_pct: float = 0.07, minimum: float = 0.0) -> float:
    return max(minimum, value + np.random.normal(0, abs(value + 1e-9) * sigma_pct))


def tick_services(state: ClusterState) -> None:
    for svc in state.services:
        # Count ready pods for this service
        svc_pods = [p for p in state.pods if p.service == svc.service_name]
        ready = sum(1 for p in svc_pods if p.phase == "Running" and p.probe_last_succeeded)
        svc.ready_replicas = ready
        svc.unavailable_replicas = max(0, svc.desired_replicas - ready)

        # Error rate rises when pods are failing probes
        failing = sum(1 for p in svc_pods if not p.probe_last_succeeded)
        base_error = getattr(svc, '_base_error_rate', 0.001)
        svc.error_rate = _jitter(
            base_error + (failing / max(1, len(svc_pods))) * 0.3,
            sigma_pct=0.1, minimum=0.0
        )
        svc.error_rate = min(1.0, svc.error_rate)

        # Latency rises with CPU pressure and probe failures
        avg_throttle = np.mean([
            p.cpu_throttled_periods / max(1, p.cpu_total_periods)
            for p in svc_pods
        ]) if svc_pods else 0.0
        base_p99 = getattr(svc, '_base_latency_p99', 80.0)
        svc.latency_p99_ms = int(_jitter(
            base_p99 * (1 + avg_throttle * 5) * (1 + failing * 0.5),
            sigma_pct=0.08, minimum=1
        ))
        svc.latency_p50_ms = int(svc.latency_p99_ms * np.random.uniform(0.2, 0.4))

        # QPS — steady with slight noise
        svc.qps = _jitter(getattr(svc, '_base_qps', 50.0), sigma_pct=0.05, minimum=0.0)

        # HPA tracks ready replicas
        svc.hpa_current_replicas = ready
