# Reliability: Building Systems That Stay Up

## What Is It? (Plain English)

Reliability is the measure of how consistently a system performs its intended function over time. A reliable system works not just when conditions are perfect, but when servers fail, networks flicker, and traffic spikes unexpectedly. It's the engineering discipline behind the promise: "when you click that button, something useful will happen."

The vocabulary of reliability revolves around three related but distinct concepts. An **SLA** (Service Level Agreement) is a contract with your users or customers — "we promise 99.9% uptime." An **SLO** (Service Level Objective) is the internal engineering target you set to give yourself headroom to meet the SLA — "we will build to 99.95% to have a safety buffer." An **SLI** (Service Level Indicator) is the actual measurement — "our monitoring system is currently reporting 99.92% uptime." Think of it as: SLA is the promise, SLO is the target, SLI is the measurement.

The "nines" of availability are a useful mental model. 99% uptime sounds impressive but means 3.65 days of downtime per year — enough to lose a major customer. 99.9% is 8.7 hours per year. 99.99% is 52 minutes per year. 99.999% is 5.3 minutes per year — what financial transaction systems aim for. The jump from 99.9% to 99.99% is easy to say but extraordinarily hard to engineer; it requires eliminating every single component that could cause more than 52 minutes of downtime annually, including planned maintenance.

## How It Works

```
RELIABILITY ARCHITECTURE LAYERS:
─────────────────────────────────────────────────────────────
                                                             
Layer 1: Redundancy (no single points of failure)           
                                                             
  Without redundancy:                                        
  User → [Single Server]  ← if this dies, 100% outage      
                                                             
  With redundancy:                                           
  User → Load Balancer → [Server 1]                         
                       → [Server 2]  (if 1 dies, 2 serves)  
                       → [Server 3]  (if 1+2 die, 3 serves) 
─────────────────────────────────────────────────────────────
                                                             
Layer 2: Health Checks (detect failures fast)               
                                                             
  Load Balancer polls every 10s:                            
    GET /health → {status: "ok"}      ✓ keep in rotation    
    GET /health → timeout (10s+)      ✗ remove from rotation
    GET /health → {status: "ok"}      ✓ restore to rotation  
─────────────────────────────────────────────────────────────
                                                             
Layer 3: Circuit Breaker (stop calling a failing service)   
                                                             
  Normal:                                                    
    Service A → [Service B]  (succeeds)                     
                                                             
  Service B starts failing (50% errors):                    
    Service A → [Circuit Breaker OPEN]                      
                → returns fallback immediately               
                → stops calling B for 30 seconds            
                                                             
  After 30s:                                                 
    Service A → [Circuit Breaker HALF-OPEN]                 
                → sends 1 test request to B                 
                → if OK: CLOSE (resume normal)              
                → if fail: OPEN again                       
─────────────────────────────────────────────────────────────
```

**The 9s Math:**
```
Availability   Downtime/Year   Downtime/Month   Downtime/Week
──────────────────────────────────────────────────────────────
99%           3.65 days       7.31 hours       1.68 hours
99.9%         8.77 hours      43.8 minutes     10.1 minutes
99.99%        52.6 minutes    4.38 minutes     1.01 minutes
99.999%       5.26 minutes    26.3 seconds     6.06 seconds
──────────────────────────────────────────────────────────────
```

## Why Google Cares About This

Google's reliability engineering is legendary. They essentially invented Site Reliability Engineering (SRE) as a discipline — the Google SRE book (freely available online) is the industry standard reference. At Google, SREs manage error budgets (the inverse of SLOs) and use them as a mechanism to balance feature velocity with reliability. Every production system has an SLO; when the error budget is exhausted, feature releases pause until reliability is restored. In a senior AI interview, Google wants to see that you think about AI systems as production systems with reliability requirements — not just research experiments. An AI system that's right 90% of the time but down 10% of the time is not production-grade.

## Interview Questions & Answers

### Q1: Explain the difference between SLA, SLO, and SLI with a concrete example.

**Answer:** Let's use ORCA's inventory management API as the example. An SLI is a measurement: "percentage of API requests that return a successful response (HTTP 200 or 202) within 500 ms." This is what your monitoring system actually measures, second by second. SLIs must be carefully chosen to represent what users care about — availability and latency are the two most universal SLIs. For AI systems, you'd also measure prediction quality SLIs: "percentage of pipeline runs that produce a valid, parseable recommendation."

The SLO is your internal target: "99.5% of API requests must succeed within 500 ms, measured over a rolling 30-day window." The SLO is set conservatively — lower than what you're capable of when everything is working — because it must remain achievable even during incidents. If you set the SLO at 99.99% and a database maintenance window takes you to 99.97%, you've breached your SLO. SLOs should have a modest headroom below your best-case performance.

The SLA is the external contractual promise — typically slightly lower than the SLO, giving another buffer. "We guarantee 99% uptime. If we fall below this, you receive a service credit." The SLA number needs to account for planned maintenance, upstream dependencies you don't control (Groq's API availability, for ORCA), and disaster recovery time. A company promising 99.99% SLA for a system dependent on a third-party API with a 99.9% availability record is making a mathematically impossible promise.

