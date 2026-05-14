# Component 1 & 2: Development Roadmap & Working Plan
## 8-Week Implementation Schedule

---

## 📅 PROJECT TIMELINE

```
Week 1 (May 12-18):   Component 1 Foundation
Week 2 (May 19-25):   Component 1 Multi-Source Collection
Week 3 (May 26-Jun 1): Component 1 Normalization & Testing
Week 4 (Jun 2-8):     Component 1 Deployment & Integration
Week 5 (Jun 9-15):    Component 2 Foundation & Baseline Engine
Week 6 (Jun 16-22):   Component 2 Detection Algorithms & Playbooks
Week 7 (Jun 23-29):   Component 2 Calibration & Admin API
Week 8 (Jun 30-Jul 6): Integration, Testing & Documentation
```

---

## WEEK 1: Component 1 Foundation

### Goals
- Define canonical schema (proto files)
- Build Kubernetes API client wrapper
- Implement basic topology discovery
- Set up project structure and CI/CD

### Deliverables

#### 1.1 Canonical Schema Definition (2 days)
**File**: `proto/observability.proto`

```protobuf
syntax = "proto3";

package kubernetes_agent.observability;

message PodMetrics {
  string pod_id = 1;                    // namespace/pod-name
  string namespace = 2;
  int64 timestamp_ms = 3;
  
  ResourceMetrics cpu = 4;
  ResourceMetrics memory = 5;
  ResourceMetrics storage = 6;
  
  repeated ProbeMetric probes = 7;
  int32 restart_count = 8;
}

message ResourceMetrics {
  double usage_percent = 1;
  double limit_bytes = 2;
  double request_bytes = 3;
  double usage_bytes = 4;
}

message ProbeMetric {
  string probe_type = 1;  // liveness, readiness, startup
  int32 latency_ms = 2;
  bool last_probe_succeeded = 3;
}

message ServiceMetrics {
  string service_id = 1;  // namespace/service-name
  double qps = 2;
  double latency_p50_ms = 3;
  double latency_p99_ms = 4;
  double error_rate = 5;
}

message NodeMetrics {
  string node_name = 1;
  double cpu_usage_percent = 2;
  double memory_usage_percent = 3;
  double disk_usage_percent = 4;
  int32 pod_count = 5;
}

message ClusterEvent {
  int64 timestamp_ms = 1;
  string event_type = 2;  // deploy, scale, config_change, pod_restart, etc.
  string affected_resource = 3;
  map<string, string> metadata = 4;
}

message NormalizedObservation {
  string tenant_id = 1;
  int64 timestamp_ms = 2;
  string cluster_name = 3;
  
  repeated PodMetrics pod_metrics = 4;
  repeated ServiceMetrics service_metrics = 5;
  repeated NodeMetrics node_metrics = 6;
  repeated ClusterEvent events = 7;
  
  CapabilityFlags capability = 8;
}

message CapabilityFlags {
  bool has_kubernetes_api = 1;
  bool has_prometheus = 2;
  bool has_kubelet_metrics = 3;
  bool has_logs = 4;
  bool has_service_mesh = 5;
  
  repeated string missing_canonical_metrics = 6;
  repeated string capability_notes = 7;
}
```

**Checklist**:
- [ ] Define all entity types (Pod, Service, Node, Event, Metrics)
- [ ] Define relationships (calls, mounts, probes)
- [ ] Define capability tracking
- [ ] Generate Go/Python bindings from proto
- [ ] Add versioning strategy

#### 1.2 K8s Client Wrapper (2 days)
**File**: `cmd/agent/sources/kubernetes_source.go`

```go
type KubernetesSource interface {
    GetPods(ctx context.Context, namespace string) ([]Pod, error)
    GetServices(ctx context.Context) ([]Service, error)
    GetNodes(ctx context.Context) ([]Node, error)
    WatchEvents(ctx context.Context) (<-chan ClusterEvent, error)
}

type kubernetesSourceImpl struct {
    clientset *kubernetes.Clientset
    informer  *informers.SharedInformerFactory
}
```

**Checklist**:
- [ ] Initialize K8s client (in-cluster config)
- [ ] List pods, services, nodes
- [ ] Watch for events (informer pattern)
- [ ] Handle RBAC permissions
- [ ] Add retry/timeout logic

#### 1.3 Topology Discovery (2 days)
**File**: `cmd/agent/discovery/topology.go`

Build a topology model:
```go
type Topology struct {
    Pods     map[string]*Pod
    Services map[string]*Service
    Nodes    map[string]*Node
    Edges    map[string]*Edge  // pod-pod calls, pod-pvc mounts, etc.
}
```

