"""
ORCA — db/transforms.py
========================
3-layer data pipeline: RAW -> STAGED -> CURATED

Staging layer  : type casting, null guards, standardisation
Curated layer  : all 13 derived business columns

FIXES vs previous version:
    FIX 1 — stock_status threshold formula corrected to match RCC bootcamp doc:
        Critical  = days_of_cover < 50% of effective_lead_time
        At Risk   = days_of_cover < 100% of effective_lead_time
        Healthy   = days_of_cover >= 100% of effective_lead_time
        Overstock = current_stock > reorder_point x 3

    FIX 2 — projected_demand and projected_shortfall added to curated_inventory:
        projected_demand    = avg_daily_demand x event_uplift_factor x event_duration_days
        projected_shortfall = projected_demand - current_stock_units (floor 0)

    FIX 4 — risk_score scaled to 0-10 to match RCC bootcamp doc:
        Previous: 0.0 to 1.0 (wrong scale)
        Corrected: 0.0 to 10.0
        Formula: (0.6 x stock_pressure + 0.4 x warehouse_pressure) x 10
        Rounded to 2 decimal places.

Dependency order for curated build:
    1.  avg_daily_demand         (curated_sales)      no deps
    2.  demand_trend_7d          (curated_sales)      no deps
    3.  event_baseline_uplift    (curated_sales)      no deps
    4.  effective_lead_time      (curated_skus)       no deps
    5.  event_uplift_factor      (curated_skus)       no deps
    6.  margin_priority_rank     (curated_skus)       no deps
    7.  coverage_gap_units       (curated_inventory)  no deps
    8.  stock_status             (curated_inventory)  needs effective_lead_time
    9.  days_to_stockout         (curated_inventory)  needs avg_daily_demand
    10. risk_score               (curated_inventory)  no deps — scaled 0-10
    11. projected_demand         (curated_inventory)  needs avg_daily_demand + event_uplift_factor
    12. projected_shortfall      (curated_inventory)  needs projected_demand
    13. store_priority_score     (curated_stores)     no deps
    14. pool_pressure_flag       (curated_capital)    no deps

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
engine  = create_engine(f"sqlite:///{DB_PATH}", echo=False)


# ==============================================================================
# GENERIC HELPERS
# ==============================================================================

def read_table(table: str) -> pd.DataFrame:
    with engine.connect() as conn:
        return pd.read_sql(f"SELECT * FROM {table}", conn)


def write_table(df: pd.DataFrame, table_name: str) -> None:
    with engine.begin() as conn:
        df.to_sql(table_name, con=conn, if_exists="replace", index=False)
    print(f"  OK  {table_name:<35} {len(df):>6} rows | {len(df.columns)} columns")


# ==============================================================================
# LAYER 1 -> LAYER 2 : STAGING
# ==============================================================================

def stage_stores(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["is_active"]          = df["is_active"].astype(str).str.strip().str.upper() == "YES"
    df["annual_revenue_aed"] = pd.to_numeric(df["annual_revenue_aed"], errors="coerce").fillna(0)
    df["monthly_footfall"]   = pd.to_numeric(df["monthly_footfall"],   errors="coerce").fillna(0)
    df["store_name"]         = df["store_name"].str.strip()
    df["region"]             = df["region"].str.strip().str.title()
    df["tier"]               = df["tier"].str.strip()
    df["store_format"]       = df["store_format"].str.strip()
    return df


def stage_skus(df: pd.DataFrame) -> pd.DataFrame:
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
    df = df.copy()
    df["allows_expedite"]   = df["allows_expedite"].astype(str).str.strip().str.upper() == "YES"
    df["is_active"]         = df["is_active"].astype(str).str.strip().str.upper() == "YES"
    df["reliability_score"] = pd.to_numeric(df["reliability_score"], errors="coerce").fillna(3.0).clip(lower=1.0, upper=5.0)
    df["lead_time_days"]    = pd.to_numeric(df["lead_time_days"],    errors="coerce").fillna(14).clip(lower=1)
    df["supplier_name"]     = df["supplier_name"].str.strip()
    df["country"]           = df["country"].str.strip().str.title()
    return df


def stage_inventory(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["days_of_cover"]         = pd.to_numeric(df["days_of_cover"], errors="coerce").fillna(0).clip(lower=0)
    df["current_stock_units"]   = pd.to_numeric(df["current_stock_units"],  errors="coerce").fillna(0).clip(lower=0).astype(int)
    df["warehouse_stock_units"] = pd.to_numeric(df["warehouse_stock_units"],errors="coerce").fillna(0).clip(lower=0).astype(int)
    df["reorder_triggered"]     = df["reorder_triggered"].astype(str).str.strip().str.upper() == "YES"
    if "reorder_point" in df.columns:
        df["reorder_point"] = pd.to_numeric(df["reorder_point"], errors="coerce").fillna(10).clip(lower=1).astype(int)
    for col in ["last_replenishment_date", "next_delivery_date", "last_updated"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")
    if "stock_status" in df.columns:
        df["stock_status"] = df["stock_status"].str.strip().str.title()
    return df


def stage_sales(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["date"]        = pd.to_datetime(df["date"], errors="coerce")
    df["units_sold"]  = pd.to_numeric(df["units_sold"], errors="coerce").fillna(0).clip(lower=0)
    df["revenue_aed"] = pd.to_numeric(df["revenue_aed"], errors="coerce").fillna(0)
    df["sale_month"]  = df["date"].dt.month
    df["sale_week"]   = df["date"].dt.isocalendar().week.astype(int)
    df["day_of_week"] = df["date"].dt.strftime("%a")
    df["event_tag"]   = (
        df["event_tag"].astype(str).str.strip()
        .str.upper().str.replace(" ", "_", regex=False)
    )
    if "gross_profit_aed" in df.columns:
        df["gross_profit_aed"] = pd.to_numeric(df["gross_profit_aed"], errors="coerce").fillna(0)
    return df


def stage_capital(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["total_budget_aed"] = pd.to_numeric(df["total_budget_aed"], errors="coerce").fillna(0)
    df["allocated_aed"]    = pd.to_numeric(df["allocated_aed"],    errors="coerce").fillna(0)
    # materialise Excel formula columns that arrive as null
    df["available_aed"]    = df["total_budget_aed"] - df["allocated_aed"]
    df["utilization_pct"]  = (
        df["allocated_aed"] / df["total_budget_aed"].replace(0, float("nan")) * 100
    ).round(1).fillna(0)
    if "priority_rank" in df.columns:
        df["priority_rank"] = pd.to_numeric(df["priority_rank"], errors="coerce").fillna(99).astype(int)
    df["pool_name"] = df["pool_name"].str.strip()
    df["pool_type"] = df["pool_type"].str.strip()
    return df


def stage_events(df: pd.DataFrame) -> pd.DataFrame:
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
    print("\n-- Loading raw tables ------------------------------------------")
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

    print("\n-- Applying staging transforms + writing staged_* ---------------")
    staged = {
        "stores":    stage_stores(raw["stores"]),
        "skus":      stage_skus(raw["skus"]),
        "suppliers": stage_suppliers(raw["suppliers"]),
        "inventory": stage_inventory(raw["inventory"]),
        "sales":     stage_sales(raw["sales"]),
        "capital":   stage_capital(raw["capital_pools"]),
        "events":    stage_events(raw["events"]),
    }
    for name, df in staged.items():
        write_table(df, f"staged_{name}")

    return staged


# ==============================================================================
# LAYER 2 -> LAYER 3 : CURATED
# ==============================================================================

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

    # 1. avg_daily_demand
    # zero-sales days ARE included (min_periods=1 uses all days in the window)
    # this matches RCC doc: "Zero-sales days ARE included in the denominator"
    df["avg_daily_demand"] = (
        df.groupby(["store_id", "sku_id"])["units_sold"]
          .transform(lambda x: x.rolling(28, min_periods=1).mean().round(2))
    )

    # 2. demand_trend_7d
    def compute_trend(x: pd.Series) -> pd.Series:
        recent = x.rolling(7,  min_periods=1).mean()
        prior  = x.shift(7).rolling(7, min_periods=1).mean()
        return ((recent - prior) / prior.replace(0, float("nan"))).round(4)

    df["demand_trend_7d"] = (
        df.groupby(["store_id", "sku_id"])["units_sold"]
          .transform(compute_trend)
    )

    # 3. event_baseline_uplift
    skus_slim = staged_skus[["sku_id", "category"]].drop_duplicates()
    df = df.merge(skus_slim, on="sku_id", how="left")

    event_avg = (
        df.groupby(["sku_id", "event_tag"])["units_sold"]
          .mean().reset_index()
          .rename(columns={"units_sold": "avg_event_demand"})
    )
    regular_avg = (
        event_avg[event_avg["event_tag"] == "REGULAR"]
        [["sku_id", "avg_event_demand"]]
        .rename(columns={"avg_event_demand": "avg_regular_demand"})
    )
    event_avg = event_avg.merge(regular_avg, on="sku_id", how="left")
    event_avg["event_baseline_uplift"] = (
        event_avg["avg_event_demand"] /
        event_avg["avg_regular_demand"].replace(0, float("nan"))
    ).round(4)
    event_avg = event_avg[event_avg["event_tag"] != "REGULAR"]

    df = df.merge(
        event_avg[["sku_id", "event_tag", "event_baseline_uplift"]],
        on=["sku_id", "event_tag"],
        how="left"
    )
    df["event_baseline_uplift"] = df["event_baseline_uplift"].fillna(1.0)

    # keep latest snapshot per store+SKU
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
        4. effective_lead_time  — lead_time adjusted for reliability score
        5. event_uplift_factor  — upcoming event demand multiplier
        6. margin_priority_rank — rank within category by gross_margin_pct
    """
    df = staged_skus.copy()

    # 4. effective_lead_time
    # Formula from RCC doc: lead_time x (1 + (5 - reliability_score) x 0.1)
    # reliability 5.0 -> no buffer | reliability 1.0 -> +40% buffer
    sup_slim = staged_suppliers[["supplier_id", "reliability_score"]].drop_duplicates()
    df = df.merge(sup_slim, on="supplier_id", how="left")
    df["reliability_score"]   = df["reliability_score"].fillna(3.0)
    df["effective_lead_time"] = (
        df["lead_time_days"] * (1 + (5 - df["reliability_score"]) * 0.1)
    ).round(1)

    # 5. event_uplift_factor
    # check if today falls within any event's planning window for this category
    today = pd.Timestamp(datetime.date.today())

    def get_uplift_for_category(category: str) -> float:
        for _, evt in staged_events.iterrows():
            planning_start = evt["start_date"] - pd.Timedelta(
                days=int(evt["planning_lead_days"])
            )
            if today < planning_start or today > evt["end_date"]:
                continue
            affected = [c.strip() for c in str(evt["affected_categories"]).split(",")]
            if category in affected or "All" in affected or "All UAE" in affected:
                return round(evt["demand_uplift_pct"] / 100 + 1.0, 4)
        return 1.0

    df["event_uplift_factor"] = df["category"].apply(get_uplift_for_category)

    # 6. margin_priority_rank — rank 1 = highest margin in category
    df["margin_priority_rank"] = (
        df.groupby("category")["gross_margin_pct"]
          .rank(method="min", ascending=False)
          .astype(int)
    )

    return df


