# install_metrics_server.ps1
# Installs metrics-server for Docker Desktop Kubernetes
# Required for pod/node CPU and memory metrics to be non-zero

Write-Host ""
Write-Host "[1/3] Applying metrics-server manifest..." -ForegroundColor Cyan
kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml

Write-Host ""
Write-Host "[2/3] Patching deployment for Docker Desktop (insecure TLS)..." -ForegroundColor Cyan
kubectl patch deployment metrics-server `
  -n kube-system `
  --type=json `
  -p='[{"op":"add","path":"/spec/template/spec/containers/0/args/-","value":"--kubelet-insecure-tls"}]'

Write-Host ""
Write-Host "[3/3] Waiting for metrics-server to be ready (90s max)..." -ForegroundColor Cyan
kubectl rollout status deployment/metrics-server -n kube-system --timeout=90s

Write-Host ""
Write-Host "Verifying: kubectl top nodes" -ForegroundColor Green
kubectl top nodes

Write-Host ""
Write-Host "Verifying: kubectl top pods --all-namespaces" -ForegroundColor Green
kubectl top pods --all-namespaces

Write-Host ""
Write-Host "Done! Restart server.py so CPU and Memory show real values." -ForegroundColor Green