**Checklist**:
- [ ] Discover pod-service bindings (via labels)
- [ ] Discover pod-pod calls (via service DNS)
- [ ] Discover pod-pvc mounts (via volumeMounts)
- [ ] Discover pod-node assignments
- [ ] Emit topology change events

#### 1.4 Project Structure & CI/CD (1 day)
**Files**:
- `go.mod`, `go.sum` (Go dependencies)
- `Dockerfile` (agent container)
- `.github/workflows/build.yml` (GitHub Actions CI)
- `charts/kubernetes-agent/` (Helm chart scaffold)

**Checklist**:
- [ ] Go module initialized with dependencies
- [ ] Docker build working
- [ ] GitHub Actions CI passing
- [ ] Helm chart template created

**Dependencies to add**:
```go
require (
    k8s.io/client-go v0.28.0
    k8s.io/api v0.28.0
    google.golang.org/protobuf v1.31.0
    google.golang.org/grpc v1.59.0
)
```

### Success Criteria
- ✅ Proto schema compiles and generates code
- ✅ K8s client successfully connects to test cluster
- ✅ Topology discovery script runs and prints discovered pods/services
- ✅ CI/CD pipeline builds and tests on every commit

### Files Created
```
proto/
  observability.proto
cmd/agent/
  main.go
  sources/
    kubernetes_source.go
  discovery/
    topology.go
  config/
    config.go
go.mod
go.sum
Dockerfile
.github/workflows/
  build.yml
charts/kubernetes-agent/
  Chart.yaml
  values.yaml
  templates/daemonset.yaml
  templates/deployment.yaml
```

---

## WEEK 2: Component 1 Multi-Source Collection

### Goals
- Implement Prometheus scraper
- Implement Kubelet metrics adapter
- Implement log stream collection
- Build multi-source orchestration

### Deliverables

#### 2.1 Prometheus Adapter (2 days)
**File**: `cmd/agent/sources/prometheus_source.go`

```go
type PrometheusSource interface {
    QueryMetric(ctx context.Context, query string) (float64, error)
    QueryRangeMetric(ctx context.Context, query string, duration time.Duration) ([]float64, error)
    WatchMetrics(ctx context.Context) (<-chan MetricUpdate, error)
}

// Example queries
const (
    PodCPUUsageQuery = `rate(container_cpu_usage_seconds_total{pod!=""}[1m])`
    PodMemoryUsageQuery = `container_memory_usage_bytes{pod!=""}`
)
```

**Implementation**:
- Prometheus HTTP API client
- Query builder with pod/node labels
- Metric caching (5-minute TTL)
- Error handling (unreachable Prometheus)

**Checklist**:
- [ ] Prometheus client library integrated
- [ ] Query templates defined for key metrics
- [ ] Scrape interval configurable (default 30s)
- [ ] Caching prevents query storms
- [ ] Graceful degradation if Prometheus unavailable

#### 2.2 Kubelet Metrics Adapter (2 days)
**File**: `cmd/agent/sources/kubelet_source.go`

```go
type KubeletSource interface {
    GetNodeMetrics(ctx context.Context) (*NodeMetrics, error)
    GetPodMetrics(ctx context.Context) ([]PodMetrics, error)
    WatchPodEvents(ctx context.Context) (<-chan PodEvent, error)
}
```

**Implementation**:
- Direct kubelet API access (port 10250, requires client cert)
- Pod resource metrics
- Node-level metrics
- Watch pod lifecycle events

**Checklist**:
- [ ] Kubelet API authentication (client cert)
- [ ] Pod metrics endpoint scraping
- [ ] Node metrics collection
- [ ] Pod event streaming
- [ ] Fallback to metrics-server if kubelet unavailable

#### 2.3 Log Stream Adapter (1 day)
**File**: `cmd/agent/sources/log_source.go`

```go
type LogSource interface {
    TailLogs(ctx context.Context, pod string, options TailOptions) (<-chan LogEntry, error)
}

// Support multiple backends
type LogBackend interface {
    Tail(ctx context.Context, selector string) (<-chan LogEntry, error)
}

// Implementations: Loki, Fluent Bit HTTP, ELK
```

