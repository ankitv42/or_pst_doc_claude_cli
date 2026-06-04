# API Development for Production AI Systems

## What Is It? (Plain English)

An API (Application Programming Interface) is a contract between two pieces of software. It defines what requests you can make, what data to send, and what responses you will receive back. When your phone's weather app shows you the temperature, it is calling a weather service's API. When the ORCA dashboard asks whether a pipeline has finished, it is calling ORCA's own API.

REST (Representational State Transfer) is the dominant style for web APIs. It organises everything around resources — inventory items, pipelines, approvals — and uses standard HTTP methods (GET, POST, DELETE) to express what you want to do with them. A well-designed REST API is predictable: any engineer can look at the URL and method and immediately understand what it does, even if they have never seen the codebase.

FastAPI is Python's modern framework for building REST APIs. It combines Python type hints with automatic validation, OpenAPI documentation generation, and async support. It is the fastest Python web framework and the one most commonly used in AI/ML systems today because it integrates naturally with Pydantic (for data validation) and works well with async LLM calls.

## How It Works

```
REST API DESIGN PRINCIPLES
══════════════════════════════════════════════════════════
Resource    Method    URL                     Meaning
──────────────────────────────────────────────────────────
Pipelines   POST      /pipeline/run           Start a new pipeline run
            GET       /pipeline/{run_id}      Get status of a run
Approval    POST      /approve/{run_id}       Approve a pending decision
            POST      /reject/{run_id}        Reject a pending decision
Inventory   GET       /inventory              List all inventory items
            GET       /inventory/{sku_id}     Get one SKU
            PATCH     /inventory/{sku_id}     Update one field of a SKU

HTTP STATUS CODES THAT MATTER:
───────────────────────────────────────────────────────
200 OK              → Request succeeded, returning data
201 Created         → Resource created (POST that creates)
202 Accepted        → Request accepted, processing async
400 Bad Request     → Client sent invalid data
401 Unauthorized    → Not authenticated
403 Forbidden       → Authenticated but not allowed
404 Not Found       → Resource doesn't exist
409 Conflict        → Resource state conflict (already exists)
422 Unprocessable   → Valid JSON but fails validation (FastAPI default)
500 Internal Error  → Something broke server-side
══════════════════════════════════════════════════════════

ORCA's 202 PATTERN:
────────────────────────────────────────────────────────
Client          FastAPI              LangGraph Pipeline
  │                │                       │
  ├─POST /run─────►│                       │
  │                ├──start background task─►│
  │◄──202 + run_id─┤                       │ (running)
  │                │                       │
  ├─GET /status───►│                       │
  │◄──{status:running}                     │ (running)
  │                │                       │
  ├─GET /status───►│                       │
  │◄──{status:awaiting_approval}           │ (paused HITL)
  │                │                       │
  ├─POST /approve─►│                       │
  │                ├───────────resume──────►│
  │◄──200 OK───────┤                       │
────────────────────────────────────────────────────────
```

## Why Google Cares About This

Google's products expose APIs consumed by billions of clients. An engineer who designs APIs must think about backwards compatibility (changing a field name breaks every client), security (never returning more data than the caller is authorised to see), scalability (pagination prevents returning 10 million rows), and observability (structured error responses that let clients understand and recover from failures). FastAPI's Pydantic integration and background task patterns are direct solutions to these problems. Demonstrating that you have built and shipped a real API — like ORCA's — with proper status codes, async processing, and HITL resume endpoints shows you understand production API design, not just tutorials.

## Interview Questions & Answers

### Q1: What is the difference between PUT and PATCH? Between 401 and 403? Between 404 and 409?

**Answer:** These are the distinctions that separate engineers who have designed real APIs from those who have only consumed them.

