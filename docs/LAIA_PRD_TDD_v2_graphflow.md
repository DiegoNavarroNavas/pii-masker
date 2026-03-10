# Local AI Browser Assistant (LAIA)
## Technical Design Document & Product Requirements

**Version**: 2.0  
**Date**: March 2026  
**Status**: Draft  
**Author**: AI Assistant  
**Framework**: graph-flow (Rust agent orchestration)

---

## 1. Executive Summary

### 1.1 Product Vision
A cross-platform, zero-configuration local AI assistant that enhances web browsing through intelligent document analysis using the Qwen3.5-4B model. The system runs entirely on the user's hardware with no external API dependencies, ensuring complete data privacy.

### 1.2 Core Value Proposition
- **Privacy-First**: All inference happens locally; zero data leaves the machine
- **Universal Access**: Single-binary distribution for Windows, macOS, and Linux
- **Zero Configuration**: Double-click to run; automatic model management
- **Browser Agnostic**: Works with Chrome, Firefox, Edge, and Safari via standard WebExtensions API
- **Agentic Workflows**: LangGraph-style stateful agent orchestration using graph-flow

### 1.3 Framework Selection: graph-flow

**Rationale**: graph-flow provides LangGraph-style explicit workflow orchestration in Rust, offering:
- **Type-safe state machines** with compile-time validation
- **Parallel execution** (FanOutTask) for multi-section document analysis
- **Human-in-the-loop** support via `NextAction::WaitForInput`
- **Production maturity**: 8 versions, 4,800+ downloads, MIT licensed
- **Lightweight**: ~1,200 SLoC core vs heavier alternatives

---

## 2. Product Requirements (PRD)

### 2.1 Target Users

| Persona | Technical Level | Use Case |
|---------|----------------|----------|
| **Privacy-Conscious Professional** | Medium | Analyze sensitive documents (legal, medical, financial) without cloud exposure |
| **Researcher/Academic** | High | Summarize papers, extract citations, compare sources across tabs |
| **Developer** | High | Quick documentation lookup, code review assistance |
| **General User** | Low | Simplify complex articles, answer questions about page content |

### 2.2 Functional Requirements

#### FR-001: Local LLM Inference
- **Description**: System shall run Qwen3.5-4B (Q4_K_M quantization) locally using llama.cpp
- **Acceptance Criteria**:
  - Support context windows up to 32,768 tokens (configurable based on available RAM)
  - Inference speed ≥ 5 tokens/second on modern CPU (Intel i5-12th gen or Apple M1 equivalent)
  - CPU-only operation (no GPU requirement)

#### FR-002: Automatic Model Management
- **Description**: System shall handle model downloading and validation automatically
- **Acceptance Criteria**:
  - On first run, download Qwen3.5-4B-GGUF (~2.1GB) from HuggingFace/Unsloth with progress indication
  - Verify SHA-256 checksum post-download
  - Support resume of interrupted downloads
  - Store models in platform-appropriate data directories

#### FR-003: Web Content Extraction
- **Description**: Browser extension shall extract readable content from web pages
- **Acceptance Criteria**:
  - Extract main article text (filter navigation, ads, footers) using Readability.js algorithm
  - Preserve structural information (headings, lists, tables)
  - Handle PDF documents opened in browser (basic text extraction)
  - Maximum extraction size: 120,000 characters (~30K tokens) per request

#### FR-004: Agentic Workflow Orchestration
- **Description**: System shall use graph-flow for multi-step document analysis workflows
- **Acceptance Criteria**:
  - Support sequential workflows (extract → analyze → summarize)
  - Support parallel workflows (FanOutTask for multi-section analysis)
  - Support human-in-the-loop for sensitive operations (via `NextAction::WaitForInput`)
  - Maximum 5 iterations per query to prevent infinite loops
  - Timeout 30s per step, 120s total per request

#### FR-005: Contextual Analysis
- **Description**: Process extracted content with user queries
- **Acceptance Criteria**:
  - Support natural language questions about page content
  - Maintain conversation history per browser tab (optional)
  - Response generation timeout: 60 seconds maximum
  - JSON mode support for structured data extraction

