# Rate Limiting: Controlling Traffic to Protect Systems

## What Is It? (Plain English)

Rate limiting is a mechanism that controls how many requests a user, client, or service can make to a system within a given time window. Without it, a single misbehaving client — whether a buggy script that accidentally fires 1,000 requests per second or a malicious actor deliberately overloading the system — can degrade the experience for all other users or crash the service entirely.

Think of rate limiting like a bouncer at a club. The club can safely handle 200 people at a time. Regardless of how many people are outside, the bouncer only lets people in at a pace the club can sustain. Everyone waits their turn fairly, and the club experience stays good for everyone inside. Without a bouncer, the first 500 people who rush in simultaneously create a crush that's bad for everyone.

Rate limiting has two beneficiaries that are easy to forget. It protects the *system* from being overwhelmed. But it also protects the *user* — by ensuring fair resource allocation so that one greedy client can't monopolize capacity that should be shared. In API design, rate limits also create a pricing lever: free tier gets 60 requests/minute, paid tier gets 1,000. This is how Groq, OpenAI, and nearly every API provider monetize their service.

## How It Works

```
FOUR RATE LIMITING ALGORITHMS:

1. Fixed Window Counter
─────────────────────────────────────────────────────────────
Time →  [00:00-01:00]   [01:00-02:00]   [02:00-03:00]
         Limit: 100      Limit: 100      Limit: 100
         Count: 75       Count: 99       Count: 30
                         ↑ At 01:00, count resets to 0
Problem: A client can make 100 req at 00:59 and 100 more
         at 01:01 — effectively 200 req in 2 seconds.

2. Sliding Window Log (precise, memory-heavy)
─────────────────────────────────────────────────────────────
Keep exact timestamps of every request.
At each request: count requests in the past 60 seconds.
If count < limit: allow. If count ≥ limit: reject.
Accurate but stores O(N) data per client.

3. Token Bucket (most common for APIs)
─────────────────────────────────────────────────────────────
 Bucket capacity: 100 tokens
 Fill rate: 10 tokens/second
 
 ┌────────────────────────────────────────┐
 │ Tokens: ████████████████████  (85/100) │
 └────────────────────────────────────────┘
 
 Each request costs 1 token.
 Tokens refill at 10/sec up to capacity.
 
 Burst behavior: client can burst up to 100 req
                 instantly, then sustained 10 req/sec
 Good for: bursty traffic that should be allowed
           in short bursts but limited long-term

4. Leaky Bucket (smooths traffic)
─────────────────────────────────────────────────────────────
Requests enter queue at any rate.
Queue drains at a fixed rate (e.g., 10 req/sec).
If queue full: reject new requests.

 ████ ████ ████ ← incoming burst
  ↓
 [Queue: max 100] → drains at exactly 10/sec → backend
  
 Guarantees: backend never sees more than 10 req/sec
 No bursting allowed — smooths all traffic
```

## Why Google Cares About This

