# Playbook Specification Guide
## Component 2 - Statistical Forecasting Engine

---

## Overview

Playbooks are the **bridge between statistical detection and qualitative reasoning**. Each playbook:
- Defines which metrics matter for a failure mode
- Specifies how to detect anomalies in those metrics
- Produces events that the reasoning layer interprets
- Links to pattern library entries for domain knowledge

Each playbook is **self-contained and independently calibrated**, making them easy to develop, test, and extend.

---

## Playbook 1: Probe-Cascade Pattern Detection

### Problem Statement
Kubernetes probes (liveness, readiness) are used to detect and restart unhealthy pods. When memory pressure increases, probe latency increases and probes start timing out, causing kubelet to kill the pod. This cascades: dead pod → other pods try to take over → more memory pressure → more probe failures → more kills.

### Failure Mode Signature
```
Timeline:
T+0:   Cluster memory usage begins climbing
T+30:  Probe latency (p99) spikes above baseline
T+45:  Probe timeout events begin (logs: "failed to get status")
T+60:  Pod restarts begin (logs: "container kill", "probe failed")
T+90:  Pattern resolves (memory released or pod gets killed/scheduled elsewhere)

Duration: 30-120 seconds
Blast radius: Typically 1-5 pods in the same namespace/workload
```

### Selected Variables

| Variable | Type | Source | Why Matters |
|----------|------|--------|------------|
| `memory_usage_percent` | Metric | Pod metrics | Root cause; memory pressure is the trigger |
| `probe_latency_p99_ms` | Metric | Kubelet events + latency tracking | Probe slowdown is early indicator |
| `probe_timeout_count` | Event count | Kubelet logs | Probes are actually failing |
| `pod_restart_rate` | Metric | Pod events | Cascade symptom; restarts are the outcome |
| `container_oom_kill_count` | Event count | Kubelet events | Terminal event; pod was killed by memory |

### Detection Algorithm

```python
class ProbePlaybookDetector:
    def evaluate(self, metrics, baselines, pattern_library):
        """
        Cascade detection with confidence scoring.
        """
        confidence = 0.0
        evidence = []
        
        # Signal 1: Memory baseline violation
        memory_z_score = (metrics.memory_usage - baselines.memory_mean) / baselines.memory_stddev
        if memory_z_score > 2.5:
            confidence += 0.3
            evidence.append(f"Memory pressure: {memory_z_score:.2f}σ above baseline")
        
        # Signal 2: Probe latency spike
        probe_latency_z = (metrics.probe_latency_p99 - baselines.probe_latency_mean) / baselines.probe_latency_stddev
        if probe_latency_z > 3.0:
            confidence += 0.2
            evidence.append(f"Probe latency spike: {probe_latency_z:.2f}σ above baseline")
        
        # Signal 3: Probe timeouts occurring
        if metrics.probe_timeout_count > 0 and memory_z_score > 2.0:
            confidence += 0.2
            evidence.append(f"Probe timeouts detected: {metrics.probe_timeout_count} in last minute")
        
        # Signal 4: Pod restart correlation
        if metrics.pod_restart_rate > baselines.pod_restart_baseline and memory_z_score > 1.5:
            confidence += 0.2
            evidence.append(f"Pod restart rate: {metrics.pod_restart_rate:.2f} /min (baseline: {baselines.pod_restart_baseline:.2f})")
        
        # Signal 5: Terminal OOM kill
        if metrics.container_oom_kill_count > 0:
            confidence += 0.1  # Confirmation signal
            evidence.append(f"OOM kill detected: {metrics.container_oom_kill_count} instances")
        
        # Temporal correlation: Memory spike followed by latency/restarts?
        if self._check_cascade_sequence(metrics.history):
            confidence = min(1.0, confidence * 1.2)  # 20% boost for detected sequence
            evidence.append("Cascade sequence detected: memory → latency → restarts")
        
        return PlaybookFiringEvent(
            playbook_id="probe-cascade",
            confidence=min(confidence, 1.0),
            selected_variable_values={
                "memory_z_score": memory_z_score,
                "probe_latency_z": probe_latency_z,
                "probe_timeouts": metrics.probe_timeout_count,
                "restart_rate": metrics.pod_restart_rate,
            },
            reason=" | ".join(evidence)
        )
```

