My Sequencing and Reasoning

  Wave 1 — Make the eval gate trustworthy (0.5–1 day)

  A1: Calibrate 3 failing retrieval cases (evals/golden_dataset.py via evals/peek.py)

  Do this first, before anything else. Right now the CI gate is failing for the wrong reasons (keyword wording mismatch, not real
  retrieval failure). Every bug fix you do after this should show up as a green gate — if the gate is already broken, you can't trust
  it as a signal. This is the foundation everything else rests on.

  ---
  Wave 2 — Fix the real bugs, highest-visibility first (3–5 days)

  B1: Agent 4 briefing/decision mismatch (agents/graph.py)

  This is the most important item in the entire document. A demo where the briefing says "Option B / AED 6,953" but the system
  actually chose "Option A / AED 11,623" is disqualifying for a portfolio project — an interviewer will catch it immediately. Fix
  this before anything else that's user-visible.

  A2: Tune classa_safety judge criterion (evals/run_judge_eval.py)

  Do this immediately after B1 — not before. The document buries this detail but it's key: ~half the false alarms in classa_safety
  are caused by the briefing bug. Fix the root cause (B1), then the eval criterion will need much less tuning. Doing A2 before B1 is
  fixing the symptom.

  B2: Fix CrewAI cache_breakpoint (agents/crew.py + version pinning)

  Lower urgency than B1 because the fallback keeps the pipeline running. But for a demo or interview walkthrough, Agent 1 silently
  falling back to raw data is a gap — you lose the whole "multi-agent sub-crew" talking point. Do it in this wave, not the stretch.

  ---
  Wave 3 — Observability + tests (4–6 days)

  C1: LangSmith tracing (mostly env vars + metadata tags)

  This is disproportionately easy for the signal it gives. Fortune 100 JDs for senior AI roles literally list "agent observability" —
  being able to pull up a per-run trace of every LLM call, token count, and latency is a concrete demo moment in interviews. The
  document is right that it's largely automatic once env vars are set. Do it early in this wave.

  E3: ADRs (move up from stretch) (docs/adr/)

  The document treats this as low-priority stretch. I disagree — for Google specifically, system design interview prep is critical,
  and writing 5 ADRs (LangGraph choice, MCP tools vs direct DB, RAGAS decision, ChromaDB in CI, HITL keyed on cost) forces you to
  articulate why every major decision was made. That's exactly what a Google interviewer will ask. 2–3 hours of writing, high return.

  C2: pytest unit-test suite (tests/)

  Hardest item in this wave but most important for the Google application gap identified earlier. Start with test_scoring.py (the
  Agent 3 formula — pure math, no LLM needed), then test_routing.py, then test_tools.py with an in-memory SQLite. Mock Groq calls
  everywhere.

  ---
  Wave 4 — CI/CD automation (2–3 days)

  D1: Full CI/CD deploy pipeline (GitHub Actions → Render deploy hook)

  Now that tests exist, wire them into CI. PR gate = pytest + retrieval eval. Merge to main = auto-deploy to Render.

  D2: Enable RAGAS/judge evals in CI (GROQ secret + nightly schedule)

  Do this after D1 is stable. Keep it on a nightly schedule, not per-push, to avoid Groq rate limits.

  ---
  Wave 5 — Stretch (only if time allows)

  E1: Ollama local-LLM → good "cost control / privacy" talking point
  E2: HuggingFace embedding comparison → shows you benchmarked, didn't just pick defaults
  E4: Online/drift eval → the honest gap in any offline-only eval story; great interview topic even if you only design it rather than
  build it

  ---
  Summary Table

  ┌───────┬───────────────────────────────┬──────────────────────────────────────────────────────┐
  │ Order │             Item              │                  Why this position                   │
  ├───────┼───────────────────────────────┼──────────────────────────────────────────────────────┤
  │ 1     │ A1 — Calibrate retrieval eval │ Foundation — makes gate trustworthy                  │
  ├───────┼───────────────────────────────┼──────────────────────────────────────────────────────┤
  │ 2     │ B1 — Fix Agent 4 briefing bug │ Highest-visibility defect; disqualifying in a demo   │
  ├───────┼───────────────────────────────┼──────────────────────────────────────────────────────┤
  │ 3     │ A2 — Tune classa_safety judge │ Root cause (B1) must be fixed first                  │
  ├───────┼───────────────────────────────┼──────────────────────────────────────────────────────┤
  │ 4     │ B2 — Fix CrewAI error         │ Recovers the Agent 1 "sub-crew" talking point        │
  ├───────┼───────────────────────────────┼──────────────────────────────────────────────────────┤
  │ 5     │ C1 — LangSmith tracing        │ Easy win, high interview signal for senior AI roles  │
  ├───────┼───────────────────────────────┼──────────────────────────────────────────────────────┤
  │ 6     │ E3 — ADRs (moved up)          │ Google system design prep; 2-3 hrs, high return      │
  ├───────┼───────────────────────────────┼──────────────────────────────────────────────────────┤
  │ 7     │ C2 — pytest suite             │ Biggest Google gap; covers Agent 3 formula + routing │
  ├───────┼───────────────────────────────┼──────────────────────────────────────────────────────┤
  │ 8     │ D1 — Full CI/CD               │ Wire tests into the pipeline                         │
  ├───────┼───────────────────────────────┼──────────────────────────────────────────────────────┤
  │ 9     │ D2 — Judge evals in CI        │ Nightly gate for quality regression                  │
  ├───────┼───────────────────────────────┼──────────────────────────────────────────────────────┤
  │ 10    │ E1, E2, E4                    │ If time allows                                       │
  └───────┴───────────────────────────────┴──────────────────────────────────────────────────────┘

  The one place I diverge meaningfully from the document: ADRs belong in Wave 3, not stretch. For a Google application, architectural
  reasoning is tested directly in interviews — having written ADRs means you've already done that thinking.