**PUT vs PATCH:** PUT replaces an entire resource. You send the complete representation of what the resource should look like after the update. If you leave out a field, it gets set to null or removed. PATCH modifies only the fields you specify. All other fields stay unchanged. In practice, PATCH is almost always what users want when "updating" a record — they want to change the quantity without touching the price or description. PUT is used when replacing an entire document or when idempotent full replacement is the semantic intent.

```
PUT /inventory/SKU-001
Body: {"quantity": 50, "price": 12.99, "description": "Widget"}
→ Replaces the ENTIRE record. All fields must be present.

PATCH /inventory/SKU-001
Body: {"quantity": 50}
→ Only updates quantity. Price and description unchanged.
```

**401 vs 403:** 401 Unauthorized means "I don't know who you are — please authenticate." The client should respond by presenting credentials (login, send an API key). 403 Forbidden means "I know exactly who you are, but you are not allowed to do this." No amount of authentication will help — it is an authorisation issue. An ORCA example: 401 if no API key is present in the header; 403 if the API key belongs to a read-only user trying to call `POST /approve/{run_id}`.

**404 vs 409:** 404 Not Found means the resource does not exist at that URL. 409 Conflict means the resource exists but the request conflicts with its current state. For ORCA: `GET /approve/nonexistent-run` → 404 (run_id not found). `POST /approve/already-approved-run` → 409 (pipeline already completed, cannot approve again).

---

### Q2: Explain FastAPI's dependency injection system. How would you use it in an AI system?

**Answer:** Dependency injection in FastAPI means declaring what a route handler needs — a database connection, an authenticated user, a rate limit check — as function parameters, and letting FastAPI automatically call the dependency functions and provide the results. This separates concerns cleanly and makes routes testable by substituting mock dependencies.

```python
from fastapi import FastAPI, Depends, HTTPException, Header
from functools import lru_cache

app = FastAPI()

# Dependency: get database connection
def get_db():
    db = connect_to_db("db/orca.db")
    try:
        yield db          # yield makes this a context manager dependency
    finally:
        db.close()        # always cleanup, even on exception

# Dependency: verify API key
async def verify_api_key(x_api_key: str = Header(...)):
    if x_api_key not in VALID_API_KEYS:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return x_api_key

# Dependency: get LLM client (expensive, should be singleton)
@lru_cache(maxsize=1)
def get_llm():
    return ChatGroq(model="llama-3.1-8b-instant")

# Route uses all three dependencies — FastAPI wires them up
@app.post("/pipeline/run", dependencies=[Depends(verify_api_key)])
async def run_pipeline(
    request: PipelineRequest,
    db = Depends(get_db),
    llm = Depends(get_llm),
    background_tasks: BackgroundTasks = BackgroundTasks()
):
    run_id = generate_run_id()
    background_tasks.add_task(execute_pipeline, run_id, request, db, llm)
    return {"run_id": run_id, "status": "accepted"}
```

For testing, you can override dependencies:

```python
app.dependency_overrides[get_db] = lambda: MockDatabase()
```

In ORCA specifically, dependency injection should be used for: the LLM client (singleton, expensive to initialise), the database connection (context-managed cleanup), the ChromaDB vector store client, and authentication.

---

### Q3: How do you design a pagination API for a large dataset? What are the trade-offs between cursor-based and offset-based pagination?

**Answer:** Pagination is essential whenever a collection can grow beyond what fits in a single response. Two main strategies exist, and they have very different properties.

**Offset-based pagination** uses `?page=3&page_size=20`. The server runs `SELECT ... OFFSET 60 LIMIT 20`. Simple to implement and allows jumping to any page.

```python
@app.get("/inventory")
async def list_inventory(page: int = 1, page_size: int = 20):
    offset = (page - 1) * page_size
    items = db.execute(
        "SELECT * FROM inventory ORDER BY sku_id LIMIT ? OFFSET ?",
        (page_size, offset)
    ).fetchall()
    total = db.execute("SELECT COUNT(*) FROM inventory").fetchone()[0]
    return {
        "items": items,
        "page": page,
        "page_size": page_size,
        "total": total,
        "total_pages": (total + page_size - 1) // page_size
    }
```