def build_curated_inventory(
    staged_inventory: pd.DataFrame,
    staged_skus:      pd.DataFrame,
    curated_sales:    pd.DataFrame,
    staged_events:    pd.DataFrame,
) -> pd.DataFrame:
    """
    Derived columns:
        7.  coverage_gap_units   — units needed to reach reorder_point
        8.  stock_status         — corrected formula: 50%/100% of effective_lead_time
        9.  days_to_stockout     — needs avg_daily_demand from curated_sales
        10. risk_score           — FIX 4: 0-10 scale (was 0-1)
        11. projected_demand     — avg_daily_demand x event_uplift_factor x planning_days
        12. projected_shortfall  — projected_demand - current_stock_units (floor 0)
    """
    df = staged_inventory.copy()

    # bring in SKU fields
    sku_slim = staged_skus[[
        "sku_id", "lead_time_days", "reorder_point",
        "effective_lead_time", "event_uplift_factor",
        "category", "abc_class"
    ]].drop_duplicates()
    df = df.merge(sku_slim, on="sku_id", how="left", suffixes=("", "_sku"))

    # resolve reorder_point
    if "reorder_point" not in df.columns:
        df["reorder_point"] = df["reorder_point_sku"]
    else:
        df["reorder_point"] = df["reorder_point"].fillna(
            df.get("reorder_point_sku", 10)
        )
    df = df.drop(columns=["reorder_point_sku"], errors="ignore")
    df["lead_time_days"]      = df["lead_time_days"].fillna(7)
    df["effective_lead_time"] = df["effective_lead_time"].fillna(7)

    # 7. coverage_gap_units
    df["coverage_gap_units"] = (
        df["reorder_point"] - df["current_stock_units"]
    ).clip(lower=0).astype(int)

    # 8. stock_status — corrected formula from RCC bootcamp doc
    # Critical  = days_of_cover < 50% of effective_lead_time
    # At Risk   = days_of_cover >= 50% AND < 100% of effective_lead_time
    # Healthy   = days_of_cover >= 100% of effective_lead_time
    # Overstock = current_stock > reorder_point x 3
    critical_threshold = df["effective_lead_time"] * 0.5
    atrisk_threshold   = df["effective_lead_time"] * 1.0

    df["stock_status"] = "Healthy"
    df.loc[df["current_stock_units"] == 0,                    "stock_status"] = "Critical"
    df.loc[df["days_of_cover"] < critical_threshold,          "stock_status"] = "Critical"
    df.loc[
        (df["days_of_cover"] >= critical_threshold) &
        (df["days_of_cover"] <  atrisk_threshold),            "stock_status"] = "At Risk"
    df.loc[
        df["current_stock_units"] > df["reorder_point"] * 3,  "stock_status"] = "Overstock"

    # 9. days_to_stockout
    demand_slim = (
        curated_sales[["store_id", "sku_id", "avg_daily_demand"]]
        .drop_duplicates(subset=["store_id", "sku_id"])
    )
    df = df.merge(demand_slim, on=["store_id", "sku_id"], how="left")
    df["days_to_stockout"] = (
        df["current_stock_units"] /
        df["avg_daily_demand"].replace(0, float("nan"))
    ).round(1).fillna(999)

    # 10. risk_score — FIX 4: scaled to 0-10 to match RCC doc
    # Previously was 0.0-1.0 which is wrong per doc ("0-10 composite")
    # Formula: (0.6 x stock_pressure + 0.4 x warehouse_pressure) x 10
    stock_pressure = (
        1 - df["current_stock_units"] /
        df["reorder_point"].replace(0, float("nan"))
    ).clip(lower=0, upper=1).fillna(1.0)

    warehouse_pressure = (
        1 - df["warehouse_stock_units"] /
        (df["reorder_point"] * 3).replace(0, float("nan"))
    ).clip(lower=0, upper=1).fillna(1.0)

    df["risk_score"] = (
        (0.6 * stock_pressure + 0.4 * warehouse_pressure) * 10
    ).round(2)

    # 11. projected_demand
    # Formula from RCC doc:
    #   projected_demand = avg_daily_demand x event_uplift_factor x event_duration_days
    # If no active event, use effective_lead_time as planning horizon
    df["event_uplift_factor"] = df["event_uplift_factor"].fillna(1.0)
    today = pd.Timestamp(datetime.date.today())

    def get_event_duration(category: str) -> int:
        for _, evt in staged_events.iterrows():
            planning_start = evt["start_date"] - pd.Timedelta(
                days=int(evt["planning_lead_days"])
            )
            if today < planning_start or today > evt["end_date"]:
                continue
            affected = [c.strip() for c in str(evt["affected_categories"]).split(",")]
            if category in affected or "All" in affected or "All UAE" in affected:
                return int(evt["duration_days"])
        return 0

    category_duration = {
        cat: get_event_duration(cat)
        for cat in df["category"].dropna().unique()
    }
    df["event_duration_days"] = df["category"].map(category_duration).fillna(0)

    # if no active event, use effective_lead_time as the planning horizon
    planning_days = df["event_duration_days"].where(
        df["event_duration_days"] > 0,
        df["effective_lead_time"]
    )

    df["projected_demand"] = (
        df["avg_daily_demand"] * df["event_uplift_factor"] * planning_days
    ).round(0).fillna(0).astype(int)

    # 12. projected_shortfall
    # Formula from RCC doc: projected_demand - current_stock_units (floor at 0)
    df["projected_shortfall"] = (
        df["projected_demand"] - df["current_stock_units"]
    ).clip(lower=0).astype(int)

    # clean up helper column
    df = df.drop(columns=["event_duration_days"], errors="ignore")

    return df


