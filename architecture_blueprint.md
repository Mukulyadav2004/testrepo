# Traceroot.ai Complete Architecture Blueprint

> **Purpose**: Definitive schema for self-hosted implementation with all OSS + closed-source components mapped.
> **Status**: Implementation roadmap — each node has file path, inputs, outputs, and connection points.

---

## Table of Contents
1. [System Overview](#system-overview)
2. [Complete Pipeline Diagram](#complete-pipeline-diagram)
3. [Layer-by-Layer Specification](#layer-by-layer-specification)
4. [Intelligence Layer Specification (TO BUILD)](#intelligence-layer-specification-to-build)
5. [Data Structures Reference](#data-structures-reference)
6. [File Dependency Graph](#file-dependency-graph)
7. [Implementation Checklist](#implementation-checklist)

---

## System Overview

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           TRACEROOT COMPLETE SYSTEM                              │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│   ┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐      │
│   │  INGEST │───▶│  BUILD  │───▶│ INTEL   │───▶│ REASON  │───▶│ PERSIST │      │
│   │         │    │  TREE   │    │ LAYER   │    │  (LLM)  │    │         │      │
│   └─────────┘    └─────────┘    └─────────┘    └─────────┘    └─────────┘      │
│       ✅            ✅            🔴 BUILD       ✅             🟡 EE           │
│                                                                                  │
│   ✅ = Open Source (have)                                                        │
│   🟡 = Enterprise Edition (stub exists, need real impl)                          │
│   🔴 = Intelligence Layer (must build from scratch)                              │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### Component Status Matrix

| Component | Status | Files | Effort |
|-----------|--------|-------|--------|
| HTTP Layer | ✅ Complete | `rest/app.py`, `rest/routers/*.py` | - |
| Telemetry Fetch | ✅ Complete (Jaeger) | `rest/service/trace/jaeger_trace_client.py` | - |
| Tree Building | ✅ Complete | `rest/agent/context/tree.py` | - |
| Agent Routing | ✅ Complete | `rest/agent/router.py` | - |
| Feature Selection | ✅ Complete | `rest/agent/filter/feature.py` | - |
| Structure Filtering | ✅ Complete | `rest/agent/filter/structure.py` | - |
| Context Chunking | ✅ Complete | `rest/agent/chunk/sequential.py` | - |
| LLM Reasoning | ✅ Complete | `rest/agent/agents/single_rca_agent.py` | - |
| Chunk Summarization | ✅ Complete | `rest/agent/summarizer/chunk.py` | - |
| **Semantic Classifier** | 🔴 TO BUILD | `rest/intel/classifier.py` | Medium |
| **Noise Suppressor** | 🔴 TO BUILD | `rest/intel/suppressor.py` | Medium |
| **Failure Locator** | 🔴 TO BUILD | `rest/intel/locator.py` | High |
| **Cause Ranker** | 🔴 TO BUILD | `rest/intel/ranker.py` | High |
| **Pattern Library** | 🔴 TO BUILD | `rest/intel/patterns/` | High |
| **Context Compressor** | 🔴 TO BUILD | `rest/intel/compressor.py` | Medium |
| **Evaluation Loop** | 🔴 TO BUILD | `rest/intel/evaluator.py` | Medium |
| MongoDB DAO | 🟡 Need Real Impl | `rest/dao/ee/mongodb_dao.py` | Medium |
| AWS Clients | 🟡 Need Real Impl | `rest/service/*/ee/aws_*.py` | Medium |

---

## Complete Pipeline Diagram

```
═══════════════════════════════════════════════════════════════════════════════════
                              COMPLETE REQUEST FLOW
═══════════════════════════════════════════════════════════════════════════════════

USER REQUEST
     │
     │  POST /v1/explore/post-chat
     │  {
     │    message: "Why is this trace slow?",
     │    trace_id: "abc-123",
     │    model: "gpt-4o",
     │    mode: "agent"
     │  }
     │
     ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│  STAGE 0: HTTP ENTRY                                                             │
│  ════════════════════                                                            │
│  File: rest/app.py → rest/routers/chat.py                                       │
│  Class: ChatRouterClass                                                          │
│  Method: post_chat()                                                             │
│                                                                                  │
│  INPUT:  ChatRequest                                                             │
│  OUTPUT: Forwards to ChatLogic.post_chat()                                       │
│  STATUS: ✅ COMPLETE                                                             │
└─────────────────────────────────────────────────────────────────────────────────┘
     │
     ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│  STAGE 1: TELEMETRY FETCH                                                        │
│  ═════════════════════════                                                       │
│  File: rest/driver/chat_logic.py                                                │
│  Class: ChatLogic                                                                │
│  Method: post_chat() lines 150-200                                              │
│                                                                                  │
│  SUBSTEP 1A: Get Trace                                                           │
│  ─────────────────────────────────────────────────────────────────────────────  │
│  │  observe_provider.trace_client.get_trace(trace_id, start_time, end_time)    │
│  │                                                                              │
│  │  File: rest/service/trace/jaeger_trace_client.py  (✅ OSS)                   │
│  │     OR rest/service/trace/ee/aws_trace_client.py  (🟡 EE)                    │
│  │                                                                              │
│  │  INPUT:  trace_id: str, start_time: datetime, end_time: datetime            │
│  │  OUTPUT: Trace {                                                             │
│  │            id: str,                                                          │
│  │            start_time: float,                                                │
│  │            end_time: float,                                                  │
│  │            duration: float,                                                  │
│  │            spans: list[Span]                                                 │
│  │          }                                                                   │
│  ─────────────────────────────────────────────────────────────────────────────  │
│                                                                                  │
│  SUBSTEP 1B: Get Logs                                                            │
│  ─────────────────────────────────────────────────────────────────────────────  │
│  │  observe_provider.log_client.get_logs_by_trace_id(trace_id, ...)            │
│  │                                                                              │
│  │  File: rest/service/log/jaeger_log_client.py  (✅ OSS)                       │
│  │     OR rest/service/log/ee/aws_log_client.py  (🟡 EE)                        │
│  │                                                                              │
│  │  INPUT:  trace_id: str, span_ids: list[str], start_time, end_time           │
│  │  OUTPUT: TraceLogs {                                                         │
│  │            trace_id: str,                                                    │
│  │            logs: list[dict[span_id, list[LogEntry]]]                         │
│  │          }                                                                   │
│  │                                                                              │
│  │  LogEntry {                                                                  │
│  │    time: float,                                                              │
│  │    level: str,           # DEBUG, INFO, WARNING, ERROR, CRITICAL            │
│  │    message: str,                                                             │
│  │    file_name: str,                                                           │
│  │    function_name: str,                                                       │
│  │    line_number: int,                                                         │
│  │    line: str,            # actual source code line                          │
│  │    lines_above: list[str],                                                   │
│  │    lines_below: list[str]                                                    │
│  │  }                                                                           │
│  ─────────────────────────────────────────────────────────────────────────────  │
│                                                                                  │
│  STATUS: ✅ COMPLETE (Jaeger) / 🟡 EE (AWS/Tencent)                              │
└─────────────────────────────────────────────────────────────────────────────────┘
     │
     │  Trace + TraceLogs
     │
     ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│  STAGE 2: TREE CONSTRUCTION                                                      │
│  ═══════════════════════════                                                     │
│  File: rest/agent/context/tree.py                                               │
│  Function: build_heterogeneous_tree(span, trace_logs)                           │
│                                                                                  │
│  INTERNAL FLOW:                                                                  │
│  ─────────────────────────────────────────────────────────────────────────────  │
│  │  1. create_logs_map(trace_logs)                                             │
│  │     INPUT:  list[dict[span_id, list[LogEntry]]]                             │
│  │     OUTPUT: dict[span_id → list[LogEntry]]  (flattened lookup)              │
│  │                                                                              │
│  │  2. convert_span_to_span_node(span, logs_map)  [RECURSIVE]                  │
│  │     INPUT:  Span, logs_map                                                   │
│  │     OUTPUT: SpanNode                                                         │
│  │                                                                              │
│  │     For each span:                                                           │
│  │       a. Get logs from logs_map[span.id]                                    │
│  │       b. Convert each LogEntry → LogNode                                     │
│  │       c. Sort logs by timestamp                                              │
│  │       d. Recursively convert child spans                                     │
│  │       e. Sort children by start_time                                         │
│  │       f. Return SpanNode                                                     │
│  ─────────────────────────────────────────────────────────────────────────────  │
│                                                                                  │
│  INPUT:  Span (root), TraceLogs                                                  │
│  OUTPUT: SpanNode (hierarchical tree with logs attached)                         │
│                                                                                  │
│  STATUS: ✅ COMPLETE                                                             │
└─────────────────────────────────────────────────────────────────────────────────┘
     │
     │  SpanNode (RAW TREE)
     │
     │
     ▼
╔═════════════════════════════════════════════════════════════════════════════════╗
║                                                                                  ║
║  ██████████████████████████████████████████████████████████████████████████████  ║
║  █                                                                            █  ║
║  █   STAGE 3: INTELLIGENCE LAYER  (🔴 TO BUILD)                               █  ║
║  █                                                                            █  ║
║  ██████████████████████████████████████████████████████████████████████████████  ║
║                                                                                  ║
║  This is where the 10x speed advantage comes from.                               ║
║  INSERT BETWEEN: Tree Construction → Agent Routing                               ║
║                                                                                  ║
║  File: rest/driver/chat_logic.py (modify post_chat method)                      ║
║  New Package: rest/intel/                                                        ║
║                                                                                  ║
║  ┌────────────────────────────────────────────────────────────────────────────┐ ║
║  │                                                                            │ ║
║  │  SpanNode (raw)                                                            │ ║
║  │       │                                                                    │ ║
║  │       ▼                                                                    │ ║
║  │  ┌─────────────────────────────────────────────────────────────────────┐  │ ║
║  │  │  STEP 3.1: SEMANTIC CLASSIFICATION                                  │  │ ║
║  │  │  ═══════════════════════════════════════                            │  │ ║
║  │  │  File: rest/intel/classifier.py                                     │  │ ║
║  │  │  Function: classify_spans(tree: SpanNode) → ClassifiedTree          │  │ ║
║  │  │                                                                     │  │ ║
║  │  │  PURPOSE: Label each span with semantic type                        │  │ ║
║  │  │                                                                     │  │ ║
║  │  │  INPUT:  SpanNode (raw tree)                                        │  │ ║
║  │  │  OUTPUT: SpanNode with added field:                                 │  │ ║
║  │  │          span_type: SpanType enum                                   │  │ ║
║  │  │                                                                     │  │ ║
║  │  │  SPAN TYPES (enum):                                                 │  │ ║
║  │  │    - LLM_CALL          (OpenAI, Anthropic, etc.)                    │  │ ║
║  │  │    - DB_QUERY          (SQL, MongoDB, Redis)                        │  │ ║
║  │  │    - HTTP_REQUEST      (external API calls)                         │  │ ║
║  │  │    - HTTP_HANDLER      (incoming request handling)                  │  │ ║
║  │  │    - QUEUE_PUBLISH     (Kafka, RabbitMQ, SQS)                        │  │ ║
║  │  │    - QUEUE_CONSUME     (message consumption)                        │  │ ║
║  │  │    - CACHE_OP          (Redis, Memcached)                           │  │ ║
║  │  │    - FILE_IO           (disk operations)                            │  │ ║
║  │  │    - RETRY_LOOP        (retry logic)                                │  │ ║
║  │  │    - HEALTH_CHECK      (k8s probes, heartbeats)                     │  │ ║
║  │  │    - INSTRUMENTATION   (tracing overhead)                           │  │ ║
║  │  │    - BUSINESS_LOGIC    (application code)                           │  │ ║
║  │  │    - UNKNOWN                                                        │  │ ║
║  │  │                                                                     │  │ ║
║  │  │  CLASSIFICATION LOGIC:                                              │  │ ║
║  │  │    1. Pattern match on span.func_full_name                          │  │ ║
║  │  │       - "openai" / "anthropic" → LLM_CALL                           │  │ ║
║  │  │       - "sqlalchemy" / "psycopg" → DB_QUERY                         │  │ ║
║  │  │       - "requests" / "httpx" / "aiohttp" → HTTP_REQUEST             │  │ ║
║  │  │    2. Pattern match on log messages                                 │  │ ║
║  │  │       - "SELECT" / "INSERT" / "UPDATE" → DB_QUERY                   │  │ ║
║  │  │       - "retry" / "attempt" → RETRY_LOOP                            │  │ ║
║  │  │    3. Duration heuristics                                           │  │ ║
║  │  │       - < 1ms with no children → INSTRUMENTATION                    │  │ ║
║  │  │    4. Fallback to BUSINESS_LOGIC                                    │  │ ║
║  │  │                                                                     │  │ ║
║  │  │  IMPLEMENTATION: Rule-based (fast) + optional LLM fallback          │  │ ║
║  │  └─────────────────────────────────────────────────────────────────────┘  │ ║
║  │       │                                                                    │ ║
║  │       ▼                                                                    │ ║
║  │  ┌─────────────────────────────────────────────────────────────────────┐  │ ║
║  │  │  STEP 3.2: NOISE SUPPRESSION                                        │  │ ║
║  │  │  ═══════════════════════════════════                                │  │ ║
║  │  │  File: rest/intel/suppressor.py                                     │  │ ║
║  │  │  Function: suppress_noise(tree: SpanNode) → SpanNode                │  │ ║
║  │  │                                                                     │  │ ║
║  │  │  PURPOSE: Remove uninformative spans to reduce context size         │  │ ║
║  │  │                                                                     │  │ ║
║  │  │  INPUT:  SpanNode (classified)                                      │  │ ║
║  │  │  OUTPUT: SpanNode (pruned, with suppression metadata)               │  │ ║
║  │  │                                                                     │  │ ║
║  │  │  SUPPRESSION RULES:                                                 │  │ ║
║  │  │    1. HEALTH_CHECK spans → REMOVE entirely                          │  │ ║
║  │  │    2. INSTRUMENTATION spans → REMOVE entirely                       │  │ ║
║  │  │    3. Spans with duration < 1ms AND no errors → COLLAPSE            │  │ ║
║  │  │    4. Repeated identical spans → DEDUPLICATE with count             │  │ ║
║  │  │       e.g., 100x "redis.get" → single node with count: 100          │  │ ║
║  │  │    5. Successful subtrees (no errors) → SUMMARIZE                   │  │ ║
║  │  │       e.g., 50 successful DB queries → "50 DB queries (all OK)"     │  │ ║
║  │  │                                                                     │  │ ║
║  │  │  PRESERVE (never suppress):                                         │  │ ║
║  │  │    - Spans with ERROR/CRITICAL logs                                 │  │ ║
║  │  │    - Spans with duration > P95 (latency anomaly)                    │  │ ║
║  │  │    - Root span and direct children                                  │  │ ║
║  │  │    - LLM_CALL spans (always interesting)                            │  │ ║
║  │  │                                                                     │  │ ║
║  │  │  OUTPUT METADATA:                                                   │  │ ║
║  │  │    suppressed_count: int    # how many spans removed                │  │ ║
║  │  │    collapsed_count: int     # how many spans collapsed              │  │ ║
║  │  │    original_span_count: int # for compression ratio                 │  │ ║
║  │  └─────────────────────────────────────────────────────────────────────┘  │ ║
║  │       │                                                                    │ ║
║  │       ▼                                                                    │ ║
║  │  ┌─────────────────────────────────────────────────────────────────────┐  │ ║
║  │  │  STEP 3.3: FAILURE LOCALITY DETECTION                               │  │ ║
║  │  │  ═════════════════════════════════════════                          │  │ ║
║  │  │  File: rest/intel/locator.py                                        │  │ ║
║  │  │  Function: locate_failures(tree: SpanNode) → FailureReport          │  │ ║
║  │  │                                                                     │  │ ║
║  │  │  PURPOSE: Find the root cause span(s) in the trace                  │  │ ║
║  │  │                                                                     │  │ ║
║  │  │  INPUT:  SpanNode (classified, pruned)                              │  │ ║
║  │  │  OUTPUT: FailureReport {                                            │  │ ║
║  │  │            failure_spans: list[FailureSpan],                        │  │ ║
║  │  │            failure_chains: list[FailureChain],                      │  │ ║
║  │  │            root_cause_candidates: list[SpanNode]                    │  │ ║
║  │  │          }                                                          │  │ ║
║  │  │                                                                     │  │ ║
║  │  │  FailureSpan {                                                      │  │ ║
║  │  │    span: SpanNode,                                                  │  │ ║
║  │  │    failure_type: FailureType,  # TIMEOUT, EXCEPTION, RATE_LIMIT...  │  │ ║
║  │  │    error_logs: list[LogNode],                                       │  │ ║
║  │  │    is_root_cause: bool                                              │  │ ║
║  │  │  }                                                                  │  │ ║
║  │  │                                                                     │  │ ║
║  │  │  FailureChain {                                                     │  │ ║
║  │  │    spans: list[SpanNode],  # ordered from root cause → symptom      │  │ ║
║  │  │    propagation_path: str   # "db_query → service_a → http_handler"  │  │ ║
║  │  │  }                                                                  │  │ ║
║  │  │                                                                     │  │ ║
║  │  │  FAILURE TYPES (enum):                                              │  │ ║
║  │  │    - TIMEOUT              # duration > threshold                    │  │ ║
║  │  │    - EXCEPTION            # unhandled exception in logs             │  │ ║
║  │  │    - RATE_LIMIT           # 429 or rate limit messages              │  │ ║
║  │  │    - RESOURCE_EXHAUSTION  # OOM, connection pool, etc.              │  │ ║
║  │  │    - DEPENDENCY_FAILURE   # external service down                   │  │ ║
║  │  │    - VALIDATION_ERROR     # 400, bad request                        │  │ ║
║  │  │    - AUTH_FAILURE         # 401, 403                                │  │ ║
║  │  │    - NOT_FOUND            # 404                                     │  │ ║
║  │  │    - INTERNAL_ERROR       # 500                                     │  │ ║
║  │  │    - UNKNOWN                                                        │  │ ║
║  │  │                                                                     │  │ ║
║  │  │  DETECTION ALGORITHM:                                               │  │ ║
║  │  │    1. Find all spans with ERROR/CRITICAL logs                       │  │ ║
║  │  │    2. For each error span, walk UP to find propagation chain        │  │ ║
║  │  │    3. For each error span, walk DOWN to find if it caused children  │  │ ║
║  │  │    4. Identify "deepest" error span as root cause candidate         │  │ ║
║  │  │    5. Match error patterns to FailureType                           │  │ ║
║  │  └─────────────────────────────────────────────────────────────────────┘  │ ║
║  │       │                                                                    │ ║
║  │       ▼                                                                    │ ║
║  │  ┌─────────────────────────────────────────────────────────────────────┐  │ ║
║  │  │  STEP 3.4: PATTERN MATCHING                                         │  │ ║
║  │  │  ═══════════════════════════════                                    │  │ ║
║  │  │  File: rest/intel/matcher.py                                        │  │ ║
║  │  │  Function: match_patterns(tree, failures) → list[PatternMatch]      │  │ ║
║  │  │                                                                     │  │ ║
║  │  │  PURPOSE: Match against known failure patterns for instant RCA      │  │ ║
║  │  │                                                                     │  │ ║
║  │  │  INPUT:  SpanNode, FailureReport                                    │  │ ║
║  │  │  OUTPUT: list[PatternMatch]                                         │  │ ║
║  │  │                                                                     │  │ ║
║  │  │  PatternMatch {                                                     │  │ ║
║  │  │    pattern_id: str,                                                 │  │ ║
║  │  │    pattern_name: str,        # "N+1 Query", "Connection Pool"       │  │ ║
║  │  │    confidence: float,        # 0.0 - 1.0                            │  │ ║
║  │  │    matched_spans: list[SpanNode],                                   │  │ ║
║  │  │    explanation: str,         # pre-written explanation              │  │ ║
║  │  │    recommended_fix: str      # pre-written fix suggestion           │  │ ║
║  │  │  }                                                                  │  │ ║
║  │  │                                                                     │  │ ║
║  │  │  PATTERN LIBRARY: rest/intel/patterns/                              │  │ ║
║  │  │    ├── database.py           # N+1, slow query, deadlock            │  │ ║
║  │  │    ├── network.py            # timeout, connection refused          │  │ ║
║  │  │    ├── llm.py                # rate limit, token limit, timeout     │  │ ║
║  │  │    ├── cache.py              # miss storm, hot key                  │  │ ║
║  │  │    ├── queue.py              # backpressure, poison pill            │  │ ║
║  │  │    ├── resource.py           # OOM, CPU, connection pool            │  │ ║
║  │  │    ├── retry.py              # retry storm, exponential backoff     │  │ ║
║  │  │    ├── deployment.py         # bad deploy, config error             │  │ ║
║  │  │    │                                                                │  │ ║
║  │  │    │   # ═══════════════════════════════════════════════════════   │  │ ║
║  │  │    │   # AGENT-NATIVE PATTERNS (NEW - Issue #365)                  │  │ ║
║  │  │    │   # ═══════════════════════════════════════════════════════   │  │ ║
║  │  │    ├── agent_reasoning.py    # reasoning loops, plan failures      │  │ ║
║  │  │    ├── agent_tools.py        # tool misuse, input/output errors    │  │ ║
║  │  │    ├── agent_context.py      # context overflow, memory issues     │  │ ║
║  │  │    ├── agent_prompts.py      # prompt injection, bad templates     │  │ ║
║  │  │    ├── agent_multiagent.py   # handoff, coordination failures      │  │ ║
║  │  │    └── agent_recovery.py     # retry exhaustion, fallback loops    │  │ ║
║  │  │                                                                     │  │ ║
║  │  │  MATCHING SPEED: < 10ms for 100+ patterns (rule-based)              │  │ ║
║  │  │                                                                     │  │ ║
║  │  │  IF pattern matched with confidence > 0.8:                          │  │ ║
║  │  │    → Can skip heavy LLM reasoning (fast path)                       │  │ ║
║  │  │    → Response time: < 1 second                                      │  │ ║
║  │  └─────────────────────────────────────────────────────────────────────┘  │ ║
║  │       │                                                                    │ ║
║  │       ▼                                                                    │ ║
║  │  ┌─────────────────────────────────────────────────────────────────────┐  │ ║
║  │  │  STEP 3.5: CAUSE RANKING                                            │  │ ║
║  │  │  ════════════════════════                                           │  │ ║
║  │  │  File: rest/intel/ranker.py                                         │  │ ║
║  │  │  Function: rank_causes(tree, failures, patterns) → RankedCauses     │  │ ║
║  │  │                                                                     │  │ ║
║  │  │  PURPOSE: Score and prioritize candidate causes                     │  │ ║
║  │  │                                                                     │  │ ║
║  │  │  INPUT:Pos  SpanNode, FailureReport, list[PatternMatch]                 │  │ ║
║  │  │  OUTPUT: RankedCauses {                                             │  │ ║
║  │  │            causes: list[RankedCause],  # sorted by score            │  │ ║
║  │  │            confidence_level: str       # HIGH, MEDIUM, LOW          │  │ ║
║  │  │          }                                                          │  │ ║
║  │  │                                                                     │  │ ║
║  │  │  RankedCause {                                                      │  │ ║
║  │  │    span: SpanNode,                                                  │  │ ║
║  │  │    score: float,             # 0.0 - 1.0                            │  │ ║
║  │  │    contributing_factors: list[ScoringFactor],                       │  │ ║
║  │  │    evidence: list[Evidence]                                         │  │ ║
║  │  │  }                                                                  │  │ ║
║  │  │                                                                     │  │ ║
║  │  │  SCORING FACTORS (weighted):                                        │  │ ║
║  │  │    - error_density: 0.25     # errors / total logs in span          │  │ ║
║  │  │    - latency_anomaly: 0.20   # duration vs P95 baseline             │  │ ║
║  │  │    - temporal_correlation: 0.20  # timing matches failure           │  │ ║
║  │  │    - pattern_match: 0.15     # known pattern confidence             │  │ ║
║  │  │    - depth_in_tree: 0.10     # deeper = more likely root cause      │  │ ║
║  │  │    - span_type_weight: 0.10  # DB, HTTP more likely than business   │  │ ║
║  │  │                                                                     │  │ ║
║  │  │  score = Σ (factor_value × weight)                                  │  │ ║
║  │  │                                                                     │  │ ║
║  │  │  CONFIDENCE THRESHOLDS:                                             │  │ ║
║  │  │    - HIGH:   top cause score > 0.8 AND 2nd cause < 0.5              │  │ ║
║  │  │    - MEDIUM: top cause score > 0.6                                  │  │ ║
║  │  │    - LOW:    top cause score < 0.6 OR multiple causes close         │  │ ║
║  │  └─────────────────────────────────────────────────────────────────────┘  │ ║
║  │       │                                                                    │ ║
║  │       ▼                                                                    │ ║
║  │  ┌─────────────────────────────────────────────────────────────────────┐  │ ║
║  │  │  STEP 3.6: CONTEXT COMPRESSION                                      │  │ ║
║  │  │  ══════════════════════════════                                     │  │ ║
║  │  │  File: rest/intel/compressor.py                                     │  │ ║
║  │  │  Function: compress_context(tree, ranked) → CompressedContext       │  │ ║
║  │  │                                                                     │  │ ║
║  │  │  PURPOSE: Reduce context size while preserving diagnostic value     │  │ ║
║  │  │           Target: 100k+ logs → ~5k tokens (250:1 ratio)             │  │ ║
║  │  │                                                                     │  │ ║
║  │  │  INPUT:  SpanNode, RankedCauses                                     │  │ ║
║  │  │  OUTPUT: CompressedContext {                                        │  │ ║
║  │  │            compressed_tree: dict,     # for LLM consumption         │  │ ║
║  │  │            token_count: int,                                        │  │ ║
║  │  │            compression_ratio: float,                                │  │ ║
║  │  │            preserved_evidence: list[Evidence]                       │  │ ║
║  │  │          }                                                          │  │ ║
║  │  │                                                                     │  │ ║
║  │  │  COMPRESSION STRATEGIES:                                            │  │ ║
║  │  │    1. HIERARCHICAL SUMMARIZATION                                    │  │ ║
║  │  │       - Keep full detail for top-ranked cause spans                 │  │ ║
║  │  │       - Summarize sibling subtrees: "47 successful HTTP calls"      │  │ ║
║  │  │       - Collapse uninvolved branches to single line                 │  │ ║
║  │  │                                                                     │  │ ║
║  │  │    2. LOG DEDUPLICATION                                             │  │ ║
║  │  │       - Group identical/similar log messages                        │  │ ║
║  │  │       - "Connection timeout" x 15 → single entry with count         │  │ ║
║  │  │                                                                     │  │ ║
║  │  │    3. SALIENT EXCERPT EXTRACTION                                    │  │ ║
║  │  │       - Keep ERROR/CRITICAL logs in full                            │  │ ║
║  │  │       - Keep first/last of repeated patterns                        │  │ ║
║  │  │       - Truncate INFO/DEBUG to first 100 chars                      │  │ ║
║  │  │                                                                     │  │ ║
║  │  │    4. EVIDENCE ANCHORING                                            │  │ ║
║  │  │       - Always preserve logs cited in ranking evidence              │  │ ║
║  │  │       - Always preserve timestamps for temporal correlation         │  │ ║
║  │  │                                                                     │  │ ║
║  │  │  TOKEN BUDGET ALLOCATION:                                           │  │ ║
║  │  │    - Top cause span: 40% of budget                                  │  │ ║
║  │  │    - Cause chain spans: 30% of budget                               │  │ ║
║  │  │    - Context/siblings: 20% of budget                                │  │ ║
║  │  │    - Metadata/structure: 10% of budget                              │  │ ║
║  │  └─────────────────────────────────────────────────────────────────────┘  │ ║
║  │       │                                                                    │ ║
║  │       ▼                                                                    │ ║
║  │                                                                            │ ║
║  │  OUTPUT: IntelligenceResult {                                              │ ║
║  │    classified_tree: SpanNode,                                              │ ║
║  │    suppression_stats: SuppressionStats,                                    │ ║
║  │    failure_report: FailureReport,                                          │ ║
║  │    pattern_matches: list[PatternMatch],                                    │ ║
║  │    ranked_causes: RankedCauses,                                            │ ║
║  │    compressed_context: CompressedContext,                                  │ ║
║  │    fast_path_available: bool,  # True if high-confidence pattern match    │ ║
║  │    processing_time_ms: float                                               │ ║
║  │  }                                                                         │ ║
║  │                                                                            │ ║
║  └────────────────────────────────────────────────────────────────────────────┘ ║
║                                                                                  ║
╚═════════════════════════════════════════════════════════════════════════════════╝
     │
     │  IntelligenceResult
     │
     ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│  STAGE 4: AGENT ROUTING                                                          │
│  ═══════════════════════                                                         │
│  File: rest/agent/router.py                                                     │
│  Class: ChatRouter                                                               │
│  Method: route_query()                                                          │
│                                                                                  │
│  INPUT:  user_message, chat_mode, has_trace_context, intelligence_result        │
│  OUTPUT: RouterOutput { agent_type, reasoning }                                  │
│                                                                                  │
│  ROUTING LOGIC:                                                                  │
│    if intelligence_result.fast_path_available:                                  │
│      → Can use pre-computed explanation from pattern match                      │
│    elif mode == CHAT:                                                           │
│      → single_rca OR general                                                    │
│    elif mode == AGENT:                                                          │
│      → single_rca OR code OR general                                            │
│                                                                                  │
│  STATUS: ✅ COMPLETE (needs minor modification to accept intel result)          │
└─────────────────────────────────────────────────────────────────────────────────┘
     │
     │  agent_type = "single_rca"
     │
     ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│  STAGE 5: LLM REASONING (Modified for Intelligence Layer)                        │
│  ════════════════════════════════════════════════════════                        │
│  File: rest/agent/agents/single_rca_agent.py                                    │
│  Class: SingleRCAAgent                                                           │
│  Method: chat()                                                                  │
│                                                                                  │
│  ┌────────────────────────────────────────────────────────────────────────────┐ │
│  │  DECISION: Fast Path vs Full Reasoning                                     │ │
│  │                                                                            │ │
│  │  IF intelligence_result.fast_path_available:                               │ │
│  │    ─────────────────────────────────────────                               │ │
│  │    │  Use pre-computed pattern explanation                                 │ │
│  │    │  Skip feature selection (already done)                                │ │
│  │    │  Skip chunking (already compressed)                                   │ │
│  │    │  Single LLM call to format/personalize response                       │ │
│  │    │                                                                       │ │
│  │    │  Response time: < 2 seconds                                           │ │
│  │    └───────────────────────────────────────                                │ │
│  │                                                                            │ │
│  │  ELSE (full reasoning):                                                    │ │
│  │    ─────────────────────────────────────────                               │ │
│  │    │  Use compressed_context instead of raw tree                           │ │
│  │    │  Include ranked_causes in system prompt                               │ │
│  │    │  Include pattern_matches as hints                                     │ │
│  │    │                                                                       │ │
│  │    │  Modified prompt:                                                     │ │
│  │    │    "The intelligence layer has identified these likely causes:        │ │
│  │    │     1. [cause] (confidence: 0.85)                                     │ │
│  │    │     2. [cause] (confidence: 0.45)                                     │ │
│  │    │     Validate and explain to the user."                                │ │
│  │    │                                                                       │ │
│  │    │  Response time: 5-15 seconds                                          │ │
│  │    └───────────────────────────────────────                                │ │
│  └────────────────────────────────────────────────────────────────────────────┘ │
│                                                                                  │
│  EXISTING FLOW (with intelligence enhancement):                                  │
│                                                                                  │
│  STEP 5.1: Feature Selection (✅ existing)                                       │
│    → SKIP if intelligence layer already filtered                                │
│                                                                                  │
│  STEP 5.2: Structure Filtering (✅ existing)                                     │
│    → SKIP if intelligence layer already pruned                                  │
│                                                                                  │
│  STEP 5.3: Context Building (✅ existing, modified)                              │
│    → Use compressed_context.compressed_tree instead of raw                      │
│    → Include ranked_causes as structured prefix                                 │
│                                                                                  │
│  STEP 5.4: Chunking (✅ existing, modified)                                      │
│    → Likely single chunk due to compression (< 5k tokens)                       │
│    → If still multiple, chunks are already optimized                            │
│                                                                                  │
│  STEP 5.5: LLM Reasoning (✅ existing)                                           │
│    → Enhanced prompt with intelligence hints                                    │
│                                                                                  │
│  STEP 5.6: Summarization (✅ existing)                                           │
│    → Usually skipped (single chunk)                                             │
│                                                                                  │
│  STATUS: ✅ COMPLETE (needs modification to use intelligence result)            │
└─────────────────────────────────────────────────────────────────────────────────┘
     │
     │  ChatOutput { answer, references }
     │
     ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│  STAGE 6: EVIDENCE SYNTHESIS & VALIDATION                                        │
│  ═════════════════════════════════════════                                       │
│  File: rest/intel/synthesizer.py (🔴 TO BUILD)                                  │
│  Function: validate_response(answer, evidence, tree) → ValidatedResponse        │
│                                                                                  │
│  PURPOSE: Ground LLM output in actual trace data to reduce hallucinations       │
│                                                                                  │
│  INPUT:  ChatOutput, IntelligenceResult                                          │
│  OUTPUT: ValidatedResponse {                                                     │
│            answer: str,           # possibly modified                            │
│            references: list[Reference],  # validated                             │
│            confidence: float,                                                    │
│            validation_notes: list[str]                                           │
│          }                                                                       │
│                                                                                  │
│  VALIDATION CHECKS:                                                              │
│    1. Reference Verification                                                     │
│       - Every cited span_id exists in tree                                      │
│       - Every cited log_message exists in that span                             │
│       - Line numbers are accurate                                               │
│                                                                                  │
│    2. Claim Verification                                                         │
│       - If answer says "timeout", verify duration supports it                   │
│       - If answer says "N+1", verify repeated query pattern exists              │
│       - If answer cites timing, verify timestamps                               │
│                                                                                  │
│    3. Consistency Check                                                          │
│       - LLM conclusion aligns with ranked_causes                                │
│       - If major disagreement, flag for review                                  │
│                                                                                  │
│  IF validation fails:                                                            │
│    → Option A: Re-run LLM with correction prompt                                │
│    → Option B: Add caveat to response                                           │
│    → Option C: Fall back to pattern-based explanation                           │
│                                                                                  │
│  STATUS: 🔴 TO BUILD                                                             │
└─────────────────────────────────────────────────────────────────────────────────┘
     │
     │  ValidatedResponse
     │
     ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│  STAGE 7: PERSISTENCE (🟡 EE)                                                    │
│  ═════════════════════════════                                                   │
│  File: rest/dao/ee/mongodb_dao.py (🟡 to implement)                             │
│     OR rest/dao/sqlite_dao.py (✅ for local)                                     │
│                                                                                  │
│  RECORDS TO STORE:                                                               │
│                                                                                  │
│  7.1: Chat Record                                                                │
│  ─────────────────────────────────────────────────────────────────────────────  │
│  │  db_client.insert_chat_record({                                             │
│  │    chat_id,                                                                 │
│  │    timestamp,                                                               │
│  │    role: "assistant",                                                       │
│  │    content: answer,                                                         │
│  │    reference: [...],                                                        │
│  │    trace_id,                                                                │
│  │    action_type: "AGENT_CHAT",                                               │
│  │    status: "SUCCESS"                                                        │
│  │  })                                                                         │
│  ─────────────────────────────────────────────────────────────────────────────  │
│                                                                                  │
│  7.2: Intelligence Metrics (🔴 NEW - for evaluation loop)                        │
│  ─────────────────────────────────────────────────────────────────────────────  │
│  │  db_client.insert_intelligence_metrics({                                    │
│  │    trace_id,                                                                │
│  │    chat_id,                                                                 │
│  │    timestamp,                                                               │
│  │    pattern_matches: [...],                                                  │
│  │    ranked_causes: [...],                                                    │
│  │    fast_path_used: bool,                                                    │
│  │    compression_ratio: float,                                                │
│  │    processing_time_ms: float,                                               │
│  │    validation_result: {...},                                                │
│  │    user_feedback: null  # filled later                                      │
│  │  })                                                                         │
│  ─────────────────────────────────────────────────────────────────────────────  │
│                                                                                  │
│  STATUS: 🟡 EE needed for production / ✅ SQLite for local                       │
└─────────────────────────────────────────────────────────────────────────────────┘
     │
     ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│  STAGE 8: RESPONSE TO USER                                                       │
│  ══════════════════════════                                                      │
│                                                                                  │
│  OUTPUT: ChatbotResponse {                                                       │
│    time: datetime,                                                               │
│    message: "The trace is slow because of an N+1 query pattern in the          │
│              user_service. The `get_users` function makes 47 individual         │
│              database queries instead of a single batch query...",              │
│    reference: [                                                                  │
│      {                                                                           │
│        number: 1,                                                                │
│        span_id: "span_abc123",                                                   │
│        span_function_name: "user_service.get_users",                             │
│        line_number: 45,                                                          │
│        log_message: "SELECT * FROM users WHERE id = ?"                           │
│      }                                                                           │
│    ],                                                                            │
│    message_type: "assistant",                                                    │
│    chat_id: "chat_xyz789",                                                       │
│    metadata: {                # 🔴 NEW: include intelligence metadata            │
│      confidence: "HIGH",                                                         │
│      pattern_matched: "N+1_QUERY",                                               │
│      fast_path: true,                                                            │
│      processing_time_ms: 847                                                     │
│    }                                                                             │
│  }                                                                               │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
     │
     ▼
╔═════════════════════════════════════════════════════════════════════════════════╗
║  STAGE 9: EVALUATION FEEDBACK LOOP (🔴 TO BUILD - Background)                    ║
║  ═══════════════════════════════════════════════════════════                     ║
║                                                                                  ║
║  File: rest/intel/evaluator.py                                                  ║
║  Run: Async background worker                                                    ║
║                                                                                  ║
║  PURPOSE: Continuously improve pattern library and ranking weights               ║
║                                                                                  ║
║  ┌────────────────────────────────────────────────────────────────────────────┐ ║
║  │  FEEDBACK SOURCES:                                                         │ ║
║  │                                                                            │ ║
║  │  1. Explicit User Feedback                                                 │ ║
║  │     - Thumbs up/down on response                                           │ ║
║  │     - "Was this helpful?" rating                                           │ ║
║  │     - User corrections in follow-up messages                               │ ║
║  │                                                                            │ ║
║  │  2. Implicit Signals                                                       │ ║
║  │     - User created GitHub issue from suggestion → positive                 │ ║
║  │     - User asked follow-up questions → needs more detail                   │ ║
║  │     - User asked same question again → negative                            │ ║
║  │     - Short session after response → possibly resolved                     │ ║
║  │                                                                            │ ║
║  │  3. Outcome Correlation                                                    │ ║
║  │     - If GitHub PR merged → positive signal                                │ ║
║  │     - If same trace pattern recurs → fix didn't work                       │ ║
║  │     - If different error on same service → partial fix                     │ ║
║  └────────────────────────────────────────────────────────────────────────────┘ ║
║                                                                                  ║
║  ┌────────────────────────────────────────────────────────────────────────────┐ ║
║  │  LEARNING ACTIONS:                                                         │ ║
║  │                                                                            │ ║
║  │  1. Pattern Library Updates                                                │ ║
║  │     - High positive feedback → increase pattern confidence                 │ ║
║  │     - Repeated negative → flag pattern for review                          │ ║
║  │     - New failure mode identified → candidate for new pattern              │ ║
║  │                                                                            │ ║
║  │  2. Ranking Weight Adjustment                                              │ ║
║  │     - Track which scoring factors correlated with correct RCA              │ ║
║  │     - Periodically retrain weights                                         │ ║
║  │                                                                            │ ║
║  │  3. Compression Optimization                                               │ ║
║  │     - Track if compressed context led to worse answers                     │ ║
║  │     - Adjust token budgets per span type                                   │ ║
║  └────────────────────────────────────────────────────────────────────────────┘ ║
║                                                                                  ║
║  STATUS: 🔴 TO BUILD (Phase 2, after core intelligence works)                    ║
║                                                                                  ║
╚═════════════════════════════════════════════════════════════════════════════════╝
```

---

## Intelligence Layer Specification (TO BUILD)

### Package Structure

```
rest/intel/                          # 🔴 NEW PACKAGE
├── __init__.py
├── types.py                         # All data types and enums
├── pipeline.py                      # Main orchestrator
├── classifier.py                    # Step 3.1: Semantic classification
├── suppressor.py                    # Step 3.2: Noise suppression
├── locator.py                       # Step 3.3: Failure locality
├── matcher.py                       # Step 3.4: Pattern matching
├── ranker.py                        # Step 3.5: Cause ranking
├── compressor.py                    # Step 3.6: Context compression
├── synthesizer.py                   # Step 6: Evidence synthesis
├── evaluator.py                     # Step 9: Feedback loop
└── patterns/                        # Pattern library
    ├── __init__.py
    ├── base.py                      # Pattern base class
    ├── database.py                  # DB patterns
    ├── network.py                   # Network patterns
    ├── llm.py                       # LLM patterns
    ├── cache.py                     # Cache patterns
    ├── queue.py                     # Queue patterns
    ├── resource.py                  # Resource patterns
    ├── retry.py                     # Retry patterns
    └── deployment.py                # Deployment patterns
```

### Main Orchestrator

```python
# rest/intel/pipeline.py

from rest.intel.types import IntelligenceResult, IntelligenceConfig
from rest.intel.classifier import classify_spans
from rest.intel.suppressor import suppress_noise
from rest.intel.locator import locate_failures
from rest.intel.matcher import match_patterns
from rest.intel.ranker import rank_causes
from rest.intel.compressor import compress_context
from rest.agent.context.tree import SpanNode

class IntelligencePipeline:
    """
    Main orchestrator for the intelligence layer.
    
    Processes raw span tree through classification, suppression,
    failure detection, pattern matching, ranking, and compression.
    """
    
    def __init__(self, config: IntelligenceConfig = None):
        self.config = config or IntelligenceConfig()
        
    async def process(
        self,
        tree: SpanNode,
        user_query: str,
    ) -> IntelligenceResult:
        """
        Main entry point for intelligence processing.
        
        Args:
            tree: Raw span tree from build_heterogeneous_tree()
            user_query: User's question (for relevance scoring)
            
        Returns:
            IntelligenceResult with all analysis and compressed context
        """
        import time
        start_time = time.time()
        
        # Step 3.1: Semantic Classification
        classified_tree = classify_spans(tree)
        
        # Step 3.2: Noise Suppression
        pruned_tree, suppression_stats = suppress_noise(
            classified_tree,
            config=self.config.suppression
        )
        
        # Step 3.3: Failure Locality Detection
        failure_report = locate_failures(pruned_tree)
        
        # Step 3.4: Pattern Matching
        pattern_matches = match_patterns(
            pruned_tree,
            failure_report,
            user_query
        )
        
        # Step 3.5: Cause Ranking
        ranked_causes = rank_causes(
            pruned_tree,
            failure_report,
            pattern_matches
        )
        
        # Step 3.6: Context Compression
        compressed_context = compress_context(
            pruned_tree,
            ranked_causes,
            token_budget=self.config.token_budget
        )
        
        # Determine if fast path is available
        fast_path = (
            len(pattern_matches) > 0 and
            pattern_matches[0].confidence > 0.8 and
            ranked_causes.confidence_level == "HIGH"
        )
        
        processing_time = (time.time() - start_time) * 1000
        
        return IntelligenceResult(
            classified_tree=classified_tree,
            suppression_stats=suppression_stats,
            failure_report=failure_report,
            pattern_matches=pattern_matches,
            ranked_causes=ranked_causes,
            compressed_context=compressed_context,
            fast_path_available=fast_path,
            processing_time_ms=processing_time
        )
```

### Integration Point

```python
# rest/driver/chat_logic.py
# MODIFY post_chat() method - insert after tree building

# Existing code:
tree = build_heterogeneous_tree(trace.spans[0], logs.logs)

# 🔴 ADD: Intelligence Layer Processing
from rest.intel.pipeline import IntelligencePipeline

intel_pipeline = IntelligencePipeline()
intel_result = await intel_pipeline.process(
    tree=tree,
    user_query=request.message
)

# Pass intel_result to agent
if router_output.agent_type == "single_rca":
    response = await self.single_rca_agent.chat(
        # ... existing params ...
        tree=tree,
        intelligence_result=intel_result,  # 🔴 ADD THIS
    )
```

---

## Data Structures Reference

### Complete Type Definitions

```python
# rest/intel/types.py

from enum import Enum
from typing import Optional
from pydantic import BaseModel
from datetime import datetime

# ═══════════════════════════════════════════════════════════════════════════════
# ENUMS
# ═══════════════════════════════════════════════════════════════════════════════

class SpanType(str, Enum):
    """Semantic type of a span."""
    # ═══════════════════════════════════════════════════════════════════════
    # TRADITIONAL SERVICE SPANS
    # ═══════════════════════════════════════════════════════════════════════
    LLM_CALL = "llm_call"
    DB_QUERY = "db_query"
    HTTP_REQUEST = "http_request"
    HTTP_HANDLER = "http_handler"
    QUEUE_PUBLISH = "queue_publish"
    QUEUE_CONSUME = "queue_consume"
    CACHE_OP = "cache_op"
    FILE_IO = "file_io"
    RETRY_LOOP = "retry_loop"
    HEALTH_CHECK = "health_check"
    INSTRUMENTATION = "instrumentation"
    BUSINESS_LOGIC = "business_logic"
    
    # ═══════════════════════════════════════════════════════════════════════
    # AGENT-NATIVE SPANS (NEW - Issue #365)
    # ═══════════════════════════════════════════════════════════════════════
    # Agent Lifecycle
    AGENT_RUN = "agent_run"              # Root span for entire agent execution
    AGENT_STEP = "agent_step"            # Single step in agent loop
    
    # Planning & Reasoning
    PLAN_GENERATION = "plan_generation"   # Agent creating execution plan
    PLAN_STEP = "plan_step"              # Single step in plan
    REASONING_STEP = "reasoning_step"     # Chain-of-thought / thinking
    DECISION_POINT = "decision_point"     # Agent making a choice
    
    # Tool Usage
    TOOL_CALL = "tool_call"              # Agent invoking a tool
    TOOL_INPUT_PREP = "tool_input_prep"  # Preparing tool inputs
    TOOL_OUTPUT_PARSE = "tool_output_parse"  # Parsing tool outputs
    
    # Memory & Context
    MEMORY_READ = "memory_read"          # Reading from agent memory
    MEMORY_WRITE = "memory_write"        # Writing to agent memory
    CONTEXT_RETRIEVAL = "context_retrieval"  # RAG / context lookup
    CONTEXT_INJECTION = "context_injection"  # Adding context to prompt
    
    # Prompts & Messages
    PROMPT_CONSTRUCTION = "prompt_construction"  # Building the prompt
    MESSAGE_EXCHANGE = "message_exchange"  # User/assistant messages
    SYSTEM_PROMPT = "system_prompt"       # System prompt setup
    
    # Control Flow
    RETRY_ATTEMPT = "retry_attempt"       # Explicit retry
    FALLBACK_EXECUTION = "fallback_execution"  # Fallback path taken
    LOOP_ITERATION = "loop_iteration"     # Agent loop iteration
    GUARD_CHECK = "guard_check"           # Safety/validation check
    
    # Multi-Agent
    AGENT_HANDOFF = "agent_handoff"       # Passing to another agent
    AGENT_DELEGATION = "agent_delegation" # Delegating subtask
    AGENT_COORDINATION = "agent_coordination"  # Multi-agent sync
    
    UNKNOWN = "unknown"


class FailureType(str, Enum):
    """Type of failure detected."""
    # ═══════════════════════════════════════════════════════════════════════
    # TRADITIONAL FAILURES
    # ═══════════════════════════════════════════════════════════════════════
    TIMEOUT = "timeout"
    EXCEPTION = "exception"
    RATE_LIMIT = "rate_limit"
    RESOURCE_EXHAUSTION = "resource_exhaustion"
    DEPENDENCY_FAILURE = "dependency_failure"
    VALIDATION_ERROR = "validation_error"
    AUTH_FAILURE = "auth_failure"
    NOT_FOUND = "not_found"
    INTERNAL_ERROR = "internal_error"
    
    # ═══════════════════════════════════════════════════════════════════════
    # AGENT-SPECIFIC FAILURES (NEW - Issue #365)
    # ═══════════════════════════════════════════════════════════════════════
    # LLM Failures
    TOKEN_LIMIT_EXCEEDED = "token_limit_exceeded"      # Context too large
    PROMPT_INJECTION = "prompt_injection"              # Detected injection
    OUTPUT_PARSE_FAILURE = "output_parse_failure"      # Can't parse LLM output
    HALLUCINATION_DETECTED = "hallucination_detected"  # Factual error detected
    SAFETY_FILTER_TRIGGERED = "safety_filter_triggered"  # Content blocked
    
    # Tool Failures
    TOOL_NOT_FOUND = "tool_not_found"                  # Tool doesn't exist
    TOOL_INPUT_INVALID = "tool_input_invalid"         # Bad tool arguments
    TOOL_OUTPUT_INVALID = "tool_output_invalid"       # Tool returned bad data
    TOOL_PERMISSION_DENIED = "tool_permission_denied" # Tool access denied
    
    # Reasoning Failures
    REASONING_LOOP = "reasoning_loop"                  # Agent stuck in loop
    PLAN_INVALID = "plan_invalid"                     # Generated bad plan
    DECISION_DEADLOCK = "decision_deadlock"           # Can't decide
    CONTEXT_OVERFLOW = "context_overflow"             # Context grew too large
    MEMORY_CORRUPTION = "memory_corruption"           # Agent memory inconsistent
    
    # Multi-Agent Failures
    HANDOFF_FAILURE = "handoff_failure"               # Agent handoff failed
    COORDINATION_TIMEOUT = "coordination_timeout"     # Multi-agent sync failed
    DELEGATION_REJECTED = "delegation_rejected"       # Subtask delegation failed
    
    # Retry/Recovery Failures
    RETRY_EXHAUSTED = "retry_exhausted"               # All retries failed
    FALLBACK_FAILED = "fallback_failed"               # Fallback also failed
    RECOVERY_LOOP = "recovery_loop"                   # Stuck retrying
    
    UNKNOWN = "unknown"


class ConfidenceLevel(str, Enum):
    """Confidence level for RCA."""
    HIGH = "high"       # Top cause > 0.8, clear winner
    MEDIUM = "medium"   # Top cause > 0.6
    LOW = "low"         # Ambiguous or weak signal


# ═══════════════════════════════════════════════════════════════════════════════
# CLASSIFIER OUTPUT
# ═══════════════════════════════════════════════════════════════════════════════

class ClassifiedSpanNode(BaseModel):
    """SpanNode with semantic classification added."""
    # Original SpanNode fields (inherited conceptually)
    span_id: str
    func_full_name: str
    span_latency: float
    span_utc_start_time: datetime
    span_utc_end_time: datetime
    logs: list  # list[LogNode]
    children_spans: list  # list[ClassifiedSpanNode]
    
    # 🔴 NEW: Classification
    span_type: SpanType
    classification_confidence: float  # 0.0 - 1.0


# ═══════════════════════════════════════════════════════════════════════════════
# SUPPRESSOR OUTPUT
# ═══════════════════════════════════════════════════════════════════════════════

class SuppressionStats(BaseModel):
    """Statistics from noise suppression."""
    original_span_count: int
    remaining_span_count: int
    suppressed_count: int
    collapsed_count: int
    compression_ratio: float  # original / remaining


# ═══════════════════════════════════════════════════════════════════════════════
# FAILURE LOCATOR OUTPUT
# ═══════════════════════════════════════════════════════════════════════════════

class FailureSpan(BaseModel):
    """A span identified as containing a failure."""
    span_id: str
    span_function: str
    failure_type: FailureType
    error_messages: list[str]
    is_root_cause: bool
    depth_in_tree: int


class FailureChain(BaseModel):
    """Chain of spans from root cause to symptom."""
    spans: list[str]  # span_ids in order
    propagation_path: str  # "db_query → service_a → handler"


class FailureReport(BaseModel):
    """Complete failure analysis."""
    failure_spans: list[FailureSpan]
    failure_chains: list[FailureChain]
    root_cause_candidates: list[str]  # span_ids
    has_failures: bool


# ═══════════════════════════════════════════════════════════════════════════════
# PATTERN MATCHER OUTPUT
# ═══════════════════════════════════════════════════════════════════════════════

class PatternMatch(BaseModel):
    """A matched failure pattern."""
    pattern_id: str
    pattern_name: str  # "N+1 Query", "Connection Pool Exhaustion"
    pattern_category: str  # "database", "network", "resource"
    confidence: float  # 0.0 - 1.0
    matched_spans: list[str]  # span_ids
    matched_evidence: list[str]  # specific log messages or metrics
    explanation: str  # Pre-written explanation template
    recommended_fix: str  # Pre-written fix suggestion


# ═══════════════════════════════════════════════════════════════════════════════
# RANKER OUTPUT
# ═══════════════════════════════════════════════════════════════════════════════

class ScoringFactor(BaseModel):
    """A factor contributing to cause score."""
    factor_name: str  # "error_density", "latency_anomaly"
    factor_value: float  # raw value
    weighted_contribution: float  # value × weight


class Evidence(BaseModel):
    """Evidence supporting a cause."""
    span_id: str
    evidence_type: str  # "error_log", "latency", "pattern"
    description: str
    timestamp: Optional[datetime]


class RankedCause(BaseModel):
    """A ranked candidate cause."""
    span_id: str
    span_function: str
    score: float  # 0.0 - 1.0
    rank: int  # 1 = top cause
    contributing_factors: list[ScoringFactor]
    evidence: list[Evidence]


class RankedCauses(BaseModel):
    """Complete ranking result."""
    causes: list[RankedCause]  # sorted by score desc
    confidence_level: ConfidenceLevel
    top_cause_score: float
    score_gap: float  # gap between #1 and #2


# ═══════════════════════════════════════════════════════════════════════════════
# COMPRESSOR OUTPUT
# ═══════════════════════════════════════════════════════════════════════════════

class CompressedContext(BaseModel):
    """Compressed context for LLM consumption."""
    compressed_tree: dict  # JSON-serializable tree
    token_count: int
    original_token_count: int
    compression_ratio: float
    preserved_evidence: list[Evidence]
    truncation_notes: list[str]  # what was cut


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN PIPELINE OUTPUT
# ═══════════════════════════════════════════════════════════════════════════════

class IntelligenceResult(BaseModel):
    """Complete output from intelligence pipeline."""
    # From each step
    classified_tree: ClassifiedSpanNode
    suppression_stats: SuppressionStats
    failure_report: FailureReport
    pattern_matches: list[PatternMatch]
    ranked_causes: RankedCauses
    compressed_context: CompressedContext
    
    # Pipeline metadata
    fast_path_available: bool
    processing_time_ms: float


# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

class SuppressionConfig(BaseModel):
    """Configuration for noise suppression."""
    suppress_health_checks: bool = True
    suppress_instrumentation: bool = True
    min_duration_ms: float = 1.0  # suppress faster spans
    collapse_repeated: bool = True
    collapse_threshold: int = 3  # collapse if > N identical


class RankingConfig(BaseModel):
    """Configuration for cause ranking."""
    error_density_weight: float = 0.25
    latency_anomaly_weight: float = 0.20
    temporal_correlation_weight: float = 0.20
    pattern_match_weight: float = 0.15
    depth_weight: float = 0.10
    span_type_weight: float = 0.10


class IntelligenceConfig(BaseModel):
    """Main configuration for intelligence pipeline."""
    suppression: SuppressionConfig = SuppressionConfig()
    ranking: RankingConfig = RankingConfig()
    token_budget: int = 5000  # target compressed tokens
    fast_path_threshold: float = 0.8  # pattern confidence for fast path
```

---

## File Dependency Graph

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           FILE DEPENDENCY GRAPH                                  │
│                                                                                  │
│  Arrows show: A ──▶ B means "A imports/calls B"                                 │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘

                            HTTP LAYER
                    ┌──────────────────────┐
                    │    rest/app.py       │
                    └──────────┬───────────┘
                               │
              ┌────────────────┼────────────────┐
              ▼                ▼                ▼
    ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
    │ routers/chat.py │ │ routers/        │ │ routers/        │
    │                 │ │ telemetry.py    │ │ internal.py     │
    └────────┬────────┘ └────────┬────────┘ └─────────────────┘
             │                   │
             ▼                   ▼
    ┌─────────────────────────────────────────────────────────┐
    │              DRIVER LAYER                                │
    │                                                          │
    │  ┌──────────────────────┐  ┌──────────────────────────┐ │
    │  │ driver/chat_logic.py │  │ driver/telemetry_logic.py│ │
    │  └──────────┬───────────┘  └──────────────────────────┘ │
    │             │                                            │
    └─────────────┼────────────────────────────────────────────┘
                  │
    ┌─────────────┴─────────────┐
    │                           │
    ▼                           ▼
┌─────────────────────┐   ┌─────────────────────────────────────┐
│  SERVICE LAYER      │   │  AGENT LAYER                        │
│                     │   │                                     │
│ ┌─────────────────┐ │   │  ┌────────────────────────────────┐ │
│ │ service/        │ │   │  │ agent/context/tree.py          │ │
│ │ provider.py     │ │   │  │  build_heterogeneous_tree()    │ │
│ └────────┬────────┘ │   │  └────────────┬───────────────────┘ │
│          │          │   │               │                     │
│          ▼          │   │               ▼                     │
│ ┌─────────────────┐ │   │  ┌────────────────────────────────┐ │
│ │ trace/jaeger_   │ │   │  │ 🔴 intel/pipeline.py           │ │
│ │ trace_client.py │ │   │  │    IntelligencePipeline        │ │
│ │       OR        │ │   │  └────────────┬───────────────────┘ │
│ │ trace/ee/aws_   │ │   │               │                     │
│ │ trace_client.py │ │   │    ┌──────────┴──────────┐          │
│ └─────────────────┘ │   │    ▼                     ▼          │
│                     │   │ ┌───────────┐    ┌───────────────┐  │
│ ┌─────────────────┐ │   │ │ intel/    │    │ intel/        │  │
│ │ log/jaeger_     │ │   │ │ classifier│    │ suppressor    │  │
│ │ log_client.py   │ │   │ │ .py       │    │ .py           │  │
│ │       OR        │ │   │ └───────────┘    └───────────────┘  │
│ │ log/ee/aws_     │ │   │    ▼                     ▼          │
│ │ log_client.py   │ │   │ ┌───────────┐    ┌───────────────┐  │
│ └─────────────────┘ │   │ │ intel/    │    │ intel/        │  │
│                     │   │ │ locator   │    │ matcher.py    │  │
└─────────────────────┘   │ │ .py       │    │               │  │
                          │ └───────────┘    └───────┬───────┘  │
                          │                          │          │
                          │                          ▼          │
                          │               ┌───────────────────┐ │
                          │               │ intel/patterns/   │ │
                          │               │  database.py      │ │
                          │               │  network.py       │ │
                          │               │  llm.py           │ │
                          │               │  ...              │ │
                          │               └───────────────────┘ │
                          │    ▼                     ▼          │
                          │ ┌───────────┐    ┌───────────────┐  │
                          │ │ intel/    │    │ intel/        │  │
                          │ │ ranker.py │    │ compressor.py │  │
                          │ └───────────┘    └───────────────┘  │
                          │               │                     │
                          │               ▼                     │
                          │  ┌────────────────────────────────┐ │
                          │  │ agent/router.py                │ │
                          │  │  ChatRouter                    │ │
                          │  └────────────┬───────────────────┘ │
                          │               │                     │
                          │    ┌──────────┴──────────┐          │
                          │    ▼          ▼          ▼          │
                          │ ┌────────┐ ┌────────┐ ┌────────┐    │
                          │ │ single │ │ code   │ │ general│    │
                          │ │ _rca_  │ │ _agent │ │ _agent │    │
                          │ │ agent  │ │ .py    │ │ .py    │    │
                          │ └───┬────┘ └────────┘ └────────┘    │
                          │     │                               │
                          │     ▼                               │
                          │ ┌────────────────────────────────┐  │
                          │ │ agent/filter/feature.py        │  │
                          │ │ agent/filter/structure.py      │  │
                          │ └────────────────────────────────┘  │
                          │     │                               │
                          │     ▼                               │
                          │ ┌────────────────────────────────┐  │
                          │ │ agent/chunk/sequential.py      │  │
                          │ │ agent/context/trace_context.py │  │
                          │ └────────────────────────────────┘  │
                          │     │                               │
                          │     ▼                               │
                          │ ┌────────────────────────────────┐  │
                          │ │ agent/summarizer/chunk.py      │  │
                          │ └────────────────────────────────┘  │
                          │     │                               │
                          │     ▼                               │
                          │ ┌────────────────────────────────┐  │
                          │ │ 🔴 intel/synthesizer.py        │  │
                          │ │    validate_response()         │  │
                          │ └────────────────────────────────┘  │
                          │                                     │
                          └─────────────────────────────────────┘
                                          │
                                          ▼
                          ┌─────────────────────────────────────┐
                          │  DAO LAYER                          │
                          │                                     │
                          │  ┌────────────────────────────────┐ │
                          │  │ dao/sqlite_dao.py (✅ local)   │ │
                          │  │         OR                     │ │
                          │  │ dao/ee/mongodb_dao.py (🟡 EE)  │ │
                          │  └────────────────────────────────┘ │
                          │                                     │
                          └─────────────────────────────────────┘
```

---

## Implementation Checklist

### Phase 1: Core Intelligence (Must Have)

```
□ rest/intel/__init__.py
□ rest/intel/types.py           - All data structures
□ rest/intel/classifier.py      - Semantic classification
□ rest/intel/suppressor.py      - Noise suppression
□ rest/intel/locator.py         - Failure locality
□ rest/intel/patterns/base.py   - Pattern base class
□ rest/intel/patterns/database.py - N+1, slow query, deadlock
□ rest/intel/patterns/network.py  - Timeout, connection refused
□ rest/intel/matcher.py         - Pattern matching engine
□ rest/intel/ranker.py          - Cause ranking/scoring
□ rest/intel/compressor.py      - Context compression
□ rest/intel/pipeline.py        - Main orchestrator

□ MODIFY: rest/driver/chat_logic.py - Integrate pipeline
□ MODIFY: rest/agent/agents/single_rca_agent.py - Use intel result
```

### Phase 2: Pattern Library Expansion

```
□ rest/intel/patterns/llm.py        - Rate limit, token limit
□ rest/intel/patterns/cache.py      - Miss storm, hot key
□ rest/intel/patterns/queue.py      - Backpressure, poison pill
□ rest/intel/patterns/resource.py   - OOM, CPU, connections
□ rest/intel/patterns/retry.py      - Retry storm, backoff
□ rest/intel/patterns/deployment.py - Bad deploy, config error
```

### Phase 3: Validation & Feedback

```
□ rest/intel/synthesizer.py     - Evidence validation
□ rest/intel/evaluator.py       - Feedback loop
□ MODIFY: rest/dao/sqlite_dao.py - Add metrics storage
```

### Phase 4: Enterprise Features

```
□ rest/dao/ee/mongodb_dao.py    - Real implementation
□ rest/service/trace/ee/aws_trace_client.py
□ rest/service/log/ee/aws_log_client.py
```

---

## Expected Performance Targets

| Metric | Before Intelligence | After Intelligence |
|--------|--------------------|--------------------|
| Avg response time | 15-30s | 2-5s (fast path: <1s) |
| Context tokens | 50k-200k | 3k-8k |
| LLM calls per query | 5-10 | 1-3 |
| Hallucination rate | ~15% | <5% |
| Pattern hit rate | 0% | ~60-80% |

---

## Quick Start Implementation Order

1. **Start with types.py** - Define all data structures first
2. **Build classifier.py** - Rule-based, no ML needed
3. **Build suppressor.py** - Simple filtering logic
4. **Build locator.py** - Tree traversal algorithm
5. **Build 3 core patterns** - database.py, network.py, llm.py
6. **Build matcher.py** - Pattern matching engine
7. **Build ranker.py** - Scoring algorithm
8. **Build compressor.py** - Token budget allocation
9. **Build pipeline.py** - Wire it all together
10. **Integrate into chat_logic.py** - Connect to existing flow
