# Component 1: Pre-Flight Checklist
## Verify Everything Is Ready Before Development Starts

---

## ✅ RUN THIS CHECKLIST BEFORE WEEK 1

This checklist ensures your environment and team are ready to begin Component 1 development. It should take **30 minutes** to complete.

---

## 🔧 PART 1: SYSTEM SETUP (15 minutes)

### 1.1 Language & Build Tools
```powershell
# Check Go installation
go version
# ✅ Should print: go version go1.21.x or higher

# Check Go workspace
go env GOPATH
# ✅ Should show a valid path (e.g., C:\Users\admin\go)

# Check if go.mod exists
ls go.mod
# ✅ Should exist; if not, run: go mod init github.com/kubernetes-agent/component1

# Verify proto compiler
protoc --version
# ✅ Should print: libprotoc 3.21.x or higher
# If not found, run: go install github.com/protocolbuffers/protobuf/cmd/protoc-gen-go@latest
```

**Status**: 
- [ ] Go v1.21+
- [ ] GOPATH set
- [ ] go.mod exists
- [ ] protoc installed

---

### 1.2 Containerization & Deployment
```powershell
# Check Docker
docker --version
# ✅ Should print: Docker version 24.x.x or higher

# Verify Docker daemon running
docker ps
# ✅ Should list containers (or empty list); NOT error

# Check Helm
helm version
# ✅ Should print: version.BuildInfo{Version:"v3.12.x" or higher}
```

**Status**:
- [ ] Docker installed and running
- [ ] Helm installed
- [ ] `docker ps` works

---

### 1.3 Kubernetes Tools
```powershell
# Check kubectl
kubectl version --client
# ✅ Should print: Client Version: v1.28.x or higher

# Check if local K8s cluster available
kubectl cluster-info
# ✅ Should show cluster info (minikube, kind, or Docker Desktop)
# If error, start minikube: minikube start

# List available contexts
kubectl config get-contexts
# ✅ Should show at least one context (highlighted is current)
```

**Status**:
- [ ] kubectl installed
- [ ] Local K8s cluster running (minikube/kind/Docker Desktop)
- [ ] kubectl can connect to cluster

---

### 1.4 Project Structure
```powershell
# Navigate to project
cd <your-workspace-path>\component1-agent

# Verify directory structure
ls cmd, internal, proto, test, charts
# ✅ Should list all directories

# Show structure
tree /L 2 /A
# ✅ Should show:
# component1-agent/
# ├── cmd/
# │   └── agent/
# ├── internal/
# │   ├── sources/
# │   ├── normalizer/
# │   ├── transport/
# │   └── config/
# ├── proto/
# ├── test/
# ├── charts/
# └── go.mod
```

**Status**:
- [ ] Project directory exists
- [ ] Directory structure complete
- [ ] go.mod present

---

### 1.5 Dependencies
```powershell
# List all dependencies
go list -m all
# ✅ Should show:
# k8s.io/client-go v0.28.0
# google.golang.org/grpc v1.59.0
# (and others)

# Verify no conflicts
go mod verify
# ✅ Should print: all modules verified

# Tidy dependencies
go mod tidy
# ✅ Should complete without errors

# Try to build
go build -o bin/agent ./cmd/agent
# ✅ Should compile without errors (may have TODOs in code, that's fine)

# Verify binary created
ls bin/agent
# ✅ Should exist
```

**Status**:
- [ ] go list shows all required dependencies
- [ ] go mod verify passes
- [ ] go mod tidy works
- [ ] Project compiles

---

## 📋 PART 2: PROTO SCHEMA (5 minutes)

### 2.1 Proto File Exists
```powershell
# Check proto file
ls proto/observability.proto
# ✅ Should exist and be readable

# Check proto content
cat proto/observability.proto | head -30
# ✅ Should show proto definitions starting with: syntax = "proto3";
```

**Status**:
- [ ] proto/observability.proto exists
- [ ] File contains at least NormalizedObservation message

---

### 2.2 Proto Compilation
```powershell
# Compile proto files
protoc --go_out=. --go-grpc_out=. proto/*.proto
# ✅ Should complete without errors

# Check generated files
ls proto/*.pb.go
# ✅ Should show: observability_pb2.go, observability_grpc.pb.go (or similar)

# Try importing in Go
echo 'package main; import "github.com/kubernetes-agent/component1/proto/observability"' | go run -
# ✅ Should work (or show import is available)
```

**Status**:
- [ ] Proto compiles
- [ ] Generated Go files exist
- [ ] Import works