def build_curated_stores(staged_stores: pd.DataFrame) -> pd.DataFrame:
    """
    Derived column:
        13. store_priority_score
            Formula from RCC doc: 0.5 x tier_rank + 0.3 x revenue_norm + 0.2 x footfall_norm
    """
    df = staged_stores.copy()

    tier_map = {"Tier-1": 1.0, "Tier-2": 0.5, "Tier-3": 0.2}
    df["tier_score"] = df["tier"].map(tier_map).fillna(0.2)

    rev_min  = df["annual_revenue_aed"].min()
    rev_max  = df["annual_revenue_aed"].max()
    foot_min = df["monthly_footfall"].min()
    foot_max = df["monthly_footfall"].max()

    df["revenue_norm"] = (
        (df["annual_revenue_aed"] - rev_min) / (rev_max - rev_min)
        if rev_max > rev_min else 0.5
    )
    df["footfall_norm"] = (
        (df["monthly_footfall"] - foot_min) / (foot_max - foot_min)
        if foot_max > foot_min else 0.5
    )

    df["store_priority_score"] = (
        0.5 * df["tier_score"] +
        0.3 * df["revenue_norm"] +
        0.2 * df["footfall_norm"]
    ).round(4)

    df = df.drop(columns=["tier_score", "revenue_norm", "footfall_norm"])
    return df