### Confidence Scoring

```
All 5 signals present (in sequence):      0.90 - 1.00
4 signals + sequence:                     0.75 - 0.89
3 signals + sequence:                     0.60 - 0.74
3 signals:                                0.50 - 0.59
2 signals:                                0.35 - 0.49
1 strong signal:                          0.20 - 0.34
No signals:                               0.00 - 0.19
```

### Pattern Library Integration

From the pattern library, this playbook references:
- **Probe-cascade sequence template**: Canonical timing (memory spike → latency spike → timeouts → restarts)
- **Memory pressure discriminator**: How to distinguish memory pressure from other latency causes
- **Cascade halt conditions**: What stops the cascade (pod killed, memory released, probe disabled)

### Recommended Operator Action

```json
{
  "headline": "Probe cascade detected: pod health checks failing due to memory pressure",
  "actions": [
    {
      "priority": "immediate",
      "action": "Increase pod memory limits by 20-30%",
      "reasoning": "Memory pressure is root cause; increasing limits can reduce probe timeout risk"
    },
    {
      "priority": "secondary",
      "action": "Reduce probe frequency or increase timeout thresholds",
      "reasoning": "Gives memory pressure more time to resolve between probes"
    },
    {
      "priority": "investigation",
      "action": "Check for memory leaks in the application",
      "reasoning": "If memory grows monotonically, the pod may have a leak rather than transient pressure"
    }
  ]
}
```

### Testing Strategy

**Unit test data**:
```yaml
Test Case 1: Classic probe cascade
  memory_usage: 92% (baseline 40%)
  probe_latency_p99: 4500ms (baseline 50ms)
  probe_timeouts: 5 in last minute
  pod_restarts: 3 in last 2 minutes
  container_oom_kills: 1
  expected_confidence: 0.92

Test Case 2: Memory spike but no probe issues
  memory_usage: 88% (baseline 40%)
  probe_latency_p99: 65ms (baseline 50ms)  # Normal
  probe_timeouts: 0
  pod_restarts: 0
  container_oom_kills: 0
  expected_confidence: 0.25

Test Case 3: Temporary memory blip
  memory_usage: 75% (baseline 40%)  # 1.75σ, below threshold
  probe_latency_p99: 120ms (baseline 50ms)
  probe_timeouts: 0
  pod_restarts: 0
  container_oom_kills: 0
  expected_confidence: 0.05
```

---

## Playbook 2: CPU Contention with Workload Coupling

### Problem Statement
On shared infrastructure, multiple workloads compete for CPU. When one workload spikes, it starves others. Unlike memory (which is largely independent), CPU is a **shared resource where one pod's consumption directly reduces another's availability**. This causes latency spikes, request timeouts, and cascading failures.

### Failure Mode Signature
```
Timeline:
T+0:   One workload's CPU usage spikes to 100%
T+5:   Other pods on the same node see reduced CPU available
T+10:  Latency metrics on affected services spike (p99 latency 10x+)
T+20:  Request timeout rate increases
T+30+: Pattern persists until spike workload completes or is throttled

Duration: 10 seconds - 10 minutes
Blast radius: All pods on the same node / core
```

### Selected Variables

| Variable | Type | Source |
|----------|------|--------|
| `cpu_usage_percent` | Metric | Pod cgroup metrics |
| `cpu_throttle_time_ms` | Metric | cgroup CPU accounting |
| `request_latency_p99_ms` | Metric | Service mesh or app-level |
| `request_timeout_rate` | Metric | App logs or service mesh |
| `context_switches_per_sec` | Metric | eBPF or /proc/stat (premium) |

