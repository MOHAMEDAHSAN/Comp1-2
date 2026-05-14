# Component 1: Environment Setup Guide
## Get Your Development Environment Ready

---

## 🛠️ PREREQUISITES

### System Requirements
- **OS**: Windows (with WSL2), macOS, or Linux
- **Go**: v1.21+ ([download](https://golang.org/dl/))
- **Docker**: v24+ ([download](https://www.docker.com/products/docker-desktop))
- **Helm**: v3.12+ ([download](https://helm.sh/docs/intro/install/))
- **Git**: v2.40+
- **kubectl**: v1.28+ ([download](https://kubernetes.io/docs/tasks/tools/))

### Optional but Recommended
- **Minikube** or **Kind**: Local K8s cluster for testing ([links](https://minikube.sigs.k8s.io/docs/start/))
- **VSCode** with Go extension
- **Protobuf compiler**: `protoc` v3.21+
- **grpcurl**: For testing gRPC endpoints

---

## 📋 SETUP CHECKLIST

### Step 1: Verify Go Installation
```powershell
# In PowerShell or Terminal
go version
# Expected output: go version go1.21.x ...

go env GOPATH
# Shows your GOPATH (default: C:\Users\<user>\go on Windows)
```

### Step 2: Verify Docker Installation
```powershell
docker --version
# Expected output: Docker version 24.x.x ...

docker run hello-world
# Should print "Hello from Docker!" if working
```

### Step 3: Verify Helm Installation
```powershell
helm version
# Expected output: version.BuildInfo{Version:"v3.12.x" ...}
```

### Step 4: Verify kubectl Installation
```powershell
kubectl version --client
# Expected output: Client Version: v1.28.x ...
```

---

## 📁 PROJECT STRUCTURE SETUP

### Step 1: Create Project Directory
```powershell
cd C:\Users\admin\Desktop\SEM-6\Kubernetes Agent
mkdir component1-agent
cd component1-agent
```

### Step 2: Initialize Go Module
```powershell
go mod init github.com/kubernetes-agent/component1
# Creates go.mod file
```

### Step 3: Create Directory Structure
```powershell
# Core directories
mkdir cmd\agent
mkdir internal\sources
mkdir internal\normalizer
mkdir internal\transport
mkdir internal\config
mkdir proto
mkdir charts\kubernetes-agent\templates
mkdir test
mkdir build

# Create .gitignore
@"
# Binaries
*.exe
*.o
*.a
*.so
bin/
dist/

# Go
vendor/
go.sum

# IDEs
.vscode/
.idea/
*.swp
*.swo

# OS
.DS_Store
Thumbs.db

# Build artifacts
*.docker
.env
.env.local

# Kubernetes
kubeconfig*
"@ | Out-File -FilePath .gitignore -Encoding UTF8
```

### Step 4: Verify Structure
```powershell
tree /L 3

# Should show:
# component1-agent/
# ├── cmd/
# │   └── agent/
# ├── internal/
# │   ├── sources/
# │   ├── normalizer/
# │   ├── transport/
# │   └── config/
# ├── proto/
# ├── charts/
# │   └── kubernetes-agent/
# │       └── templates/
# ├── test/
# ├── build/
# ├── go.mod
# └── .gitignore
```

---

## 📦 INSTALL DEPENDENCIES

### Step 1: Get Go Dependencies
```powershell
# Kubernetes client
go get k8s.io/client-go@v0.28.0
go get k8s.io/api@v0.28.0

# Protocol Buffers
go get google.golang.org/protobuf@v1.31.0
go get google.golang.org/grpc@v1.59.0
go get google.golang.org/grpc/cmd/protoc-gen-go-grpc@v1.3.0

# HTTP client (for Prometheus)
go get github.com/prometheus/client_golang@v1.17.0

# Config parsing
go get github.com/spf13/viper@v1.17.0

# Logging
go get go.uber.org/zap@v1.26.0

# Testing
go get github.com/stretchr/testify@v1.8.4
```

### Step 2: Verify Dependencies
```powershell
go mod tidy
go mod verify

# Check go.mod and go.sum
cat go.mod | head -20
```

---

## 🔧 INSTALL PROTOBUF COMPILER

### Option 1: Using Chocolatey (Windows)
```powershell
choco install protoc
protoc --version
# Expected: libprotoc 3.21.x
```

### Option 2: Manual Installation (Any OS)
1. Download from: https://github.com/protocolbuffers/protobuf/releases
2. Extract and add to PATH
3. Verify: `protoc --version`

### Option 3: Using Go (Recommended for Go projects)
```powershell
go install github.com/protocolbuffers/protobuf/cmd/protoc-gen-go@latest
go install google.golang.org/grpc/cmd/protoc-gen-go-grpc@latest

# Add to PATH if needed
$env:PATH += ";$env:GOPATH\bin"
```

---

## 🐳 DOCKER SETUP

### Create Dockerfile
**File**: `Dockerfile`
```dockerfile
FROM golang:1.21-alpine AS builder

WORKDIR /app

# Copy go mod files
COPY go.mod go.sum ./

# Download dependencies
RUN go mod download

# Copy source
COPY . .

# Build
RUN CGO_ENABLED=0 GOOS=linux go build -a -installsuffix cgo -o agent ./cmd/agent

# Final image
FROM alpine:3.18

RUN apk --no-cache add ca-certificates

WORKDIR /root/

COPY --from=builder /app/agent .

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD ["/root/agent", "-health"]

ENTRYPOINT ["/root/agent"]
```

### Create Docker Build Script
**File**: `build/docker-build.sh` (or `.ps1` for Windows)
```powershell
# build/docker-build.ps1
param(
    [string]$Version = "0.1.0"
)

docker build -t kubernetes-agent:$Version -f Dockerfile .
docker tag kubernetes-agent:$Version kubernetes-agent:latest

Write-Host "Docker image built: kubernetes-agent:$Version"
```

**Usage**:
```powershell
.\build\docker-build.ps1 -Version "0.1.0"
```

---

## ⚙️ GO PROJECT SCAFFOLDING

### Create Main Entry Point
**File**: `cmd/agent/main.go`
```go
package main

import (
	"flag"
	"fmt"
	"log"
)

var (
	configPath = flag.String("config", "config.yaml", "Path to config file")
	health     = flag.Bool("health", false, "Run health check")
	version    = flag.Bool("version", false, "Print version")
)

const Version = "0.1.0"

func main() {
	flag.Parse()

	if *version {
		fmt.Printf("kubernetes-agent v%s\n", Version)
		return
	}

	if *health {
		log.Println("OK")
		return
	}

	log.Printf("Starting kubernetes-agent v%s\n", Version)
	log.Printf("Config: %s\n", *configPath)

	// TODO: Load config
	// TODO: Initialize sources
	// TODO: Start collection loop
}
```

### Create Interfaces
**File**: `internal/sources/source.go`
```go
package sources

import (
	"context"
)

type Source interface {
	Name() string
	IsAvailable(ctx context.Context) bool
	Collect(ctx context.Context) (interface{}, error)
	Close() error
}
```

---

## 🧪 LOCAL KUBERNETES CLUSTER

### Option 1: Minikube
```powershell
# Start cluster
minikube start --cpus 4 --memory 8192 --disk-size 30GB

# Verify
kubectl get nodes
kubectl get pods --all-namespaces

# Stop
minikube stop
```

### Option 2: Kind (Kubernetes in Docker)
```powershell
# Create cluster
kind create cluster --name k8s-test

# Verify
kubectl cluster-info

# Delete
kind delete cluster --name k8s-test
```

### Option 3: Docker Desktop Kubernetes
1. Open Docker Desktop settings
2. Enable Kubernetes
3. Verify: `kubectl cluster-info`

---

## 📝 CONFIGURATION FILE

### Create `config.yaml`
```yaml
agent:
  cluster_name: "local-test"
  namespace: "kube-system"
  log_level: "info"

sources:
  kubernetes:
    enabled: true
    api_server: "https://kubernetes.default.svc.cluster.local"
    
  prometheus:
    enabled: true
    url: "http://prometheus:9090"
    scrape_interval: 30s
    query_timeout: 10s
    
  kubelet:
    enabled: true
    port: 10250
    
  logs:
    enabled: false
    # TODO: Log source config
    
normalization:
  dedup_window_seconds: 30
  custom_metric_mappings: {}

transport:
  backend_url: "http://localhost:8081"
  auth_token: "test-token"
  send_interval_seconds: 30
  batch_size: 100
  max_retries: 3
```

---

## 🚀 BUILD COMMANDS

### Create Makefile (Optional but Recommended)
**File**: `Makefile`
```makefile
.PHONY: build run test clean docker-build lint

VERSION := 0.1.0
BINARY := agent

build:
	go build -o bin/$(BINARY) ./cmd/agent

run: build
	./bin/$(BINARY) -config config.yaml

test:
	go test -v -race -coverprofile=coverage.out ./...

cover: test
	go tool cover -html=coverage.out

lint:
	golangci-lint run ./...

clean:
	rm -rf bin/
	rm -f coverage.out

proto:
	protoc --go_out=. --go-grpc_out=. proto/*.proto

docker-build:
	docker build -t kubernetes-agent:$(VERSION) -f Dockerfile .

docker-run:
	docker run -it kubernetes-agent:$(VERSION)
```

**Usage**:
```powershell
make build
make test
make docker-build
```

---

## ✅ FINAL VERIFICATION

Run this checklist to confirm setup is complete:

```powershell
# 1. Go environment
go env | grep GOPATH
go version

# 2. Project structure
ls cmd/agent/
ls internal/sources/
ls proto/

# 3. Dependencies
go list -m all

# 4. Docker
docker --version

# 5. Kubernetes
kubectl version --client

# 6. Helm
helm version

# 7. Protobuf
protoc --version

# 8. Build test
go build -o bin/agent ./cmd/agent
ls bin/agent
```

All should succeed without errors ✅

---

## 📚 NEXT STEPS

1. **Run this setup guide** (should take 30 minutes)
2. **Verify all checks pass**
3. **Start with Week 1 of DEVELOPMENT_ROADMAP.md**
   - Create proto schema
   - Build K8s client wrapper
   - Implement topology discovery
4. **Test locally** with minikube/kind cluster

---

## 🆘 TROUBLESHOOTING

### Problem: `go: command not found`
**Solution**: Go not installed or not in PATH
```powershell
# Check installation
where.exe go

# Add to PATH if needed
$env:PATH += ";C:\Users\<user>\go\bin"
```

### Problem: `docker: command not found`
**Solution**: Docker not installed or Docker Desktop not running
```powershell
# Verify Docker Desktop running
docker ps

# If fails, start Docker Desktop (look for Docker icon in System Tray)
```

### Problem: `kubectl: command not found`
**Solution**: kubectl not installed
```powershell
# Install via Chocolatey
choco install kubernetes-cli

# Or download binary from https://kubernetes.io/docs/tasks/tools/
```

### Problem: `protoc: command not found`
**Solution**: protoc not installed or not in PATH
```powershell
# Verify installation
where.exe protoc

# If not found, install via package manager or add to PATH
```

### Problem: Go module conflicts
**Solution**: Clean and re-sync
```powershell
go clean -modcache
go mod tidy
go mod download
```

---

## 📖 RECOMMENDED READINGS

- **Go Modules**: https://golang.org/doc/tutorial/create-module
- **Kubernetes Client-Go**: https://github.com/kubernetes/client-go
- **Protocol Buffers**: https://developers.google.com/protocol-buffers
- **gRPC**: https://grpc.io/docs/languages/go/
- **Helm**: https://helm.sh/docs/intro/quickstart/

---

## 🎯 ONCE SETUP IS COMPLETE

✅ You're ready to start **Week 1** of Component 1 development!

Proceed to: `DEVELOPMENT_ROADMAP.md` → Week 1 Plan