def build_curated_capital(staged_capital: pd.DataFrame) -> pd.DataFrame:
    """
    Derived column:
        14. pool_pressure_flag
            HIGH   = utilization > 85%
            MEDIUM = utilization > 60%
            LOW    = utilization <= 60%
    """
    df = staged_capital.copy()
    df["pool_pressure_flag"] = "LOW"
    df.loc[df["utilization_pct"] > 60, "pool_pressure_flag"] = "MEDIUM"
    df.loc[df["utilization_pct"] > 85, "pool_pressure_flag"] = "HIGH"
    return df


def run_curated(staged: dict) -> None:
    print("\n-- Building curated tables (dependency order) ------------------")

    # curated_sales FIRST — curated_inventory needs avg_daily_demand
    curated_sales = build_curated_sales(
        staged_sales=staged["sales"],
        staged_skus=staged["skus"],
    )
    write_table(curated_sales, "curated_sales")

    # curated_skus — effective_lead_time needed by curated_inventory
    curated_skus = build_curated_skus(
        staged_skus=staged["skus"],
        staged_suppliers=staged["suppliers"],
        staged_events=staged["events"],
    )
    write_table(curated_skus, "curated_skus")

    # curated_inventory — reads curated_sales AND curated_skus
    curated_inventory = build_curated_inventory(
        staged_inventory=staged["inventory"],
        staged_skus=curated_skus,       # use curated so effective_lead_time is present
        curated_sales=curated_sales,
        staged_events=staged["events"],
    )
    write_table(curated_inventory, "curated_inventory")

    # curated_stores
    curated_stores = build_curated_stores(staged_stores=staged["stores"])
    write_table(curated_stores, "curated_stores")

    # curated_capital
    curated_capital = build_curated_capital(staged_capital=staged["capital"])
    write_table(curated_capital, "curated_capital")


