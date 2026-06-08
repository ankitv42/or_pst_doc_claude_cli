Types of Agent Memory

  There are four types. Interviewers at Google expect you to know at least the first three.

  ---
  1. In-Context Memory (Short-term)

  The simplest form. You include prior conversation turns directly in the prompt.

  System: You are an inventory assistant.
  User: What is the CP003 limit?
  Assistant: AED 20,000.
  User: What about CP001?   ← agent "remembers" context of the conversation

  How LangGraph does it: Add a messages: list[BaseMessage] field to the TypedDict state. Each node appends to it. The LLM sees the full history every call.

  Limitation: Context window fills up. 128k tokens sounds like a lot until you have a 6-hour HITL session with many back-and-forth approvals.

  ---
  2. In-Graph State Memory (What ORCA already has)

  The LangGraph TypedDict state IS memory within a single pipeline run. Agent 3 can read the scored_options that Agent 2 wrote. Agent 4 can read approval_required that Agent 3 set. That's shared
  mutable memory across 4 nodes.

  ORCA's exact quote for the interview:

  ▎ "LangGraph's TypedDict state is the shared memory for the run — every agent reads from and writes back to the same typed object, so Agent 3 doesn't have to repeat the work Agent 2 already did."

  ---
  3. Checkpoint / Episodic Memory (What ORCA already has)

  The SqliteSaver checkpointer persists the full state to disk. This means:
  - Server restarts don't lose the pipeline position
  - HITL can wait hours — the graph resumes from exact state
  - You can replay any past run by loading its checkpoint

  This is "episodic memory" — memory of a specific event (this pipeline run) that persists across time.

  ---
  4. Semantic / Long-term Memory (What ORCA could add)

  Memory that spans multiple pipeline runs — not just this one.

  For ORCA specifically, this would mean: "SKU-001 was escalated 3 times in the last 90 days. Each time it was CP001. Each time the human approved. The average order cost was AED 45,000." Agent 1
  could use that when assessing urgency.

  Two ways to implement it:

  a) Simple: Database table
  # Store: After every run, write a summary row
  INSERT INTO sku_memory (sku_id, date, route, cost, approved_by)

  # Retrieve: At start of next run for same SKU
  SELECT * FROM sku_memory WHERE sku_id = ? ORDER BY date DESC LIMIT 5
  Inject that history into the Agent 1 prompt.

  b) Semantic: Vector store
  Store past decision summaries as embeddings in ChromaDB. At run time, retrieve the 3 most similar past scenarios (by SKU category, urgency, pool) and inject them as context. This is "memory as RAG."

  ---
  How to Say It in the Interview

  ▎ "ORCA has two memory layers already. In-run memory is the LangGraph TypedDict state — all four agents share it. Cross-session memory is the SqliteSaver checkpoint — it persists the full state to
  ▎ SQLite so the HITL resume survives server restarts. The natural next layer is long-term episodic memory — storing past run decisions in the database and injecting them as context at the start of
  ▎ each new run for the same SKU. That's a new table and one extra query in Agent 1's fetch function."

  ---
  The Mental Model Table

  ┌──────────────────────┬───────────────────────────┬──────────────────────────────┬─────────────────────────┐
  │     Memory Type      │           Scope           │         Where Stored         │       ORCA Today        │
  ├──────────────────────┼───────────────────────────┼──────────────────────────────┼─────────────────────────┤
  │ In-context           │ Single LLM call           │ Prompt messages list         │ Optional messages field │
  ├──────────────────────┼───────────────────────────┼──────────────────────────────┼─────────────────────────┤
  │ In-graph state       │ Single pipeline run       │ TypedDict state              │ Yes                     │
  ├──────────────────────┼───────────────────────────┼──────────────────────────────┼─────────────────────────┤
  │ Checkpoint           │ Across restarts, same run │ db/checkpoints.db            │ Yes                     │
  ├──────────────────────┼───────────────────────────┼──────────────────────────────┼─────────────────────────┤
  │ Long-term / episodic │ Across multiple runs      │ New DB table or vector store │ Not yet — upgrade path  │
  └──────────────────────┴───────────────────────────┴──────────────────────────────┴─────────────────────────┘


### Teach me like andrew ng the concepts. I am bit fresher for server client memory concept. My doubt from your earlier response. I understood the In-graph state...it is simple...agent kicks and complete in 90 s or 3 min whaever....this memory in ram I am good. But how checkpoint is working bro for a HITL case whcih wait for let say 1 day ?? server needs to be active/up for one day right 

                                                                                                 