---

## 🗂️ PART 3: CONFIGURATION (5 minutes)

### 3.1 Config File Ready
```powershell
# Check if config.yaml exists
ls config.yaml
# ✅ Should exist

# Verify it's valid YAML
cat config.yaml | head -20
# ✅ Should show indented YAML structure

# Expected sections
cat config.yaml | grep -E "agent:|sources:|transport:"
# ✅ Should show at least these three sections
```

**Status**:
- [ ] config.yaml exists
- [ ] Contains agent, sources, transport sections
- [ ] Looks like valid YAML

---

### 3.2 Dockerfile Ready
```powershell
# Check Dockerfile exists
ls Dockerfile
# ✅ Should exist

# Verify structure
cat Dockerfile | head -10
# ✅ Should show: FROM golang:1.21-alpine
```

**Status**:
- [ ] Dockerfile exists
- [ ] Contains Go 1.21 base image

---

## 👥 PART 4: TEAM COORDINATION (5 minutes)

### 4.1 Component 2 Requirements Awaited
```powershell
# Check if requirements form template exists
ls COMPONENT1_COMPONENT2_HANDOFF_CHECKLIST.md
# ✅ Should exist - use this for Component 2 to specify needs

# Note: Fill this in when Component 2 team provides requirements
cat COMPONENT1_COMPONENT2_HANDOFF_CHECKLIST.md | grep "COMPONENT 2 REQUIREMENTS FORM" -A 20
# ✅ Should show template
```

**Status**:
- [ ] Handoff checklist document exists
- [ ] Aware that Component 2 needs to fill out requirements form
- [ ] Scheduled sync with Component 2 team

---

### 4.2 Development Roadmap Reviewed
```powershell
# Check roadmap exists
ls DEVELOPMENT_ROADMAP.md
# ✅ Should exist

# Find Week 1 section
cat DEVELOPMENT_ROADMAP.md | grep "## WEEK 1:" -A 30
# ✅ Should show tasks for Week 1
```

**Status**:
- [ ] Roadmap document reviewed
- [ ] Week 1 deliverables understood
- [ ] Team has read Week 1 plan

---

## 🧪 PART 5: VERIFICATION BUILD (5 minutes)

### 5.1 Clean Build
```powershell
# Clean previous builds
rm -r bin/
go clean -modcache

# Fresh build
go build -o bin/agent ./cmd/agent
# ✅ Should succeed

# Test running help
bin/agent -help
# ✅ Should show flags (version, config, health, help)

# Test version
bin/agent -version
# ✅ Should print: kubernetes-agent v0.1.0 (or similar)

# Test health check
bin/agent -health
# ✅ Should print: OK
```

**Status**:
- [ ] Clean build succeeds
- [ ] Agent binary runs
- [ ] Help/version/health flags work

---

### 5.2 Docker Build
```powershell
# Build Docker image
docker build -t kubernetes-agent:test -f Dockerfile .
# ✅ Should complete without errors (may take 1-2 minutes)

# Verify image exists
docker images kubernetes-agent:test
# ✅ Should list the image with tag "test"

# Test running container
docker run --rm kubernetes-agent:test -version
# ✅ Should print: kubernetes-agent v0.1.0

# Cleanup
docker image rm kubernetes-agent:test
# ✅ Image should be removed
```

**Status**:
- [ ] Docker builds successfully
- [ ] Image runs and shows version
- [ ] Image cleaned up

---

### 5.3 Helm Chart Structure
```powershell
# Check chart directory
ls charts/kubernetes-agent/
# ✅ Should show: Chart.yaml, values.yaml, templates/

# List templates
ls charts/kubernetes-agent/templates/
# ✅ Should show: daemonset.yaml, deployment.yaml, rbac.yaml, configmap.yaml

# Lint chart (basic check)
helm lint charts/kubernetes-agent/
# ✅ Should complete (may show warnings, that's OK for now)
```

**Status**:
- [ ] Helm chart directory structure exists
- [ ] Chart.yaml present
- [ ] Template files present
- [ ] Chart lints without critical errors

---

## 📊 PART 6: DOCUMENTATION (5 minutes)

### 6.1 Core Documents Exist
```powershell
# Check all key documents exist
ls COMPONENT_1_2_IMPLEMENTATION_GUIDE.md
ls PLAYBOOK_SPECIFICATION_GUIDE.md
ls DEVELOPMENT_ROADMAP.md
ls ENVIRONMENT_SETUP_GUIDE.md
ls QUICK_REFERENCE.md
ls COMPONENT1_COMPONENT2_HANDOFF_CHECKLIST.md
# ✅ All should exist

# Count total documentation (rough idea of completeness)
(ls *.md).Count
# ✅ Should be 6+ markdown files
```

