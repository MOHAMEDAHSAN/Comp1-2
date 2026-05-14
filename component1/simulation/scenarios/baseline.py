"""
baseline.py  — Normal healthy cluster operation.
No faults injected. Used for the calibration phase.
"""
from cluster_state import ClusterState


def apply(state: ClusterState, tick: int, total_ticks: int) -> None:
    """Reset all fault intensities to 0 (healthy baseline)."""
    for pod in state.pods:
        pod._fault_intensity = 0.0
        pod._net_drop_rate = 0.0
    node = state.node
    node._base_retrans_rate = 0.001
    node._base_dns_latency = 5.0
    node._base_dns_servfail = 0.0
    node.disk_io_weighted_rate = 0.05
    node.io_pressure_waiting_rate = 0.01