The practical value of this framework is the **error budget**: 100% - SLO = the budget for failure. At 99.5% SLO over 30 days, you have 0.5% failure budget — equivalent to 3.6 hours of complete downtime. This budget is "spent" by every incident, every deployment that causes errors, and every planned maintenance window. When the budget runs low, you slow down deployments to protect reliability. This is how Google operationalizes the tradeoff between moving fast and staying stable.

### Q2: What is the difference between availability and reliability?

**Answer:** Availability and reliability are related but measure different things, and conflating them leads to misleading metrics. Availability is the percentage of time a system is operational — essentially uptime. A system that's up 99.9% of the time has 99.9% availability. Reliability is about consistent, correct behavior over time — a reliable system not only stays up but performs its function correctly and predictably.

A system can be highly available but unreliable. Consider a web server that's always running (high availability, near 100% uptime) but returns wrong data 5% of the time (low reliability). From an infrastructure perspective, the health check passes — the server responds to requests. From a user perspective, it's broken. This is particularly relevant for AI systems: an LLM inference endpoint can be 99.99% available (always responds) but 80% reliable (outputs correct answers only 80% of the time).

Another distinction: availability is typically measured as a ratio over time (percentage of minutes in a month when the system was up). Reliability is often measured as MTBF (Mean Time Between Failures) — the average time between incidents. A system with MTBF of 6 months is more reliable than one with MTBF of 1 week, even if both recover quickly from failures. The companion metric is MTTR (Mean Time To Recovery) — how quickly the system recovers when it does fail. High reliability means rare failures; short MTTR means fast recovery. Both together give you high availability.

For senior AI system design, you should differentiate: infrastructure reliability (the API stays up), model reliability (the model produces correct outputs), and data reliability (the features and data pipeline provide accurate inputs). A system can fail on any of these dimensions independently. Monitoring must cover all three.

### Q3: How do health checks work and what should a production health check endpoint return?

**Answer:** A health check is a lightweight API endpoint (typically `GET /health`) that a load balancer or orchestration system polls to determine whether a server instance is healthy enough to receive traffic. If the health check fails, the instance is removed from the load balancer pool — traffic stops routing to it — preventing degraded instances from serving users.

There are two levels of health checks with different semantics. A **liveness probe** asks "is the process still running?" — if it fails, restart the instance. A **readiness probe** asks "is this instance ready to serve traffic?" — if it fails, stop routing traffic to it but don't restart it. These are distinct because a slow startup (loading 7B model weights) doesn't mean the process is dead; it means it's not ready yet. In Kubernetes, both probes are configured separately for exactly this reason.

A production-grade health check endpoint does more than return 200 OK. It checks the critical dependencies: can the service connect to the database? Is the model loaded and responding? Is the cache accessible? A well-designed response body might be:

```json
{
  "status": "healthy",
  "timestamp": "2026-06-04T10:00:00Z",
  "checks": {
    "database": {"status": "ok", "latency_ms": 2},
    "llm_api": {"status": "ok", "latency_ms": 145},
    "rag_index": {"status": "ok", "chunk_count": 71},
    "queue": {"status": "ok", "depth": 3}
  },
  "version": "2.1.4",
  "uptime_seconds": 86400
}
```

If any check fails, the endpoint returns HTTP 503 (Service Unavailable) with details. The load balancer sees 503 and routes traffic away. Critically, health checks must be fast — under 1 second — because they run every 10–30 seconds and add up at scale. Avoid heavy database queries in health checks; use lightweight connection tests.

For ORCA specifically, the health check should verify: FastAPI is alive (trivial), SQLite is accessible (quick query), and the ChromaDB index is loaded (check collection count). The Groq API availability is trickier — you can't call Groq on every health check (it costs tokens and is rate-limited), so instead monitor Groq's status page separately and use a flag that gets set when a recent real call succeeded.

### Q4: What is a circuit breaker and how does it protect a system under failure?

**Answer:** A circuit breaker is a software pattern that wraps calls to an external dependency (another service, a database, an API) and automatically stops making those calls when the dependency starts failing. The name comes from electrical circuit breakers: when current exceeds a safe threshold, the breaker opens and stops current flow, protecting the circuit from damage.

Without a circuit breaker, when Service B starts failing slowly (taking 10 seconds per request instead of 200 ms), Service A keeps calling it. Threads accumulate waiting for responses. Eventually, Service A's thread pool is exhausted — it can't handle any requests, even requests that don't involve Service B. One slow dependency has cascaded into a complete outage. This is called a **cascade failure**.

With a circuit breaker, the behavior changes. The breaker monitors failures. After a threshold (e.g., 50% error rate over 60 seconds), it opens. In the open state, it immediately returns a fallback response without calling Service B at all — protecting Service A's threads. After a timeout (30 seconds), it transitions to "half-open": it lets one request through to test if B has recovered. If that request succeeds, the breaker closes (normal operation resumes). If it fails, the breaker reopens.

