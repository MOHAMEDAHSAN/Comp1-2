# Component 1 ↔ Component 2: Handoff Checklist
## What Component 1 Must Deliver (Data Contract)

---

## 📋 WHAT COMPONENT 2 NEEDS FROM COMPONENT 1

This checklist defines the **contract** between components. Use this to validate that Component 1 is delivering what Component 2 needs.

### Tier 1: CRITICAL (Must Have for v1)

#### 1.1 Observation Schema
- [ ] Proto definition: `NormalizedObservation` message
- [ ] Proto definition: `PodMetrics` with CPU, memory, restart count
- [ ] Proto definition: `ServiceMetrics` with latency (p50, p99), error rate, QPS
- [ ] Proto definition: `NodeMetrics` with CPU, memory, disk usage
- [ ] Proto definition: `ClusterEvent` with type, timestamp, affected resource
- [ ] Proto definition: `CapabilityFlags` (which data sources available)

#### 1.2 Data Collection Coverage
- [ ] Kubernetes API: Pod topology (namespace, name, labels, restart count)
- [ ] Kubernetes API: Service topology (namespace, name, selector)
- [ ] Kubernetes API: Node information (name, resources)
- [ ] Kubernetes API: Events (pod restarts, scheduling, errors)
- [ ] Prometheus: CPU usage per pod (container_cpu_usage_seconds_total or equivalent)
- [ ] Prometheus: Memory usage per pod (container_memory_usage_bytes)
- [ ] Prometheus: Service latency (p50, p99) if available
- [ ] Prometheus: Request errors if available
- [ ] Kubelet: Pod state (running, pending, failed)
- [ ] Kubelet: Probe events (liveness, readiness, startup)
- [ ] Kubelet: Container restarts

#### 1.3 Data Normalization
- [ ] Custom metric names mapped to canonical names
- [ ] All metrics converted to standard units (bytes, seconds, percent)
- [ ] All timestamps in milliseconds since epoch
- [ ] Deduplication working (same event not sent twice in 30s window)
- [ ] Missing data handled gracefully (nulls, not errors)

#### 1.4 Capability Tracking
- [ ] Capability flags report: Kubernetes API available (Y/N)
- [ ] Capability flags report: Prometheus available (Y/N)
- [ ] Capability flags report: Kubelet metrics available (Y/N)
- [ ] Capability flags report: Logs available (Y/N)
- [ ] Capability flags report: Service mesh available (Y/N)
- [ ] Missing canonical metrics listed with degradation impact
- [ ] Notes explain "if X metric missing, Y playbook has reduced capability"

#### 1.5 Transport & Reliability
- [ ] Observations sent in batches (max 100 per batch)
- [ ] Batch send interval: max 30 seconds
- [ ] Secure transport: mTLS or HTTPS + auth token
- [ ] Tenancy isolation: tenant_id required in every observation
- [ ] Retry logic: exponential backoff for transient failures
- [ ] Local cache: queues observations if backend unreachable for >1 minute

#### 1.6 Performance & Scale
- [ ] Handles 500+ pods without CPU throttling
- [ ] Memory usage <500MB for 500 pods
- [ ] Data loss <5% under normal conditions
- [ ] Latency per collection cycle <30 seconds
- [ ] No memory leaks over 24-hour runtime

---

### Tier 2: RECOMMENDED (Nice to Have for v1)

#### 2.1 Enhanced Metrics
- [ ] Pod I/O metrics (if available from cgroup)
- [ ] Network metrics (bytes sent/received per pod)
- [ ] Storage metrics (PVC usage, I/O latency)
- [ ] Probe response times (latency in milliseconds)

#### 2.2 Log Integration
- [ ] Stream pod logs (last 100 lines for recent crashes)
- [ ] Parse OOM kill events from logs
- [ ] Parse crash/restart patterns from logs
- [ ] Extract error messages for context

#### 2.3 Service Mesh Integration (Optional)
- [ ] Istio: Request rate per service-to-service call
- [ ] Istio: Latency per call (p50, p95, p99)
- [ ] Linkerd: Similar metrics if available
- [ ] Failure on missing mesh (capability flag, not error)