**Status**:
- [ ] Implementation guide exists
- [ ] Playbook guide exists
- [ ] Roadmap exists
- [ ] Setup guide exists
- [ ] Quick reference exists
- [ ] Handoff checklist exists

---

### 6.2 Proto Documentation
```powershell
# Check proto file has comments
cat proto/observability.proto | grep "/\*\*" -A 3 | head -30
# ✅ Should show documented messages

# Count message definitions
(cat proto/observability.proto | grep "^message " | wc -l)
# ✅ Should be 10+ message types
```

**Status**:
- [ ] Proto file well-commented
- [ ] All message types documented

---

## ✅ FINAL READINESS CHECKLIST

### All Systems Go?

```
SYSTEM SETUP (Part 1)
  ✅ Go v1.21+
  ✅ Docker installed & running
  ✅ Helm installed
  ✅ kubectl installed & cluster available
  ✅ Project structure complete
  ✅ Dependencies resolved

PROTO SCHEMA (Part 2)
  ✅ Proto file exists
  ✅ Proto compiles
  ✅ Generated files present

CONFIGURATION (Part 3)
  ✅ config.yaml ready
  ✅ Dockerfile ready

TEAM COORDINATION (Part 4)
  ✅ Handoff checklist reviewed
  ✅ Roadmap understood
  ✅ Component 2 requirements awaited

VERIFICATION BUILD (Part 5)
  ✅ Clean build succeeds
  ✅ Agent binary works
  ✅ Docker build works
  ✅ Helm chart structure ready

DOCUMENTATION (Part 6)
  ✅ All guides present
  ✅ Proto well-documented
```

If all boxes checked: **YOU ARE READY TO START WEEK 1** 🚀

---

## 🚨 BLOCKERS (Fix These First)

### Blocker: Go Version < 1.21
**Fix**: 
```powershell
# Download Go 1.21+
# https://golang.org/dl/

# Verify after install
go version
```

### Blocker: Docker Not Running
**Fix**:
```powershell
# Windows: Start Docker Desktop (click icon in taskbar)
# Mac/Linux: sudo systemctl start docker

# Verify
docker ps
```

### Blocker: kubectl Can't Connect to Cluster
**Fix**:
```powershell
# Option 1: Start minikube
minikube start

# Option 2: Start Kind cluster
kind create cluster

# Option 3: Use Docker Desktop Kubernetes (enable in settings)
```

### Blocker: Proto Compiler Missing
**Fix**:
```powershell
go install github.com/protocolbuffers/protobuf/cmd/protoc-gen-go@latest
go install google.golang.org/grpc/cmd/protoc-gen-go-grpc@latest

# Add to PATH if needed
$env:PATH += ";$env:GOPATH\bin"
```

### Blocker: Project Won't Compile
**Fix**:
```powershell
# Clean everything
go clean -modcache
rm go.sum

# Re-sync
go mod tidy
go mod download

# Try build again
go build -o bin/agent ./cmd/agent
```

---

## 📞 IF STUCK

1. **Check this checklist** - 80% of issues are in system setup
2. **Review ENVIRONMENT_SETUP_GUIDE.md** - Detailed troubleshooting there
3. **Run individual commands** - Don't assume; verify each step
4. **Ask Component 2 team** - If unsure about requirements
5. **Check Go docs** - go.dev has excellent guides

---

## 🎯 ONCE APPROVED

When this checklist is complete:

1. **Screenshot/note** that all items are checked
2. **Notify the team** that environment is ready
3. **Sync with Component 2** - Share handoff checklist, discuss requirements
4. **Schedule kickoff** - Start Week 1 planning meeting
5. **Begin Week 1** - Follow DEVELOPMENT_ROADMAP.md

---

## ⏱️ ESTIMATED TIME

- **Part 1 (System)**: 10 minutes
- **Part 2 (Proto)**: 3 minutes
- **Part 3 (Config)**: 2 minutes
- **Part 4 (Team)**: 3 minutes
- **Part 5 (Build)**: 10 minutes (Docker build takes time)
- **Part 6 (Docs)**: 2 minutes
- **Total**: ~30 minutes

---

**Print this out or bookmark it. Reference it when things break. 99% of setup issues are caught here.** ✅