For ORCA's multi-agent pipeline, a circuit breaker around Groq API calls is valuable. If Groq is having an incident and all calls fail, without a circuit breaker the pipeline runs all agents, each waiting for timeouts before failing. With a circuit breaker, after the first few failures, subsequent pipeline runs immediately fail fast with a clear "LLM API unavailable" error — using no Groq quota and returning quickly. The dashboard can show a clear "service degraded" state rather than an indefinite spinner.

Libraries that implement circuit breakers: Python's `tenacity` (retry with backoff), `pybreaker`, or the pattern built into service mesh tools like Istio at the infrastructure layer. In Go, the `gobreaker` library is popular. The Hystrix library (Netflix, Java) popularized the pattern and its documentation is the best reference for understanding the state machine.

### Q5: How do you design for reliability when your system depends on a third-party API (like Groq or OpenAI) that you don't control?

**Answer:** Third-party API dependencies are reliability Achilles' heels because their uptime is outside your control and their degradation affects your SLA. A system with 99.9% internal reliability that depends on a third-party API with 99.5% availability can only achieve at most 99.4% combined availability (they multiply: 0.999 × 0.995 = 0.994). The practical approach has three components: defensive calling, graceful degradation, and multi-provider resilience.

Defensive calling means every call to the third-party API has a timeout, retry with exponential backoff and jitter, and circuit breaker protection. Never call an external API without a timeout — a hung connection will hang your entire request. A timeout of 10–15 seconds is reasonable for LLM generation; for shorter operations, 2–5 seconds. Retries should use exponential backoff (wait 1s, then 2s, then 4s, then give up) with jitter (random ±20% on the wait time) to avoid thundering herd problems.

Graceful degradation means designing fallback behavior when the API is unavailable. For ORCA, if Groq is down, the options are: (1) queue the pipeline run for retry when Groq recovers, (2) fall back to a simpler rule-based recommendation engine, or (3) immediately escalate to human review with "AI analysis unavailable." Option 3 is actually appropriate for ORCA's criticality — a stock decision with no AI recommendation is better served to a human than blocked entirely. The dashboard should show a clear status message rather than a generic error.

Multi-provider resilience is the most robust solution: maintain the ability to switch between LLM providers. ORCA's `agents/llm_factory.py` abstracts the LLM provider behind a factory pattern — an excellent design decision. To add provider resilience, you'd add a fallback chain: primary Groq → secondary OpenAI → tertiary Anthropic. If Groq's circuit breaker is open, the factory automatically tries OpenAI. This requires keeping API keys for multiple providers and testing the system with each, but it eliminates a single provider as a single point of failure.

## Key Points to Say in the Interview

- SLA is the external promise, SLO is the internal target, SLI is the actual measurement — understand all three and their relationship
- Error budget = 100% - SLO; when it's spent, deployments pause to protect reliability
- Availability and reliability are different: availability is uptime percentage; reliability includes correctness and consistency
- Health checks must be fast, check real dependencies, and distinguish liveness (is the process alive?) from readiness (can it serve traffic?)
- Circuit breakers prevent cascade failures — they protect the caller by failing fast when a dependency is degraded
- Third-party API dependencies cap your system's maximum achievable reliability — design around this with fallbacks and multi-provider patterns
- MTBF (frequency of failures) and MTTR (speed of recovery) together determine availability — improving either improves availability

## Common Mistakes to Avoid

- Do NOT use "availability" and "reliability" interchangeably — they are distinct concepts and conflating them signals imprecision
- Do NOT describe SLA and SLO as the same thing — the SLO is always stricter than the SLA to provide a safety buffer
- Do NOT forget that health checks can themselves become a reliability risk if they're too expensive — they run constantly and must be lightweight
- Do NOT promise SLAs that assume 100% availability of third-party dependencies — be realistic about the dependency chain
- Do NOT present circuit breakers as an error handling mechanism — they are a protection mechanism that deliberately stops making calls to prevent cascade failures

## Further Reading

- [Google SRE Book: Service Level Objectives](https://sre.google/sre-book/service-level-objectives/) — The Google Site Reliability Engineering book, free online; the definitive resource on SLAs, SLOs, SLIs, and error budgets
- [Martin Fowler: Circuit Breaker Pattern](https://martinfowler.com/bliki/CircuitBreaker.html) — The canonical description of the circuit breaker pattern with state diagrams
- [The Twelve-Factor App: Health Checks and Resilience](https://12factor.net/) — The foundational principles for building production-grade cloud applications
- [AWS: Health Checks for Load Balancers](https://docs.aws.amazon.com/elasticloadbalancing/latest/application/target-group-health-checks.html) — Concrete reference for configuring health checks with real production parameters
- [Netflix Tech Blog: Hystrix Circuit Breaker](https://netflixtechblog.com/making-the-netflix-api-more-resilient-a8ec62159c2d) — How Netflix used circuit breakers to prevent cascade failures in their microservice architecture