**Checklist**:
- [ ] Loki HTTP API client
- [ ] Fluent Bit HTTP plugin
- [ ] Selector syntax (namespace, pod name, labels)
- [ ] Streaming architecture (don't load all logs into memory)

#### 2.4 Multi-Source Orchestration (1 day)
**File**: `cmd/agent/sources/orchestrator.go`

```go
type SourceOrchestrator struct {
    k8s        KubernetesSource
    prometheus PrometheusSource
    kubelet    KubeletSource
    logs       LogSource
}

func (o *SourceOrchestrator) CollectObservations(ctx context.Context) (*proto.NormalizedObservation, error) {
    // Parallel collection from all sources
    // Merge results
    // Handle partial failures
}
```

**Checklist**:
- [ ] Parallel scraping from all sources (prevent blocking)
- [ ] Timeout handling (max 30s per full collection cycle)
- [ ] Partial failure graceful degradation
- [ ] Metrics: scrape latency per source, success rate

### Success Criteria
- ✅ Prometheus queries return expected metrics for test cluster
- ✅ Kubelet metrics successfully scraped
- ✅ Log tail works and shows expected pod logs
- ✅ Multi-source orchestrator collects from all sources in <30s

### Files Created
```
cmd/agent/sources/
  prometheus_source.go
  kubelet_source.go
  log_source.go
  orchestrator.go
cmd/agent/
  scrapers.go
```

---

## WEEK 3: Component 1 Normalization & Testing

### Goals
- Implement schema normalizer
- Implement capability detection
- Build deduplicator
- Create end-to-end test

### Deliverables

#### 3.1 Schema Normalizer (2 days)
**File**: `cmd/agent/normalizer/schema_normalizer.go`

```go
type SchemaNormalizer interface {
    Normalize(raw interface{}, source SourceType) (*proto.PodMetrics, error)
}

type MetricMapper struct {
    // Map custom metric names to canonical names
    // Prometheus: "container_cpu_usage_seconds_total" -> "cpu"
    mappings map[string]string
    
    // Track missing canonical metrics
    missingMetrics map[string]bool
}

func (m *MetricMapper) Map(prometheusMetricName string) (string, bool) {
    // Returns (canonical_name, found)
}
```

**Implementation**:
- Prometheus metric name → canonical conversion
- Kubelet metric extraction and conversion
- Log pattern extraction (OOM, crash, error patterns)
- Custom metric name registration

**Checklist**:
- [ ] Prometheus metrics mapped to canonical names
- [ ] Kubelet metrics extracted and normalized
- [ ] Log entries parsed for key patterns
- [ ] Missing metric detection
- [ ] 95%+ data preservation

#### 3.2 Capability Detection (1 day)
**File**: `cmd/agent/discovery/capability_detector.go`

```go
type CapabilityDetector struct {
    canonicalMetrics map[string]bool
    sources          map[SourceType]bool
}

func (c *CapabilityDetector) GetCapabilityFlags() *proto.CapabilityFlags {
    // Returns: which sources are available, which canonical metrics are available
    // Sets degradation notes if critical metrics missing
}
```

**Checklist**:
- [ ] Detect available data sources
- [ ] Map available metrics to canonical schema
- [ ] Identify missing critical metrics
- [ ] Generate capability degradation notes
- [ ] Log capability report at startup

#### 3.3 Deduplicator (1 day)
**File**: `cmd/agent/normalizer/deduplicator.go`

```go
type Deduplicator struct {
    // Track recently seen events/metrics to avoid duplicates
    recentEvents map[string]time.Time
    recentMetrics map[string]time.Time
}

func (d *Deduplicator) IsDuplicate(event interface{}) bool {
    // Compute hash of event, check if seen recently
}
```

**Checklist**:
- [ ] Deduplicator reduces duplicate events by 90%+
- [ ] Sliding window cleanup (forget events >5min old)
- [ ] Metric deduplication on pod basis

#### 3.4 End-to-End Test (1 day)
**File**: `test/e2e_test.go`

```go
func TestE2EObservationCollection(t *testing.T) {
    // Spin up test K8s cluster (minikube/kind)
    // Deploy test workloads
    // Run agent
    // Verify observations collected and normalized
    // Verify capability flags set correctly
}
```

**Checklist**:
- [ ] Test setup: kind or minikube cluster
- [ ] Deploy 10 test pods (various CPU/memory profiles)
- [ ] Run agent, collect observations for 5 minutes
- [ ] Verify all pods discovered
- [ ] Verify metrics normalized to canonical schema
- [ ] Verify no data loss >5%

### Success Criteria
- ✅ Normalizer converts raw metrics without data loss
- ✅ Capability detection accurate
- ✅ E2E test passes on test cluster
- ✅ Agent runs for 5+ minutes without memory leaks

---

## WEEK 4: Component 1 Deployment & Integration

### Goals
- Complete Helm chart
- Create secure transport layer
- Set up integration with Component 2
- Deploy to testbed cluster

### Deliverables

#### 4.1 Helm Chart Completion (2 days)
**Files**:
- `charts/kubernetes-agent/Chart.yaml`
- `charts/kubernetes-agent/values.yaml`
- `charts/kubernetes-agent/templates/daemonset.yaml`
- `charts/kubernetes-agent/templates/deployment.yaml`
- `charts/kubernetes-agent/templates/rbac.yaml`
- `charts/kubernetes-agent/templates/configmap.yaml`

**Chart Structure**:
```yaml
apiVersion: v2
name: kubernetes-agent
version: 0.1.0
appVersion: "0.1.0"
description: Kubernetes observability agent

---
# values.yaml
image:
  repository: kubernetes-agent
  tag: "0.1.0"
  pullPolicy: IfNotPresent

daemonset:
  resources:
    requests:
      cpu: 100m
      memory: 128Mi
    limits:
      cpu: 500m
      memory: 512Mi

deployment:
  replicaCount: 1
  resources:
    requests:
      cpu: 250m
      memory: 256Mi
    limits:
      cpu: 1000m
      memory: 1Gi

prometheus:
  url: "http://prometheus:9090"
  scrapeInterval: 30s

component2:
  url: "https://component2-backend:443"
  authToken: "<set at install time>"
```

**Checklist**:
- [ ] DaemonSet runs on all nodes
- [ ] Deployment runs 1 replica (or configurable)
- [ ] RBAC permissions minimal (read pods, services, nodes)
- [ ] ConfigMap for settings
- [ ] Secret for auth token
- [ ] Health checks (liveness, readiness)
- [ ] Helm lint passes

#### 4.2 Secure Transport Layer (2 days)
**File**: `cmd/agent/transport/secure_transport.go`

```go
type SecureTransport interface {
    Send(ctx context.Context, obs *proto.NormalizedObservation) error
    Close() error
}

type gRPCTransport struct {
    conn *grpc.ClientConn
    client proto.ObservationServiceClient
    tenantID string
    authToken string
}

func (t *gRPCTransport) Send(ctx context.Context, obs *proto.NormalizedObservation) error {
    // Set tenant ID and auth headers
    ctx = metadata.AppendToOutgoingContext(ctx, "tenant-id", t.tenantID)
    ctx = metadata.AppendToOutgoingContext(ctx, "authorization", "Bearer " + t.authToken)
    
    // Send with retry logic
    return t.client.SendObservation(ctx, obs)
}
```

**Implementation**:
- gRPC with TLS
- Bearer token authentication
- Batch queueing (max 100 observations per batch)
- Exponential backoff retry (max 3 retries)
- Circuit breaker (if Component 2 unreachable for >5min, cache locally)

**Checklist**:
- [ ] mTLS or TLS + token auth working
- [ ] Batch protocol efficient
- [ ] Retry logic working
- [ ] Local caching on backend failure
- [ ] Auth errors logged and surface capability flag
- [ ] Connection pooling prevents resource exhaustion

#### 4.3 Agent Configuration (1 day)
**Files**:
- `cmd/agent/config/config.go`
- `config.yaml` (example)

```yaml
agent:
  cluster_name: "production"
  namespace: "kube-system"
  
sources:
  kubernetes:
    enabled: true
  prometheus:
    enabled: true
    url: "http://prometheus:9090"
    scrape_interval: 30s
  kubelet:
    enabled: true
  logs:
    enabled: false  # Requires additional setup
    
normalization:
  custom_metric_mappings:
    "my_cpu_metric": "cpu"
    
transport:
  backend_url: "https://component2-backend:443"
  auth_token_path: "/var/secrets/auth-token"
  max_batch_size: 100
  send_interval: 10s
```

**Checklist**:
- [ ] Config file parsing (YAML, TOML, JSON)
- [ ] Environment variable overrides
- [ ] Config validation on startup
- [ ] Defaults for all optional fields

#### 4.4 Integration Test with Component 2 (1 day)
**File**: `test/integration_test.go`

```go
func TestComponent1Component2Integration(t *testing.T) {
    // Start mock Component 2 backend
    // Deploy agent to test cluster
    // Verify observations reach backend
    // Verify schema compliance
}
```

**Checklist**:
- [ ] Mock Component 2 backend accepting observations
- [ ] Agent successfully sends observations
- [ ] Backend receives complete, valid observations
- [ ] Schema validation passes

### Success Criteria
- ✅ Helm chart deploys in <2 minutes
- ✅ Agent pod runs and reports healthy
- ✅ Observations reach mock backend
- ✅ No RBAC or auth errors in logs
- ✅ Agent resource usage <500MB memory

---

## WEEK 5: Component 2 Foundation & Baseline Engine

### Goals
- Set up Component 2 project structure
- Implement baseline store (DB schema)
- Implement pooled-σ baseline calibration
- Build integration with Component 1

### Deliverables

#### 5.1 Project Structure & Proto (1 day)
**Files**:
- `proto/forecasting.proto`
- `cmd/forecasting-engine/main.go`
- `go.mod` (Python or Go, choose based on team preference)

```protobuf
message BaselineMetrics {
    string tenant_id = 1;
    string cluster_name = 2;
    string metric_name = 3;
    
    // Pooled statistics
    double mean = 4;
    double stddev = 5;
    double p25 = 6;
    double p75 = 7;
    
    int64 last_updated_ms = 8;
    int64 window_count = 9;
}

message PlaybookFiringEvent {
    string playbook_id = 1;
    string tenant_id = 2;
    int64 timestamp_ms = 3;
    
    float confidence = 4;
    repeated string affected_pod_ids = 5;
    map<string, double> selected_variable_values = 6;
    string reason = 7;
}
```

**Checklist**:
- [ ] Proto compiles
- [ ] Go/Python bindings generated
- [ ] Event models defined

#### 5.2 Baseline Store & Schema (1 day)
**File**: `internal/store/baseline_store.go` (or Python equivalent)

**PostgreSQL Schema**:
```sql
CREATE TABLE baseline_metrics (
    id SERIAL PRIMARY KEY,
    tenant_id VARCHAR(255) NOT NULL,
    cluster_name VARCHAR(255) NOT NULL,
    metric_name VARCHAR(255) NOT NULL,
    
    mean FLOAT NOT NULL,
    stddev FLOAT NOT NULL,
    p25 FLOAT,
    p75 FLOAT,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    window_count INT DEFAULT 0,
    
    UNIQUE(tenant_id, cluster_name, metric_name)
);

CREATE TABLE baseline_windows (
    id SERIAL PRIMARY KEY,
    baseline_id INT REFERENCES baseline_metrics(id),
    window_start_ms BIGINT NOT NULL,
    window_end_ms BIGINT NOT NULL,
    value_count INT NOT NULL,
    mean FLOAT,
    stddev FLOAT
);

CREATE INDEX idx_baseline_tenant_metric ON baseline_metrics(tenant_id, metric_name);
```

**Interface**:
```go
type BaselineStore interface {
    GetBaseline(ctx context.Context, tenantID, metricName string) (*BaselineMetrics, error)
    CreateOrUpdateBaseline(ctx context.Context, baseline *BaselineMetrics) error
    GetWindows(ctx context.Context, baselineID int) ([]BaselineWindow, error)
    CreateWindow(ctx context.Context, window *BaselineWindow) error
}
```

**Checklist**:
- [ ] PostgreSQL schema created
- [ ] Migrations working
- [ ] CRUD operations implemented
- [ ] Indexes created for performance

#### 5.3 Pooled-σ Calibration Engine (2 days)
**File**: `internal/calibration/pooled_sigma.go`

```python
def compute_pooled_sigma(windows: List[BaselineWindow]) -> Tuple[float, float]:
    """
    Compute mean and stddev across multiple baseline windows using pooled estimate.
    
    Args:
        windows: List of windows, each with values
        
    Returns:
        (mean, stddev)
    """
    n_total = sum(w.n for w in windows)
    
    # Overall mean
    overall_mean = sum(w.mean * w.n for w in windows) / n_total
    
    # Pooled variance
    pooled_var = sum(
        (w.n - 1) * w.stddev**2 + w.n * (w.mean - overall_mean)**2
        for w in windows
    ) / (n_total - len(windows))
    
    return overall_mean, sqrt(pooled_var)

class BaselineCalibrator:
    def __init__(self, observation_store, baseline_store):
        self.observation_store = observation_store
        self.baseline_store = baseline_store
    
    def calibrate_for_tenant(self, tenant_id: str, days: int = 7):
        """
        Full baseline calibration for a tenant using last N days of observations.
        """
        # Get observations for last N days
        observations = self.observation_store.get_observations(tenant_id, days=days)
        
        # For each metric, create baseline windows
        metrics_by_name = {}
        for obs in observations:
            for metric_name, value in extract_metrics(obs).items():
                if metric_name not in metrics_by_name:
                    metrics_by_name[metric_name] = []
                metrics_by_name[metric_name].append((obs.timestamp_ms, value))
        
        # For each metric, compute windows and pooled-sigma
        for metric_name, values in metrics_by_name.items():
            windows = self._create_windows(values, window_size_hours=6)
            mean, stddev = compute_pooled_sigma(windows)
            
            baseline = BaselineMetrics(
                tenant_id=tenant_id,
                metric_name=metric_name,
                mean=mean,
                stddev=stddev,
                window_count=len(windows)
            )
            self.baseline_store.create_or_update_baseline(baseline)
    
    def _create_windows(self, values, window_size_hours: int):
        """Create non-overlapping time windows."""
        windows = []
        current_window = []
        current_window_start = values[0][0]
        window_duration_ms = window_size_hours * 3600 * 1000
        
        for timestamp, value in values:
            if timestamp - current_window_start > window_duration_ms:
                # Create window and start new one
                w = self._compute_window_stats(current_window)
                windows.append(w)
                current_window = [(timestamp, value)]
                current_window_start = timestamp
            else:
                current_window.append((timestamp, value))
        
        # Final window
        if current_window:
            windows.append(self._compute_window_stats(current_window))
        
        return windows
    
    def _compute_window_stats(self, values):
        data = [v for _, v in values]
        return WindowStats(
            mean=np.mean(data),
            stddev=np.std(data),
            n=len(data)
        )
```

**Checklist**:
- [ ] Pooled-σ algorithm implemented
- [ ] Window creation working
- [ ] Baseline computation tested with synthetic data
- [ ] Baseline storage and retrieval working
- [ ] Drift detection (baseline compared to new observations) implemented

#### 5.4 Observation Ingestion (1 day)
**File**: `internal/ingestion/observation_handler.go`

```go
type ObservationHandler struct {
    baselineStore BaselineStore
    observationStore ObservationStore
}

func (h *ObservationHandler) HandleObservation(ctx context.Context, obs *proto.NormalizedObservation) error {
    // Store observation for later baseline calibration
    err := h.observationStore.Store(ctx, obs)
    if err != nil {
        return err
    }
    
    // Trigger playbook evaluation
    return h.evaluatePlaybooks(ctx, obs)
}
```

**Checklist**:
- [ ] gRPC server accepting observations
- [ ] Observation deserialization working
- [ ] Storage to DB successful
- [ ] Auth/tenancy isolation enforced

### Success Criteria
- ✅ PostgreSQL schema created and migrated
- ✅ Pooled-σ algorithm correctly computes baseline
- ✅ Observations successfully ingested and stored
- ✅ Baseline calibration runs successfully on test data

---

## WEEK 6: Component 2 Detection Algorithms & Playbooks

### Goals
- Implement base detector infrastructure
- Implement all 5 playbooks
- Build confidence scoring
- Create playbook state management

### Deliverables

#### 6.1 Detector Base Infrastructure (2 days)
**File**: `internal/detection/detector.go`

```go
type Detector interface {
    Evaluate(ctx context.Context, obs *proto.NormalizedObservation, baseline *BaselineMetrics) (*PlaybookFiringEvent, error)
    GetPlaybookID() string
}

type BaseDetector struct {
    playbookID string
    baselineStore BaselineStore
    stateManager PlaybookStateManager
}

func (d *BaseDetector) ComputeZScore(value float64, baseline *BaselineMetrics) float64 {
    if baseline.Stddev == 0 {
        return 0
    }
    return (value - baseline.Mean) / baseline.Stddev
}

func (d *BaseDetector) IsAnomalous(zScore float64, threshold float64) bool {
    return abs(zScore) > threshold
}
```

**Checklist**:
- [ ] Base detector interface defined
- [ ] Z-score computation utility
- [ ] Threshold checking utilities

#### 6.2 Probe-Cascade Playbook (1 day)
**File**: `internal/detection/probe_cascade_detector.go`

(Implement as per Playbook Specification Guide)

**Checklist**:
- [ ] All 5 signals detected
- [ ] Confidence scoring working
- [ ] Test cases passing

#### 6.3 CPU Contention Playbook (1 day)
**File**: `internal/detection/cpu_contention_detector.go`

**Checklist**:
- [ ] CPU spike detection
- [ ] Co-located pod identification
- [ ] Latency correlation
- [ ] Confidence scoring

#### 6.4 OOM Cascade, gRPC, Storage Playbooks (2 days)
**Files**:
- `internal/detection/oom_detector.go`
- `internal/detection/grpc_detector.go`
- `internal/detection/storage_detector.go`

**Checklist** (for each):
- [ ] Detection algorithm implemented
- [ ] Test cases for normal/anomalous scenarios
- [ ] Confidence scoring

#### 6.5 Playbook State Management (0.5 days)
**File**: `internal/detection/state_manager.go`

```go
type PlaybookState string
const (
    StateNew      PlaybookState = "new"
    StateFiring   PlaybookState = "firing"
    StateResolving PlaybookState = "resolving"
    StateResolved PlaybookState = "resolved"
)

type PlaybookInstance struct {
    ID        string
    PlaybookID string
    State     PlaybookState
    FirstSeen int64
    LastSeen  int64
    Confidence float32
}

type PlaybookStateManager struct {
    instances map[string]*PlaybookInstance
    mu sync.RWMutex
}

func (m *PlaybookStateManager) UpdateOrCreate(event *PlaybookFiringEvent) *PlaybookInstance {
    // If playbook already firing, update state
    // If not firing, create new instance
    // If resolving and no new evidence, move to resolved
}
```

**Checklist**:
- [ ] State transitions correct
- [ ] Deduplication working (same playbook doesn't fire twice rapidly)
- [ ] Resolution tracking working

### Success Criteria
- ✅ All 5 detectors implemented
- ✅ Unit tests passing for each detector
- ✅ Confidence scoring produces expected values
- ✅ State management correctly tracks playbook lifecycle

---

## WEEK 7: Component 2 Calibration & Admin API

### Goals
- Online calibration (per-customer baseline tuning)
- Admin API for playbook management
- Metrics dashboard
- Integration testing

### Deliverables

#### 7.1 Online Calibration (1 day)
**File**: `internal/calibration/online_calibration.go`

```go
type OnlineCalibrator struct {
    baselineStore BaselineStore
    config *CalibrationConfig
}

type CalibrationConfig struct {
    // When to reset baseline
    ResetOnClusterEvents bool
    ResetEventTypes []string  // "deploy", "scale", "config_change"
    
    // When baseline drifts too much
    DriftThreshold float64  // e.g., 0.15 = 15% drift
}

func (oc *OnlineCalibrator) OnClusterEvent(ctx context.Context, tenantID string, event *proto.ClusterEvent) {
    if oc.config.ResetOnClusterEvents {
        // Reset baselines for affected pods
        // Clear baseline cache
    }
}

func (oc *OnlineCalibrator) MonitorDrift(ctx context.Context, tenantID string) {
    // Periodically compare new observations to baselines
    // If drift > threshold, re-calibrate
}
```

**Checklist**:
- [ ] Event-based baseline reset working
- [ ] Drift detection implemented
- [ ] Online recalibration triggered correctly

#### 7.2 Admin API (2 days)
**File**: `internal/api/admin_handler.go`

```go
// GET /admin/playbooks
// Lists all available playbooks with status
func (h *AdminHandler) ListPlaybooks(w http.ResponseWriter, r *http.Request) {
    response := []PlaybookInfo{
        {ID: "probe-cascade", Enabled: true, ConfidenceThreshold: 0.65},
        {ID: "cpu-contention", Enabled: true, ConfidenceThreshold: 0.60},
        // ...
    }
    json.NewEncoder(w).Encode(response)
}

// POST /admin/playbooks/{id}/config
// Update playbook configuration
func (h *AdminHandler) UpdatePlaybookConfig(w http.ResponseWriter, r *http.Request) {
    // Update confidence threshold, enable/disable, etc.
}

// GET /admin/baselines
// Inspect baseline metrics for a tenant
func (h *AdminHandler) GetBaselines(w http.ResponseWriter, r *http.Request) {
    // Returns current baselines, window count, last update time
}

// POST /admin/recalibrate
// Manually trigger baseline recalibration
func (h *AdminHandler) Recalibrate(w http.ResponseWriter, r *http.Request) {
    // Recalibrate baselines for tenant
}
```

**Checklist**:
- [ ] REST API endpoints implemented
- [ ] Request validation working
- [ ] Auth/tenancy checks enforced
- [ ] API documentation (OpenAPI/Swagger)

#### 7.3 Diagnostics Dashboard (1 day)
**File**: `internal/api/dashboard_handler.go`

Create an HTML dashboard that shows:
- Baseline status per metric
- Playbook firing rates
- False positive rates
- Recent firing events
- Confidence score distribution

**Checklist**:
- [ ] Dashboard HTML/CSS created
- [ ] Backend endpoints feeding dashboard
- [ ] Charts displaying playbook metrics

#### 7.4 Integration Testing (0.5 days)
**File**: `test/component2_integration_test.go`

```go
func TestEndToEndPlaybookFiring(t *testing.T) {
    // Create synthetic observations with known anomalies
    // Feed to component 2
    // Verify playbooks fire as expected
    // Check confidence scores
}
```

**Checklist**:
- [ ] Synthetic anomaly scenarios created
- [ ] Playbooks correctly detect each scenario
- [ ] Confidence scores match expectations

### Success Criteria
- ✅ Admin API fully functional
- ✅ Baseline inspection working
- ✅ Dashboard accessible and displays data
- ✅ Integration tests pass

---

## WEEK 8: Integration, Testing & Documentation

### Goals
- Full end-to-end integration (Component 1 ↔ Component 2)
- Performance testing
- Documentation completion
- Testbed deployment

### Deliverables

#### 8.1 E2E Integration Testing (2 days)
**File**: `test/e2e_component12_test.go`

```go
func TestFullSystem(t *testing.T) {
    // Start test cluster
    // Deploy Component 1 (agent)
    // Deploy Component 2 (backend)
    // Create synthetic workloads with known failure patterns
    // Verify:
    //   - Component 1 scrapes and sends observations
    //   - Component 2 receives observations
    //   - Playbooks fire as expected
    //   - Event stream emits events to Component 3 (mock)
}
```

**Test Scenarios**:
1. Probe-cascade: Create memory pressure, verify detection
2. CPU contention: Create CPU spike, verify detection
3. OOM: Create memory leak, verify detection
4. False positive check: Normal cluster, verify low false positive rate

**Checklist**:
- [ ] E2E tests pass
- [ ] All 5 playbooks tested
- [ ] False positive rate <1%
- [ ] Mean detection latency <5 seconds

#### 8.2 Performance Testing (1 day)
**Benchmarks**:
- Component 1 memory/CPU usage at 500+ pods
- Component 2 event processing latency (p99 <1s)
- Baseline computation time (<1 minute for 1000 metrics)
- Admin API response time (<100ms)

**File**: `test/benchmark_test.go`

**Checklist**:
- [ ] Component 1: <500MB memory at 500+ pods
- [ ] Component 2: <1s latency for all playbooks
- [ ] No memory leaks over 24 hours

#### 8.3 Documentation (1 day)
**Files to create**:
- `docs/COMPONENT_1_ARCHITECTURE.md` - Deep dive into data collection
- `docs/COMPONENT_2_ARCHITECTURE.md` - Deep dive into detection
- `docs/API_REFERENCE.md` - Admin API docs
- `docs/PLAYBOOK_TUNING.md` - How to adjust playbook thresholds
- `docs/TROUBLESHOOTING.md` - Common issues and solutions
- `DEPLOYMENT_GUIDE.md` - Step-by-step deployment

**Checklist**:
- [ ] All APIs documented
- [ ] Helm chart deployment guide complete
- [ ] Playbook tuning guide complete
- [ ] Troubleshooting guide complete

#### 8.4 Testbed Deployment (1 day)
**Deploy full system to multi-pod testbed cluster**

**Checklist**:
- [ ] Component 1 deployed via Helm
- [ ] Component 2 running on backend
- [ ] Test workloads deployed
- [ ] System running stably for 24+ hours
- [ ] All playbooks tested on real data

### Success Criteria
- ✅ E2E tests pass
- ✅ Performance benchmarks met
- ✅ Documentation complete
- ✅ System stable in testbed for 24+ hours

---

## 🎯 MILESTONES & GATES

| Week | Milestone | Gate |
|------|-----------|------|
| 1    | Component 1 foundation | K8s API client works, topology discovered |
| 2    | Component 1 multi-source | All 5 sources scraping |
| 3    | Component 1 normalization | E2E test passes, <5% data loss |
| 4    | Component 1 deployment | Helm chart deploys, observations reach backend |
| 5    | Component 2 baseline | Pooled-σ algorithm working, baselines calibrated |
| 6    | Component 2 playbooks | All 5 detectors implemented, unit tests pass |
| 7    | Component 2 admin | API functional, dashboard live |
| 8    | Integration & docs | E2E tests pass, deployed to testbed |

---

## 📊 SUCCESS METRICS

### Component 1 Deliverables
- [ ] Scrapes from 5 data sources (K8s, Prometheus, Kubelet, Logs, optional Mesh)
- [ ] Normalizes data with <5% loss
- [ ] Transmits securely (mTLS + token auth)
- [ ] Helm chart deploys in <2 minutes
- [ ] Memory usage <500MB for 500+ pods
- [ ] Data send latency <30 seconds per collection cycle

### Component 2 Deliverables
- [ ] Baseline calibration achieves <1% false positive on quiet clusters
- [ ] 5 playbooks implemented and calibrated
- [ ] Playbook detection latency <5 seconds
- [ ] Confidence scores correlate with manual analysis (>0.8)
- [ ] Admin API fully functional
- [ ] Diagnostics dashboard showing all metrics

### System Integration
- [ ] Observations flow from Component 1 → Component 2 → Component 3 (mock)
- [ ] E2E latency (anomaly → detection) <5 seconds
- [ ] 24-hour stability test passed
- [ ] All documentation complete

---

## 🚦 CHECKPOINT REVIEWS

- **End of Week 2**: Code review of Component 1 sources
- **End of Week 4**: Deployment & integration review
- **End of Week 6**: Playbook correctness review
- **End of Week 8**: Final system demo & documentation review

---

## 📝 NOTES FOR TEAM

1. **Daily Standups**: 15 min sync on blockers, progress
2. **Weekly Reviews**: Sunday evening checkpoint
3. **Parallel Work**: Component 1 and 2 can develop in parallel after Week 1 (Component 1 foundation must complete first)
4. **Testing Priority**: Write unit tests as you code, not after
5. **Documentation**: Update docs as you develop, not at the end
6. **Feedback Loop**: Run E2E tests frequently (not just at checkpoints)