### Detection Algorithm

```python
class CPUContentionDetector:
    def evaluate(self, metrics, baselines, topology):
        """
        Detect CPU contention by correlating high CPU usage with
        latency increases on co-located pods.
        """
        confidence = 0.0
        evidence = []
        
        # Signal 1: CPU spike on this pod
        cpu_z_score = (metrics.cpu_usage - baselines.cpu_mean) / baselines.cpu_stddev
        if cpu_z_score > 2.0:
            confidence += 0.25
            evidence.append(f"CPU spike: {cpu_z_score:.2f}σ above baseline")
        
        # Signal 2: CPU throttling occurring
        if metrics.cpu_throttle_time > baselines.cpu_throttle_baseline:
            throttle_increase = metrics.cpu_throttle_time / baselines.cpu_throttle_baseline
            if throttle_increase > 5.0:  # 5x increase
                confidence += 0.25
                evidence.append(f"CPU throttling: {throttle_increase:.1f}x increase")
        
        # Signal 3: Latency impact on co-located pods
        co_located_pods = self._find_co_located_pods(metrics.pod_id, topology)
        latency_impacts = 0
        for pod in co_located_pods:
            pod_latency_z = (metrics.pod_latencies[pod] - baselines.latencies[pod].mean) / baselines.latencies[pod].stddev
            if pod_latency_z > 2.5:
                latency_impacts += 1
        
        if latency_impacts > 0:
            confidence += 0.25
            evidence.append(f"Latency spike on {latency_impacts} co-located pods")
        
        # Signal 4: Request timeout increase correlated with CPU
        if metrics.timeout_rate > baselines.timeout_baseline and cpu_z_score > 1.5:
            timeout_increase = metrics.timeout_rate / baselines.timeout_baseline
            confidence += 0.25
            evidence.append(f"Timeout rate: {timeout_increase:.1f}x baseline")
        
        return PlaybookFiringEvent(
            playbook_id="cpu-contention",
            confidence=min(confidence, 1.0),
            affected_pods=co_located_pods,
            reason=" | ".join(evidence)
        )
```

### Confidence Scoring

```
CPU spike (>2σ) + throttling (>5x) + latencies spike + timeouts:    0.85 - 1.00
3 of above + correlated timing:                                      0.70 - 0.84
CPU spike + either throttling or latency spike:                      0.50 - 0.69
CPU spike alone:                                                     0.20 - 0.49
```

### Recommended Operator Action

```json
{
  "headline": "CPU contention: This pod's CPU spike is impacting co-located workloads",
  "actions": [
    {
      "priority": "immediate",
      "action": "Set CPU limits on the spiking workload",
      "reasoning": "Prevents this workload from consuming all shared CPU"
    },
    {
      "priority": "secondary",
      "action": "Increase node CPU capacity or move workloads to separate nodes",
      "reasoning": "If contention is structural, may need resource expansion"
    }
  ]
}
```

---

## Playbook 3: OOM Cascade

### Problem Statement
When a pod hits Out-Of-Memory condition, the kubelet kills it. If the workload restarts quickly and repeats the memory leak, it can cascade: one pod restarts → other replicas handle traffic → they hit memory limits too → they also restart → traffic concentrates → crash loop.

### Selected Variables

| Variable | Type |
|----------|------|
| `memory_usage_percent` | Metric |
| `memory_resident_set_size_mb` | Metric |
| `oom_kill_count` | Event count |
| `pod_restart_rate` | Metric |
| `available_memory_on_node_mb` | Metric |

### Detection Algorithm

```python
# Detect OOM restart cycle: repeated memory growth → kill → restart
if metrics.oom_kill_count > 0 and metrics.pod_restart_rate > baseline.restart_rate:
    # Check if memory grows back to limits post-restart
    if metrics.memory_rss > 0.9 * metrics.memory_limit:
        confidence = 0.85  # Classic OOM leak pattern
```

