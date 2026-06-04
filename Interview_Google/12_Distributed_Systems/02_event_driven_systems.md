# Event-Driven Systems

## What Is It? (Plain English)

An event-driven system is one where components communicate by publishing and reacting to events rather than by directly calling each other. An event is a record of something that happened: "Order was placed," "Inventory level dropped below threshold," "Payment was processed," "Model prediction was generated." When a component publishes an event, it does not know or care who will react to it. Other components subscribe to events they care about and take action accordingly.

Think of a newspaper publication. The newspaper does not know who will read it or what actions they will take. Subscribers receive the paper, read the parts they care about, and act on the information — some place stock trades, some adjust restaurant orders, some update travel plans. The newspaper and its subscribers are completely decoupled. Compare this to a phone call: the caller must know the recipient's number, the recipient must be available, and only one conversation happens at a time. Events are the newspaper model; synchronous API calls are the phone model.

Event-driven architecture differs from request-response in a subtle but profound way: the publisher relinquishes control. When Service A calls Service B's API, A is in control — it waits for B's response and handles it. When A publishes an event "inventory alert created," A is done. It does not know how many services will react, in what order, or whether they will succeed. This inversion of control makes systems more scalable and loosely coupled, but it makes them harder to reason about, trace, and debug.

## How It Works

```
REQUEST-RESPONSE (Synchronous)
──────────────────────────────
  Service A ──────────────────────────────► Service B
            ◄────────────────────────────── (waits for response)

  Characteristics:
  + Simple, easy to reason about
  + Immediate error feedback
  - Temporal coupling: A blocked if B is slow/down
  - Tight coupling: A must know B's API
  - Hard to scale: A's latency = sum of all B calls


EVENT-DRIVEN (Asynchronous)
────────────────────────────
  Service A ──► Event Bus ──► Service B (independent subscriber)
                         └──► Service C (independent subscriber)
                         └──► Service D (independent subscriber)

  Characteristics:
  + Loose coupling: A doesn't know about B, C, D
  + Temporal decoupling: B, C, D can be offline
  + Easy fan-out: add Service E with no A changes
  - Harder to trace: no single call stack
  - Eventual consistency: B may not have processed yet
  - Complex error handling: who handles B's failure?


EVENT SOURCING PATTERN
───────────────────────
  Traditional (State Storage):
  ┌──────────┐         ┌──────────────┐
  │ Command  │──────►  │ Current State│
  │ "Add 50  │  write  │ qty_on_hand: │
  │  units"  │         │    150       │
  └──────────┘         └──────────────┘
  History lost. "Why is it 150?" — unknown.

  Event Sourcing:
  ┌──────────┐         ┌──────────────────────────────────┐
  │ Command  │──────►  │ Event Log (append-only)          │
  │ "Add 50" │ append  │ [received_100, sold_30, received_80,│
  └──────────┘         │  sold_50, received_50]           │
                       └──────────────────────────────────┘
                              │
                              ▼ (replay events)
                       Current state: qty = 100-30+80-50+50 = 150

  Benefits: full audit history, time-travel queries, replay


CQRS PATTERN (Command Query Responsibility Segregation)
────────────────────────────────────────────────────────
  Write Side                       Read Side
  (Commands)                       (Queries)
  ┌───────────┐                   ┌───────────┐
  │Inventory  │── events ───────► │Analytics  │
  │Write DB   │                   │Read Model │
  │(normalised│                   │(denorm,   │
  │ for writes)│                   │ optimised │
  └───────────┘                   │ for reads)│
                                  └───────────┘
  Optimise writes and reads independently.
  Events keep both sides synchronised.


OUTBOX PATTERN
───────────────
  Problem: Write to DB AND publish event — what if one fails?

  ┌─────────────────────────────────────────┐
  │ Database Transaction (atomic):          │
  │  INSERT INTO orders (...)               │
  │  INSERT INTO outbox (event_payload, ...) │
  └─────────────────────────────────────────┘
        │
        ▼ (background process)
  Outbox Poller ──► Event Bus ──► Subscribers

  Guarantee: event is published if and only if DB write succeeded.
  Prevents partial failures (order created but event not published).
```

**Event sourcing** stores state as an append-only log of events rather than a mutable current-state record. The current state is computed by replaying events from the beginning (or from a snapshot). This provides a complete audit trail, enables time-travel queries ("what was inventory on March 15?"), and supports event replay for ML reprocessing.

**CQRS (Command Query Responsibility Segregation)** separates the write model (optimised for commands: normalised, transactionally consistent) from the read model (optimised for queries: denormalised, potentially eventually consistent). Events flow from the write side to the read side to keep them synchronised.

## Why Google Cares About This

Google's internal systems extensively use event-driven patterns for scalability. Google Cloud Pub/Sub, Cloud Events, and Eventarc are core GCP products built on event-driven principles. Senior AI/ML engineers must understand how to design AI pipelines that react to events from production systems (user actions, data updates, model predictions) rather than polling or being called directly. Event-driven patterns also underpin the HITL (human-in-the-loop) approval flows that senior candidates are expected to design.

## Interview Questions & Answers

