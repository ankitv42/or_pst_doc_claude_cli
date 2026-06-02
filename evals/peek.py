"""
ORCA — evals/peek.py
======================
Inspection tool (NOT a test). Calls ONE retriever method and prints the
context string it returns, so you can SEE what policy text an agent receives.

Use this BEFORE writing a golden test case: run it, read the output, then copy
real phrases from the output into golden_dataset.py's must_contain list.

RUN (from repo root):
    python evals/peek.py
"""

import sys
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
if os.path.exists(r"C:/lit"):
    sys.path.append(r"C:/lit")

from docs.rag.retriever import get_retriever

retriever = get_retriever()
print("RAG available?", retriever.is_available())
print("=" * 60)

# ── edit this call to inspect different situations ──────────────────────────
context = retriever.query_for_agent2(
    category="Personal Care",
    supplier_name="Hindustan FMCG",
    lead_time_too_late=True,
)

# other examples (uncomment to try):
# context = retriever.query_for_agent3(category="Grocery", urgency="CRITICAL",
#                                      abc_class="A", approval_pool="CP003")
# context = retriever.query_for_agent1(category="Grocery", abc_class="A",
#                                      event_name="Ramadan")

print("Context the agent receives:\n")
print(context)