---

## Playbook 4: gRPC Degradation Under Network Impairment

### Problem Statement
gRPC uses HTTP/2 connection multiplexing. When network latency or loss increases, gRPC connection setup time increases, and multiplexed streams compete for limited bandwidth. This causes request latency to spike even though the backend pods are healthy.

### Selected Variables

| Variable | Type |
|----------|------|
| `network_latency_p99_ms` | Metric |
| `packet_loss_percent` | Metric |
| `grpc_request_latency_p99_ms` | Metric |
| `grpc_error_rate` | Metric |
| `connection_pool_depth` | Metric |

### Detection Algorithm

```python
# Detect gRPC degradation: network latency spike correlated with gRPC latency spike
if network_latency_z > 2.0 and grpc_latency_z > 3.0:
    confidence = 0.80  # Network issue is affecting gRPC
```

---

## Playbook 5: Storage Queue Saturation

### Problem Statement
PVCs are bounded storage resources. When a pod's writes outpace the storage backend's throughput, the write queue saturates. This causes:
- Write latency to increase (requests block waiting for I/O)
- Storage utilization to hit 100%
- Other pods using the same PVC to also block

### Selected Variables

| Variable | Type |
|----------|------|
| `pvc_usage_percent` | Metric |
| `storage_io_latency_p99_ms` | Metric |
| `write_queue_depth` | Metric |
| `disk_utilization_percent` | Metric |
| `pod_io_wait_percent` | Metric |

### Detection Algorithm

```python
# Detect storage saturation: queue depth high + latency elevated + utilization near 100%
if (write_queue_z > 2.5 and storage_latency_z > 2.0 and disk_util > 95):
    confidence = 0.80  # Classic storage bottleneck
```

---

## Calibration Process

### Baseline Establishment (Day 0-7)

1. **Collection**: Run in observation-only mode for 24-48 hours, collecting metrics
2. **Window creation**: Create multiple 6-hour baseline windows
3. **Pooled-σ computation**: For each metric, compute pooled standard deviation across windows
4. **Drift detection**: Monitor for metric drift during warmup period
5. **False positive tuning**: Run against synthetic test data; adjust thresholds

### Per-Customer Calibration (Week 1-4)

1. **Online warmup**: Collect 7 days of real customer data
2. **Baseline refinement**: Recompute baselines with customer-specific data
3. **Threshold adjustment**: Fine-tune playbook thresholds based on customer's normal operating patterns
4. **Manual incident review**: If any false positives, adjust algorithm parameters

### Ongoing Tuning (Month 1+)

1. **Drift monitoring**: Track if baselines are drifting (cluster growing, workload characteristics changing)
2. **False positive analysis**: Review any misfired playbooks; adjust if systematic
3. **Missed detection analysis**: Review if any incidents happened that playbooks should have caught
4. **Operator feedback**: Incorporate tuning requests from operators

---

## Implementation Checklist

- [ ] **Proto schema** for `PlaybookFiringEvent`, `BaselineData`, `PlaybookConfig`
- [ ] **Baseline store schema** (metric baselines, per-customer)
- [ ] **Pooled-σ algorithm** implementation
- [ ] **Probe-cascade detector** implementation + test cases
- [ ] **CPU contention detector** + test cases
- [ ] **OOM cascade detector** + test cases
- [ ] **gRPC degradation detector** + test cases
- [ ] **Storage queue detector** + test cases
- [ ] **Confidence scorer** (aggregation logic)
- [ ] **Event emitter** (to Component 3)
- [ ] **Admin API** for playbook enable/disable, threshold tuning
- [ ] **Dashboard** for baseline inspection, detector status

---

## References

- High-level design: Section 8 (Failure-Mode Playbooks)
- Pattern library: Architecture/Low_Level/3. Knowledge Graph & Multi-Agent Reasoning/
- Test data: Pre-experimentation/k8s-spike/trials_*/

