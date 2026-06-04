# Caching: Storing Results to Avoid Recomputation

## What Is It? (Plain English)

Caching is the practice of storing the result of an expensive operation so that future requests for the same result can be served instantly, without repeating the work. The classic analogy is a librarian who keeps the 20 most-requested books on a small shelf right next to their desk. When someone asks for a popular book, the librarian grabs it from the small shelf in seconds rather than searching the entire library for minutes. The small shelf is the cache.

In computing, "expensive" means anything that takes time: a database query, an API call to another service, a complex calculation, or an LLM inference call. If the same query or calculation is performed repeatedly and the result doesn't change much between calls, caching that result and returning it directly eliminates the repeated expense. A well-tuned cache can reduce database load by 90%, cut response latency from 200 ms to 2 ms, and handle traffic spikes that would otherwise saturate backend services.

The price of caching is staleness. A cached result is a snapshot from the past. If the underlying data changes, the cache might return an outdated answer. "Cache invalidation" — deciding when a cached result is no longer valid and should be refreshed — is famously described as one of the two hardest problems in computer science (the other being naming things). This tension between freshness and performance is the central design challenge in every caching decision.

## How It Works

```
WITHOUT CACHE:
─────────────────────────────────────────────────────────────
Request: "What are the features for SKU-1234?"
         │
         ▼
    [FastAPI] → [Database: SELECT * FROM sku WHERE id=1234]
                             ↑ takes 50ms every time
─────────────────────────────────────────────────────────────

WITH CACHE (Cache-Aside / Lazy Loading):
─────────────────────────────────────────────────────────────
Request: "What are the features for SKU-1234?"
         │
         ▼
    [FastAPI] → [Redis cache] → cache HIT? → return result (2ms)
                     │
                     └── cache MISS → [Database] → store in cache
                                                  → return result (52ms)
                                                    (first time only)
─────────────────────────────────────────────────────────────

CACHING LAYERS IN A FULL STACK:
─────────────────────────────────────────────────────────────
User Browser ─► CDN ─────────────────────────────────► Static files (CSS, images)
                │
                ▼
          API Gateway ──► In-memory cache (per-process) ──► Hot config data
                │
                ▼
          FastAPI App ──► Redis (shared distributed cache) ──► DB query results,
                │                                               session state,
                ▼                                               rate limit counters
          Database ──────► Database buffer cache ──────────► Recent query pages
                │                                            (managed by DB itself)
                ▼
        Object Storage
─────────────────────────────────────────────────────────────

SEMANTIC CACHING FOR LLMS (GPTCache):
─────────────────────────────────────────────────────────────
User query: "What is the reorder policy for Class A SKUs?"
                │
                ▼
         [Embedding model] → query vector
                │
                ▼
    [Vector similarity search in cache]
         │
         ├── Cosine similarity > 0.95 → HIT → return cached LLM response
         │   (query: "reorder rules for Tier A items?" → same meaning)
         │
         └── No similar query found → MISS → call LLM → cache response
─────────────────────────────────────────────────────────────
```

## Why Google Cares About This

Google's entire infrastructure depends on caching. Google Search pre-computes and caches search results for popular queries. YouTube caches video metadata, thumbnails, and even segments of popular videos in CDN nodes close to users. Google's Bigtable and Memcache are used at massive scale. In a senior interview, caching knowledge signals that you understand performance engineering — not just "write the correct code" but "write code that runs efficiently at scale." They're specifically interested in whether you understand the tradeoffs: what to cache, for how long, and what breaks when the cache is stale.

## Interview Questions & Answers

### Q1: Explain the cache-aside pattern versus write-through caching. When is each appropriate?

**Answer:** Cache-aside (also called lazy loading) is the most common caching pattern. The application code is responsible for reading from and writing to the cache. On a read: check the cache first. If the value is there (cache hit), return it. If not (cache miss), read from the database, store the result in the cache with an expiry TTL, and return it. On a write: update the database, then invalidate (delete) the corresponding cache entry. The cache is *aside* — it's consulted and populated by the application, not automatically.

Cache-aside has a key property: the cache only contains data that has actually been requested. You never pre-load data that nobody wants. The tradeoff is cache stampede: when a popular cached item expires, many simultaneous requests miss the cache and all hit the database at once. The first request that misses starts loading the DB value; before it finishes, 50 other requests have also missed and are all querying the DB simultaneously. Solutions: probabilistic early expiration (randomly expire items slightly before their TTL, so the refresh happens before a thundering herd), or a lock mechanism so only one request refreshes the cache while others wait.

Write-through caching means the application always writes to the cache first, and the cache system synchronously writes to the database before confirming the write. Every write updates both cache and database atomically. The cache is always consistent with the database — no invalidation needed. The tradeoff is write latency: every write pays the database latency (defeating the point of caching for write-heavy workloads) and you cache many items that may never be read (wasting memory).

