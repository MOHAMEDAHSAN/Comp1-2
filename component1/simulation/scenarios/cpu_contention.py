"""
cpu_contention.py
Simulates: Shared-core CPU contention -> CFS throttling -> latency -> probe timeout

Causal chain:
  Ticks 0-5   : Baseline
  Ticks 5-15  : CPU usage rises on the node, throttle ratio creeps up
  Ticks 15-25 : Service latency rises from throttling
  Ticks 25+   : Probe timeouts and restarts
"""
from cluster_state import ClusterState


def apply(state: ClusterState, tick: int, total_ticks: int) -> None:
    progress = tick / max(1, total_ticks)

    # Target: backend pods
    target_pods = [p for p in state.pods if p.service == "backend"]

    for pod in target_pods:
        if progress < 0.2:
            pod._fault_intensity = 0.0

        elif progress < 0.6:
            # Throttle ratio ramps from 5% -> 70%
            throttle = 0.05 + (progress - 0.2) / 0.4 * 0.65
            pod._fault_intensity = throttle
            # CPU usage also rises — close to limit
            pod.cpu_usage_millicores = pod.cpu_limit_millicores * (0.7 + throttle * 0.4)

        else:
            # Severe throttling -> probe timeout
            pod._fault_intensity = 0.75
            pod.cpu_usage_millicores = pod.cpu_limit_millicores * 1.1  # over limit
            # Probe latency climbs
            severity = (progress - 0.6) / 0.4
            pod.probe_latency_ms = int(50 + severity * 2200)

    # Node-level CPU rises too
    if progress > 0.3:
        state.node.cpu_pressure_waiting_rate = 0.02 + (progress - 0.3) * 0.6
        state.node.cpu_sched_wait_ratio = 0.05 + (progress - 0.3) * 0.5