Problems with offset pagination: (1) at large offsets (page 50,000), the database must scan and discard 1 million rows before returning the 20 you want — expensive. (2) If items are inserted or deleted between page requests, items can be skipped or duplicated.

**Cursor-based pagination** uses an opaque cursor (typically a base64-encoded last-seen ID or timestamp). The server runs `SELECT ... WHERE id > last_id LIMIT 20`. Much more efficient for large datasets — the index is used directly. Stable against insertions (no skipping/duplication).

```python
import base64, json

@app.get("/inventory")
async def list_inventory(cursor: str | None = None, limit: int = 20):
    if cursor:
        last_id = json.loads(base64.b64decode(cursor))["last_id"]
        items = db.execute(
            "SELECT * FROM inventory WHERE sku_id > ? ORDER BY sku_id LIMIT ?",
            (last_id, limit + 1)    # fetch one extra to detect next page
        ).fetchall()
    else:
        items = db.execute(
            "SELECT * FROM inventory ORDER BY sku_id LIMIT ?", (limit + 1,)
        ).fetchall()

    has_next = len(items) > limit
    items = items[:limit]
    next_cursor = None
    if has_next:
        next_cursor = base64.b64encode(
            json.dumps({"last_id": items[-1]["sku_id"]}).encode()
        ).decode()
    return {"items": items, "next_cursor": next_cursor}
```

Use offset pagination when: dataset is small, users need to jump to arbitrary pages, or the UI has page numbers. Use cursor pagination when: dataset is large, streaming sequential access, or real-time feeds.

---

### Q4: Explain JWT authentication. How would you implement it in FastAPI for ORCA?

**Answer:** JWT (JSON Web Token) is a self-contained authentication mechanism. Instead of looking up a session in a database on every request, the server issues a signed token at login that contains the user's identity and permissions. Every subsequent request includes this token, and the server verifies the signature without any database lookup.

A JWT has three parts separated by dots: `header.payload.signature`. The header identifies the signing algorithm. The payload contains claims — user ID, roles, expiration time. The signature is an HMAC or RSA signature over the header and payload using a secret key only the server knows.

```
JWT structure:
eyJhbGciOiJIUzI1NiJ9   .   eyJ1c2VyX2lkIjoiYW5rZXQiLCJyb2xlIjoiYXBwcm92ZXIiLCJleHAiOjE3MTk4MzM2MDB9   .   <signature>
      header                                         payload                                                    signature
```

FastAPI implementation for ORCA:

```python
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
from datetime import datetime, timedelta

SECRET_KEY = "your-secret-key"   # from environment variable in production
ALGORITHM = "HS256"
security = HTTPBearer()

def create_token(user_id: str, role: str) -> str:
    payload = {
        "user_id": user_id,
        "role": role,
        "exp": datetime.utcnow() + timedelta(hours=8)
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

def require_approver(token = Depends(verify_token)):
    if token["role"] != "approver":
        raise HTTPException(status_code=403, detail="Approver role required")
    return token

# Protected endpoint — only approvers can call this
@app.post("/approve/{run_id}")
async def approve_pipeline(run_id: str, user = Depends(require_approver)):
    # ... approval logic
```

API keys are simpler than JWT — just a long random string stored in a database. Use API keys for machine-to-machine communication (services calling services). Use JWT for human users (login sessions). OAuth2 delegates authentication to a trusted third party (Google, GitHub) — appropriate for consumer products.

---

### Q5: What are the key differences between synchronous and asynchronous FastAPI route handlers? When should you use BackgroundTasks vs a task queue like Celery?

**Answer:** A synchronous FastAPI route handler runs in a thread pool — FastAPI spawns a thread from a pool to run it, keeping the event loop free. An async route handler runs directly on the event loop. Both approaches work, but for different workloads.

