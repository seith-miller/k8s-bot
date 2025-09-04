# Kubernetes External IP Pending Issue Recreation

This repository contains all files needed to reproduce the "external IP pending" issue with Kubernetes LoadBalancer services.

## Files Included

- `deployment.yaml` - Nginx deployment with 3 replicas
- `service.yaml` - LoadBalancer service that will show pending external IP
- `setup.sh` - Automated setup script

## Prerequisites

- Docker
- minikube
- kubectl

## Quick Start

1. Make the setup script executable:
   ```bash
   chmod +x setup.sh
   ```

2. Run the setup script:
   ```bash
   ./setup.sh
   ```

## Manual Setup

If you prefer manual setup:

1. Start minikube:
   ```bash
   minikube start
   ```

2. Apply the deployment:
   ```bash
   kubectl apply -f deployment.yaml
   ```

3. Apply the service:
   ```bash
   kubectl apply -f service.yaml
   ```

## Verifying the Issue

Check the service status:
```bash
kubectl get svc nginx-ils-service
```

Expected output showing pending external IP:
```
NAME                TYPE           CLUSTER-IP     EXTERNAL-IP   PORT(S)        AGE
nginx-ils-service   LoadBalancer   10.96.x.x      <pending>     80:30062/TCP   30s
```

## Root Cause

The external IP remains pending because:
- Local clusters (minikube, kind) don't have cloud provider load balancer integration
- No load balancer provisioner available to assign external IPs
- Kubernetes can't fulfill the LoadBalancer service request

## Solutions

### Option 1: Use minikube tunnel
```bash
minikube tunnel
```

### Option 2: Access via NodePort
```bash
minikube service nginx-ils-service --url
```

### Option 3: Use port forwarding
```bash
kubectl port-forward service/nginx-ils-service 8080:80
```

### Option 4: Patch with external IP
```bash
kubectl patch svc nginx-ils-service -p '{"spec": {"type": "LoadBalancer", "externalIPs":["$(minikube ip)"]}}'
```

### Option 5: Install MetalLB (for production-like setup)
```bash
kubectl apply -f https://raw.githubusercontent.com/metallb/metallb/v0.13.7/config/manifests/metallb-native.yaml
```

## Cleanup

```bash
kubectl delete -f service.yaml
kubectl delete -f deployment.yaml
minikube delete
```