#### FR-006: Tool Calling
- **Description**: Agent shall support tool use for extended capabilities
- **Acceptance Criteria**:
  - Implement `Tool` trait for extractors, summarizers, and comparators
  - JSON Schema generation via `schemars` for type-safe arguments
  - Tool execution with timeout and error recovery

#### FR-007: Cross-Platform Distribution
- **Description**: Single binary execution on all major desktop platforms
- **Acceptance Criteria**:
  - Windows 10/11 (x64)
  - macOS 12+ (Intel & Apple Silicon)
  - Ubuntu 20.04+ / Fedora 35+ / Arch (x64, ARM64)

### 2.3 Non-Functional Requirements

| ID | Category | Requirement | Target |
|----|----------|-------------|--------|
| **NFR-001** | Performance | Cold start time (binary to ready) | < 5 seconds |
| **NFR-002** | Performance | Memory footprint (idle) | < 500MB (without model) |
| **NFR-003** | Performance | Memory footprint (inference) | < 4GB total (including model) |
| **NFR-004** | Reliability | Uptime | 99.9% (local service) |
| **NFR-005** | Security | No external network calls except model download | Enforced by firewall rules |
| **NFR-006** | Usability | Extension detection of backend | Auto-retry with exponential backoff |
| **NFR-007** | Maintainability | Log rotation | 7 days retention, max 100MB |
| **NFR-008** | Compatibility | Browser extension API | Manifest V3 |
| **NFR-009** | Debugging | Structured tracing for agent steps | OpenTelemetry compatible |
| **NFR-010** | Workflow | Compile-time state validation | All state transitions checked at build |

---

## 3. Technical Design (TDD)

### 3.1 System Architecture

```
┌─────────────────────────────────────────┐
│           User Machine                  │
│  ┌─────────────────────────────────┐   │
│  │     Browser Environment         │   │
│  │  ┌──────────┐    ┌──────────┐  │   │
│  │  │ Content  │───▶│ Background│  │   │
│  │  │ Script   │    │ Service  │  │   │
│  │  └──────────┘    └────┬─────┘  │   │
│  │       ▲               │        │   │
│  │       └───────────────┘        │   │
│  │            HTTP POST           │   │
│  └─────────────────────────────────┘   │
│                   │                     │
│                   ▼                     │
│  ┌─────────────────────────────────┐   │
│  │     Rust Backend (Binary)       │   │
│  │  ┌─────────────────────────┐   │   │
│  │  │   Axum Server :3000     │   │   │
│  │  └───────────┬─────────────┘   │   │
│  │              │                  │   │
│  │  ┌───────────▼──────────┐      │   │
│  │  │   graph-flow         │      │   │
│  │  │   Agent Graph        │      │   │
│  │  │  ┌────────────────┐  │      │   │
│  │  │  │ Extract Task   │  │      │   │
│  │  │  │ Analyze Task   │  │      │   │
│  │  │  │ Summarize Task │  │      │   │
│  │  │  └────────────────┘  │      │   │
│  │  └──────────────────────┘      │   │
│  │              │                  │   │
│  │  ┌───────────▼──────────┐      │   │
│  │  │   LlmManager         │      │   │
│  │  │  (llama.cpp client)  │      │   │
│  │  └──────────────────────┘      │   │
│  └─────────────────────────────────┘   │
└─────────────────────────────────────────┘
```

### 3.2 Component Design

#### 3.2.1 Core Backend (Rust)

**Responsibilities**:
- HTTP server (REST API) via Axum
- graph-flow agent orchestration
- Process lifecycle management (llama.cpp)
- Model file management (download, cache, verify)

**Key Modules**:

```rust
src/
├── main.rs              // Tokio runtime, graceful shutdown
├── server.rs            // Axum routes, CORS, state management
├── agent/               // graph-flow agent definitions
│   ├── graph.rs         // Workflow graph builder
│   ├── tasks.rs         // Task implementations (Extract, Analyze, etc.)
│   └── tools.rs         // Tool trait implementations
├── llm/
│   ├── manager.rs       // Spawns/monitors llama-server process
│   ├── model.rs         // GGUF metadata, download logic
│   └── provider.rs      // LlmProvider trait for graph-flow integration
├── extractors/          // Content cleaning (HTML→Markdown)
└── config.rs            // Platform paths, constants
```

