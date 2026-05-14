"""
grpc_degradation.py
Simulates: Network impairment -> TCP retransmits + DNS slowness -> gRPC timeouts

Causal chain:
  Ticks 0-5   : Baseline
  Ticks 5-12  : TCP retransmit rate rises (packet loss)
  Ticks 12-18 : DNS latency spikes (CoreDNS upstream slow)
  Ticks 18-25 : Service error rate rises, latency p99 blows up
  Ticks 25+   : Conntrack approaching limit
"""
from cluster_state import ClusterState


def apply(state: ClusterState, tick: int, total_ticks: int) -> None:
    progress = tick / max(1, total_ticks)
    n = state.node

    if progress < 0.2:
        n._base_retrans_rate = 0.001
        n._base_dns_latency = 5.0
        n._base_dns_servfail = 0.0

    elif progress < 0.5:
        # TCP retransmit rate rises: 0.1% -> 3%
        retrans = 0.001 + (progress - 0.2) / 0.3 * 0.029
        n._base_retrans_rate = retrans

    elif progress < 0.72:
        # DNS latency spikes: 5ms -> 500ms
        n._base_retrans_rate = 0.03
        dns_severity = (progress - 0.5) / 0.22
        n._base_dns_latency = 5.0 + dns_severity * 495.0
        n._base_dns_servfail = dns_severity * 2.0  # up to 2/s

    else:
        # Conntrack filling up + packet drops on all pods
        n._base_retrans_rate = 0.04
        n._base_dns_latency = 600.0
        n._base_dns_servfail = 3.0
        severity = (progress - 0.72) / 0.28
        n.conntrack_entries = int(n.conntrack_limit * (0.80 + severity * 0.18))
        # Network drops on pods
        for pod in state.pods:
            pod._net_drop_rate = severity * 50  # drops/s