### Q1: How does event-driven architecture differ from request-response, and when should you choose each?

**Answer:** The fundamental difference is about who controls the flow. In request-response, the caller is in control: it initiates a call, waits for a response, and decides what to do next. The interaction is synchronous, direct, and bilateral. In event-driven architecture, no single component is in control: a publisher emits an event, and zero or more subscribers react independently. The interaction is asynchronous, broadcast, and indirect.

Choose request-response when you need an immediate answer to proceed. A user clicks "check stock availability" on an e-commerce site — the UI must show availability before rendering the page. A payment processor must respond with success or failure before the user's session can continue. These interactions are inherently synchronous: the user is waiting. Forcing them into an event-driven model creates complexity without benefit — you would publish an event, wait for a response event, and simulate synchrony with extra infrastructure.

Choose event-driven when coupling between components should be minimal, when multiple downstream components need to react to the same occurrence, or when the originating component does not need to wait for reactions. An order placed on an e-commerce site triggers: inventory reservation, payment processing, shipping notification, analytics recording, fraud detection, and loyalty points calculation. These are all independent reactions to one event. If the analytics service is down, the order should still complete. If loyalty points take 5 seconds to calculate, the user should not wait. Event-driven architecture handles this fan-out elegantly and allows each downstream service to fail, scale, and deploy independently.

The practical hybrid is most common: synchronous APIs for user-facing queries (latency-sensitive, need immediate responses), event-driven for side effects and background processing (fan-out, eventual consistency acceptable). ORCA uses this hybrid: the dashboard calls the API synchronously for immediate feedback, the API internally triggers the pipeline asynchronously via events.

### Q2: What is event sourcing? What are its advantages and disadvantages for an AI inventory system?

**Answer:** Event sourcing is an architectural pattern where the state of a system is stored not as a current-state snapshot but as an append-only log of all events that have ever occurred. Rather than "the inventory level is 150," the system stores "received 100, sold 30, received 80, sold 50, received 50" and computes 150 by replaying the log. The event log is the primary source of truth; any view of current state is a derived projection.

The advantages for an AI inventory system are substantial. First, **complete audit history**: every change to inventory is recorded with a timestamp, actor, and reason. "Why did the AI recommend a reorder on March 15?" can be answered precisely by examining the event log for that day. Regulators and auditors can verify decisions without relying on logs that might have been rotated. This is increasingly required for AI governance.

Second, **time-travel queries**: because the full history is stored, you can replay events to see what the inventory state was at any point in time. This is invaluable for ML model training — you can reconstruct the exact feature values that the model saw when making a historical decision, rather than using current-state values that may have changed since.

Third, **event replay for ML reprocessing**: if a bug is discovered in the demand calculation logic, you can replay the historical event stream through the fixed logic to produce corrected outputs, without needing to re-collect historical data.

The disadvantages are also real. First, **query complexity**: getting the current state requires replaying all events or maintaining up-to-date projections (read models). Querying "what is current inventory for all 10,000 SKUs?" by replaying events for each is prohibitively expensive. This is solved by maintaining materialised projections (current-state views), but these add infrastructure complexity. Second, **event schema evolution**: if the structure of events must change, migrating historical events is painful — you either version events and handle both formats, or write migration scripts. Third, **storage growth**: an append-only log of all events for 4,700 stores and 100,000 SKUs over years is substantial storage. Compaction and archival policies are necessary.

For ORCA, event sourcing would replace the `scheduler.py` synthetic alert generation with a real stream of inventory delta events. The audit trail benefits are significant for AI governance; the query complexity requires investment in projection maintenance.

### Q3: Explain the outbox pattern. Why is it necessary in event-driven systems?

**Answer:** The outbox pattern solves the dual-write problem: when a service must atomically perform a database write AND publish an event, and both operations must either succeed together or fail together.

The naive approach is to write to the database first, then publish the event. This fails if the process crashes between the two steps: the database has the new record, but the event was never published. Downstream subscribers are never notified. Worse, the system is in an inconsistent state with no mechanism to detect or recover from it.

The alternative naive approach — publish the event first, then write to the database — has the inverse problem: the event is published, subscribers react, but the database write fails. Subscribers processed an event for a record that does not exist.

The outbox pattern solves this by writing both the business record and an "outbox record" (the event payload to be published) in a single database transaction. The database transaction is atomic: either both writes succeed, or neither does. The business record and the event "intent" are always consistent.

A separate, lightweight background process (the outbox poller) continuously scans the outbox table for unpublished events, publishes them to the event bus (Kafka, Pub/Sub), and marks them as published. If the poller crashes after publishing but before marking as published, it will re-publish the event on restart — this means events can be delivered more than once (at-least-once semantics), so subscribers must be idempotent.

For ORCA, the outbox pattern is relevant when writing an alert to the database and publishing a "pipeline trigger" event. Without the outbox, if the process crashes between the database write and the event publish, ORCA has a critical inventory alert with no AI pipeline triggered to address it. The outbox ensures that if the alert is in the database, a trigger event will eventually be published and processed.

### Q4: How would you design ORCA's pipeline triggering using an event-driven approach?