Google's APIs serve billions of requests daily. Without rate limiting, Google Search or YouTube's API would be trivially vulnerable to denial-of-service attacks, and large corporate clients could inadvertently consume resources meant for millions of individual users. Google's API Gateway products (Cloud Endpoints, Apigee) implement rate limiting as a first-class feature. In a senior interview, rate limiting knowledge matters both as a system design pattern (how would you protect ORCA's API?) and as an operational concern (how do you handle being rate-limited *by* Groq or Google's own APIs in your system?).

## Interview Questions & Answers

### Q1: Compare the token bucket and leaky bucket algorithms. When would you use each?

**Answer:** Token bucket and leaky bucket are the two dominant rate limiting algorithms, and choosing between them depends on whether you want to allow bursting.

The token bucket algorithm works like a bucket that fills with tokens at a constant rate (the "refill rate") up to a maximum capacity. Each incoming request consumes one or more tokens. If enough tokens are available, the request proceeds. If not, it's rejected (or queued). The key property is that unused tokens accumulate: a client that hasn't made requests for 60 seconds builds up a full bucket, which it can then spend on a burst of requests all at once. Token bucket allows bursting up to the bucket capacity, then enforces the average rate over time.

The leaky bucket algorithm works like a bucket with a hole in the bottom — it drains at a constant rate regardless of how fast water (requests) flows in. Requests enter a queue; they leave the queue at a fixed, constant rate. If the queue is full when a new request arrives, it's rejected. The key property is that the outflow is always smooth — the downstream service never sees more than N requests per second, regardless of incoming traffic patterns. Leaky bucket smooths traffic but doesn't allow bursting.

Use token bucket when: your downstream service can handle bursts (LLM inference can batch), you want to be fair to clients who are below their quota (they can save up capacity), and you're designing the rate limit on the *incoming* traffic side. Use leaky bucket when: you're protecting a fragile downstream service from any spikes (a database that can only handle exactly X writes/second), you want strictly uniform downstream load, and you're designing the rate limit on the *outgoing* side.

In practice, most API rate limits (Groq, OpenAI, Google APIs) use token bucket semantics: you have a quota of requests per minute, unused quota doesn't roll over indefinitely (it caps at the max), and you can burst up to your quota limit.

### Q2: How do you implement rate limiting for a multi-tenant API and where does it live in the architecture?

**Answer:** Multi-tenant rate limiting means each client (tenant) has their own rate limit, tracked independently. Tenant A making 50 requests doesn't affect Tenant B's remaining quota. The implementation choice is where to enforce the limit: at the API gateway, at the application level, or both.

API gateway rate limiting (Kong, AWS API Gateway, Google Cloud Endpoints) is the preferred approach for production. The gateway sits in front of all application servers and enforces limits before requests reach your code. This is computationally efficient (rejected requests never touch your app servers) and centralized (you configure limits in one place, enforced for all instances). The gateway uses a distributed store (Redis) to share rate limit counters across all gateway instances, so a client that splits traffic across gateway nodes doesn't bypass limits.

Application-level rate limiting (middleware in FastAPI, Django, or similar) is appropriate for smaller deployments or when you need fine-grained control that the gateway doesn't provide. FastAPI with `slowapi` (which wraps `limits`) adds rate limiting as a decorator: `@limiter.limit("30/minute")` on an endpoint. The application middleware increments a Redis counter for the client's API key on every request.

Both layers can coexist. Gateway-level rate limiting protects the infrastructure from abuse at scale. Application-level rate limiting provides more granular control — different limits per endpoint (expensive pipeline trigger endpoints get tighter limits than cheap status polling endpoints), rate limits based on user tier (paying users get 10x the limit), and custom error messages.

For Redis-backed distributed rate limiting, the counter key is typically: `rate_limit:{client_id}:{window_start}`. The pipeline is atomic: `INCR rate_limit:clientA:1717497600` → `EXPIRE rate_limit:clientA:1717497600 60` → if count > limit, return 429. Using Redis atomic operations (INCR + EXPIRE in a single pipeline) ensures thread-safety across distributed application servers.

### Q3: How do you handle being rate-limited BY a third-party provider like Groq in your own system?

**Answer:** Being on the receiving end of rate limiting (as a client, not a server) is a common operational challenge for AI systems. Groq's free tier limits are approximately 30 requests per minute on some models. ORCA's 4-agent pipeline makes at least 4 Groq API calls per pipeline run. If 8 pipeline runs are triggered simultaneously, that's 32 calls in quick succession — likely hitting the rate limit.

The immediate technical response is to catch rate limit responses (HTTP 429) and implement retry with exponential backoff. The Groq SDK's `APIStatusError` with status code 429 should trigger the retry logic. The `Retry-After` header in the 429 response tells you exactly how long to wait — always respect this header rather than guessing.

The architectural response is to use a request queue with rate limit awareness. Instead of the pipeline directly calling Groq, it sends tasks to a queue. A single worker dequeues tasks and calls Groq at a controlled rate (29 calls/minute to stay under the 30 limit, with headroom). This rate-aware queue acts as a token bucket at the application level — it naturally paces Groq calls even under high load.

The operational response is to monitor rate limit hit rate as a metric. If you're hitting rate limits more than 1% of the time, you've either grown beyond the free tier's capacity and need to upgrade, or a bug is creating runaway API calls. Alert on rate limit hit rate. Log every 429 response with its context (which agent, which pipeline run) to debug anomalous patterns.

For critical production systems, maintain a multi-provider fallback: primary Groq → secondary OpenAI → tertiary Anthropic. When Groq is rate-limited, the factory automatically routes to the next provider. This requires maintaining API keys for multiple providers and slightly different prompt formatting, but it eliminates Groq's rate limit as a single point of failure.

### Q4: What is the sliding window rate limiting algorithm and when is it better than fixed window?

**Answer:** Fixed window rate limiting resets its counter at regular clock intervals. If the limit is 100 requests per minute and the window is 12:00–12:01, a client can make 100 requests at 12:00:58 and another 100 requests at 12:01:02 — 200 requests in 4 seconds, exploiting the window boundary. This "boundary burst" is the classic fixed window vulnerability.

Sliding window rate limiting solves this by using a window that slides with each request, always looking backward N seconds from *now* rather than from the last fixed boundary. At any point in time, the question is "how many requests has this client made in the last 60 seconds?" — regardless of where the clock minute boundaries fall. The client that made 100 requests at 12:00:58 will find that at 12:01:02, those 100 requests are still within the last 60 seconds — they used their quota, and the next 60 requests are blocked.

There are two implementations: sliding window log (exact, memory-heavy) and sliding window counter (approximate, memory-efficient). The sliding window log stores the exact timestamp of every request in a sorted set (Redis ZADD). On each new request, expire timestamps older than 60 seconds (ZREMRANGEBYSCORE), then count remaining entries. Precise but uses O(N) memory per client where N is the number of requests per window.

The sliding window counter is a clever approximation. It keeps two fixed-window counters: the current window and the previous window. It estimates the sliding window count as: `previous_window_count × (1 - elapsed_fraction) + current_window_count`. If the current minute is 30% elapsed, and the previous minute had 80 requests and the current minute has 20 requests, the estimated count is `80 × 0.7 + 20 = 76`. This is slightly inaccurate but uses only two counters per client — an excellent tradeoff for large-scale systems. Redis's `INCR` and TTL mechanism implements this efficiently.

Use sliding window when fairness matters and boundary bursting would cause real problems — financial APIs, safety-critical systems. Use fixed window when the slight boundary vulnerability is acceptable, because it's simpler to implement and reason about.

### Q5: How would you design rate limiting for ORCA's API to protect both Groq's quota and the system's own resources?

**Answer:** ORCA needs rate limiting at two levels: protecting the Groq API quota (30 req/min, shared across all users) and protecting ORCA's own pipeline execution resources (each pipeline run holds threads and database connections for 15-30 seconds).

At the API gateway level (or FastAPI middleware), I'd implement per-client rate limits on the expensive endpoints: `POST /run/{sku_id}` (triggers a pipeline run) gets a strict limit of 5 requests/minute per API key. `GET /pipeline/{run_id}` (polling for status) gets a generous limit of 60 requests/minute (it's lightweight). `POST /approve/{run_id}` and `/reject/{run_id}` (HITL decisions) get high limits since they must always be available to human reviewers.