#### 3.2.2 graph-flow Integration

**Agent Graph Definition**:

```rust
use graph_flow::{Task, GraphBuilder, Context, NextAction};
use serde::{Deserialize, Serialize};

// Define tasks
pub struct ExtractTask;
#[async_trait]
impl Task for ExtractTask {
    type Input = String;  // Raw HTML
    type Output = ExtractedContent;  // Clean text + metadata

    async fn execute(&self, input: Self::Input, ctx: &Context) -> NextAction {
        // Extract main content using readability algorithm
        let extracted = readability::extract(&input);
        ctx.insert("extracted", extracted.clone());

        if extracted.word_count > 10000 {
            // For long docs, fan out to parallel analysis
            NextAction::FanOut(vec!["analyze_chunk_1", "analyze_chunk_2"])
        } else {
            NextAction::Continue("analyze".to_string())
        }
    }
}

pub struct AnalyzeTask;
#[async_trait]
impl Task for AnalyzeTask {
    type Input = ExtractedContent;
    type Output = AnalysisResult;

    async fn execute(&self, input: Self::Input, ctx: &Context) -> NextAction {
        let llm = ctx.get::<LlmClient>("llm").unwrap();
        let query = ctx.get::<String>("user_query").unwrap();

        let prompt = format!(
            "Analyze this content and answer: {}

Content: {}",
            query, input.text
        );

        let response = llm.complete(&prompt).await;
        ctx.insert("analysis", response.clone());

        NextAction::Continue("summarize".to_string())
    }
}

pub struct SummarizeTask;
#[async_trait]
impl Task for SummarizeTask {
    type Input = AnalysisResult;
    type Output = String;  // Final answer

    async fn execute(&self, input: Self::Input, ctx: &Context) -> NextAction {
        // Optional: Summarize if analysis is too long
        NextAction::End(input.summary)
    }
}
```

**Graph Construction**:

```rust
pub fn build_analysis_graph() -> Graph {
    let extract = ExtractTask.boxed();
    let analyze = AnalyzeTask.boxed();
    let summarize = SummarizeTask.boxed();

    GraphBuilder::new("document_analyzer")
        .add_task(extract.clone())
        .add_task(analyze.clone())
        .add_task(summarize.clone())
        .add_edge(extract.id(), analyze.id())
        .add_edge(analyze.id(), summarize.id())
        .build()
}
```

#### 3.2.3 Tool Calling with graph-flow

**Tool Definition**:

```rust
use schemars::JsonSchema;
use serde::{Deserialize, Serialize};

#[derive(Serialize, Deserialize, JsonSchema, Debug)]
pub struct SearchArgs {
    #[schemars(description = "Search query terms")]
    pub query: String,
    #[schemars(description = "Maximum results to return", maximum = 10)]
    pub limit: Option<usize>,
}

pub struct SearchTool {
    client: reqwest::Client,
}

#[async_trait]
impl Tool for SearchTool {
    type Args = SearchArgs;
    type Output = Vec<SearchResult>;

    async fn call(&self, args: Self::Args) -> Result<Self::Output, ToolError> {
        // Implementation
        Ok(vec![])
    }

    fn name() -> &'static str {
        "web_search"
    }

    fn description() -> &'static str {
        "Search the web for current information"
    }
}
```

#### 3.2.4 LLM Process Spawning Strategy

**Why Spawning vs Embedding**:

| Aspect | Spawning | Embedding (llama-cpp-rs) |
|--------|----------|-------------------------|
| **Binary Size** | Smaller (~6MB + sidecar) | Larger (~15MB+ with static linking) |
| **Update Flexibility** | Swap llama-server binary independently | Recompile entire application |
| **Build Complexity** | Lower (no C++ toolchain needed for Rust compile) | Higher (bindgen, C++ deps) |
| **Debugging** | Easy (check llama logs separately) | Harder (monolithic) |
| **Memory Isolation** | Process boundary protects from crashes | Shared memory space |

**Implementation**:

