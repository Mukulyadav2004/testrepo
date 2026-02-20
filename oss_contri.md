# Issue #365: AI Agent Observability - OSS Contribution Guide

> **Scope**: This document covers ONLY open source contributions that can be pushed to the main Traceroot.ai repository. No closed/EE/intelligence layer components.

---

## 📋 Executive Summary

**Issue**: [#365 - Pivot to AI Agent Observability & Debugging Agent Platform](https://github.com/traceroot-ai/traceroot/issues/365)

**Goal**: Enable Traceroot to capture, store, and visualize AI agent execution traces with the same developer experience as traditional application tracing.

**Roadmap Items**:
| Issue | Feature | Type | Priority |
|-------|---------|------|----------|
| #369 | Decorator-based SDK | SDK | P0 |
| #370 | OTEL traces to blob storage | Backend | P0 |
| #371 | Auto-instrumentation | SDK | P1 |
| #372 | Signup/login with basic auth | UI | P0 |
| #373 | Org and project management | UI | P1 |
| #374 | Tracing page for LLM calls | UI | P0 |
| #375 | Basic filtering in tracing page | UI | P1 |

---

## 🏗️ Current OSS Architecture

### What We Have (Existing Open Source)

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        EXISTING OSS COMPONENTS                           │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  SDK (examples/)                                                         │
│  ├── Python: @traceroot.trace() decorator, traceroot.get_logger()       │
│  └── TypeScript: @traceroot.trace() decorator, traceroot.getLogger()    │
│                                                                          │
│  Backend (rest/)                                                         │
│  ├── routers/telemetry.py    → list-traces, get-logs-by-trace-id        │
│  ├── routers/internal.py     → /v1/traces (OTLP receiver)               │
│  ├── service/trace/          → TraceClient ABC + Jaeger implementation  │
│  ├── service/log/            → LogClient ABC + Jaeger implementation    │
│  ├── dao/sqlite_dao.py       → Local SQLite persistence                 │
│  └── agent/                  → RCA agent, chunking, filtering           │
│                                                                          │
│  UI (ui/src/)                                                            │
│  ├── app/explore/            → Trace exploration page                    │
│  ├── components/explore/     → Trace, SearchBar, TimeButton, etc.       │
│  ├── components/agent-panel/ → AI debugging agent sidebar               │
│  └── models/trace.ts         → Span, Trace interfaces                   │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### Extension Points for Agent Observability

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    AGENT OBSERVABILITY ADDITIONS                         │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  1. EXTEND SPAN MODEL (ui/src/models/trace.ts)                          │
│     └── Add: span_type, agent metadata, tool calls, model info          │
│                                                                          │
│  2. EXTEND TRACE CONFIG (rest/config/trace.py)                          │
│     └── Add: agent-specific fields, span type enum                      │
│                                                                          │
│  3. NEW SDK DECORATORS (new package or extend examples/)                │
│     └── @trace_agent(), @trace_tool(), @trace_llm_call()               │
│                                                                          │
│  4. NEW UI COMPONENTS (ui/src/components/)                              │
│     └── LLMCallView, ToolCallView, AgentFlowDiagram                    │
│                                                                          │
│  5. NEW FILTERING (extend existing SearchBar)                           │
│     └── Filter by span_type, model, token_count, etc.                  │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 📝 Task Breakdown

### Phase 1: Data Model Extensions (#370, #374)

#### Task 1.1: Extend Span Interface
**File**: `ui/src/models/trace.ts`

```typescript
// ADDITIONS to existing Span interface
export interface Span {
  // ... existing fields ...
  
  // NEW: Agent observability fields
  span_type?: SpanType;
  
  // LLM call metadata
  model?: string;
  provider?: string;
  input_tokens?: number;
  output_tokens?: number;
  total_tokens?: number;
  prompt?: string;
  completion?: string;
  temperature?: number;
  
  // Tool call metadata
  tool_name?: string;
  tool_input?: Record<string, unknown>;
  tool_output?: string;
  
  // Agent metadata
  agent_name?: string;
  agent_type?: string;
  iteration?: number;
}

export type SpanType = 
  | 'generic'           // Default/existing spans
  | 'llm_call'          // LLM API call
  | 'tool_call'         // Tool/function execution
  | 'agent_step'        // Agent reasoning step
  | 'retrieval'         // RAG retrieval
  | 'embedding'         // Embedding generation
  | 'chain'             // Chain execution
  | 'memory_read'       // Memory access
  | 'memory_write';     // Memory write
```

**Effort**: 1 day | **Dependencies**: None

---

#### Task 1.2: Extend Backend Trace Config
**File**: `rest/config/trace.py`

```python
from enum import Enum

class SpanType(str, Enum):
    """Span types for agent observability."""
    GENERIC = "generic"
    LLM_CALL = "llm_call"
    TOOL_CALL = "tool_call"
    AGENT_STEP = "agent_step"
    RETRIEVAL = "retrieval"
    EMBEDDING = "embedding"
    CHAIN = "chain"
    MEMORY_READ = "memory_read"
    MEMORY_WRITE = "memory_write"


class Span(BaseModel):
    """Extended span model with agent observability fields."""
    id: str
    name: str
    start_time: datetime
    end_time: datetime
    duration: float
    
    # Existing log counts
    num_debug_logs: int = 0
    num_info_logs: int = 0
    num_warning_logs: int = 0
    num_error_logs: int = 0
    num_critical_logs: int = 0
    
    # NEW: Agent observability
    span_type: SpanType = SpanType.GENERIC
    
    # LLM metadata
    model: str | None = None
    provider: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    prompt: str | None = None
    completion: str | None = None
    temperature: float | None = None
    
    # Tool metadata
    tool_name: str | None = None
    tool_input: dict | None = None
    tool_output: str | None = None
    
    # Agent metadata
    agent_name: str | None = None
    agent_type: str | None = None
    iteration: int | None = None
    
    # Nested spans
    spans: list["Span"] = []
```

**Effort**: 1 day | **Dependencies**: Task 1.1

---

#### Task 1.3: Update OTLP Receiver to Parse Agent Attributes
**File**: `rest/routers/internal.py`

Add parsing for new span attributes:

```python
# In receive_traces method, add extraction for agent attributes
AGENT_ATTRIBUTES = [
    "span_type",
    "model", "provider", "input_tokens", "output_tokens", "total_tokens",
    "prompt", "completion", "temperature",
    "tool_name", "tool_input", "tool_output",
    "agent_name", "agent_type", "iteration"
]

for attr in span.attributes:
    if attr.key in AGENT_ATTRIBUTES:
        # Store in span metadata for later retrieval
        pass
```

**Effort**: 1 day | **Dependencies**: Task 1.2

---

### Phase 2: SDK Enhancements (#369, #371)

#### Task 2.1: Python Agent Decorators
**File**: `examples/python/agent_decorators.py` (new)

```python
"""Agent-aware tracing decorators for Traceroot.

Usage:
    from traceroot.agent import trace_llm, trace_tool, trace_agent
    
    @trace_llm(model="gpt-4", provider="openai")
    async def call_llm(prompt: str) -> str:
        # LLM call implementation
        pass
    
    @trace_tool()
    def search_web(query: str) -> list[str]:
        # Tool implementation
        pass
    
    @trace_agent(name="research_agent")
    async def research_agent(task: str) -> str:
        # Agent implementation
        pass
"""

import functools
from typing import Callable, TypeVar, ParamSpec

import traceroot

P = ParamSpec("P")
R = TypeVar("R")


def trace_llm(
    model: str | None = None,
    provider: str | None = None,
    capture_prompt: bool = True,
    capture_completion: bool = True,
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Decorator for tracing LLM calls.
    
    Automatically captures:
    - Model and provider info
    - Input/output token counts
    - Prompt and completion (if enabled)
    - Latency and errors
    
    Args:
        model: Model name (e.g., "gpt-4", "claude-3")
        provider: Provider name (e.g., "openai", "anthropic")
        capture_prompt: Whether to capture the prompt text
        capture_completion: Whether to capture the completion text
    """
    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        @functools.wraps(func)
        @traceroot.trace(
            span_name=f"llm:{model or func.__name__}",
            attributes={
                "span_type": "llm_call",
                "model": model,
                "provider": provider,
            }
        )
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            result = await func(*args, **kwargs)
            # Token counting would be added via callback or response parsing
            return result
        return wrapper
    return decorator


def trace_tool(
    tool_name: str | None = None,
    capture_input: bool = True,
    capture_output: bool = True,
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Decorator for tracing tool/function calls.
    
    Automatically captures:
    - Tool name
    - Input arguments
    - Output result
    - Execution time and errors
    
    Args:
        tool_name: Override tool name (defaults to function name)
        capture_input: Whether to capture input arguments
        capture_output: Whether to capture output result
    """
    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        name = tool_name or func.__name__
        
        @functools.wraps(func)
        @traceroot.trace(
            span_name=f"tool:{name}",
            attributes={
                "span_type": "tool_call",
                "tool_name": name,
            }
        )
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            # Capture input if enabled
            if capture_input:
                traceroot.set_span_attribute("tool_input", {
                    "args": args,
                    "kwargs": kwargs
                })
            
            result = func(*args, **kwargs)
            
            # Capture output if enabled
            if capture_output:
                traceroot.set_span_attribute("tool_output", str(result))
            
            return result
        return wrapper
    return decorator


def trace_agent(
    name: str | None = None,
    agent_type: str = "generic",
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Decorator for tracing agent execution.
    
    Creates a parent span for the entire agent execution,
    with nested spans for each step/iteration.
    
    Args:
        name: Agent name
        agent_type: Type of agent (e.g., "react", "cot", "planning")
    """
    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        agent_name = name or func.__name__
        
        @functools.wraps(func)
        @traceroot.trace(
            span_name=f"agent:{agent_name}",
            attributes={
                "span_type": "agent_step",
                "agent_name": agent_name,
                "agent_type": agent_type,
            }
        )
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            return await func(*args, **kwargs)
        return wrapper
    return decorator
```

**Effort**: 2 days | **Dependencies**: Task 1.2

---

#### Task 2.2: TypeScript Agent Decorators
**File**: `examples/typescript/agent-decorators.ts` (new)

```typescript
import * as traceroot from './src/index';

/**
 * Decorator for tracing LLM calls.
 */
export function traceLlm(options?: {
  model?: string;
  provider?: string;
  capturePrompt?: boolean;
  captureCompletion?: boolean;
}) {
  return function (
    target: any,
    propertyKey: string,
    descriptor: PropertyDescriptor
  ) {
    const originalMethod = descriptor.value;
    
    descriptor.value = traceroot.trace({
      spanName: `llm:${options?.model || propertyKey}`,
      attributes: {
        span_type: 'llm_call',
        model: options?.model,
        provider: options?.provider,
      }
    })(originalMethod);
    
    return descriptor;
  };
}

/**
 * Decorator for tracing tool calls.
 */
export function traceTool(options?: {
  toolName?: string;
  captureInput?: boolean;
  captureOutput?: boolean;
}) {
  return function (
    target: any,
    propertyKey: string,
    descriptor: PropertyDescriptor
  ) {
    const originalMethod = descriptor.value;
    const toolName = options?.toolName || propertyKey;
    
    descriptor.value = traceroot.trace({
      spanName: `tool:${toolName}`,
      attributes: {
        span_type: 'tool_call',
        tool_name: toolName,
      }
    })(originalMethod);
    
    return descriptor;
  };
}

/**
 * Decorator for tracing agent execution.
 */
export function traceAgent(options?: {
  name?: string;
  agentType?: string;
}) {
  return function (
    target: any,
    propertyKey: string,
    descriptor: PropertyDescriptor
  ) {
    const originalMethod = descriptor.value;
    const agentName = options?.name || propertyKey;
    
    descriptor.value = traceroot.trace({
      spanName: `agent:${agentName}`,
      attributes: {
        span_type: 'agent_step',
        agent_name: agentName,
        agent_type: options?.agentType || 'generic',
      }
    })(originalMethod);
    
    return descriptor;
  };
}
```

**Effort**: 1 day | **Dependencies**: Task 2.1 (parallel)

---

#### Task 2.3: Auto-Instrumentation for Popular LLM Libraries (#371)
**File**: `examples/python/auto_instrument.py` (new)

```python
"""Auto-instrumentation for popular LLM libraries.

Automatically patches:
- openai (ChatCompletion, Completion)
- anthropic (Messages)
- langchain (LLMChain, AgentExecutor)
- litellm (completion)

Usage:
    import traceroot
    from traceroot.auto_instrument import instrument_all
    
    traceroot.init()
    instrument_all()  # Patches all supported libraries
    
    # Now all LLM calls are automatically traced
    import openai
    response = openai.ChatCompletion.create(...)  # Automatically traced!
"""

import functools
import importlib
from typing import Any, Callable

import traceroot


def _wrap_openai():
    """Patch OpenAI library."""
    try:
        import openai
        
        original_create = openai.ChatCompletion.create
        
        @functools.wraps(original_create)
        @traceroot.trace(
            span_name="llm:openai",
            attributes={"span_type": "llm_call", "provider": "openai"}
        )
        def patched_create(*args, **kwargs):
            model = kwargs.get("model", "unknown")
            traceroot.set_span_attribute("model", model)
            
            result = original_create(*args, **kwargs)
            
            # Extract token usage
            if hasattr(result, "usage"):
                traceroot.set_span_attribute("input_tokens", result.usage.prompt_tokens)
                traceroot.set_span_attribute("output_tokens", result.usage.completion_tokens)
                traceroot.set_span_attribute("total_tokens", result.usage.total_tokens)
            
            return result
        
        openai.ChatCompletion.create = patched_create
        print("[traceroot] Instrumented: openai.ChatCompletion.create")
        
    except ImportError:
        pass  # OpenAI not installed


def _wrap_anthropic():
    """Patch Anthropic library."""
    try:
        import anthropic
        
        original_create = anthropic.Anthropic.messages.create
        
        @functools.wraps(original_create)
        @traceroot.trace(
            span_name="llm:anthropic",
            attributes={"span_type": "llm_call", "provider": "anthropic"}
        )
        def patched_create(self, *args, **kwargs):
            model = kwargs.get("model", "unknown")
            traceroot.set_span_attribute("model", model)
            
            result = original_create(self, *args, **kwargs)
            
            # Extract token usage from response
            if hasattr(result, "usage"):
                traceroot.set_span_attribute("input_tokens", result.usage.input_tokens)
                traceroot.set_span_attribute("output_tokens", result.usage.output_tokens)
            
            return result
        
        anthropic.Anthropic.messages.create = patched_create
        print("[traceroot] Instrumented: anthropic.Anthropic.messages.create")
        
    except ImportError:
        pass  # Anthropic not installed


def _wrap_langchain():
    """Patch LangChain library."""
    try:
        from langchain.chains.base import Chain
        
        original_call = Chain.__call__
        
        @functools.wraps(original_call)
        @traceroot.trace(
            span_name="chain:langchain",
            attributes={"span_type": "chain"}
        )
        def patched_call(self, *args, **kwargs):
            traceroot.set_span_attribute("chain_type", self.__class__.__name__)
            return original_call(self, *args, **kwargs)
        
        Chain.__call__ = patched_call
        print("[traceroot] Instrumented: langchain.chains.base.Chain")
        
    except ImportError:
        pass  # LangChain not installed


def instrument_all():
    """Apply auto-instrumentation to all supported libraries."""
    _wrap_openai()
    _wrap_anthropic()
    _wrap_langchain()
```

**Effort**: 3 days | **Dependencies**: Task 2.1

---

### Phase 3: UI Enhancements (#374, #375)

#### Task 3.1: LLM Call Visualization Component
**File**: `ui/src/components/explore/span/LLMCallView.tsx` (new)

```tsx
"use client";

import { Span } from "@/models/trace";

interface LLMCallViewProps {
  span: Span;
}

export default function LLMCallView({ span }: LLMCallViewProps) {
  if (span.span_type !== 'llm_call') return null;
  
  return (
    <div className="llm-call-view border rounded-lg p-4 bg-slate-50">
      {/* Header with model info */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <span className="px-2 py-1 bg-blue-100 text-blue-800 rounded text-sm">
            {span.provider || 'LLM'}
          </span>
          <span className="font-mono text-sm">{span.model || 'Unknown Model'}</span>
        </div>
        <div className="text-sm text-gray-500">
          {span.duration}ms
        </div>
      </div>
      
      {/* Token usage */}
      {(span.input_tokens || span.output_tokens) && (
        <div className="flex gap-4 mb-4 text-sm">
          <div className="flex items-center gap-1">
            <span className="text-gray-500">Input:</span>
            <span className="font-mono">{span.input_tokens || 0}</span>
          </div>
          <div className="flex items-center gap-1">
            <span className="text-gray-500">Output:</span>
            <span className="font-mono">{span.output_tokens || 0}</span>
          </div>
          <div className="flex items-center gap-1">
            <span className="text-gray-500">Total:</span>
            <span className="font-mono">{span.total_tokens || 0}</span>
          </div>
        </div>
      )}
      
      {/* Prompt */}
      {span.prompt && (
        <div className="mb-4">
          <div className="text-sm font-medium text-gray-700 mb-1">Prompt</div>
          <pre className="bg-white border rounded p-3 text-sm overflow-x-auto whitespace-pre-wrap">
            {span.prompt}
          </pre>
        </div>
      )}
      
      {/* Completion */}
      {span.completion && (
        <div>
          <div className="text-sm font-medium text-gray-700 mb-1">Completion</div>
          <pre className="bg-white border rounded p-3 text-sm overflow-x-auto whitespace-pre-wrap">
            {span.completion}
          </pre>
        </div>
      )}
    </div>
  );
}
```

**Effort**: 2 days | **Dependencies**: Task 1.1

---

#### Task 3.2: Tool Call Visualization Component
**File**: `ui/src/components/explore/span/ToolCallView.tsx` (new)

```tsx
"use client";

import { Span } from "@/models/trace";

interface ToolCallViewProps {
  span: Span;
}

export default function ToolCallView({ span }: ToolCallViewProps) {
  if (span.span_type !== 'tool_call') return null;
  
  return (
    <div className="tool-call-view border rounded-lg p-4 bg-amber-50">
      {/* Header with tool info */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <span className="px-2 py-1 bg-amber-100 text-amber-800 rounded text-sm">
            Tool
          </span>
          <span className="font-mono text-sm font-medium">
            {span.tool_name || span.name}
          </span>
        </div>
        <div className="text-sm text-gray-500">
          {span.duration}ms
        </div>
      </div>
      
      {/* Tool Input */}
      {span.tool_input && (
        <div className="mb-4">
          <div className="text-sm font-medium text-gray-700 mb-1">Input</div>
          <pre className="bg-white border rounded p-3 text-sm overflow-x-auto">
            {JSON.stringify(span.tool_input, null, 2)}
          </pre>
        </div>
      )}
      
      {/* Tool Output */}
      {span.tool_output && (
        <div>
          <div className="text-sm font-medium text-gray-700 mb-1">Output</div>
          <pre className="bg-white border rounded p-3 text-sm overflow-x-auto whitespace-pre-wrap">
            {span.tool_output}
          </pre>
        </div>
      )}
    </div>
  );
}
```

**Effort**: 1 day | **Dependencies**: Task 1.1

---

#### Task 3.3: Span Type Filter in SearchBar (#375)
**File**: `ui/src/components/explore/SearchBar.tsx` (modify existing)

Add span type filtering to existing SearchBar:

```tsx
// Add to SearchCriterion type
export interface SearchCriterion {
  category: string;
  value: string;
  operation?: string;
}

// New span type filter options
const SPAN_TYPE_OPTIONS = [
  { value: 'llm_call', label: 'LLM Calls' },
  { value: 'tool_call', label: 'Tool Calls' },
  { value: 'agent_step', label: 'Agent Steps' },
  { value: 'retrieval', label: 'Retrievals' },
  { value: 'embedding', label: 'Embeddings' },
  { value: 'chain', label: 'Chains' },
];

// Add new filter dropdown for span types
<Select
  value={spanTypeFilter}
  onValueChange={setSpanTypeFilter}
>
  <SelectTrigger className="w-[180px]">
    <SelectValue placeholder="Span Type" />
  </SelectTrigger>
  <SelectContent>
    <SelectItem value="all">All Span Types</SelectItem>
    {SPAN_TYPE_OPTIONS.map(opt => (
      <SelectItem key={opt.value} value={opt.value}>
        {opt.label}
      </SelectItem>
    ))}
  </SelectContent>
</Select>
```

**Effort**: 1 day | **Dependencies**: Task 3.1

---

#### Task 3.4: Token Usage Summary Component
**File**: `ui/src/components/explore/TokenUsageSummary.tsx` (new)

```tsx
"use client";

import { Trace } from "@/models/trace";

interface TokenUsageSummaryProps {
  traces: Trace[];
}

export default function TokenUsageSummary({ traces }: TokenUsageSummaryProps) {
  // Calculate totals across all LLM spans
  const totals = traces.reduce((acc, trace) => {
    const llmSpans = findLLMSpans(trace.spans);
    llmSpans.forEach(span => {
      acc.inputTokens += span.input_tokens || 0;
      acc.outputTokens += span.output_tokens || 0;
      acc.totalTokens += span.total_tokens || 0;
      acc.llmCallCount += 1;
    });
    return acc;
  }, { inputTokens: 0, outputTokens: 0, totalTokens: 0, llmCallCount: 0 });
  
  return (
    <div className="token-usage-summary grid grid-cols-4 gap-4 p-4 bg-slate-100 rounded-lg">
      <div className="text-center">
        <div className="text-2xl font-bold">{totals.llmCallCount}</div>
        <div className="text-sm text-gray-500">LLM Calls</div>
      </div>
      <div className="text-center">
        <div className="text-2xl font-bold">{totals.inputTokens.toLocaleString()}</div>
        <div className="text-sm text-gray-500">Input Tokens</div>
      </div>
      <div className="text-center">
        <div className="text-2xl font-bold">{totals.outputTokens.toLocaleString()}</div>
        <div className="text-sm text-gray-500">Output Tokens</div>
      </div>
      <div className="text-center">
        <div className="text-2xl font-bold">{totals.totalTokens.toLocaleString()}</div>
        <div className="text-sm text-gray-500">Total Tokens</div>
      </div>
    </div>
  );
}

function findLLMSpans(spans: Span[]): Span[] {
  const result: Span[] = [];
  for (const span of spans) {
    if (span.span_type === 'llm_call') {
      result.push(span);
    }
    if (span.spans) {
      result.push(...findLLMSpans(span.spans));
    }
  }
  return result;
}
```

**Effort**: 1 day | **Dependencies**: Task 1.1

---

### Phase 4: Auth & Project Management (#372, #373)

#### Task 4.1: Basic Auth Backend
**File**: `rest/routers/auth.py` (new)

```python
"""Basic authentication router for open source deployment.

Provides simple email/password authentication without external providers.
"""

import hashlib
import secrets
from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel, EmailStr

from rest.dao.sqlite_dao import TraceRootSQLiteClient


class SignupRequest(BaseModel):
    email: EmailStr
    password: str
    name: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class AuthRouter:
    """Authentication router for basic auth."""
    
    def __init__(self):
        self.router = APIRouter()
        self.db = TraceRootSQLiteClient()
        self._setup_routes()
    
    def _setup_routes(self):
        self.router.post("/signup")(self.signup)
        self.router.post("/login")(self.login)
        self.router.post("/logout")(self.logout)
    
    async def signup(self, req: SignupRequest) -> dict:
        """Register a new user."""
        # Hash password
        password_hash = hashlib.sha256(
            (req.password + "traceroot_salt").encode()
        ).hexdigest()
        
        try:
            await self.db.create_user(
                email=req.email,
                password_hash=password_hash,
                name=req.name,
            )
            return {"success": True, "message": "User created successfully"}
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))
    
    async def login(self, req: LoginRequest, response: Response) -> dict:
        """Login and return session token."""
        password_hash = hashlib.sha256(
            (req.password + "traceroot_salt").encode()
        ).hexdigest()
        
        user = await self.db.get_user_by_email(req.email)
        
        if not user or user["password_hash"] != password_hash:
            raise HTTPException(status_code=401, detail="Invalid credentials")
        
        # Generate session token
        token = secrets.token_urlsafe(32)
        expires = datetime.utcnow() + timedelta(days=7)
        
        await self.db.create_session(
            user_id=user["id"],
            token=token,
            expires=expires,
        )
        
        # Set cookie
        response.set_cookie(
            key="session",
            value=token,
            httponly=True,
            secure=True,
            samesite="lax",
            expires=expires,
        )
        
        return {
            "success": True,
            "user": {"email": user["email"], "name": user["name"]}
        }
    
    async def logout(self, response: Response) -> dict:
        """Logout and clear session."""
        response.delete_cookie("session")
        return {"success": True}
```

**Effort**: 2 days | **Dependencies**: None

---

#### Task 4.2: SQLite User/Project Tables
**File**: `rest/dao/sqlite_dao.py` (extend existing)

Add new tables:

```python
# Add to _init_db method:

# Users table
await db.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT NOT NULL UNIQUE,
        password_hash TEXT NOT NULL,
        name TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
""")

# Sessions table
await db.execute("""
    CREATE TABLE IF NOT EXISTS sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        token TEXT NOT NULL UNIQUE,
        expires TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id)
    )
""")

# Organizations table
await db.execute("""
    CREATE TABLE IF NOT EXISTS organizations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        slug TEXT NOT NULL UNIQUE,
        created_by INTEGER NOT NULL,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (created_by) REFERENCES users(id)
    )
""")

# Projects table
await db.execute("""
    CREATE TABLE IF NOT EXISTS projects (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        slug TEXT NOT NULL,
        org_id INTEGER NOT NULL,
        api_key TEXT NOT NULL UNIQUE,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (org_id) REFERENCES organizations(id),
        UNIQUE(org_id, slug)
    )
""")

# Org memberships table
await db.execute("""
    CREATE TABLE IF NOT EXISTS org_members (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        org_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        role TEXT NOT NULL DEFAULT 'member',
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (org_id) REFERENCES organizations(id),
        FOREIGN KEY (user_id) REFERENCES users(id),
        UNIQUE(org_id, user_id)
    )
""")
```

**Effort**: 1 day | **Dependencies**: Task 4.1

---

#### Task 4.3: Login/Signup UI Pages
**File**: `ui/src/app/login/page.tsx` (new)

```tsx
"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const router = useRouter();
  
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError("");
    
    try {
      const res = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });
      
      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || "Login failed");
      }
      
      router.push("/explore");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setLoading(false);
    }
  };
  
  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="max-w-md w-full space-y-8 p-8 bg-white rounded-xl shadow">
        <div className="text-center">
          <h2 className="text-3xl font-bold">Sign in to Traceroot</h2>
        </div>
        
        <form onSubmit={handleSubmit} className="space-y-6">
          {error && (
            <div className="bg-red-50 text-red-500 p-3 rounded">
              {error}
            </div>
          )}
          
          <div>
            <label className="block text-sm font-medium text-gray-700">
              Email
            </label>
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md"
            />
          </div>
          
          <div>
            <label className="block text-sm font-medium text-gray-700">
              Password
            </label>
            <input
              type="password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md"
            />
          </div>
          
          <button
            type="submit"
            disabled={loading}
            className="w-full py-2 px-4 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50"
          >
            {loading ? "Signing in..." : "Sign in"}
          </button>
        </form>
        
        <div className="text-center text-sm">
          Don't have an account?{" "}
          <a href="/signup" className="text-blue-600 hover:underline">
            Sign up
          </a>
        </div>
      </div>
    </div>
  );
}
```

**Effort**: 2 days | **Dependencies**: Task 4.1

---

## 📊 Implementation Timeline

```
Week 1: Data Model & SDK Foundation
├── Day 1-2: Task 1.1, 1.2 (Span model extensions)
├── Day 3:   Task 1.3 (OTLP receiver updates)
├── Day 4-5: Task 2.1 (Python decorators)

Week 2: SDK & Auto-instrumentation
├── Day 1:   Task 2.2 (TypeScript decorators)
├── Day 2-4: Task 2.3 (Auto-instrumentation)
├── Day 5:   Testing & documentation

Week 3: UI Components
├── Day 1-2: Task 3.1 (LLM call view)
├── Day 3:   Task 3.2 (Tool call view)
├── Day 4:   Task 3.3 (Span type filter)
├── Day 5:   Task 3.4 (Token usage summary)

Week 4: Auth & Project Management
├── Day 1-2: Task 4.1 (Auth backend)
├── Day 3:   Task 4.2 (SQLite tables)
├── Day 4-5: Task 4.3 (Login/signup UI)

Week 5: Integration & Testing
├── Day 1-2: End-to-end testing
├── Day 3-4: Documentation
├── Day 5:   PR preparation
```

---

## 🔌 Integration Points with Existing Code

### Files to Modify

| File | Changes |
|------|---------|
| `ui/src/models/trace.ts` | Add SpanType, agent fields to Span interface |
| `rest/config/trace.py` | Add SpanType enum, extend Span model |
| `rest/routers/internal.py` | Parse agent attributes from OTLP spans |
| `rest/dao/sqlite_dao.py` | Add user/org/project tables |
| `rest/app.py` | Register new auth router |
| `ui/src/components/explore/SearchBar.tsx` | Add span type filter |
| `ui/src/components/explore/Trace.tsx` | Render span type-specific views |

### New Files to Create

| File | Purpose |
|------|---------|
| `examples/python/agent_decorators.py` | Agent-aware tracing decorators |
| `examples/typescript/agent-decorators.ts` | TypeScript agent decorators |
| `examples/python/auto_instrument.py` | Auto-instrumentation patches |
| `rest/routers/auth.py` | Basic authentication router |
| `ui/src/components/explore/span/LLMCallView.tsx` | LLM call visualization |
| `ui/src/components/explore/span/ToolCallView.tsx` | Tool call visualization |
| `ui/src/components/explore/TokenUsageSummary.tsx` | Token usage metrics |
| `ui/src/app/login/page.tsx` | Login page |

---

## ✅ Acceptance Criteria

### #369: Decorator-based SDK
- [ ] `@trace_llm()` decorator captures model, provider, token counts
- [ ] `@trace_tool()` decorator captures tool name, input, output
- [ ] `@trace_agent()` decorator captures agent name, type, iteration
- [ ] All decorators compatible with existing `@traceroot.trace()`
- [ ] Documentation with usage examples

### #370: OTEL Traces to Blob Storage
- [ ] OTLP receiver parses agent-specific attributes
- [ ] Spans stored with span_type field
- [ ] LLM metadata (model, tokens) persisted
- [ ] Tool metadata (name, input, output) persisted

### #371: Auto-instrumentation
- [ ] OpenAI ChatCompletion automatically traced
- [ ] Anthropic Messages automatically traced
- [ ] LangChain chains automatically traced
- [ ] Zero-code instrumentation via `instrument_all()`

### #372: Signup/Login
- [ ] Email/password registration works
- [ ] Email/password login works
- [ ] Session cookie set correctly
- [ ] Logout clears session

### #373: Org/Project Management
- [ ] Create organization
- [ ] Create project within org
- [ ] Generate API key per project
- [ ] List user's organizations

### #374: Tracing Page for LLM Calls
- [ ] LLM calls display with model/provider badge
- [ ] Token counts visible
- [ ] Prompt/completion expandable
- [ ] Latency displayed

### #375: Basic Filtering
- [ ] Filter by span_type (llm_call, tool_call, etc.)
- [ ] Filter by model name
- [ ] Filter by provider
- [ ] Existing filters still work

---

## 🚀 Getting Started

### 1. Clone and Setup
```bash
git clone https://github.com/traceroot-ai/traceroot
cd traceroot
git checkout -b feature/agent-observability
```

### 2. Install Dependencies
```bash
# Backend
pip install -e .

# UI
cd ui && npm install
```

### 3. Start Development
```bash
# Terminal 1: Backend
cd rest && uvicorn app:app --reload

# Terminal 2: UI
cd ui && npm run dev
```

### 4. Run Tests
```bash
# Backend tests
pytest test/

# UI tests
cd ui && npm test
```

---

## 📚 References

- [Issue #365 - Original Feature Request](https://github.com/traceroot-ai/traceroot/issues/365)
- [OpenTelemetry Semantic Conventions for LLM](https://opentelemetry.io/docs/specs/semconv/gen-ai/)
- [Existing Traceroot SDK Examples](./examples/)
- [Current Trace Model](./ui/src/models/trace.ts)
