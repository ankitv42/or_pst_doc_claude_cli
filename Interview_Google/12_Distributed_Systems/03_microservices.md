# Microservices

## What Is It? (Plain English)

Microservices is an architectural style where a software application is decomposed into small, independent services, each responsible for a specific business function, communicating with each other via well-defined APIs. Instead of one large application that does everything (a "monolith"), you have dozens of smaller applications that each do one thing well and can be deployed, scaled, and changed independently.

Think of a large department store versus a shopping mall. The department store is a monolith: one building, one inventory system, one management team, one IT system. If the electronics section needs new checkout software, the entire store must be updated and potentially closed during the upgrade. A shopping mall is microservices: each store (tenant) operates independently with its own systems, staff, and hours. The electronics store can remodel without affecting the bookshop next door. A new store can open without any other store being involved.

The promise of microservices is that small teams can develop, deploy, and scale their services independently, enabling larger organisations to move fast without coordinating every change across the entire codebase. The reality is that microservices trade application complexity for operational complexity: a monolith has one deployment, one database, one log stream; a microservices system has tens or hundreds of each, all of which must be orchestrated, monitored, and kept consistent with each other.

## How It Works

```
MONOLITH vs MICROSERVICES
──────────────────────────

  Monolith:
  ┌─────────────────────────────────────┐
  │          Single Deployment          │
  │  ┌────────┐ ┌───────┐ ┌──────────┐ │
  │  │  API   │ │  ML   │ │Dashboard │ │
  │  │Handler │ │Pipeline│ │  Logic   │ │
  │  └───┬────┘ └───┬───┘ └────┬─────┘ │
  │      └──────────┴──────────┘        │
  │           Shared DB + Code          │
  └─────────────────────────────────────┘
  + Simple deployment, one codebase, easy to test
  - Scale the whole thing for one bottleneck
  - Team coordination required for every release
  - One bug can bring down everything


  Microservices:
  ┌──────────┐    ┌───────────┐    ┌────────────┐
  │ FastAPI  │    │ LangGraph │    │ Streamlit  │
  │   API    │◄──►│ Pipeline  │    │ Dashboard  │
  │ Service  │    │  Service  │    │  Service   │
  └────┬─────┘    └─────┬─────┘    └─────┬──────┘
       │                │                │
       ▼                ▼                ▼
    API DB         Pipeline DB      (stateless)
    (Postgres)     (SQLite/Redis)

  + Scale each service independently
  + Teams deploy independently
  + Fault isolation: one service crash doesn't cascade
  - Distributed system complexity
  - Network calls replace function calls (latency, failures)
  - Data consistency across services is hard


CONWAY'S LAW
──────────────
  "Any organisation that designs a system will produce
   a design whose structure is a copy of the organisation's
   communication structure."

  Big monolith team ──► Monolith architecture
  3 separate teams  ──► 3-service architecture
  Many feature teams ──► Many microservices

  Implication: microservices are as much an organizational
  pattern as a technical one.


SERVICE MESH
─────────────
  Without service mesh:
  Service A ──HTTP──► Service B
  (A must implement: retries, auth, tracing, rate limiting)

  With service mesh (Istio, Linkerd):
  Service A ──► [Sidecar Proxy] ──► [Sidecar Proxy] ──► Service B
                 (handles: mTLS,     (handles: metrics,
                  retries,            circuit breaking,
                  load balancing,     tracing)
                  rate limiting)

  Service A and B contain ONLY business logic.
  Cross-cutting concerns handled by infrastructure.
```

**Service boundaries** should be drawn along business domains, not technical layers. A boundary is good when the team owning Service A can deploy it without coordinating with the team owning Service B. A boundary is bad when every feature requires changes to both services simultaneously (this is called "distributed monolith" — the worst of both worlds).

**Distributed tracing** (Jaeger, Zipkin, Google Cloud Trace) assigns a trace ID to each request and propagates it through all service calls. When a user reports a slow request, you can pull the trace ID and see which service in the chain was the bottleneck. Without distributed tracing, debugging cross-service issues is extremely difficult.

**API contracts** define the interface between services. When Service A calls Service B's API, both teams must agree on and honour the contract. Breaking changes require versioning (`/v1/`, `/v2/`) or a deprecation period. Consumer-Driven Contract Testing (Pact) allows consumers to publish their expectations and producers to verify they meet them — catching breaking changes before deployment.

## Why Google Cares About This

Google runs one of the largest microservices ecosystems in the world — its internal infrastructure (Borg, gRPC, Stubby) predates and influenced the industry's microservices movement. Senior AI/ML engineers at Google must understand service decomposition, API design, distributed tracing, and the operational overhead of microservices. They also need to recognise when a monolith is the right answer for a given team size and product stage, rather than defaulting to microservices for every new project.

## Interview Questions & Answers

### Q1: How do you decide where to draw service boundaries in a microservices architecture?

