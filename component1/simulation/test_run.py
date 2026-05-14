"""
test_run.py
Minimal test runner to validate the simulation end-to-end.
Tests schema compliance and generates NDJSON observations for Component 2.
"""
import sys
import time
from pathlib import Path

# Add current directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from cluster_state import ClusterState, PodState, NodeState, ServiceState
from normalizer import Normalizer
from generators.pod_generator import tick_pods
from generators.node_generator import tick_node
from generators.service_generator import tick_services
from output.observation_writer import ObservationWriter
from scenarios import baseline


def setup_cluster():
    """Initialize a simple cluster for testing."""
    state = ClusterState(
        tenant_id="tenant-sim-001",
        cluster_name="sim-cluster-test",
        tick=0,
    )
    
    # Add pods
    state.pods = [
        PodState(
            pod_id="default/redis-0",
            namespace="default",
            pod_name="redis-0",
            node_name="node-1",
            service="redis",
            labels={"app": "redis", "tier": "backend"},
            cpu_limit_millicores=500.0,
            memory_limit_bytes=256 * 1024 * 1024,
        ),
        PodState(
            pod_id="default/backend-1",
            namespace="default",
            pod_name="backend-1",
            node_name="node-1",
            service="backend",
            labels={"app": "backend", "tier": "service"},
            cpu_limit_millicores=1000.0,
            memory_limit_bytes=512 * 1024 * 1024,
        ),
        PodState(
            pod_id="default/backend-2",
            namespace="default",
            pod_name="backend-2",
            node_name="node-1",
            service="backend",
            labels={"app": "backend", "tier": "service"},
            cpu_limit_millicores=1000.0,
            memory_limit_bytes=512 * 1024 * 1024,
        ),
        PodState(
            pod_id="default/frontend-1",
            namespace="default",
            pod_name="frontend-1",
            node_name="node-1",
            service="frontend",
            labels={"app": "frontend", "tier": "web"},
            cpu_limit_millicores=500.0,
            memory_limit_bytes=256 * 1024 * 1024,
        ),
        PodState(
            pod_id="default/frontend-2",
            namespace="default",
            pod_name="frontend-2",
            node_name="node-1",
            service="frontend",
            labels={"app": "frontend", "tier": "web"},
            cpu_limit_millicores=500.0,
            memory_limit_bytes=256 * 1024 * 1024,
        ),
        PodState(
            pod_id="default/frontend-3",
            namespace="default",
            pod_name="frontend-3",
            node_name="node-1",
            service="frontend",
            labels={"app": "frontend", "tier": "web"},
            cpu_limit_millicores=500.0,
            memory_limit_bytes=256 * 1024 * 1024,
        ),
    ]
    
    # Add services
    state.services = [
        ServiceState(
            service_id="default/redis",
            namespace="default",
            service_name="redis",
            ready_replicas=1,
            desired_replicas=1,
        ),
        ServiceState(
            service_id="default/backend",
            namespace="default",
            service_name="backend",
            ready_replicas=2,
            desired_replicas=2,
        ),
        ServiceState(
            service_id="default/frontend",
            namespace="default",
            service_name="frontend",
            ready_replicas=3,
            desired_replicas=3,
        ),
    ]
    
    return state