Write-through is appropriate when: reads and writes are balanced (a messaging inbox), cache consistency is critical (financial balances, inventory counts), and cache population on write is acceptable (you know every written item will be read soon). Cache-aside is appropriate when: reads vastly outnumber writes (product catalogs, user profiles, policy documents), write latency must be minimal, and some cache staleness is tolerable.

### Q2: What is semantic caching for LLMs and how does it work?

**Answer:** Traditional caching uses exact key matching: cache the response to request X, and when request X arrives again, return the cached response. This works well for deterministic queries ("what is the price of SKU-1234?") but not for natural language queries where two different phrasings mean the same thing. "What is the reorder policy for Class A SKUs?" and "How do I handle restocking for Tier A products?" are semantically equivalent — an exact-match cache treats them as completely different keys and misses both opportunities to cache.

Semantic caching solves this by converting queries to embedding vectors and using cosine similarity to check whether an incoming query is semantically similar enough to a cached query that the cached response is still relevant. The similarity threshold (e.g., 0.95 cosine similarity) controls the strictness: 0.95 means only very similar phrasings hit the cache; 0.85 allows more approximate matches at the risk of returning slightly mismatched responses.

GPTCache is the most popular library for semantic caching of LLM calls. It intercepts LLM API calls, converts the prompt to an embedding, searches a vector index of cached prompts, and returns a cached response if similarity exceeds the threshold. The performance impact is significant: a Groq API call takes 1–3 seconds; a cache hit takes under 20 milliseconds (embedding lookup + vector search). For an application like ORCA where the same policy questions appear repeatedly across many pipeline runs, semantic caching could reduce Groq API calls by 30–60%.