```rust
pub async fn spawn_llama_server(&mut self) -> Result<(), LlmError> {
    let binary = self.get_platform_binary()?; // llama-server.exe, etc.

    let child = Command::new(binary)
        .arg("-m").arg(&self.model_path)
        .arg("--ctx-size").arg("32768")
        .arg("--port").arg("8080")
        .arg("--host").arg("127.0.0.1")     // localhost only
        .arg("--n-gpu-layers").arg("0")      // CPU only
        .arg("--parallel").arg("1")          // Single slot
        .arg("--batch-size").arg("512")      // Reasonable for CPU
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()?;

    // Health check loop (max 30s)
    self.wait_for_ready().await?;
    self.process = Some(child);
    Ok(())
}
```

### 3.3 Data Flow & API Specification

#### 3.3.1 REST API Endpoints

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| GET | `/health` | Liveness check, returns model status | None |
| POST | `/analyze` | Main analysis endpoint (triggers agent graph) | None |
| POST | `/analyze/stream` | Streaming analysis endpoint | None |
| GET | `/models` | List available/local models | None |
| POST | `/models/download` | Trigger model download | None |
| GET | `/version` | App version for updates | None |
| GET | `/debug/graph` | Returns current graph structure (dev mode) | None |

**Request/Response Schemas**:

```json
// POST /analyze
{
  "url": "https://example.com/article",
  "title": "Article Title",
  "content": "Extracted text content...",
  "query": "What are the main arguments?",
  "options": {
    "temperature": 0.7,
    "max_tokens": 1024,
    "parallel": true,
    "stream": false
  }
}

// Response
{
  "success": true,
  "data": {
    "answer": "The main arguments are...",
    "tokens_used": 1450,
    "processing_time_ms": 3200,
    "steps_executed": ["extract", "analyze", "summarize"]
  }
}
```

#### 3.3.2 LLM Prompt Engineering

**System Prompt** (for Qwen3.5 ChatML format):
```
<|im_start|>system
You are a helpful research assistant analyzing web content. 
Provide accurate, concise answers based on the provided context.
If the answer is not in the context, say "I don't see that information in the page."
Always cite specific sections when possible.
<|im_end|>
<|im_start|>user
URL: {{url}}
Title: {{title}}
Content: {{content}}
Question: {{query}}
<|im_end|>
<|im_start|>assistant
```

### 3.4 Platform Abstraction

#### 3.4.1 Data Directory Strategy

Using the `dirs` crate for cross-platform paths:

| OS | Model Storage Path |
|----|-------------------|
| Windows | `%LOCALAPPDATA%\LocalAI\models\` |
| macOS | `~/Library/Application Support/LocalAI/models/` |
| Linux | `~/.local/share/LocalAI/models/` |

#### 3.4.2 Binary Distribution Strategy

**Sidecar Pattern**:
- Main Rust binary (`local-ai`)
- Platform-specific `llama-server` binary (downloaded on first run or bundled)

**Download Sources** (llama.cpp releases):
- `https://github.com/ggml-org/llama.cpp/releases/download/b4500/llama-b4500-bin-win-avx2-x64.zip`
- `https://github.com/ggml-org/llama.cpp/releases/download/b4500/llama-b4500-bin-macos-arm64.zip`
- etc.

**Verification**: SHA-256 checksum validation for both llama-server and model files.

### 3.5 Error Handling & Resilience

#### 3.5.1 Failure Modes

| Scenario | Detection | Mitigation |
|----------|-----------|------------|
| llama.cpp crash | Process exit code | Auto-restart (max 3 attempts), fallback to error message |
| Model corruption | SHA-256 mismatch | Re-download automatically |
| Port conflict (3000/8080) | Bind error | Increment port (3001, 3002...) and notify extension |
| Out of Memory | System signals | Graceful degradation (reduce ctx-size to 8192), user alert |
| Network timeout (download) | 30s no data | Resume from byte offset |
| Agent loop timeout | graph-flow timeout | Return partial results with timeout warning |
| Tool execution failure | ToolError | Log error, continue with available tools |

#### 3.5.2 Logging Strategy