● Great question. This is the most important thing to understand about stateful agents.

  ---
  The Core Confusion: RAM vs Disk

  Think of your phone.

  - RAM = what's open right now. You close the app → gone.
  - Disk = the photos, messages, notes saved to storage. You turn off the phone → still there.

  Your computer works the same way. The Python process (the server) lives in RAM. If the server dies → RAM is wiped. Everything in RAM is gone.

  So the question is exactly right: if HITL waits 1 day, can the server stay up?

  The answer is: it doesn't have to.

  ---
  How SqliteSaver Works — Step by Step

  TIMELINE:

  10:00 AM  →  Supply planner clicks Analyse
  10:00 AM  →  Pipeline starts. Agent 1, 2, 3 run (90 seconds). All in RAM.
  10:01 AM  →  Agent 3 says: approval_required = True. Cost = AED 48,000.
  10:01 AM  →  LangGraph hits interrupt_before=["hitl_node"]

                ┌─────────────────────────────────────────┐
                │  PAUSE. Write EVERYTHING to SQLite disk. │
                └─────────────────────────────────────────┘

  10:01 AM  →  Server goes to sleep. Nobody touches it.
                RAM: nothing relevant.
                Disk (db/checkpoints.db): full state saved.

  11:00 AM  →  Server crashes. Render.com restarts it.
                RAM: empty. Process is fresh.
                Disk: still has the saved state.

  Next day
  10:00 AM  →  Manager opens dashboard. Sees ESCALATED alert.
  10:00 AM  →  Clicks Approve.
  10:00 AM  →  Dashboard sends: POST /pipeline/PIPE_SKU001_2026-06-07/approve

                ┌──────────────────────────────────────────────────────┐
                │  API reads db/checkpoints.db. Finds the saved state.  │
                │  Loads it back into RAM.                              │
                │  Resumes the graph from hitl_node.                    │
                └──────────────────────────────────────────────────────┘

  10:00 AM  →  hitl_node runs. Execution continues. Done.

  ---
  The Video Game Analogy (Andrew Ng style)

  You're playing a long RPG game. You reach a difficult boss.

  - You hit Save → game writes your progress (level, items, location) to the cartridge/disk.
  - You turn off the console. Power off. RAM gone.
  - Next week you come back. You hit Load Save.
  - Console reads from disk. You're back at the same spot, same items.

  That's exactly what SqliteSaver does.

  - Save = interrupt_before=["hitl_node"] triggers → LangGraph serializes the TypedDict state to db/checkpoints.db
  - Turn off console = server can crash, restart, sleep — doesn't matter
  - Load Save = POST /approve endpoint → reads checkpoint from disk, resumes graph

  ---
  What Gets Saved to Disk?

  The full TypedDict state object. In ORCA that means:

  {
    "sku_id": "SKU-001",
    "demand_summary": { ... },      # Agent 1's output
    "replenishment_options": [...], # Agent 2's output
    "scored_options": [...],        # Agent 3's output
    "approval_required": True,
    "recommended_option": "C",
    "pipeline_id": "PIPE_SKU001_2026-06-07",
    ...
  }

  LangGraph converts this Python dict → JSON bytes → writes to SQLite row. That's it.

  When you resume, it reads the JSON bytes back → converts to Python dict → graph continues.

  ---
  The Key Code Lines in ORCA

  At graph creation — tell LangGraph where to save:
  # agents/graph.py
  checkpointer = SqliteSaver.from_conn_string("db/checkpoints.db")
  graph = workflow.compile(
      checkpointer=checkpointer,
      interrupt_before=["hitl_node"]   # ← pause HERE and save to disk
  )

  At pipeline run — give it a unique ID (the "save slot"):
  config = {"configurable": {"thread_id": pipeline_id}}  # "PIPE_SKU001_2026-06-07"
  graph.invoke(state, config=config)

  At resume — load that exact save slot:
  graph.invoke(None, config=config)  # None = don't restart, resume from checkpoint

  The thread_id is the save slot name. Like naming your save file. Pass the same thread_id → resume that exact run.

  ---
  The One-Line Summary for Interview

  ▎ "The server doesn't need to stay up. LangGraph serializes the full state to SQLite at the interrupt point. The server can crash and restart — when the human approves, the resume endpoint loads the checkpoint from disk and
  ▎ the graph continues from exactly where it paused. It's the same principle as a video game save file."

  
  
  ### so "The full TypedDict state object. In ORCA that means:" so this is agentstate right, it is getting saved to two places (ram and disk both)...so in requiremt.txt we will be installing sqlite saver right ?so on render server  it will be installed and checked would be saved ??                                                                                                                                                                                

  ---
  Question 1: Is AgentState saved to RAM and Disk both?

  Not at the same time. Think of it as a relay race:

  Agents 1-3 running (90 seconds)
      → State lives in RAM only
      → LangGraph also writes a snapshot to disk after EACH node
        (so if it crashes mid-run, it can retry from the last node)

  LangGraph hits interrupt_before=["hitl_node"]
      → Writes FULL state to disk (db/checkpoints.db)
      → graph.invoke() RETURNS (the function call ends)
      → RAM is freed — Python has no reference to it anymore
      → Only disk has the state now

  Human approves (1 day later)
      → Resume endpoint reads from disk → loads into RAM
      → Graph runs hitl_node
      → Done → RAM freed again

  So: RAM while running. Disk at pause. RAM again on resume. Never both indefinitely.

  Yes, AgentState (the TypedDict) is exactly what gets serialized.

  ---
  Question 2: Is SqliteSaver in requirements.txt?

  Yes — and I found something important:

  requirements.txt (local dev):
    langgraph-checkpoint==4.1.1
    langgraph-checkpoint-sqllite==3.1.0   ✅ ← SqliteSaver is here
    aiosqlite==0.21.0
  ---
  The Right Fix for Production

  Swap SqliteSaver for PostgresSaver. One line change:

  # Today (local only)
  from langgraph.checkpoint.sqlite import SqliteSaver
  checkpointer = SqliteSaver.from_conn_string("db/checkpoints.db")

  # Production (Render + any cloud)
  from langgraph.checkpoint.postgres import PostgresSaver
  checkpointer = PostgresSaver.from_conn_string(os.getenv("DATABASE_URL"))

  ---
  How to Say It in the Interview

  ▎ "Locally, ORCA uses SqliteSaver — the state is serialized to a local SQLite file and survives server restarts. On Render free tier, the disk is ephemeral, so for production HITL the upgrade path is a one-line swap to
  ▎ PostgresSaver, pointing at a persistent Postgres database. The LangGraph checkpoint interface is the same — only the connection string changes."
 