The implementation considerations: the embedding model used for the cache index must match or be compatible with the embedding model used for RAG (in ORCA's case, nomic-embed-v1.5). Cache entries need TTLs based on how quickly the underlying information changes — policy documents change rarely, so long TTLs (24 hours) are safe; market conditions change daily, so shorter TTLs (1–4 hours) are appropriate for demand-related queries. The cache key should also include the relevant context (which SKU, which agent) to prevent returning a cached response for Agent 2 when Agent 3 asked a similar question with different intent.

### Q3: How do you calculate cache hit rate and what does it tell you about your caching strategy?

**Answer:** Cache hit rate is the percentage of cache lookups that find a valid cached value, rather than having to fetch the result from the underlying source. The formula is: `hit_rate = cache_hits / (cache_hits + cache_misses)`. A hit rate of 95% means 95 out of every 100 requests are served from cache; only 5 go to the database.

The hit rate is the primary measure of whether your caching strategy is working. A high hit rate (>90%) means the cache is effectively absorbing load from the backend. A low hit rate (<50%) means your cache is missing frequently — possible causes: TTL is too short (items expire before they're reused), the cache is too small (items get evicted before reuse), the access pattern is not repetitive (every request is for a different item), or the cache key is too granular (minor variations in the key are treated as cache misses).

The useful derived metric is **byte hit rate**: percentage of data bytes served from cache. This matters for CDN caching where bandwidth costs money. A CDN with 99% hit rate on tiny HTML files but 50% hit rate on large video files has a poor byte hit rate — most bytes are cache misses, and those are the expensive ones.

For an LLM semantic cache, hit rate has additional nuance. A "hit" returns a response from a prior similar query. If the similarity threshold is too loose (0.70), you get high hit rate but some hits return semantically wrong responses — a "quality-adjusted hit rate" that discounts false hits. The right metric is: among hits that were used (not discarded by the caller), what percentage were rated as accurate by downstream evaluation? This requires sampling and human (or LLM-judge) review, making it a quality metric, not just a performance metric.

### Q4: What is cache invalidation and why is it called one of the hardest problems in computer science?

**Answer:** Cache invalidation is deciding when a cached value is no longer fresh and should be removed or updated. It's conceptually simple — "when the underlying data changes, update the cache" — but enormously difficult in practice because systems are distributed, data changes through multiple paths, and the consequences of stale cache serving wrong data range from mildly annoying to catastrophically wrong.

The simplest strategy is TTL-based (Time to Live) expiration: every cache entry has a timer, and after the timer expires, the entry is evicted. The next request re-fetches from the source. Simple, but the tradeoff is that entries may be stale for up to TTL seconds after the underlying data changes. For product prices, a 5-minute TTL is fine — prices don't change that often. For inventory stock counts, a 5-minute stale count could cause significant over-selling. For financial balances, any staleness is unacceptable.

Event-driven invalidation is more precise: when the database row for SKU-1234 is updated, an event is published (on a message bus or via database triggers), and the cache listener deletes the corresponding cache entry. The next request refreshes from the fresh database value. This is near-real-time freshness. The complexity is the bookkeeping: every cache entry must be traceable back to the data it depends on, and every data change must correctly invalidate all affected cache entries. In practice, a single database row might be the basis for 20 different cache entries (different views, aggregations, joined queries) — invalidating all of them correctly requires careful mapping.

The "hardest problem" label comes from distributed systems complexity. In a single-server cache, invalidation is straightforward. Across a distributed cache (many Redis nodes), ensuring that an invalidation message reaches every node that might have a copy of the stale entry, without race conditions, without double-invalidation, and without accidentally invalidating a recently-refreshed entry — this is genuinely hard. Real systems often accept limited staleness as an engineering tradeoff: "cache entries are eventually consistent with the database within N seconds" is a contractual statement, not a failure.

### Q5: When can caching break an AI system and how do you prevent it?

**Answer:** Caching is especially dangerous in AI systems because ML models depend on inputs being fresh representations of the current world state. Serving a cached feature to a model is effectively telling the model "here is what the world looked like X minutes ago" — and if the model makes a consequential decision (reorder quantity, drug dosage, fraud alert), stale inputs mean consequential wrong decisions.

The most dangerous pattern is caching features that are proxies for real-time state. If ORCA caches "current stock level for SKU-1234" for 10 minutes, and a large order comes in at minute 2 that depletes the stock, the pipeline runs at minutes 3–10 all see the pre-order stock level. They all conclude "stock is adequate; no reorder needed." Meanwhile, the SKU is actually depleted. Stockouts occur. The cache caused a direct business failure.

The prevention strategy is to classify features by their change frequency and consequence of staleness. Real-time state (inventory counts, live prices, order status) should either not be cached or cached with very short TTLs (under 30 seconds). Slowly-changing reference data (supplier lead times, SKU classification, store configuration) can be cached for hours. Historical aggregates (30-day rolling average, seasonality coefficients) can be cached for days.

LLM output caching has a different risk: the cached LLM response was correct when it was generated, but the context has since changed. A cached "ESCALATE this order" recommendation for SKU-1234 might have been correct last Tuesday when supply chain risk was high. On Friday, when the supply chain normalized, the same query hits the cache and returns "ESCALATE" — wrong given the current context. The solution is to include volatile context variables (supply chain risk score, current inventory level, alert timestamp) in the cache key. Even if the query text is semantically similar, different context values should produce different cache lookups.

A practical rule for AI caching: never cache the final decision (ESCALATE/AUTO_EXECUTE). Cache intermediate computations that are expensive and stable (embeddings, historical statistics, policy document chunks). The final decision should always be computed fresh from current inputs, even if some of those inputs were themselves cached.

## Key Points to Say in the Interview

- Caching is a performance tool with a staleness tradeoff — every caching decision must explicitly address what happens when the cached data is wrong
- Cache-aside is for read-heavy workloads with tolerable staleness; write-through is for read-write balanced workloads requiring strong consistency
- Cache hit rate is the primary health metric; target >90% for significant load reduction
- Semantic caching extends caching to LLMs using embedding similarity — a game-changer for applications with repetitive natural language queries
- Cache invalidation is the hard problem: TTL-based is simple but imprecise; event-driven is precise but complex
- Never cache final AI decisions; cache stable intermediate computations
- Cache stampede (thundering herd on cache expiry) is a reliability risk — mitigate with probabilistic early expiration or request coalescing

## Common Mistakes to Avoid

- Do NOT cache without TTLs — a cache that never expires will serve stale data forever as the underlying data evolves
- Do NOT cache real-time state (inventory counts, prices) with long TTLs in an AI system — the model will make decisions based on outdated state
- Do NOT think of the cache as a permanent store — it is always throwaway data that can be regenerated; never use it as the system of record
- Do NOT implement in-process caching (variables in your FastAPI app's memory) without acknowledging that horizontal scaling creates multiple inconsistent caches
- Do NOT forget that caching reduces load on the backend, not on the cache itself — a popular cache under heavy load can become the bottleneck, requiring Redis clustering

## Further Reading

- [Redis Documentation: Caching Patterns](https://redis.io/docs/manual/patterns/) — Official Redis documentation on cache-aside, write-through, and cache-as-primary-db patterns
- [AWS: Caching Best Practices](https://aws.amazon.com/caching/best-practices/) — Comprehensive guide to CDN, database, and session caching with practical tradeoff guidance
- [GPTCache: Semantic Caching for LLMs](https://github.com/zilliztech/GPTCache) — The leading open-source library for LLM semantic caching; well-documented with real performance benchmarks
- [Martin Fowler: Patterns of Enterprise Application Architecture — Caching](https://martinfowler.com/eaaCatalog/) — Foundational cache patterns (cache-aside, write-through, write-behind) with pattern descriptions
- [Cloudflare: CDN Caching Documentation](https://developers.cloudflare.com/cache/concepts/cache-control/) — Practical guide to HTTP Cache-Control headers and CDN behavior; essential for understanding the browser-to-server caching stack