At the application level, I'd add a global concurrent pipeline execution limit — a semaphore that allows at most N concurrent pipeline runs. This directly maps to Groq quota management: if each run uses 4 Groq calls, and Groq allows 30/minute, the maximum sustainable pipeline throughput is 7.5 runs/minute (30 calls ÷ 4 calls/run). With a concurrency limit of 4 simultaneous runs (each taking ~15s), throughput averages ~16 runs/minute — but each run's 4 calls are spread over 15 seconds, so the peak call rate is ~1 call/second/run × 4 concurrent runs = 4 calls/second = 240/minute. That would violate Groq's limit. The semaphore limit should be set at 2 concurrent runs maximum on the free tier, with monitoring to detect when the limit is frequently hit.

```
Rate Limiting Architecture for ORCA:
─────────────────────────────────────────────────────────────
Request arrives
    │
    ▼
[API Gateway / FastAPI Middleware]
    ├── /run endpoint: 5 req/min/client (token bucket, Redis)
    ├── /pipeline status: 60 req/min/client (token bucket)
    ├── /approve + /reject: 120 req/min (high limit for HITL)
    │
    ▼ (if not rate-limited)
[Global Pipeline Semaphore]
    ├── MAX 2 concurrent pipeline runs (Groq quota protection)
    ├── If semaphore full: return 429 with Retry-After: 30s
    │
    ▼ (if semaphore acquired)
[Pipeline Execution]
    ├── Groq calls: backoff on 429, Retry-After respected
    └── Release semaphore on completion/failure
─────────────────────────────────────────────────────────────
```

## Key Points to Say in the Interview

- Rate limiting protects both the server (from overload) and users (from each other, ensuring fair access)
- Token bucket allows controlled bursting; leaky bucket enforces smooth constant-rate output — choose based on whether bursting is acceptable
- Sliding window eliminates the boundary burst vulnerability of fixed window at moderate additional cost
- For multi-tenant APIs, use Redis as the distributed counter store so rate limits are enforced across all application instances
- When *receiving* rate limits from third parties, catch 429s, respect the Retry-After header, and implement a rate-aware request queue
- Rate limiting and circuit breakers complement each other: rate limiting prevents overload; circuit breakers handle failures
- For AI systems, the LLM API rate limit often becomes the bottleneck before the system's own compute resources — design around it explicitly

## Common Mistakes to Avoid

- Do NOT implement rate limiting with only in-process counters — in a horizontally scaled system, each instance has its own counter and the limit becomes N × limit per instance
- Do NOT ignore the Retry-After header — using random backoff when an exact retry time is provided wastes time and wastes quota
- Do NOT rate limit HITL approval endpoints aggressively — a warehouse manager unable to approve an order because of a rate limit is a business failure
- Do NOT conflate rate limiting with authentication/authorization — rate limiting controls volume; auth controls identity and permissions
- Do NOT set rate limits based on your current scale — size them for the traffic spikes you expect, not average load, or the rate limit itself becomes the cause of incidents

## Further Reading

- [Redis Rate Limiting Patterns](https://redis.io/docs/manual/patterns/rate-limiting/) — Official Redis documentation on implementing sliding window rate limiting with atomic operations
- [Cloudflare: How Rate Limiting Works](https://developers.cloudflare.com/rate-limiting/about/) — Practical explanation of sliding window algorithm from a company that implements rate limiting at massive scale
- [AWS API Gateway: Rate Limiting](https://docs.aws.amazon.com/apigateway/latest/developerguide/api-gateway-request-throttling.html) — Production reference for configuring rate limits in AWS's API gateway
- [ByteByteGo: Rate Limiter Design](https://blog.bytebytego.com/p/rate-limiting-fundamentals) — Visual walkthrough of all four rate limiting algorithms with system design interview context
- [Groq API Rate Limits Documentation](https://console.groq.com/docs/rate-limits) — The actual rate limits ORCA works with; useful for framing answers with real numbers
