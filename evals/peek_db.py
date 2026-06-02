"""
ORCA — evals/peek_db.py
=========================
Inspection tool for saved pipeline decisions in db/orca.db.

Use it to see the pipeline_log columns, count saved runs, and read one saved
decision field-by-field (to verify a judge score BY HAND).

RUN (from repo root):
    python evals/peek_db.py                 # most recent run
    python evals/peek_db.py SKU00033        # latest run for one SKU
"""

import sys
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "db" / "orca.db"

sku_filter = sys.argv[1] if len(sys.argv) > 1 else None

conn = sqlite3.connect(str(DB))
conn.row_factory = sqlite3.Row
cur = conn.cursor()

cur.execute("PRAGMA table_info(pipeline_log)")
cols = [r["name"] for r in cur.fetchall()]
print("pipeline_log columns:")
for c in cols:
    print("   -", c)

cur.execute("SELECT COUNT(*) AS n FROM pipeline_log")
print("\nTotal saved runs:", cur.fetchone()["n"])

if sku_filter:
    print(f"\n--- latest saved run for {sku_filter} ---")
    cur.execute(
        "SELECT * FROM pipeline_log WHERE sku_id = ? ORDER BY rowid DESC LIMIT 1",
        (sku_filter,),
    )
else:
    print("\n--- most recent saved run ---")
    cur.execute("SELECT * FROM pipeline_log ORDER BY rowid DESC LIMIT 1")

row = cur.fetchone()
if row:
    for c in cols:
        value = str(row[c])
        if len(value) > 400:
            value = value[:400] + " ...[truncated]"
        print(f"\n[{c}]\n{value}")
else:
    print("No matching run found.")

conn.close()