# Agent Observability & Evaluation Platform

A production-grade backend for capturing, storing, and evaluating traces emitted by AI
agent applications. An instrumented app uses the **Python SDK** to stream traces and span
events over **gRPC** to the **Ingestion Server**, which publishes them onto a **Redis
Stream**; a **Redis Streams Worker** consumes that stream and persists traces into
**PostgreSQL**. Each newly stored trace triggers an **AWS Lambda Evaluator** that performs
LLM-as-judge scoring via **Ollama** and writes evaluation results back to PostgreSQL. A
**FastAPI REST API Server** exposes the traces and their evaluations to clients, while a
nightly **Spark Batch Job** scans all traces for anomalies. Every component is containerized
with **Docker** and deployed together on **Kubernetes (minikube)**, with `docker-compose` and
the Protobuf schema in `proto/` providing the shared contract and local development backbone.

## Architecture

```
                    ┌─────────────┐
   Instrumented     │ Python SDK  │   gRPC (Protobuf)
   AI application──▶ │ AgentTracer │ ───────────────┐
                    └─────────────┘                 ▼
                                          ┌────────────────────┐
                                          │  Ingestion Server  │  async gRPC
                                          │     (grpc.aio)     │
                                          └─────────┬──────────┘
                                                    │ XADD
                                                    ▼
                                          ┌────────────────────┐
                                          │   Redis Stream     │  "traces"
                                          │   (consumer group) │
                                          └─────────┬──────────┘
                                                    │ XREADGROUP
                                                    ▼
                                          ┌────────────────────┐
                                          │   Streams Worker   │  async consumer
                                          │ (asyncpg/SQLAlchemy)│
                                          └─────────┬──────────┘
                                                    │ INSERT
                                                    ▼
   ┌────────────────────┐  read/write    ┌────────────────────┐
   │  Spark Batch Job   │ ◀────JDBC─────▶ │     PostgreSQL     │
   │ (nightly anomaly   │                 │ traces/evaluations │
   │   detection)       │                 │     /anomalies     │
   └────────────────────┘                 └─────────┬──────────┘
                                            ▲        │
                            psycopg2 write  │        │ asyncpg read
                                            │        ▼
                          ┌─────────────────┴──┐  ┌────────────────────┐
                          │  Lambda Evaluator  │  │   REST API Server  │
                          │ (LLM-as-judge via  │◀─│      (FastAPI)     │
                          │      Ollama)       │  │  /traces /stats    │
                          └────────────────────┘  └────────────────────┘
```

## Skills Demonstrated

| Skill          | Where it lives in this project                                        |
| -------------- | -------------------------------------------------------------------- |
| **gRPC**       | SDK → ingestion server streaming (`sdk/`, `ingestion-server/`)        |
| **REST**       | External query API for traces, evaluations, and stats (`api-server/`) |
| **Protobuf**   | `Trace` / `SpanEvent` schema and service contract (`proto/`)          |
| **Redis**      | Stream + consumer group between ingestion and worker                  |
| **PostgreSQL** | Trace, evaluation, and anomaly storage (SQLAlchemy + Alembic)         |
| **Async Python** | `grpc.aio` ingestion server and async Redis/DB worker              |
| **Docker**     | Every service containerized (`*/Dockerfile`, `docker-compose.yml`)    |
| **Kubernetes** | Full minikube deployment with ConfigMap/Secret/PVC (`k8s/`)          |
| **AWS Lambda** | Serverless LLM-as-judge evaluator (`evaluator/handler.py`)           |
| **Spark**      | Nightly statistical anomaly detection over all traces (`spark-jobs/`) |
| **ML domain**  | LLM-as-judge scoring + mean/stddev anomaly scoring                    |

## Repository Layout

| Path                | Description                                                        |
| ------------------- | ------------------------------------------------------------------ |
| `proto/`            | Protobuf schema (`trace.proto`) and stub generation script         |
| `ingestion-server/` | gRPC server receiving traces from the SDK                          |
| `sdk/`              | Python SDK that instruments an app and sends traces                |
| `worker/`           | Redis Streams consumer that writes traces to PostgreSQL            |
| `evaluator/`        | AWS Lambda LLM-as-judge evaluator (Ollama)                         |
| `api-server/`       | FastAPI REST API exposing traces and evaluation results            |
| `spark-jobs/`       | Nightly Spark anomaly-detection batch job                          |
| `k8s/`              | Kubernetes manifests for minikube deployment                       |
| `docker-compose.yml`| Local infrastructure: PostgreSQL, Redis, Ollama                    |

## Getting Started

```bash
# Install Python dependencies
pip install -r requirements.txt

# Generate gRPC stubs from the Protobuf schema
bash proto/generate.sh

# Start local infrastructure (PostgreSQL, Redis, Ollama)
docker compose up -d
```