# ==============================================================================
# VERIFICATION
# ==============================================================================

def verify_all() -> None:
    print("\n-- Verification ------------------------------------------------\n")

    with engine.connect() as conn:

        # all tables with row counts
        all_tables = conn.execute(text(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )).fetchall()
        print("  All tables in orca.db:")
        for (t,) in all_tables:
            count = conn.execute(text(f"SELECT COUNT(*) FROM {t}")).scalar()
            layer = "RAW    " if not t.startswith(("staged","curated")) else \
                    "STAGED " if t.startswith("staged") else "CURATED"
            print(f"    [{layer}]  {t:<35} {count:>6} rows")

        # FIX 1: stock_status distribution
        print("\n  FIX 1 -- stock_status distribution:")
        rows = conn.execute(text("""
            SELECT stock_status, COUNT(*) cnt
            FROM   curated_inventory
            GROUP BY stock_status ORDER BY cnt DESC
        """)).fetchall()
        for r in rows:
            print(f"    {r[0]:<12} : {r[1]:>5}")

        # FIX 2: projected_demand and shortfall
        print("\n  FIX 2 -- projected_shortfall top 5:")
        rows = conn.execute(text("""
            SELECT store_id, sku_id, current_stock_units,
                   avg_daily_demand, event_uplift_factor,
                   projected_demand, projected_shortfall
            FROM   curated_inventory
            WHERE  projected_shortfall > 0
            ORDER BY projected_shortfall DESC
            LIMIT 5
        """)).fetchall()
        print(f"    {'store':<10} {'sku':<12} {'stock':>6} "
              f"{'demand':>8} {'uplift':>7} {'proj_demand':>12} {'shortfall':>10}")
        print(f"    {'-'*70}")
        for r in rows:
            print(f"    {r[0]:<10} {r[1]:<12} {r[2]:>6} "
                  f"{str(r[3]):>8} {str(r[4]):>7} {r[5]:>12} {r[6]:>10}")

        # FIX 4: risk_score scale
        print("\n  FIX 4 -- risk_score scale (should be 0-10):")
        rows = conn.execute(text("""
            SELECT MIN(risk_score), MAX(risk_score), AVG(risk_score)
            FROM   curated_inventory
        """)).fetchone()
        print(f"    min={rows[0]:.2f}  max={rows[1]:.2f}  avg={rows[2]:.2f}")

        # top 5 by risk_score
        print("\n  Top 5 positions by risk_score:")
        rows = conn.execute(text("""
            SELECT store_id, sku_id, days_of_cover,
                   effective_lead_time, risk_score, stock_status
            FROM   curated_inventory
            ORDER BY risk_score DESC LIMIT 5
        """)).fetchall()
        for r in rows:
            print(f"    {r[0]} | {r[1]} | doc={r[2]} | "
                  f"eff_lead={r[3]} | risk={r[4]} | {r[5]}")

        # capital pools
        print("\n  curated_capital pressure flags:")
        rows = conn.execute(text("""
            SELECT pool_id, pool_name, utilization_pct, pool_pressure_flag,
                   auto_approve_limit_aed
            FROM   curated_capital ORDER BY utilization_pct DESC
        """)).fetchall()
        for r in rows:
            print(f"    {r[0]} | {str(r[1]):<35} | "
                  f"util={r[2]}% | {r[3]} | "
                  f"auto_approve=AED {r[4]:,.0f}")

    print("\n  All curated tables verified.\n")


# ==============================================================================
# MAIN
# ==============================================================================

if __name__ == "__main__":
    print("\nORCA Transforms -- RAW -> STAGED -> CURATED\n")
    staged = run_staging()
    run_curated(staged)
    verify_all()