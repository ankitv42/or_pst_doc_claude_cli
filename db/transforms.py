"""
ORCA — Staging + Curated Transforms
====================================
3-layer architecture:
    RAW     → raw tables already in orca.db (loaded by init_db.py)
    STAGING → staged_* tables  (cleaned, type-cast, standardised)
    CURATED → curated_* tables (all 12 derived business columns)
 
Flow:
    raw tables
        ↓  stage_*() functions
    staged_* tables  (written to orca.db)
        ↓  build_curated_*() functions
    curated_* tables (written to orca.db)
 
Dependency order for curated build:
    1.  avg_daily_demand        (curated_sales)     — no deps
    2.  demand_trend_7d         (curated_sales)     — no deps
    3.  event_baseline_uplift   (curated_sales)     — no deps
    4.  effective_lead_time     (curated_skus)      — no deps
    5.  event_uplift_factor     (curated_skus)      — no deps
    6.  margin_priority_rank    (curated_skus)      — no deps
    7.  coverage_gap_units      (curated_inventory) — no deps
    8.  stock_status            (curated_inventory) — no deps
    9.  days_to_stockout        (curated_inventory) — needs avg_daily_demand
    10. risk_score              (curated_inventory) — no deps
    11. store_priority_score    (curated_stores)    — no deps
    12. pool_pressure_flag      (curated_capital)   — no deps
 
Usage:
    python db/transforms.py
"""

import sys
import datetime
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

import pandas as pd
from sqlalchemy import create_engine, text

DB_PATH = Path(__file__).parent / "orca.db"
engine = create_engine(f"sqlite:///{DB_PATH}", echo=False, future=True)

# ── Helpers ───────────────────────────────────────────────────────────────────

def read_table(table: str) -> pd.DataFrame:
    """Read any table from orca.db into a DataFrame."""
    with engine.connect() as conn:
        return pd.read_sql(text(f"SELECT * FROM {table}"), conn)

def write_table(df: pd.DataFrame, table_name: str) -> None:
    """Write a DataFrame to orca.db, replacing existing table."""
    with engine.begin() as conn:
        df.to_sql(table_name, con=conn, if_exists="replace", index=False)
    print(f"  ✅  {table_name:<30} written — {len(df):>6} rows | {len(df.columns)} columns")


# ── STAGING CLEAN ─────────────────────────────────────────────────────────────
# Applied before any curated transforms.
# Fixes types, nulls, standardises strings.

def stage_stores(df: pd.DataFrame) -> pd.DataFrame:
    """
    Clean raw stores table.
    - Cast is_active to boolean
    - Fill null revenue with 0
    - Strip whitespace from text columns
    """
    df = df.copy()
    df["is_active"]           = df["is_active"].astype(str).str.strip().str.upper() == "YES"
    df["annual_revenue_aed"]  = pd.to_numeric(df["annual_revenue_aed"], errors="coerce").fillna(0)
    df["monthly_footfall"]    = pd.to_numeric(df["monthly_footfall"],   errors="coerce").fillna(0)
    df["store_name"]          = df["store_name"].str.strip()
    df["region"]              = df["region"].str.strip().str.title()
    df["tier"]                = df["tier"].str.strip()
    df["store_format"]        = df["store_format"].str.strip()
    return df



def stage_skus(df: pd.DataFrame) -> pd.DataFrame:
    """
    Clean raw SKUs table.
    - Cast is_seasonal to boolean
    - Ensure lead_time_days >= 1
    - Round margin to 2 dp
    - Standardise abc_class to uppercase
    """
    df = df.copy()
    df["is_seasonal"]      = df["is_seasonal"].astype(str).str.strip().str.upper() == "YES"
    df["gross_margin_pct"] = pd.to_numeric(df["gross_margin_pct"], errors="coerce").round(2).fillna(0)
    df["lead_time_days"]   = pd.to_numeric(df["lead_time_days"],   errors="coerce").fillna(7).clip(lower=1)
    df["reorder_point"]    = pd.to_numeric(df["reorder_point"],    errors="coerce").fillna(10).clip(lower=1)
    df["min_order_qty"]    = pd.to_numeric(df["min_order_qty"],    errors="coerce").fillna(50).clip(lower=1)
    df["abc_class"]        = df["abc_class"].astype(str).str.strip().str.upper()
    df["category"]         = df["category"].str.strip().str.title()
    df["sku_name"]         = df["sku_name"].str.strip()
    return df


