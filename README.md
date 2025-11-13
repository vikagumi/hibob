# Python API — GitOps Workflow (Dev → Stage → Prod)

This repository demonstrates a complete GitOps delivery pipeline for a Python API using FastAPI, Docker, Helm, Argo CD, Prometheus Operator, and GitHub Actions. The same image digest is promoted across all environments without rebuilding the image.

---

## Running the API Locally

The API can be started in a local Python environment. Dependencies are installed from a requirements file, and the application is launched using a local ASGI server. Automated tests validate the core functionality before any build or deployment happens.

```console
cd py-api
python3 -m venv .venv
source .venv/bin/activate
pip install -r app/requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Run local tests

```console
python -m pytest -q app/tests
```

Local endpoints available during development:
- A health check endpoint - /healthz
- A work endpoint for normal responses - /work 
- A work endpoint that can intentionally fail - /work?fail=true
- A metrics endpoint that exposes Prometheus-compatible metrics - /metrics 

These endpoints confirm functional behavior and metrics instrumentation before deploying to Kubernetes.

---

## Kubernetes Deployment with Kind

A local Kubernetes cluster is created using Kind.  
Argo CD is installed into its own namespace and used to manage deployments for three environments:

- Development  
- Staging  
- Production  

Each environment is deployed through Argo CD Applications that point to specific Helm value files inside this repository.

Argo CD continuously monitors Git changes and automatically syncs any updates to the cluster.

Commands to run :
```console
kind create cluster --name py-api --config kind-config.yaml
kubectl create namespace argocd
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
cd py-api/argocd
kubectl apply -f .
```


---

## Helm Chart Structure

The repository contains one shared Helm chart used by all environments.  
Each environment overrides only its specific settings through separate values files.

The structure includes:
- A central chart defining the Deployment, Service, ServiceMonitor, and PrometheusRule  
- A values file for shared defaults  
- A folder with environment-specific value overrides for development, staging, and production  

This structure ensures consistency while supporting configuration drift between environments.

---

## CI/CD Workflow Overview
### 🔐 Required GitHub Secrets

| Secret Name         | Description |
|---------------------|-------------|
| **DOCKERHUB_USERNAME** | Your Docker Hub username. |
| **DOCKERHUB_TOKEN**    | Docker Hub Access Token (created in Docker Hub → Security → Access Tokens). |
| **PR_PAT**             | GitHub Personal Access Token with permissions: Contents (RW), Pull Requests (RW), Metadata (RO). |

The GitHub Actions pipeline is split into three logical workflows:

### 1. Build and Update Development
- Installs dependencies  
- Lints the code  
- Runs tests  
- Builds a Docker image  
- Pushes the image to Docker Hub  
- Extracts the container image digest  
- Updates the development environment values file with the digest  
- Argo CD automatically deploys the update to development  

### 2. Promote Development to Staging
- Triggered only when the development pipeline succeeds  
- Reads the digest deployed to development  
- Writes the same digest into the staging environment values  
- Opens a pull request containing the promotion change  

### 3. Promote Staging to Production
- Triggered only when the staging pull request is merged  
- Reads the digest assigned to staging  
- Updates the production environment values with the same digest  
- Opens a pull request promoting the change to production  

This guarantees that development, staging, and production are all running the same exact artifact.

---

## Prometheus Observability

Prometheus Operator provides:
- A ServiceMonitor to scrape application metrics  
- A PrometheusRule that calculates error rates and triggers alerts  
- Automated discovery based on Kubernetes labels  

Each environment exposes its own metrics through the same instrumentation, allowing consistent monitoring.  
The Prometheus UI shows targets for the currently deployed environment and reflects the active ServiceMonitor configuration.

---

## Acceptance Criteria

This project meets all required acceptance checks:

### 1. The health and metrics endpoints return valid responses in every environment.  

```console
kubectl port-forward svc/py-api -n dev 8000:8000
curl -i http://localhost:8000/healthz
curl -s http://localhost:8000/metrics | head
```
```console
kubectl port-forward svc/py-api -n stage 8001:8000
curl -i http://localhost:8000/healthz
curl -s http://localhost:8000/metrics | head
```
```console
kubectl port-forward svc/py-api -n prod 8002:8000
curl -i http://localhost:8000/healthz
curl -s http://localhost:8000/metrics | head
```
### 2. Prometheus successfully scrapes the application metrics for the active environment.  
```console
kubectl port-forward svc/kube-prometheus-stack-prometheus -n monitoring 9090:9090
```
To confirm that Prometheus is scraping the application for the currently active environment, open the Prometheus UI and check the scrape targets page. The application should appear as an active scrape target, and its status must be reported as "UP". This indicates that Prometheus is successfully reaching the `/metrics` endpoint exposed by the application.

After verifying that the target is active, use the Prometheus query interface to search for metrics such as `http_requests_total` or `http_errors_total`. These metrics should appear with labels that match the environment (dev, stage, or prod), confirming that Prometheus has collected the data.
### 3. The same image digest progresses from development to staging to production with no rebuilds.
To confirm that the same image digest is used in dev → stage → prod without rebuilding, check that each environment’s values file contains the **exact same digest**. After merging the promotion PRs, the digest in staging and production must match the one originally written to development.

Argo CD will also show this digest in each Application view. If all three environments display the same digest, the promotion flow is correct and no new image was built.  
### 4. CI/CD pipelines build the image, update development, and automatically generate pull requests for staging and production promotions.  
To confirm that CI/CD works correctly:

1. Push a new commit to `main`.  
   GitHub Actions should automatically:
   - run tests and linting,
   - build and push the new container image,
   - update the **dev** environment with the new image digest.

2. After the dev update succeeds, a **promotion PR** should be automatically created for the **stage** environment.  
   Once you merge it, another **auto-generated PR** should appear for **prod**.

If both promotion PRs show the same digest and each merge updates the correct environment, the CI/CD workflow is functioning as required.

## 📊 Prometheus Observability & PromQL Documentation

This project includes built-in observability using Prometheus. The API exposes a `/metrics` endpoint with request counters and error counters, and Prometheus scrapes these metrics using a `ServiceMonitor`. This section documents the **exact PromQL** used for monitoring and alerting.

---

##  PromQL Queries Used

### **1. 5xx Error Rate (raw query)**  
Calculates the rate of HTTP 5xx responses over the last 5 minutes:

```promql
sum(rate(http_requests_total{status=~"5.."}[5m]))
```
### **2. Total Request Rate (raw query)
Calculates the rate of all HTTP requests over the last 5 minutes:
```promql
sum(rate(http_requests_total[5m]))
```

### **3. Error Ratio (recording rule)
This ratio is used to determine overall error behavior. It divides 5xx request rate by the total request rate:
```promql
sum(rate(http_requests_total{status=~"5.."}[5m]))
/
sum(rate(http_requests_total[5m]))
```
### **4. Recorded Metric Name
Prometheus stores the final computed ratio under the following time-series name:
```promql
py_api:http_error_rate:ratio
```