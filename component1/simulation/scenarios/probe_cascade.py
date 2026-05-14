"""
probe_cascade.py
Simulates: Memory pressure -> probe latency spike -> consecutive failures -> restart loop

Causal chain (time-ordered):
  Ticks 0-5   : Baseline — everything healthy
  Ticks 5-10  : Memory creeps up (pod working_set approaches limit)
  Ticks 10-15 : Probe latency rises (app slows under memory pressure)
  Ticks 15-20 : Consecutive probe failures start -> kubelet restarts pod
  Ticks 20+   : CrashLoopBackOff if memory not fixed
"""
from cluster_state import ClusterState


def apply(state: ClusterState, tick: int, total_ticks: int) -> None:
    progress = tick / max(1, total_ticks)  # 0.0 -> 1.0

    # Target the frontend pods (first 3 pods)
    target_pods = [p for p in state.pods if p.service == "frontend"]

    for pod in target_pods:
        if progress < 0.2:
            # Phase 1: healthy
            pod._fault_intensity = 0.0

        elif progress < 0.5:
            # Phase 2: memory creeps up toward limit (80% -> 98%)
            mem_pct = 0.80 + (progress - 0.2) / 0.3 * 0.18
            pod.memory_working_set_bytes = int(pod.memory_limit_bytes * mem_pct)

        elif progress < 0.75:
            # Phase 3: probe latency spikes due to memory pressure
            # (memory at ~96%, probe timeout at 2000ms)
            pod.memory_working_set_bytes = int(pod.memory_limit_bytes * 0.97)
            latency_ramp = (progress - 0.5) / 0.25  # 0->1
            pod.probe_latency_ms = int(300 + latency_ramp * 1800)  # 300ms -> 2100ms

        else:
            # Phase 4: probe fails -> restarts -> crash loop
            pod.memory_working_set_bytes = int(pod.memory_limit_bytes * 0.99)
            pod.probe_latency_ms = 2500  # over threshold -> probe fails
            pod.last_terminated_reason = "OOMKilled"
