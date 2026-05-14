"""
node_generator.py
Adds realistic drift to node-level raw metrics each tick.
"""
import numpy as np
from cluster_state import ClusterState


def _jitter(value: float, sigma_pct: float = 0.05, minimum: float = 0.0, maximum: float = float('inf')) -> float:
    noise = np.random.normal(0, abs(value + 1e-6) * sigma_pct)
    return float(np.clip(value + noise, minimum, maximum))


def tick_node(state: ClusterState) -> None:
    n = state.node

    # Aggregate CPU from pods
    total_cpu_used = sum(p.cpu_usage_millicores for p in state.pods if p.phase == "Running")
    total_cpu_capacity = 4000.0  # 4 cores = 4000m
    n.cpu_usage_percent = _jitter(
        min(99.9, (total_cpu_used / total_cpu_capacity) * 100),
        sigma_pct=0.04, minimum=0.0, maximum=99.9
    )
    n.cpu_load1 = _jitter(total_cpu_used / 1000.0, sigma_pct=0.08, minimum=0.0)

    # Aggregate memory from pods
    total_mem_used = sum(p.memory_working_set_bytes for p in state.pods if p.phase == "Running")
    n.memory_available_bytes = max(
        0, n.memory_total_bytes - int(_jitter(total_mem_used, sigma_pct=0.02, minimum=0))
    )
    avail_pct = n.memory_available_bytes / n.memory_total_bytes

    # PSI signals respond to resource pressure
    n.cpu_pressure_waiting_rate = _jitter(
        max(0.0, (n.cpu_usage_percent - 50) / 500),
        sigma_pct=0.1, minimum=0.0, maximum=1.0
    )
    n.cpu_sched_wait_ratio = _jitter(
        max(0.0, (n.cpu_usage_percent - 40) / 600),
        sigma_pct=0.1, minimum=0.0, maximum=1.0
    )
    n.memory_pressure_waiting_rate = _jitter(
        max(0.0, (0.2 - avail_pct) * 5),
        sigma_pct=0.15, minimum=0.0, maximum=1.0
    )

    # IO / storage — noisy baseline
    n.disk_io_weighted_rate = _jitter(n.disk_io_weighted_rate, sigma_pct=0.1, minimum=0.0, maximum=1.0)
    n.io_pressure_waiting_rate = _jitter(n.io_pressure_waiting_rate, sigma_pct=0.1, minimum=0.0, maximum=1.0)

    # Network — accumulate TCP counters
    new_out = int(np.random.poisson(10000))
    n.tcp_out_segs += new_out
    retrans_base = getattr(n, '_base_retrans_rate', 0.001)
    new_retrans = int(np.random.poisson(max(0, new_out * retrans_base)))
    n.tcp_retrans_segs += new_retrans
    n.tcp_syn_retrans_rate = _jitter(
        max(0.0, (retrans_base - 0.001) * 100),
        sigma_pct=0.2, minimum=0.0
    )
    n.conntrack_entries = int(_jitter(n.conntrack_entries, sigma_pct=0.05, minimum=100))

    # DNS — baseline very low latency
    n.dns_latency_p99_ms = int(_jitter(getattr(n, '_base_dns_latency', 5.0), sigma_pct=0.15, minimum=1))
    n.dns_servfail_rate = _jitter(getattr(n, '_base_dns_servfail', 0.0), sigma_pct=0.3, minimum=0.0)

    # Update node conditions based on pressure
    conditions = ["Ready"]
    if avail_pct < 0.1:
        conditions.append("MemoryPressure")
        state.add_event("node_condition", n.name, "warning", "NodeHasMemoryPressure")
    if n.disk_io_weighted_rate > 0.8:
        conditions.append("DiskPressure")
        state.add_event("node_condition", n.name, "warning", "NodeHasDiskPressure")
    n.conditions = conditions