---

### Tier 3: PREMIUM (v1.1 and Beyond)

#### 3.1 eBPF-based Observation
- [ ] TCP connection metrics (SYN/ACK times)
- [ ] Context switch rates per pod
- [ ] Advanced network diagnostics

#### 3.2 Multi-Cluster Support
- [ ] cluster_name field in observations
- [ ] Handling of multiple clusters in single stream

---

## 📊 DATA QUALITY REQUIREMENTS

### Accuracy
| Data | Tolerance |
|------|-----------|
| CPU usage | ±5% of actual (Prometheus scrape error inherent) |
| Memory usage | ±5% of actual |
| Latency (p99) | ±10% of actual |
| Restart count | Exact |
| Pod state | Exact |

### Completeness
| Metric | Availability |
|--------|--------------|
| Pod CPU + Memory | >95% pods, >95% time |
| Service latency | >80% services, >80% time (optional if no mesh) |
| Pod restart events | >99% (critical for Probe-Cascade playbook) |
| Node metrics | >90% nodes, >90% time |

### Freshness
| Data | Max Age |
|------|---------|
| Pod topology | <5 seconds (real-time from API) |
| Metrics (CPU, memory) | <60 seconds (Prometheus scrape interval) |
| Events (restarts) | <10 seconds (kubelet event watch) |
| Observations batch | <30 seconds (agent send interval) |

---

## 🧪 VALIDATION TESTS (Component 2 Will Run)

Component 2 will test Component 1 with these scenarios:

### Test 1: Basic Observation Structure
```python
def test_observation_schema():
    """Verify observation matches proto schema"""
    obs = receive_observation()
    assert obs.HasField("tenant_id")
    assert obs.HasField("timestamp_ms")
    assert len(obs.pod_metrics) > 0
    assert all(m.HasField("memory_usage_percent") for m in obs.pod_metrics)
```

### Test 2: Metric Ranges
```python
def test_metric_ranges():
    """Verify metrics are in expected ranges"""
    obs = receive_observation()
    for metric in obs.pod_metrics:
        assert 0 <= metric.cpu_usage_percent <= 100
        assert 0 <= metric.memory_usage_percent <= 100
        assert metric.restart_count >= 0
```

### Test 3: Capability Accuracy
```python
def test_capability_flags():
    """Verify capability flags match actual data"""
    obs = receive_observation()
    if obs.capability.has_kubernetes_api:
        assert len(obs.pod_metrics) > 0  # Should have pod data
    if obs.capability.has_prometheus:
        assert all(m.HasField("cpu_usage_percent") for m in obs.pod_metrics)
```

### Test 4: Tenancy Isolation
```python
def test_tenancy_isolation():
    """Verify each observation is properly scoped"""
    obs1 = receive_observation(tenant_id="tenant-a")
    obs2 = receive_observation(tenant_id="tenant-b")
    assert obs1.tenant_id == "tenant-a"
    assert obs2.tenant_id == "tenant-b"
    # Different tenants should never mix data
```

### Test 5: Time Series Continuity
```python
def test_time_series():
    """Verify observations arrive at predictable intervals"""
    observations = collect_observations(duration=5_minutes)
    timestamps = [o.timestamp_ms for o in observations]
    intervals = [timestamps[i+1] - timestamps[i] for i in range(len(timestamps)-1)]
    assert all(20000 <= interval <= 40000 for interval in intervals)  # ~30s ± 10s
```

### Test 6: Deduplication
```python
def test_deduplication():
    """Verify duplicate events are suppressed"""
    # Simulate pod restart event
    obs1 = receive_observation()  # Has restart
    obs2 = receive_observation()  # 2 seconds later, restart resolved
    obs3 = receive_observation()  # 30 seconds later, restart again (same pod)
    
    # First restart should appear in obs1
    # NOT appear in obs2 (within dedup window)
    # SHOULD appear in obs3 (outside dedup window)
```

---

## 📅 DELIVERY TIMELINE

