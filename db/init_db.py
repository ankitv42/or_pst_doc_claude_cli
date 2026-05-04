"""
ORCA — Database Initialiser
Reads all 7 Excel files via data/generator.py
and loads them into a local SQLite database (orca.db).

Usage:
    python db/init_db.py
"""

from itertools import count
import sys
from pathlib import Path

# so we can import data/generator.py from the db/ folder
sys.path.append(str(Path(__file__).parent.parent))

from sqlalchemy import create_engine,text
from data.generator import load_all


# ── Engine ────────────────────────────────────────────────────────────────────

DB_PATH = Path(__file__).parent / "orca.db"

engine = create_engine(f"sqlite:///{DB_PATH}", echo=False, future=True)

# ── Load ──────────────────────────────────────────────────────────────────────
def init_db():
    print("\n🚀  ORCA DB Initialiser starting...\n")

    # Step 1 — load all DataFrames from Excel
    data = load_all()

    # Step 2 — write each DataFrame into SQLite
    # if_exists="replace" drops and recreates the table every time
    # index=False means don't write the pandas row index as a column

    with engine.begin() as conn:
        for table_name, df in data.items():
            df.to_sql(table_name, conn, if_exists="replace", index=False)
            print(f"✅  Loaded '{table_name}' into database with {len(df)} rows.")
    
    print("\n🎉  ORCA DB Initialisation complete! Database file: orca.db\n")

# ── Verify ────────────────────────────────────────────────────────────────────

def verify_db():
    print("🔍  Verifying database contents...\n")

    queries = {
        "stores":        "SELECT COUNT(*) FROM stores",
        "skus":          "SELECT COUNT(*) FROM skus",
        "suppliers":     "SELECT COUNT(*) FROM suppliers",
        "inventory":     "SELECT COUNT(*) FROM inventory",
        "sales":         "SELECT COUNT(*) FROM sales",
        "capital_pools": "SELECT COUNT(*) FROM capital_pools",
        "events":        "SELECT COUNT(*) FROM events",
    }

    with  engine.connect() as conn:
        for table, query in queries.items():
            result = conn.execute(text(query)).scalar()
            print(f"✅  {table:<20} -> {result} rows")

    print("\n── Sample: At Risk inventory ───────────────────────────────────")
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT  i.store_id,
                    i.sku_id,
                    i.current_stock_units,
                    i.days_of_cover,
                    i.stock_status
            FROM    inventory i
            WHERE   i.stock_status IN ('Critical', 'At Risk')
            ORDER BY i.days_of_cover ASC
            LIMIT 5
        """))
        rows = result.fetchall()
        print(f"  {'store_id':<12} {'sku_id':<12} {'stock':<8} {'days_cover':<12} {'status'}")
        print(f"  {'-'*55}")
        for row in rows:
            print(f"  {row[0]:<12} {row[1]:<12} {row[2]:<8} {row[3]:<12} {row[4]}")

    print("\n── Sample: Top 5 SKUs by gross margin ──────────────────────────")
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT  sku_id,
                    sku_name,
                    category,
                    gross_margin_pct,
                    abc_class
            FROM    skus
            ORDER BY gross_margin_pct DESC
            LIMIT 5
        """))
        rows = result.fetchall()
        print(f"  {'sku_id':<12} {'sku_name':<25} {'category':<12} {'margin%':<10} {'abc'}")
        print(f"  {'-'*65}")
        for row in rows:
            print(f"  {row[0]:<12} {row[1]:<25} {row[2]:<12} {row[3]:<10} {row[4]}")

    print("\n── Sample: Capital pools available budget ───────────────────────")
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT  pool_name,
                    total_budget_aed,
                    available_aed,
                    utilization_pct
            FROM    capital_pools
            ORDER BY priority_rank ASC
        """))
        rows = result.fetchall()
        print(f"  {'pool_name':<35} {'total':>12} {'available':>12} {'util%':>6}")
        print(f"  {'-'*68}")
        for row in rows:
            print(f"  {row[0]:<35} {row[1]:>12,.0f} {row[2]:>12,.0f} {row[3]:>6.1f}%")

    print("\n✅  Database verified successfully.\n")


# ── Main ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    init_db()
    verify_db()

