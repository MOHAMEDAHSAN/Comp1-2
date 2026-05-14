"""
oom_cascade.py
Simulates: Pod OOMKilled -> node memory pressure -> evictions cascade

Causal chain:
  Ticks 0-5   : Baseline
  Ticks 5-12  : Memory leak — one pod's WSS grows steadily
  Ticks 12-16 : Pod hits limit -> OOMKilled (exit 137)
  Ticks 16-20 : Node memory pressure rises (eviction manager triggers)
  Ticks 20+   : Other pods evicted, node MemoryPressure condition
"""
from cluster_state import ClusterState


def apply(state: ClusterState, tick: int, total_ticks: int) -> None:
    progress = tick / max(1, total_ticks)

    # Target: first redis pod (memory-heavy workload)
    target = next((p for p in state.pods if p.service == "redis"), None)
    if not target:
        return

    if progress < 0.2:
        pass  # healthy

    elif progress < 0.5:
        # Slow memory leak — WSS grows from 60% -> 100% of limit
        mem_pct = 0.60 + (progress - 0.2) / 0.3 * 0.40
        target.memory_working_set_bytes = int(target.memory_limit_bytes * mem_pct)
        target.memory_rss_bytes = int(target.memory_working_set_bytes * 0.9)
        target.memory_major_fault_rate = max(0, (mem_pct - 0.8) * 500)

    elif progress < 0.65:
        # OOM hit — pod killed, restarts
        target.memory_working_set_bytes = int(target.memory_limit_bytes * 1.02)
        target.memory_oom_events += 1
        target.memory_failcnt += 1
        target.last_terminated_reason = "OOMKilled"
        state.add_event("oom_kill", target.pod_id, "error", "OOMKilling")

    else:
        # Node-level pressure -> evict other pods
        severity = (progress - 0.65) / 0.35
        state.node.memory_available_bytes = int(
            state.node.memory_total_bytes * max(0.02, 0.15 - severity * 0.13)
        )
        state.node.memory_pressure_waiting_rate = min(1.0, severity * 0.8)
        # Evict backend pods
        for pod in state.pods:
            if pod.service == "backend" and progress > 0.8:
                pod.phase = "Failed"
                pod.last_terminated_reason = "Evicted"
                state.add_event("eviction", pod.pod_id, "error",
                                "The node was low on resource: memory.available")