- **Level**: INFO for production, DEBUG for dev
- **Output**: 
  - Console (development)
  - File rotating logs (`logs/local-ai.log`, max 10MB x 3 files)
- **Content**: HTTP requests, LLM spawn/kill events, graph execution steps, errors (not content)
- **Privacy**: Never log page content or user queries

### 3.6 Security Architecture

#### 3.6.1 Threat Model

| Threat | Risk | Mitigation |
|--------|------|------------|
| **Localhost exploit** | Malicious site scanning localhost | CORS restricted to `chrome-extension://` origins only |
| **Model poisoning** | Downloaded model is malicious | SHA-256 verification against known good hash |
| **Memory inspection** | Other processes reading model weights | File permissions 0600 (user read only) |
| **CSRF** | Cross-site request to localhost | No state-changing GET requests; validate Origin header |
| **Agent escape** | Tool calls unintended actions | Tool allowlist, timeout limits, no network access for local tools |

#### 3.6.2 CORS Policy

```rust
// Strict CORS - only browser extensions
let cors = CorsLayer::new()
    .allow_origin([
        "chrome-extension://*".parse().unwrap(),
        "moz-extension://*".parse().unwrap(),
    ])
    .allow_methods([Method::GET, Method::POST])
    .allow_headers([header::CONTENT_TYPE])
    .max_age(Duration::from_secs(3600));
```

**Note**: Wildcards (`*`) not allowed with credentials, so we use reflection to validate specific extension IDs in production.

#### 3.6.3 Sandboxing

- llama-server runs with same user privileges (no elevation required)
- Optional: Use `seccomp` (Linux) or `sandbox-exec` (macOS) to restrict llama.cpp process to file read-only + localhost network

### 3.7 Performance Optimization

#### 3.7.1 Memory Management

**RAM Tiers**:

```rust
pub fn get_optimal_ctx_size() -> u32 {
    let total_ram = sysinfo::System::new_all().total_memory(); // MB

    match total_ram {
        r if r < 8192 => 8192,   // 8GB system: 8K context
        r if r < 16384 => 16384, // 16GB system: 16K context  
        r if r < 32768 => 32768, // 32GB system: 32K context
        _ => 131072,             // 64GB+: 128K context
    }
}
```

#### 3.7.2 Concurrency

- **Tokio**: Multi-threaded scheduler (num_cpus cores)
- **graph-flow**: Handles task spawning, parallel FanOutTask execution
- **HTTP**: Concurrent connections up to 100 (Axum default)

#### 3.7.3 Caching Strategy

- **Model**: Keep file handle open for faster reloads
- **graph context**: Cache compiled graph structures (avoid rebuilds)
- **Responses**: No caching (content is dynamic per page)
- **Sessions**: Optional conversation memory (LRU cache, 10 recent tabs max)

### 3.8 Build & Deployment

#### 3.8.1 CI/CD Pipeline

```yaml
# .github/workflows/release.yml
strategy:
  matrix:
    include:
      - target: x86_64-pc-windows-gnu
        os: ubuntu-latest
        suffix: .exe
      - target: x86_64-apple-darwin
        os: macos-latest
        suffix: ""
      - target: aarch64-apple-darwin
        os: macos-latest
        suffix: ""
      - target: x86_64-unknown-linux-gnu
        os: ubuntu-latest
        suffix: ""

steps:
  - uses: actions/checkout@v4
  - name: Build
    run: cargo build --release --target ${{ matrix.target }}
  - name: Package
    run: |
      mkdir -p dist
      cp target/${{ matrix.target }}/release/local-ai${{ matrix.suffix }} dist/
      tar czf local-ai-${{ matrix.target }}.tar.gz dist/
```

#### 3.8.2 Extension Distribution

- **Chrome Web Store**: Public or private (domain-restricted)
- **Firefox Add-ons**: AMO listing
- **Edge Add-ons**: Microsoft Store
- **Manual**: `.zip` file for side-loading (developer mode)

**Extension ID Management**:
- Development: Use fixed key in manifest for consistent ID
- Production: Store-issued IDs added to backend CORS whitelist

---

## 4. Development Phases (MVP Roadmap)