Use async handlers when: the route calls async functions (LLM APIs, async database drivers, HTTP clients). FastAPI can serve many concurrent requests in a single thread.

Use sync handlers when: the route calls blocking synchronous code that you cannot easily convert, and you accept the thread pool overhead.

```python
# Async handler — best for LLM calls
@app.get("/inventory/{sku_id}")
async def get_sku(sku_id: str, db = Depends(get_db)):
    return await db.fetch_one("SELECT * FROM inventory WHERE sku_id = ?", sku_id)

# Sync handler — FastAPI runs this in a thread pool automatically
@app.post("/pipeline/run")
def run_pipeline_sync(request: PipelineRequest):
    # blocking call — ok, FastAPI handles it in thread pool
    result = synchronous_pipeline(request)
    return result
```

**BackgroundTasks vs Celery:**

`BackgroundTasks` runs the task in the same process as the FastAPI server, after the response is sent. It is simple (no extra infrastructure), but has limitations: if the server restarts, the task is lost. Tasks cannot be retried. You cannot distribute tasks across multiple workers. This is fine for ORCA because it runs as a single instance.

Celery is a distributed task queue. Tasks are serialised and sent to a message broker (Redis, RabbitMQ). Worker processes pick up tasks, run them, and store results. Tasks survive server restarts, can be retried automatically, and can be distributed across hundreds of workers. The trade-off is significant infrastructure complexity.

```
BackgroundTasks:
  ✓ Zero extra infrastructure
  ✓ No serialisation overhead
  ✗ Tasks lost on server crash
  ✗ Cannot distribute across workers
  → Use for: single-server apps, prototypes, ORCA

Celery + Redis:
  ✓ Distributed, fault-tolerant
  ✓ Retry logic, task monitoring (Flower)
  ✓ Handles thousands of concurrent tasks
  ✗ Redis/RabbitMQ infrastructure needed
  ✗ Task arguments must be serialisable
  → Use for: production scale, multiple workers, payment processing
```

ORCA's `BackgroundTasks` choice is intentional and appropriate for its current scale and deployment on Render's free tier. Acknowledging this trade-off in an interview demonstrates architecture maturity.

## Key Points to Say in the Interview

- "PATCH modifies specific fields; PUT replaces the entire resource."
- "202 Accepted is the right status code for async pipelines — the work is happening, check back later."
- "FastAPI dependency injection separates concerns and enables testing via `dependency_overrides`."
- "Cursor pagination is O(1) per page regardless of dataset size; offset pagination is O(n) at large offsets."
- "JWT is stateless authentication — the server verifies a signature, no database lookup needed per request."
- "BackgroundTasks is appropriate for single-server deployments; Celery is for distributed, fault-tolerant processing."
- "Always return structured error responses with a `detail` field — clients need to understand failures programmatically."
- "API versioning via URL prefix (`/v1/`, `/v2/`) is the most pragmatic approach; header versioning is cleaner but harder to test."

## Common Mistakes to Avoid

- Returning 200 OK for async operations that haven't completed — use 202 Accepted.
- Putting sensitive data (passwords, secrets) in JWT payloads — the payload is base64-encoded, not encrypted.
- Not setting JWT expiration (`exp` claim) — tokens that never expire are a security liability.
- Using blocking I/O calls in async route handlers without `run_in_executor` — blocks the entire event loop.
- Forgetting to validate and sanitise inputs at API boundaries — Pydantic models provide this automatically.

## Further Reading

- [FastAPI documentation](https://fastapi.tiangolo.com/) — comprehensive official docs including dependency injection, background tasks, and security
- [HTTP Status Codes (MDN)](https://developer.mozilla.org/en-US/docs/Web/HTTP/Status) — definitive reference for HTTP status code semantics
- [JWT.io](https://jwt.io/) — interactive JWT decoder and library reference for every language