def stage_suppliers(df: pd.DataFrame) -> pd.DataFrame:
    """
    Clean raw suppliers table.
    - Cast allows_expedite to boolean
    - Clamp reliability_score to 1.0 – 5.0
    - Cast is_active to boolean
    """
    df = df.copy()
    df["allows_expedite"]    = df["allows_expedite"].astype(str).str.strip().str.upper() == "YES"
    df["is_active"]          = df["is_active"].astype(str).str.strip().str.upper() == "YES"
    df["reliability_score"]  = pd.to_numeric(df["reliability_score"], errors="coerce").fillna(3.0).clip(lower=1.0, upper=5.0)
    df["lead_time_days"]     = pd.to_numeric(df["lead_time_days"],    errors="coerce").fillna(14).clip(lower=1)
    df["supplier_name"]      = df["supplier_name"].str.strip()
    df["country"]            = df["country"].str.strip().str.title()
    return df


def stage_inventory(df: pd.DataFrame) -> pd.DataFrame:
    """
    Clean raw inventory table.
    - Parse date columns
    - Clip days_of_cover to >= 0
    - Ensure stock units are non-negative integers
    - Standardise stock_status to title case
    """
    df = df.copy()
    df["days_of_cover"]          = pd.to_numeric(df["days_of_cover"], errors="coerce").fillna(0).clip(lower=0)
    df["current_stock_units"]    = pd.to_numeric(df["current_stock_units"],  errors="coerce").fillna(0).clip(lower=0).astype(int)
    df["warehouse_stock_units"]  = pd.to_numeric(df["warehouse_stock_units"],errors="coerce").fillna(0).clip(lower=0).astype(int)
    if "reorder_point" in df.columns:
        df["reorder_point"] = pd.to_numeric(df["reorder_point"], errors="coerce").fillna(10).clip(lower=1).astype(int)
    df["reorder_triggered"]      = df["reorder_triggered"].astype(str).str.strip().str.upper() == "YES"
 
    for col in ["last_replenishment_date", "next_delivery_date", "last_updated"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")
 
    if "stock_status" in df.columns:
        df["stock_status"] = df["stock_status"].str.strip().str.title()
 
    return df


def stage_sales(df: pd.DataFrame) -> pd.DataFrame:
    """
    Clean raw sales table.
    - Parse date column
    - Extract time dimensions: sale_month, sale_week, day_of_week
    - Standardise event_tag to UPPER_SNAKE_CASE
    - Ensure units_sold >= 0
    """
    df = df.copy()
    df["date"]        = pd.to_datetime(df["date"], errors="coerce")
    df["units_sold"]  = pd.to_numeric(df["units_sold"], errors="coerce").fillna(0).clip(lower=0)
    df["revenue_aed"] = pd.to_numeric(df["revenue_aed"], errors="coerce").fillna(0)
 
    # extract time dimensions — useful for agent queries later
    df["sale_month"]  = df["date"].dt.month
    df["sale_week"]   = df["date"].dt.isocalendar().week.astype(int)
    df["day_of_week"] = df["date"].dt.strftime("%a")
 
    # standardise event_tag
    df["event_tag"] = (
        df["event_tag"]
        .astype(str)
        .str.strip()
        .str.upper()
        .str.replace(" ", "_", regex=False)
    )
 
    if "gross_profit_aed" in df.columns:
        df["gross_profit_aed"] = pd.to_numeric(df["gross_profit_aed"], errors="coerce").fillna(0)
 
    return df


def stage_capital(df: pd.DataFrame) -> pd.DataFrame:
    """
    Clean raw capital_pools table.
    - Materialise formula columns (available_aed, utilization_pct)
      which come through as NaN from Excel formula cells
    - Ensure numeric types
    """
    df = df.copy()
    df["total_budget_aed"] = pd.to_numeric(df["total_budget_aed"], errors="coerce").fillna(0)
    df["allocated_aed"]    = pd.to_numeric(df["allocated_aed"],    errors="coerce").fillna(0)
 
    # materialise Excel formula columns
    df["available_aed"]   = df["total_budget_aed"] - df["allocated_aed"]
    df["utilization_pct"] = (
        df["allocated_aed"] / df["total_budget_aed"].replace(0, float("nan")) * 100
    ).round(1).fillna(0)
 
    if "priority_rank" in df.columns:
        df["priority_rank"] = pd.to_numeric(df["priority_rank"], errors="coerce").fillna(99).astype(int)
 
    df["pool_name"] = df["pool_name"].str.strip()
    df["pool_type"] = df["pool_type"].str.strip()
 
    return df

def stage_events(df: pd.DataFrame) -> pd.DataFrame:
    """
    Clean raw events table.
    - Parse date columns
    - Ensure numeric uplift values
    - Standardise affected_categories list
    """
    df = df.copy()
    df["start_date"]          = pd.to_datetime(df["start_date"], errors="coerce")
    df["end_date"]            = pd.to_datetime(df["end_date"],   errors="coerce")
    df["demand_uplift_pct"]   = pd.to_numeric(df["demand_uplift_pct"],  errors="coerce").fillna(0)
    df["planning_lead_days"]  = pd.to_numeric(df["planning_lead_days"], errors="coerce").fillna(14)
    df["event_name"]          = df["event_name"].str.strip()
    df["event_type"]          = df["event_type"].str.strip().str.title()
    df["affected_categories"] = df["affected_categories"].str.strip()
    return df


def run_staging() -> dict:
    """
    Load all raw tables, apply staging transforms,
    write staged_* tables to orca.db.
    Returns dict of staged DataFrames for curated layer.
    """
    print("\n── Loading raw tables ──────────────────────────────────────────")
    raw = {
        "stores":        read_table("stores"),
        "skus":          read_table("skus"),
        "suppliers":     read_table("suppliers"),
        "inventory":     read_table("inventory"),
        "sales":         read_table("sales"),
        "capital_pools": read_table("capital_pools"),
        "events":        read_table("events"),
    }
    print(f"  Loaded {len(raw)} raw tables")
 
    print("\n── Applying staging transforms + writing staged_* ──────────────")
    staged = {
        "stores":    stage_stores(raw["stores"]),
        "skus":      stage_skus(raw["skus"]),
        "suppliers": stage_suppliers(raw["suppliers"]),
        "inventory": stage_inventory(raw["inventory"]),
        "sales":     stage_sales(raw["sales"]),
        "capital":   stage_capital(raw["capital_pools"]),
        "events":    stage_events(raw["events"]),
    }
 
    # write every staged DataFrame to orca.db
    for name, df in staged.items():
        write_table(df, f"staged_{name}")
 
    return staged


# ══════════════════════════════════════════════════════════════════════════════
# LAYER 2 → LAYER 3 : CURATED
# Read staged_* tables, compute derived columns, write curated_* to orca.db
# ══════════════════════════════════════════════════════════════════════════════


def build_curated_sales(
    staged_sales: pd.DataFrame,
    staged_skus:  pd.DataFrame,
) -> pd.DataFrame:
    """
    Derived columns:
        1. avg_daily_demand      — 28-day rolling mean per store+SKU
        2. demand_trend_7d       — last 7d vs prior 7d % change
        3. event_baseline_uplift — actual uplift per SKU per event vs REGULAR
    """
    df = staged_sales.copy()
    df = df.sort_values(["store_id", "sku_id", "date"])
 
    # ── 1. avg_daily_demand ───────────────────────────────────────────────
    df["avg_daily_demand"] = (
        df.groupby(["store_id", "sku_id"])["units_sold"]
          .transform(lambda x: x.rolling(28, min_periods=1).mean().round(2))
    )
 
    # ── 2. demand_trend_7d ────────────────────────────────────────────────
    def compute_trend(x: pd.Series) -> pd.Series:
        recent = x.rolling(7,  min_periods=1).mean()
        prior  = x.shift(7).rolling(7, min_periods=1).mean()
        return ((recent - prior) / prior.replace(0, float("nan"))).round(4)
 
    df["demand_trend_7d"] = (
        df.groupby(["store_id", "sku_id"])["units_sold"]
          .transform(compute_trend)
    )
 
    # ── 3. event_baseline_uplift ──────────────────────────────────────────
    # join category from staged_skus
    skus_slim = staged_skus[["sku_id", "category"]].drop_duplicates()
    df = df.merge(skus_slim, on="sku_id", how="left")
 
    # average units_sold per sku + event_tag
    event_avg = (
        df.groupby(["sku_id", "event_tag"])["units_sold"]
          .mean()
          .reset_index()
          .rename(columns={"units_sold": "avg_event_demand"})
    )
 
    # baseline = REGULAR average
    regular_avg = (
        event_avg[event_avg["event_tag"] == "REGULAR"]
        [["sku_id", "avg_event_demand"]]
        .rename(columns={"avg_event_demand": "avg_regular_demand"})
    )
 
    event_avg = event_avg.merge(regular_avg, on="sku_id", how="left")
    event_avg["event_baseline_uplift"] = (
        event_avg["avg_event_demand"] / event_avg["avg_regular_demand"]
        .replace(0, float("nan"))
    ).round(4)
 
    # drop REGULAR rows — uplift of 1.0 vs itself is not useful
    event_avg = event_avg[event_avg["event_tag"] != "REGULAR"]
 
    df = df.merge(
        event_avg[["sku_id", "event_tag", "event_baseline_uplift"]],
        on=["sku_id", "event_tag"],
        how="left"
    )
    df["event_baseline_uplift"] = df["event_baseline_uplift"].fillna(1.0)
 
    # keep latest row per store+SKU as snapshot
    df = (
        df.sort_values("date", ascending=False)
          .drop_duplicates(subset=["store_id", "sku_id"])
          .reset_index(drop=True)
    )
 
    return df


def build_curated_skus(
    staged_skus:      pd.DataFrame,
    staged_suppliers: pd.DataFrame,
    staged_events:    pd.DataFrame,
) -> pd.DataFrame:
    """
    Derived columns:
        4. effective_lead_time   — lead_time adjusted for reliability score
        5. event_uplift_factor   — upcoming event demand multiplier
        6. margin_priority_rank  — rank within category by gross_margin_pct
    """
    df = staged_skus.copy()
 
    # ── 4. effective_lead_time ────────────────────────────────────────────
    # formula: lead_time * (1 + (5 - reliability) * 0.1)
    # reliability 5 = no adjustment, reliability 1 = +40% buffer
    sup_slim = staged_suppliers[["supplier_id", "reliability_score"]].drop_duplicates()
    df = df.merge(sup_slim, on="supplier_id", how="left")
    df["reliability_score"]   = df["reliability_score"].fillna(3.0)
    df["effective_lead_time"] = (
        df["lead_time_days"] * (1 + (5 - df["reliability_score"]) * 0.1)
    ).round(1)
 
    # ── 5. event_uplift_factor ────────────────────────────────────────────
    # if today falls within planning window of an upcoming event
    # and the event affects this SKU's category → apply uplift
    today = pd.Timestamp(datetime.date.today())
 
    def get_uplift_for_category(category: str) -> float:
        for _, evt in staged_events.iterrows():
            planning_start = evt["start_date"] - pd.Timedelta(
                days=int(evt["planning_lead_days"])
            )
            if today < planning_start or today > evt["end_date"]:
                continue
            affected = [c.strip() for c in str(evt["affected_categories"]).split(",")]
            if category in affected or "All UAE" in affected:
                return round(evt["demand_uplift_pct"] / 100 + 1.0, 4)
        return 1.0  # no active event
 
    df["event_uplift_factor"] = df["category"].apply(get_uplift_for_category)
 
    # ── 6. margin_priority_rank ───────────────────────────────────────────
    df["margin_priority_rank"] = (
        df.groupby("category")["gross_margin_pct"]
          .rank(method="min", ascending=False)
          .astype(int)
    )
 
    return df


def build_curated_inventory(
    staged_inventory: pd.DataFrame,
    staged_skus:      pd.DataFrame,
    curated_sales:    pd.DataFrame,       # ← comes from curated layer, not staged
) -> pd.DataFrame:
    """
    Derived columns:
        7.  coverage_gap_units  — units needed to reach reorder_point
        8.  stock_status        — dynamic threshold (lead_time based, not fixed 7d)
        9.  days_to_stockout    — needs avg_daily_demand from curated_sales
        10. risk_score          — composite urgency 0.0 to 1.0
    """
    df = staged_inventory.copy()
 
    # bring in lead_time_days from staged_skus for dynamic threshold
    sku_slim = staged_skus[["sku_id", "lead_time_days", "reorder_point"]].drop_duplicates()
    df = df.merge(sku_slim, on="sku_id", how="left", suffixes=("", "_sku"))
 
    # use SKU reorder_point if inventory one is missing
    if "reorder_point" not in df.columns:
        df["reorder_point"] = df["reorder_point_sku"]
    else:
        df["reorder_point"] = df["reorder_point"].fillna(df.get("reorder_point_sku", 10))
    df = df.drop(columns=["reorder_point_sku"], errors="ignore")
 
    df["lead_time_days"] = df["lead_time_days"].fillna(7)
 
    # ── 7. coverage_gap_units ─────────────────────────────────────────────
    df["coverage_gap_units"] = (
        df["reorder_point"] - df["current_stock_units"]
    ).clip(lower=0).astype(int)
 
    # ── 8. stock_status — dynamic threshold ───────────────────────────────
    # at_risk_threshold = lead_time_days / 10 + 5
    # e.g. lead 7d → threshold 5.7d | lead 45d → threshold 9.5d
    risk_threshold = df["lead_time_days"] / 10 + 5
 
    df["stock_status"] = "Healthy"
    df.loc[df["current_stock_units"] == 0,          "stock_status"] = "Critical"
    df.loc[df["days_of_cover"] < 3,                 "stock_status"] = "Critical"
    df.loc[
        (df["days_of_cover"] >= 3) &
        (df["days_of_cover"] < risk_threshold),      "stock_status"] = "At Risk"
    df.loc[
        df["current_stock_units"] > df["reorder_point"] * 3,
                                                     "stock_status"] = "Overstock"
 
    # ── 9. days_to_stockout — from curated_sales avg_daily_demand ─────────
    demand_slim = (
        curated_sales[["store_id", "sku_id", "avg_daily_demand"]]
        .drop_duplicates(subset=["store_id", "sku_id"])
    )
    df = df.merge(demand_slim, on=["store_id", "sku_id"], how="left")
 
    df["days_to_stockout"] = (
        df["current_stock_units"] /
        df["avg_daily_demand"].replace(0, float("nan"))
    ).round(1).fillna(999)   # 999 = no sales data, treat as no risk
 
    # ── 10. risk_score ────────────────────────────────────────────────────
    # weighted composite:
    #   60% — how far below reorder_point is current stock
    #   40% — how depleted is warehouse backup stock
    stock_pressure = (
        1 - df["current_stock_units"] / df["reorder_point"].replace(0, float("nan"))
    ).clip(lower=0, upper=1).fillna(1.0)
 
    warehouse_pressure = (
        1 - df["warehouse_stock_units"] / (df["reorder_point"] * 3).replace(0, float("nan"))
    ).clip(lower=0, upper=1).fillna(1.0)
 
    df["risk_score"] = (
        0.6 * stock_pressure + 0.4 * warehouse_pressure
    ).round(4)
 
    return df


def build_curated_stores(staged_stores: pd.DataFrame) -> pd.DataFrame:
    """
    Derived columns:
        11. store_priority_score — weighted: tier (50%) + revenue (30%) + footfall (20%)
    """
    df = staged_stores.copy()
 
    # tier score — Tier-1 highest
    tier_map = {"Tier-1": 1.0, "Tier-2": 0.5, "Tier-3": 0.2}
    df["tier_score"] = df["tier"].map(tier_map).fillna(0.2)
 
    # min-max normalise revenue
    rev_min = df["annual_revenue_aed"].min()
    rev_max = df["annual_revenue_aed"].max()
    df["revenue_norm"] = (
        (df["annual_revenue_aed"] - rev_min) / (rev_max - rev_min)
        if rev_max > rev_min else 0.5
    )
 
    # min-max normalise footfall
    foot_min = df["monthly_footfall"].min()
    foot_max = df["monthly_footfall"].max()
    df["footfall_norm"] = (
        (df["monthly_footfall"] - foot_min) / (foot_max - foot_min)
        if foot_max > foot_min else 0.5
    )
 
    df["store_priority_score"] = (
        0.5 * df["tier_score"] +
        0.3 * df["revenue_norm"] +
        0.2 * df["footfall_norm"]
    ).round(4)
 
    # drop helper columns — not needed downstream
    df = df.drop(columns=["tier_score", "revenue_norm", "footfall_norm"])
 
    return df


def build_curated_capital(staged_capital: pd.DataFrame) -> pd.DataFrame:
    """
    Derived columns:
        12. pool_pressure_flag — HIGH / MEDIUM / LOW based on utilization_pct
    """
    df = staged_capital.copy()
 
    df["pool_pressure_flag"] = "LOW"
    df.loc[df["utilization_pct"] > 60, "pool_pressure_flag"] = "MEDIUM"
    df.loc[df["utilization_pct"] > 85, "pool_pressure_flag"] = "HIGH"
 
    return df


def run_curated(staged: dict) -> None:
    """
    Build all curated tables from staged DataFrames.
    Dependency order is enforced — curated_sales built first.
    """
    print("\n── Building curated tables (dependency order) ──────────────────")
 
    # 1-3: curated_sales FIRST — curated_inventory needs avg_daily_demand
    curated_sales = build_curated_sales(
        staged_sales=staged["sales"],
        staged_skus=staged["skus"],
    )
    write_table(curated_sales, "curated_sales")
 
    # 4-6: curated_skus
    curated_skus = build_curated_skus(
        staged_skus=staged["skus"],
        staged_suppliers=staged["suppliers"],
        staged_events=staged["events"],
    )
    write_table(curated_skus, "curated_skus")
 
    # 7-10: curated_inventory — reads curated_sales for days_to_stockout
    curated_inventory = build_curated_inventory(
        staged_inventory=staged["inventory"],
        staged_skus=staged["skus"],
        curated_sales=curated_sales,        # ← curated, not staged
    )
    write_table(curated_inventory, "curated_inventory")
 
    # 11: curated_stores
    curated_stores = build_curated_stores(staged_stores=staged["stores"])
    write_table(curated_stores, "curated_stores")
 
    # 12: curated_capital
    curated_capital = build_curated_capital(staged_capital=staged["capital"])
    write_table(curated_capital, "curated_capital")


# ══════════════════════════════════════════════════════════════════════════════
# VERIFICATION
# ══════════════════════════════════════════════════════════════════════════════
 
def verify_all() -> None:
    print("\n🔍  Verification\n")
 
    with engine.connect() as conn:
 
        # ── all tables present ─────────────────────────────────────────────
        all_tables = conn.execute(text(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )).fetchall()
        print("── All tables in orca.db ───────────────────────────────────────")
        for (t,) in all_tables:
            count = conn.execute(text(f"SELECT COUNT(*) FROM {t}")).scalar()
            layer = "RAW    " if not t.startswith(("staged","curated")) else \
                    "STAGED " if t.startswith("staged") else "CURATED"
            print(f"  [{layer}]  {t:<35} {count:>7} rows")
 
        # ── curated_inventory stock_status ────────────────────────────────
        print("\n── curated_inventory: stock_status (dynamic threshold) ─────────")
        rows = conn.execute(text("""
            SELECT stock_status, COUNT(*) as cnt
            FROM   curated_inventory
            GROUP BY stock_status
            ORDER BY cnt DESC
        """)).fetchall()
        for row in rows:
            print(f"  {row[0]:<12} : {row[1]:>5} records")
 
        # ── top 5 highest risk ────────────────────────────────────────────
        print("\n── curated_inventory: top 5 by risk_score ──────────────────────")
        rows = conn.execute(text("""
            SELECT  store_id, sku_id,
                    current_stock_units, days_of_cover,
                    days_to_stockout, risk_score, stock_status
            FROM    curated_inventory
            ORDER BY risk_score DESC
            LIMIT 5
        """)).fetchall()
        print(f"  {'store':<10} {'sku':<12} {'stock':>6} {'doc':>6} {'stockout':>9} {'risk':>6}  status")
        print(f"  {'-'*65}")
        for r in rows:
            print(f"  {r[0]:<10} {r[1]:<12} {r[2]:>6} {r[3]:>6} {r[4]:>9} {r[5]:>6}  {r[6]}")
 
        # ── effective_lead_time ───────────────────────────────────────────
        print("\n── curated_skus: effective_lead_time sample ────────────────────")
        rows = conn.execute(text("""
            SELECT  sku_id, category, lead_time_days,
                    effective_lead_time, event_uplift_factor, margin_priority_rank
            FROM    curated_skus
            ORDER BY effective_lead_time DESC
            LIMIT 5
        """)).fetchall()
        for r in rows:
            print(f"  {r[0]} | {r[1]:<12} | raw={r[2]}d → effective={r[3]}d "
                  f"| uplift={r[4]} | rank={r[5]}")
 
        # ── store priority ────────────────────────────────────────────────
        print("\n── curated_stores: top 5 by store_priority_score ───────────────")
        rows = conn.execute(text("""
            SELECT  store_id, store_name, tier,
                    annual_revenue_aed, store_priority_score
            FROM    curated_stores
            ORDER BY store_priority_score DESC
            LIMIT 5
        """)).fetchall()
        for r in rows:
            print(f"  {r[0]} | {str(r[1]):<35} | {r[2]} | AED {r[3]:>12,.0f} | score={r[4]}")
 
        # ── capital pool pressure ─────────────────────────────────────────
        print("\n── curated_capital: pool pressure flags ────────────────────────")
        rows = conn.execute(text("""
            SELECT  pool_name, total_budget_aed,
                    available_aed, utilization_pct, pool_pressure_flag
            FROM    curated_capital
            ORDER BY utilization_pct DESC
        """)).fetchall()
        print(f"  {'pool_name':<35} {'total':>12} {'avail':>12} {'util%':>6}  flag")
        print(f"  {'-'*75}")
        for r in rows:
            print(f"  {str(r[0]):<35} {r[1]:>12,.0f} {r[2]:>12,.0f} {r[3]:>6.1f}%  {r[4]}")
 
    print("\n✅  Verification complete.\n")
 
 
# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════
 
if __name__ == "__main__":
    print("\n🚀  ORCA Transforms — 3-layer pipeline starting...")
    print("     RAW → STAGED → CURATED\n")
 
    # Layer 1 → 2
    staged = run_staging()
 
    # Layer 2 → 3
    run_curated(staged)
 
    # Verify everything
    verify_all()