**Answer:** Drawing service boundaries is the most consequential decision in microservices design, and the most common source of "distributed monolith" failures where teams decomposed services along the wrong lines. The correct principle is to draw boundaries along **business domains** (Domain-Driven Design bounded contexts), not along technical layers.

A bad boundary splits a single business operation across multiple services. For example, separating "product data storage" from "product business logic" into two services means every product-related feature requires changes to both services simultaneously. The teams cannot deploy independently — they are a distributed monolith. The test is: can Team A deploy a new feature without Team B being involved? If not, the boundary is wrong.

A good boundary encloses all the data and logic for a specific business domain. An Inventory Service owns all inventory data and all inventory-related logic. An Orders Service owns all order data and logic. They communicate via well-defined events or APIs. Team Inventory can add a new replenishment algorithm without touching the Orders codebase.

Three practical heuristics. First, **team autonomy**: each service should be owned by a team small enough to feed with two pizzas (Bezos's rule). If the service is too large for one team, split it. If it is too small for meaningful work, it should be merged. Second, **data ownership**: each service should own its data store. Services that share a database are tightly coupled at the data layer regardless of how clean their APIs look. Third, **change frequency**: if two components always change together, they belong in the same service; if they change independently, they are good candidates for separate services.

For ORCA, the natural boundaries map to its existing components: an API Service (handles HTTP, authentication, rate limiting), a Pipeline Service (runs the LangGraph 4-agent pipeline, owns the pipeline state), a Data Service (manages inventory alerts, owns the database), and an MCP Service (exposes the MCP tools). These boundaries allow, for example, the Pipeline Service to be scaled independently when demand for AI recommendations spikes.

### Q2: What is Conway's Law and how should it influence microservices architecture?

**Answer:** Conway's Law, originally stated by Melvin Conway in 1967, observes that "organisations which design systems are constrained to produce designs which are copies of the communication structures of those organisations." In plain English: the structure of your software mirrors the structure of your organisation.

Conway's Law is not merely descriptive — it is predictive and prescriptive. If you have a large, centralised engineering team, they will build a monolith because a monolith is how one team naturally works. If you have three small, autonomous teams each owning a domain, they will naturally build three services. Attempting to impose a microservices architecture on a small, tightly-coupled team will result in a distributed monolith because the team's communication patterns require coordination across all services anyway.

The "inverse Conway maneuver" is the strategic application of this law: if you want a particular architecture, first reshape the organisation to match it. Before splitting a monolith into microservices, create domain-focused teams that own each proposed service. Only then do the technical boundaries become maintainable, because the organisational boundaries reinforce the technical ones.

For AI/ML systems, Conway's Law manifests in how ML platform teams are structured. If the data engineering team, model training team, and model serving team are three separate groups, you will naturally get three distinct systems (data pipeline, training infrastructure, serving infrastructure) with well-defined interfaces between them. If all ML work is done by a single team, a monolithic ML platform that couples all three is more likely — and works fine at that team size.

The takeaway for interviews: when asked "should we use microservices?", the technically honest answer starts with "what does your org look like?" A 5-person startup building microservices is making their lives harder for no benefit. A 500-person company with 20 domain teams cannot effectively coordinate on a monolith.

### Q3: When do microservices become a mistake? What are the signs of a distributed monolith?

**Answer:** Microservices are a mistake when the operational overhead of distributed systems exceeds the organisational benefit of service independence. They become counterproductive in several specific scenarios.

The clearest failure mode is the **distributed monolith**: you have decomposed a system into multiple services, but they are so tightly coupled that every feature requires simultaneous changes to multiple services and coordinated deployments. This combines the worst of both worlds: the complexity of a distributed system (network calls, partial failures, distributed tracing) without the organisational benefit of independent teams and deployments. Signs: teams routinely open pull requests in three or four services simultaneously, deployments require a "deployment order" because services must go live in sequence, one service going down cascades to failures in all services.

A second failure mode is **premature decomposition**: starting with microservices before the business domain is well understood. Martin Fowler calls this "microservices premium" — the cost of distributed systems is real, and it only pays off when the organisational scale and domain stability justify it. A startup that decomposes into 15 microservices on day one and spends 70% of engineering time on infrastructure is a common cautionary tale. The right sequence is: build a modular monolith first, understand the domain boundaries through actual usage, then extract services where the independence benefit is demonstrated.

A third failure mode is **chatty services**: a single user request triggers 10+ synchronous service-to-service calls. The latency compounds (50ms + 50ms + 50ms + ... = 500ms for a 100ms user-facing operation), and each hop is a new failure point. This usually indicates services were split too finely (nano-services, not microservices) and should be merged.

Signs of healthy microservices: each service can be deployed independently without coordination, teams can hire and onboard new engineers to a single service without needing to understand the entire system, each service has its own data store, failure in one service degrades functionality gracefully rather than causing total system failure.

### Q4: What is a service mesh and when is it worth the investment?

**Answer:** A service mesh is a dedicated infrastructure layer for handling service-to-service communication in a microservices system. It is implemented as a set of lightweight network proxies (sidecars) deployed alongside each service container. The sidecar intercepts all network traffic to and from the service and applies cross-cutting concerns — mutual TLS authentication, load balancing, circuit breaking, retries with exponential backoff, rate limiting, and distributed tracing — transparently, without requiring changes to the service code.

Without a service mesh, each service team must implement these cross-cutting concerns in their service code. Team A uses a different retry library than Team B. Team C implemented circuit breaking but Team D did not. When a bug is discovered in the mTLS implementation, it must be fixed in every service's codebase. The service mesh centralises these concerns into infrastructure code that is maintained once and applied everywhere.

The most widely used service meshes are Istio (built on Envoy proxy, the most feature-rich) and Linkerd (lighter weight, lower operational complexity). Google Cloud's Traffic Director is a managed service mesh that integrates with GKE.

The investment is worth it when you have 10+ services, multiple teams, and are struggling with: inconsistent security (not all services using mTLS), debugging cross-service latency (no distributed tracing), or reliability issues (services not implementing circuit breaking). At that scale, the centralised approach pays for itself in operational consistency.

It is not worth it for small systems (< 5 services) or early-stage products. A service mesh adds substantial operational complexity — the Istio control plane itself is a non-trivial distributed system. Debugging sidecar networking issues requires expertise. Start without a mesh; introduce it when the cross-cutting concern inconsistencies become a demonstrable problem.

### Q5: How does ORCA's architecture relate to microservices principles, and what would a production ORCA service decomposition look like?

**Answer:** ORCA's current architecture already reflects microservices thinking even though it is not formally decomposed into separate services. The three existing components — FastAPI backend, Streamlit dashboard, and MCP server — are conceptually separate services that communicate via well-defined interfaces (HTTP REST, MCP stdio protocol). The pipeline and the API are decoupled via an async execution model. This is good design that would translate cleanly into a formal microservices deployment.

A production ORCA decomposition would have five services. The **API Gateway Service** (`api/main.py`) handles all external HTTP requests: authentication, rate limiting, request routing, and the 202/polling pattern. It is stateless and horizontally scalable. It communicates with downstream services via internal APIs or a message queue.

The **Pipeline Orchestration Service** wraps `agents/graph.py`. It receives pipeline trigger messages, manages LangGraph execution, maintains HITL state via the MemorySaver checkpointer, and emits pipeline status events. This service is stateful (LangGraph checkpoints) and needs persistent storage. It scales by adding more worker instances consuming from the pipeline task queue.

The **Data Service** owns the SQLite/Postgres database: all reads and writes to `orca.db` go through this service's API. No other service accesses the database directly. This enforces the "one service, one database" principle and allows the data layer to evolve (migrate from SQLite to Postgres to a sharded database) without affecting other services.

The **RAG Service** wraps `docs/rag/retriever.py` and the ChromaDB vector store. Agents call this service to retrieve policy context. Because embedding models (nomic-embed-text) are memory-intensive, this service can be scaled and resourced independently from the lightweight API service.

The **MCP Service** (`mcp_server/server.py`) exposes the 6 MCP tools. In the current design, this runs as a subprocess; in production it would be a separate network service accessible via gRPC or HTTP, allowing tool invocations to be distributed, monitored, and rate-limited independently.

## Key Points to Say in the Interview

- Draw service boundaries along business domains, not technical layers — the test is "can Team A deploy without Team B?"
- Conway's Law: your software architecture mirrors your org structure — use the inverse Conway maneuver intentionally
- A distributed monolith is worse than a monolith — you get distributed system complexity without independence benefits
- Service meshes centralise cross-cutting concerns (mTLS, retries, tracing) into infrastructure; worth it at 10+ services
- Start with a modular monolith; decompose into services only when domain boundaries are well-understood and team size justifies it
- ORCA already applies microservices thinking: decoupled components with well-defined interfaces

## Common Mistakes to Avoid

- Decomposing by technical layer (data layer, business layer, UI layer) rather than business domain — creates chatty, tightly-coupled services
- Sharing a database between services — destroys service independence at the data layer
- Building microservices for a team of 3 — the operational overhead is not justified until team and domain scale demands it
- Not implementing distributed tracing from the start — debugging production issues without trace IDs is very difficult
- Treating microservices as a goal rather than a means — the goal is independent deployability and team autonomy; microservices are one way to get there

## Further Reading

- [Martin Fowler: Microservices](https://martinfowler.com/articles/microservices.html) — The original comprehensive article on microservices trade-offs and decision criteria
- [Martin Fowler: Strangler Fig Pattern](https://martinfowler.com/bliki/StranglerFigApplication.html) — How to incrementally migrate from a monolith to microservices without a big-bang rewrite
- [System Design Primer: Microservices](https://github.com/donnemartin/system-design-primer#microservices) — Microservices patterns and trade-offs in the context of large-scale system design
