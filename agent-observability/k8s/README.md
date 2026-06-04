# Kubernetes Deployment (minikube)

Manifests to deploy the Agent Observability & Evaluation Platform into the
`observability` namespace on minikube. Custom service images use
`imagePullPolicy: Never`, so they must be **built into minikube's Docker daemon** before
deploying (no registry push needed).

## 1. Start minikube

```bash
minikube start
```

## 2. Build the custom images inside minikube's Docker daemon

Point your shell's Docker client at minikube, then build each image with the tag the
manifests expect:

```bash
eval $(minikube docker-env)

# Run from the repository root (agent-observability/)
docker build -t agentobs-ingestion-server:latest ./ingestion-server
docker build -t agentobs-worker:latest ./worker
docker build -t agentobs-api-server:latest -f api-server/Dockerfile .
```

> The api-server image is built from the repo root because it bundles the evaluator
> package (used by the inline `POST /traces/{id}/evaluate` endpoint).

## 3. Apply the manifests, in order

```bash
# Namespace first
kubectl apply -f k8s/namespace.yaml

# Shared config + secret
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/secret.yaml

# Stateful / infra dependencies
kubectl apply -f k8s/postgres-pvc.yaml
kubectl apply -f k8s/postgres-deployment.yaml
kubectl apply -f k8s/postgres-service.yaml
kubectl apply -f k8s/redis-deployment.yaml
kubectl apply -f k8s/redis-service.yaml
kubectl apply -f k8s/ollama-deployment.yaml
kubectl apply -f k8s/ollama-service.yaml

# Application services
kubectl apply -f k8s/ingestion-server-deployment.yaml
kubectl apply -f k8s/ingestion-server-service.yaml
kubectl apply -f k8s/worker-deployment.yaml
kubectl apply -f k8s/api-server-deployment.yaml
kubectl apply -f k8s/api-server-service.yaml
```

Or apply the whole directory at once (kubectl resolves ordering by kind well enough,
though you may need to re-apply if dependencies aren't ready):

```bash
kubectl apply -f k8s/
```

## 4. Verify

```bash
kubectl get pods -n observability
kubectl get svc -n observability
```

## 5. Access the API server

The api-server is exposed as a NodePort service:

```bash
minikube service api-server -n observability --url
# then, e.g.
curl "$(minikube service api-server -n observability --url)/stats"
```

## 6. Pull an Ollama model (for the evaluator)

```bash
kubectl exec -n observability deploy/ollama -- ollama pull llama3
```

## Notes / caveats

- **Run DB migrations** before relying on the worker/api: exec into the worker pod and
  run Alembic (`alembic upgrade head`) or let `init_db` create tables on first run.
- **`DATABASE_URL` driver suffix.** The secret stores the `postgresql+asyncpg://` form so
  the worker's async SQLAlchemy engine works. Both the api-server (asyncpg) and the evaluator
  (psycopg2) strip the `+asyncpg` suffix at startup, so the single secret works everywhere.
- **Ollama models are ephemeral here** (`emptyDir`); add a PVC if you want them to persist
  across pod restarts.