### Phase 1: Core Infrastructure (Week 1-2)
- [ ] Rust Axum server scaffolding
- [ ] llama.cpp process spawning (Windows/Linux/Mac)
- [ ] Model download with progress
- [ ] Basic `/health` and `/analyze` endpoints
- [ ] LlmProvider trait implementation for graph-flow integration

### Phase 2: graph-flow Integration (Week 2-3)
- [ ] Add graph-flow dependency and understand Task trait
- [ ] Implement ExtractTask (HTML → clean text)
- [ ] Implement AnalyzeTask (LLM completion)
- [ ] Implement SummarizeTask (optional final step)
- [ ] Build sequential graph (Extract → Analyze → Summarize)
- [ ] Test graph execution with error handling

### Phase 3: Advanced Workflows (Week 3-4)
- [ ] Implement FanOutTask for parallel document chunk analysis
- [ ] Add tool calling support (Tool trait implementations)
- [ ] Implement human-in-the-loop via NextAction::WaitForInput
- [ ] Add structured output parsing (JSON mode)
- [ ] Session storage for conversation history

### Phase 4: Browser Integration (Week 4-5)
- [ ] Manifest V3 extension scaffold
- [ ] Content script extraction (Readability.js port)
- [ ] Service worker ↔ Rust HTTP communication
- [ ] Popup UI showing agent execution steps/progress
- [ ] Handle long-running tasks with progress indicators

### Phase 5: Polish & Distribution (Week 5-6)
- [ ] Cross-compilation pipeline (GitHub Actions)
- [ ] Auto-updater mechanism
- [ ] Error handling & user notifications
- [ ] Documentation & README
- [ ] Performance optimization (context window management)

---

## 5. Open Questions & Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| **Qwen 3.5 GGUF availability** | High | Fallback to Qwen 2.5 7B if 3.5 not available on Unsloth |
| **llama.cpp breaking changes** | Medium | Pin to specific release (b4500+), test before auto-updating |
| **graph-flow maintenance** | Medium | MIT license allows forking; ~1,200 SLoC is manageable to maintain |
| **Antivirus false positives** | Medium | Code signing certificate ($), submit to AV vendors for whitelisting |
| **Browser store policies** | Medium | Ensure no remote code execution; all logic in binary |
| **Complex multi-agent workflows** | Low | graph-flow supports up to complex sequential/parallel flows; subagents not needed for MVP |

---

## 6. Appendix

### A. Technology Stack Summary

| Component | Technology | Justification |
|-----------|-----------|---------------|
| **Backend Language** | Rust | Memory safety, single-binary output, performance |
| **HTTP Framework** | Axum | Tokio-native, excellent middleware ecosystem |
| **Agent Orchestration** | graph-flow | LangGraph-style workflows, explicit state machines, MIT licensed |
| **LLM Integration** | llama.cpp (spawned) | Local inference, no API keys, CPU-optimized |
| **Async Runtime** | Tokio | Industry standard for Rust async |
| **Process Management** | `std::process` + `tokio::process` | Native Rust, async-aware |
| **Serialization** | Serde + schemars | De facto standard + JSON Schema generation |
| **Logging** | Tracing + Tracing-Subscriber | Structured logging for agent step observability |
| **Extension** | Vanilla JS + Manifest V3 | Maximum compatibility, minimal bundle size |

### B. External Dependencies

- **llama.cpp**: `llama-server` binary (b4500 or later)
- **graph-flow**: `0.4.0+` (crates.io)
- **Model**: `Qwen3.5-4B-Q4_K_M.gguf` (HuggingFace)
- **Browser APIs**: Storage, Scripting, ActiveTab (no special permissions)

### C. Success Metrics

- **Adoption**: 100+ GitHub stars in first month
- **Performance**: <3s time-to-first-token on modern hardware
- **Reliability**: <1% crash rate
- **Satisfaction**: Users can analyze 50-page documents without chunking errors

---

**Document Control**:  
This TDD/PRD is a living document. Implementation details may be refined during development, but architectural decisions (graph-flow for orchestration, HTTP vs Native Messaging, spawning vs embedding) are locked to ensure consistency across platforms.