| Week | Deliverable | Status |
|------|-------------|--------|
| 1 | Proto schema agreed | ⏳ Pending |
| 1-2 | K8s API + Prometheus scraping | ⏳ Pending |
| 2-3 | Schema normalization + capability tracking | ⏳ Pending |
| 3 | Integration test (mock Component 2) | ⏳ Pending |
| 4 | Helm chart deployment | ⏳ Pending |
| 4 | Live integration with Component 2 | ⏳ Pending |

---

## 🚨 COMMON FAILURE MODES (Avoid These)

### ❌ Proto Schema Not Agreed
**Problem**: Component 1 sends data, Component 2 can't parse it  
**Solution**: Lock down proto schema in Week 1; use versioning if changes needed

### ❌ Missing Capability Flags
**Problem**: Component 2 tries to use metrics that aren't available  
**Solution**: Always report what data sources are available

### ❌ Inconsistent Timestamps
**Problem**: Baselines calculated with wrong time windows  
**Solution**: All timestamps in milliseconds since epoch; validate in Week 1

### ❌ Deduplication Too Aggressive
**Problem**: Same event misses in obs #2 but Component 2 didn't see #1  
**Solution**: Conservative dedup window (30s); events outside window always sent

### ❌ Tenancy Not Isolated
**Problem**: Customer A sees Customer B's data  
**Solution**: tenant_id required in EVERY observation; validate in Week 1 tests

### ❌ High Latency Observations
**Problem**: By the time observation arrives, data is stale and useless for detection  
**Solution**: Max 30s send interval; aggressively batch to keep fresh

---

## ✅ HANDOFF ACCEPTANCE CRITERIA

Component 1 is **ready for Component 2** when:

- [ ] Proto schema finalized and approved by both teams
- [ ] Component 1 successfully sends 1000+ observations
- [ ] All validation tests pass (6 tests above)
- [ ] Capability flags accurately reflect reality
- [ ] Zero data loss over 1-hour test
- [ ] <5% CPU overhead on 500-pod cluster
- [ ] <500MB memory overhead
- [ ] Helm chart deploys reliably
- [ ] Component 2 can use observations without modifications
- [ ] Documentation complete (proto, data flow, deployment)

---

## 📞 HANDOFF MEETING CHECKLIST

Before Component 2 team takes over:

- [ ] **Walk through proto schema** (10 min)
  - Each field explained
  - Why each field is included
  - Any optional fields

- [ ] **Demo the data flow** (15 min)
  - Component 1 running
  - Show observations being generated
  - Show observations reaching backend (Component 2)

- [ ] **Review capability flags** (10 min)
  - What each flag means
  - What to do if a flag is false
  - How degradation impacts Component 2

- [ ] **Discuss failure scenarios** (15 min)
  - What happens if Prometheus down?
  - What happens if K8s API unreachable?
  - How does Component 2 handle partial observations?

- [ ] **Q&A** (15 min)
  - Any data fields Component 2 needs that Component 1 can add?
  - Any observations Component 2 finds problematic?

---

## 📋 FOR COMPONENT 2 TEAM (Template Response)

When your teammate provides requirements, fill this out:

```
COMPONENT 2 REQUIREMENTS FORM:

Playbook: [name]
Required Metrics:
  [ ] [metric_name] - source: [K8s API / Prometheus / Kubelet / Logs]
  [ ] [metric_name] - source: [...]

Baseline Granularity:
  - Per pod? Per node? Per service? Per namespace?

Detection Precision:
  - False positive tolerance: X%
  - False negative tolerance: Y%

Data Freshness:
  - Max acceptable data age: X seconds

Scaling:
  - Needs to support X pods
  - Needs to support X services

Optional:
  - Any metrics Component 1 should prioritize?
  - Any edge cases we should handle?
```

---

## 🎯 NEXT STEPS

1. **This week**: Share this checklist with Component 2 team
2. **This week**: Lock down proto schema
3. **Week 1**: Start Component 1 implementation (begin with proto + data models)
4. **Week 1**: Await Component 2 requirements form
5. **Week 2-3**: Build Component 1 with requirements from Component 2
6. **Week 4**: Integration test + handoff meeting

