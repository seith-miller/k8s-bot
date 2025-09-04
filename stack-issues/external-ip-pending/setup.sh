#!/bin/bash

# Setup script to recreate the "external IP pending" issue
# This script will create a local Kubernetes cluster and deploy the problematic configuration

echo "Setting up Kubernetes cluster to reproduce external IP pending issue..."

# Check if minikube is installed
if ! command -v minikube &> /dev/null; then
    echo "Error: minikube is not installed. Please install minikube first."
    exit 1
fi

# Check if kubectl is installed
if ! command -v kubectl &> /dev/null; then
    echo "Error: kubectl is not installed. Please install kubectl first."
    exit 1
fi

# Start minikube cluster
echo "Starting minikube cluster..."
minikube start --driver=docker

# Wait for cluster to be ready
echo "Waiting for cluster to be ready..."
kubectl wait --for=condition=Ready nodes --all --timeout=300s

# Apply the nginx deployment
echo "Applying nginx deployment..."
kubectl apply -f deployment.yaml

# Wait for deployment to be ready
echo "Waiting for deployment to be ready..."
kubectl wait --for=condition=Available deployment/deployment-example --timeout=300s

# Apply the LoadBalancer service (this will show pending external IP)
echo "Applying LoadBalancer service..."
kubectl apply -f service.yaml

echo ""
echo "Setup complete! The issue should now be visible."
echo ""
echo "To see the pending external IP, run:"
echo "kubectl get svc nginx-ils-service"
echo ""
echo "Expected output:"
echo "NAME                TYPE           CLUSTER-IP     EXTERNAL-IP   PORT(S)                      AGE"
echo "nginx-ils-service   LoadBalancer   10.x.x.x       <pending>     80:30062/TCP                 Xs"
echo ""
echo "To access the service despite pending external IP:"
echo "minikube service nginx-ils-service --url"
echo ""
echo "To fix the pending issue (if needed):"
echo "minikube tunnel"