**Answer:** Currently, ORCA's pipeline is triggered by an explicit HTTP call to the FastAPI endpoint, which runs the pipeline in a background thread. An event-driven redesign would make the pipeline reactive — it would start automatically in response to inventory change events, without requiring explicit API calls.

The redesigned flow has four components. First, an **event producer**: inventory systems (POS, WMS, ERP) publish inventory delta events to a Kafka topic or Cloud Pub/Sub topic in near real-time. Each event contains SKU ID, store ID, quantity change, reason code, and timestamp.

Second, a **stream processor**: a Flink job or Cloud Dataflow pipeline consumes the inventory events, maintains per-SKU rolling state (current on-hand, demand rate, lead time), evaluates risk thresholds, and publishes `InventoryRiskDetected` events to a separate topic when thresholds are crossed. This separates concern: the source systems publish raw deltas; ORCA decides what is risky.

Third, the **ORCA pipeline worker**: a Cloud Run service or Kubernetes deployment subscribes to the `InventoryRiskDetected` topic and triggers a LangGraph pipeline run for each event. The worker publishes pipeline status events (`PipelineStarted`, `AgentCompleted`, `HITL_Required`, `ReorderApproved`) to an audit event log.

Fourth, the **HITL event handler**: when the pipeline publishes `HITL_Required`, the human approval is received via the dashboard and published as an `ApprovalDecisionMade` event. The pipeline worker subscribes to this event and resumes the LangGraph graph from its checkpoint.

This design has several advantages over the current model: zero polling (events trigger actions rather than a 3-second poll loop), horizontal scaling (multiple pipeline workers consume from the topic in parallel), complete event log for auditing (every state transition is recorded), and loose coupling (the dashboard never directly calls the pipeline — it communicates via events).

### Q5: What is CQRS and when is it appropriate for an AI system?

**Answer:** CQRS (Command Query Responsibility Segregation) separates the write path (commands that change state) from the read path (queries that return state). Instead of a single model that handles both reads and writes, you have a write model optimised for transactional consistency and a read model optimised for query performance.

The motivation is that write and read requirements are often in tension. A write model needs normalised data to ensure consistency and avoid update anomalies — a third-normal-form relational schema is ideal. A read model needs denormalised, pre-aggregated data to serve complex queries quickly — a wide, flat table or a pre-built materialized view is ideal. CQRS resolves this tension by maintaining both, using events to synchronise the write model's changes to the read model asynchronously.

CQRS is appropriate for AI systems when read and write load patterns are dramatically different and need independent scaling. In ORCA at scale, the write path (inventory events arriving from hundreds of stores simultaneously) and the read path (agents querying current stock levels, AI pipeline reading demand history) have very different characteristics. The write path needs high throughput and transactional integrity; the read path needs low latency and complex aggregation. With a single model, optimising for one degrades the other.

It is also appropriate when the query shape is known and stable — materialised views can be pre-computed for the most common agent queries (Agent 1's demand trend, Agent 2's supplier lead times, Agent 3's budget utilisation). These pre-built read models make agent response times deterministic.

CQRS is not appropriate when the system is simple, the team is small, or the operational complexity of maintaining two synchronised models outweighs the benefit. For a startup, a single PostgreSQL database handles both reads and writes. CQRS is justified when that database becomes the bottleneck — typically when write throughput and read query complexity cannot both be served by the same schema simultaneously.

## Key Points to Say in the Interview

- Event-driven architecture inverts control: publishers do not know about subscribers, enabling loose coupling and independent scaling
- Use synchronous request-response for latency-sensitive user-facing queries; use events for side effects, fan-out, and background processing
- Event sourcing stores history as an append-only event log — enables audit trails, time-travel queries, and ML data replay
- The outbox pattern solves dual-write atomicity — write to DB and event store in one transaction, publish from outbox in a background process
- CQRS separates read and write models — appropriate when read and write patterns are incompatible; events keep models synchronised
- ORCA's HITL flow is naturally event-driven: `HITL_Required` event → human decision → `ApprovalDecisionMade` event → pipeline resumes

## Common Mistakes to Avoid

- Using event-driven architecture for everything — synchronous calls are simpler and more appropriate for query/response patterns
- Not implementing the outbox pattern for dual-write operations — this creates silent inconsistency that is hard to detect and fix
- Ignoring eventual consistency implications — downstream subscribers may not have processed events yet, so "read your own writes" requires care
- Building CQRS prematurely — the synchronisation overhead is real; only add it when a single model demonstrably fails
- Not implementing distributed tracing (Jaeger, Cloud Trace) in event-driven systems — debugging without a trace ID that crosses service boundaries is very difficult

## Further Reading

- [Martin Fowler: Event Sourcing](https://martinfowler.com/eaaDev/EventSourcing.html) — Original pattern description with detailed examples of state reconstruction from event logs
- [Martin Fowler: CQRS](https://martinfowler.com/bliki/CQRS.html) — Concise explanation of command query separation with guidance on when it is and is not appropriate
- [System Design Primer: Event-Driven Architecture](https://github.com/donnemartin/system-design-primer#event-driven-architecture) — Event-driven patterns in the context of large-scale system design interviews
