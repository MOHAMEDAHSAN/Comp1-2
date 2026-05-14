"""
storage_saturation.py
Simulates: Heavy I/O -> disk queue fills -> PSI io_waiting -> pod hangs

Causal chain:
  Ticks 0-5   : Baseline
  Ticks 5-12  : Disk IO weighted rate rises
  Ticks 12-18 : PSI io_waiting rises — other pods affected
  Ticks 18-24 : PVC fills up, CSI attach latency spikes
  Ticks 24+   : Pods hang on write() -> probe timeouts
"""
from cluster_state import ClusterState


def apply(state: ClusterState, tick: int, total_ticks: int) -> None:
    progress = tick / max(1, total_ticks)
    n = state.node

    if progress < 0.2:
        n.disk_io_weighted_rate = 0.05
        n.io_pressure_waiting_rate = 0.01

    elif progress < 0.5:
        # IO weighted rate rises: 5% -> 80%
        io_rate = 0.05 + (progress - 0.2) / 0.3 * 0.75
        n.disk_io_weighted_rate = min(1.0, io_rate)

    elif progress < 0.72:
        # PSI io_waiting rises: 1% -> 40%
        n.disk_io_weighted_rate = 0.85
        psi = 0.01 + (progress - 0.5) / 0.22 * 0.39
        n.io_pressure_waiting_rate = min(1.0, psi)

    else:
        # PVC fills up + CSI latency spikes + pod probe hangs
        severity = (progress - 0.72) / 0.28
        n.disk_io_weighted_rate = 0.95
        n.io_pressure_waiting_rate = min(1.0, 0.40 + severity * 0.55)
        n.csi_attach_latency_ms = int(200 + severity * 59800)  # up to 60s

        # PVC used_bytes fills up
        for pvc in state.pvcs:
            pvc_pod = next((p for p in state.pods if p.service in pvc.pvc_id), None)
            if pvc_pod:
                pvc_pod.storage_used_bytes = int(
                    pvc_pod.storage_capacity_bytes * min(0.99, 0.50 + severity * 0.49)
                )

        # Probe hangs on pods doing I/O
        for pod in state.pods:
            pod.probe_latency_ms = int(pod.probe_latency_ms * (1 + severity * 4))

        # Emit storage events
        state.add_event("storage_error", n.name, "error", "FailedMount")