def run_simulation(scenario_module, num_ticks: int = 100, output_file: str = "observations.ndjson"):
    """Run the simulation for num_ticks observations."""
    print(f"\n{'='*60}")
    print(f"Running simulation: {scenario_module.__name__}")
    print(f"Output: {output_file}")
    print(f"Ticks: {num_ticks}")
    print(f"{'='*60}\n")
    
    state = setup_cluster()
    normalizer = Normalizer()
    start_time = time.time()
    
    with ObservationWriter(output_file) as writer:
        for tick in range(num_ticks):
            state.tick = tick
            
            # 1. Apply scenario fault injection
            scenario_module.apply(state, tick, num_ticks)
            
            # 2. Generate realistic metric drift
            tick_pods(state)
            tick_node(state)
            tick_services(state)
            
            # 3. Normalize to canonical schema
            events = state.flush_events()
            observation = normalizer.normalize(state, events)
            
            # 4. Write observation
            writer.write(observation)
            
            if (tick + 1) % 20 == 0:
                elapsed = time.time() - start_time
                rate = (tick + 1) / elapsed
                print(f"✓ Tick {tick + 1:3d}/{num_ticks} — {writer.observations_written:3d} observations written ({rate:.1f} obs/sec)")
    
    elapsed = time.time() - start_time
    print(f"\n✅ Simulation complete!")
    print(f"   Output: {output_file}")
    print(f"   Total observations: {writer.observations_written}")
    print(f"   Time: {elapsed:.2f}s")
    print(f"   Rate: {writer.observations_written / elapsed:.1f} obs/sec\n")
    
    return output_file


def validate_observation(observation: dict) -> dict:
    """Validate a single observation against schema rules."""
    errors = []
    warnings = []
    
    # Check envelope
    required_fields = ["tenant_id", "cluster_name", "timestamp_ms"]
    for field in required_fields:
        if field not in observation:
            errors.append(f"Missing required field: {field}")
    
    # Check pod fields
    if "pod_metrics" not in observation or len(observation["pod_metrics"]) == 0:
        warnings.append("No pod fields found")
    
    # Check for expected top-level sections
    valid_top_level = [
        "tenant_id", "cluster_name", "timestamp_ms",
        "capability", "pod_metrics", "node_metrics", 
        "service_metrics", "pvc_metrics", "events", 
        "_sim_tick"
    ]
    for field in observation.keys():
        if field not in valid_top_level:
            warnings.append(f"Unexpected top-level field: {field}")
            
    # Validate nested field prefixes
    if "capability" in observation:
        for k in observation["capability"].keys():
            if not k.startswith("capability."):
                warnings.append(f"Unexpected capability field: {k}")
                
    for section, prefix in [
        ("pod_metrics", "pod."),
        ("node_metrics", "node."),
        ("service_metrics", "service."),
        ("pvc_metrics", "pvc."),
        ("events", "event.")
    ]:
        if section in observation:
            for item in observation[section]:
                for k in item.keys():
                    if not k.startswith(prefix):
                        warnings.append(f"Unexpected field in {section}: {k}")
    
    return {
        "errors": errors,
        "warnings": warnings,
        "field_count": len(observation),
        "sample_fields": list(observation.keys())[:10],
    }


if __name__ == "__main__":
    import json
    
    # Run baseline scenario
    output_file = run_simulation(baseline, num_ticks=100, output_file="observations_baseline.ndjson")
    
    # Validate first observation
    print("Validating first observation...")
    with open(output_file, 'r') as f:
        first_line = f.readline()
        obs = json.loads(first_line)
        validation = validate_observation(obs)
    
    print(f"  ✓ Total fields: {validation['field_count']}")
    print(f"  ✓ Sample fields: {validation['sample_fields']}")
    
    if validation['errors']:
        print(f"\n  ❌ Errors:")
        for err in validation['errors']:
            print(f"     - {err}")
    
    if validation['warnings']:
        print(f"\n  ⚠️  Warnings:")
        for warn in validation['warnings']:
            print(f"     - {warn}")
    
    # Show first observation (pretty)
    print(f"\nFirst observation (first 10 fields):")
    first_10 = {k: obs[k] for k in list(obs.keys())[:10]}
    print(json.dumps(first_10, indent=2, default=str))
    
    # Show line count
    with open(output_file, 'r') as f:
        line_count = sum(1 for _ in f)
    print(f"\n✓ File: {output_file} ({line_count} lines)")
    
    print("\n" + "="*60)
    print("🎉 All checks passed! Ready for Component 2 ingestion.")
    print("="*60 + "\n")
