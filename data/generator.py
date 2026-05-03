"""
ORCA — Data Generator (v2)
Loads directly from the actual RCC Excel source files.
No fake data — this is the real retail dataset.

Usage:
    python data/generator.py

Outputs:
    Prints summary stats for all 7 tables.
    DataFrames are returned for use by db/init_db.py (Day 3).
"""

import pandas as pd
from pathlib import Path

# ── Paths ─────────────────────────────────────────────────────────────────────
# Put your Excel files in a data/source/ folder inside the project
SOURCE_DIR = Path(__file__).parent / "source"


# ── Loaders ───────────────────────────────────────────────────────────────────

def load_stores() -> pd.DataFrame:
    df = pd.read_excel(SOURCE_DIR / "01_Stores.xlsx")

    # Normalise column names — strip spaces, lowercase
    df.columns = df.columns.str.strip().str.lower()

    # Ensure is_active exists and filter only active stores
    if "is_active" in df.columns:
        df = df[df["is_active"] == "Yes"].reset_index(drop=True)

    print(f"✅  Stores loaded        : {len(df)} rows  |  cols: {list(df.columns)}")
    return df


def load_skus() -> pd.DataFrame:
    df = pd.read_excel(SOURCE_DIR / "02_SKUs.xlsx")
    df.columns = df.columns.str.strip().str.lower()

    print(f"✅  SKUs loaded          : {len(df)} rows  |  cols: {list(df.columns)}")
    return df


def load_suppliers() -> pd.DataFrame:
    df = pd.read_excel(SOURCE_DIR / "03_Suppliers.xlsx")
    df.columns = df.columns.str.strip().str.lower()

    if "is_active" in df.columns:
        df = df[df["is_active"] == "Yes"].reset_index(drop=True)

    print(f"✅  Suppliers loaded     : {len(df)} rows  |  cols: {list(df.columns)}")
    return df


def load_inventory() -> pd.DataFrame:
    df = pd.read_excel(SOURCE_DIR / "04_Inventory.xlsx")
    df.columns = df.columns.str.strip().str.lower()

    # Convert date columns
    for col in ["last_replenishment_date", "next_delivery_date", "last_updated"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")

    print(f"✅  Inventory loaded     : {len(df)} rows  |  cols: {list(df.columns)}")
    return df


def load_sales() -> pd.DataFrame:
    df = pd.read_excel(SOURCE_DIR / "05_Sales_History.xlsx")
    df.columns = df.columns.str.strip().str.lower()

    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")

    print(f"✅  Sales History loaded : {len(df)} rows  |  cols: {list(df.columns)}")
    return df


def load_capital_pools() -> pd.DataFrame:
    df = pd.read_excel(SOURCE_DIR / "06_Capital_Pools.xlsx")
    df.columns = df.columns.str.strip().str.lower()

    # Compute available_aed if missing (formula column in Excel)
    if "available_aed" not in df.columns or df["available_aed"].isna().all():
        df["available_aed"] = df["total_budget_aed"] - df["allocated_aed"]

    if "utilization_pct" not in df.columns or df["utilization_pct"].isna().all():
        df["utilization_pct"] = (
            df["allocated_aed"] / df["total_budget_aed"] * 100
        ).round(1)

    print(f"✅  Capital Pools loaded : {len(df)} rows  |  cols: {list(df.columns)}")
    return df


def load_events() -> pd.DataFrame:
    df = pd.read_excel(SOURCE_DIR / "07_Event_Calendar.xlsx")
    df.columns = df.columns.str.strip().str.lower()

    for col in ["start_date", "end_date"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")

    print(f"✅  Event Calendar loaded: {len(df)} rows  |  cols: {list(df.columns)}")
    return df


# ── Summary helpers ───────────────────────────────────────────────────────────

def print_inventory_summary(inventory_df: pd.DataFrame) -> None:
    print("\n── Inventory: stock_status distribution ───────────────────────")
    if "stock_status" in inventory_df.columns:
        print(inventory_df["stock_status"].value_counts().to_string())
    else:
        print("  stock_status column not found")

    print("\n── Inventory: At Risk / Critical items (first 5) ──────────────")
    risk_cols = ["record_id", "store_id", "sku_id",
                 "current_stock_units", "days_of_cover", "stock_status"]
    risk_cols = [c for c in risk_cols if c in inventory_df.columns]
    at_risk = inventory_df[
        inventory_df["stock_status"].isin(["Critical", "At Risk"])
    ]
    print(at_risk[risk_cols].head(5).to_string(index=False))
    print(f"\n  Total At Risk + Critical: {len(at_risk)} records")


def print_sales_summary(sales_df: pd.DataFrame) -> None:
    print("\n── Sales History summary ───────────────────────────────────────")
    print(f"  Total transactions : {len(sales_df):,}")

    if "revenue_aed" in sales_df.columns:
        print(f"  Total revenue      : AED {sales_df['revenue_aed'].sum():>15,.2f}")
    if "gross_profit_aed" in sales_df.columns:
        print(f"  Total gross profit : AED {sales_df['gross_profit_aed'].sum():>15,.2f}")
    if "date" in sales_df.columns:
        print(f"  Date range         : {sales_df['date'].min().date()}  →  {sales_df['date'].max().date()}")
    if "event_tag" in sales_df.columns:
        print(f"\n── Sales: event_tag distribution ───────────────────────────────")
        print(sales_df["event_tag"].value_counts().to_string())


def print_capital_summary(capital_df: pd.DataFrame) -> None:
    print("\n── Capital Pools summary ───────────────────────────────────────")
    cols = ["pool_id", "pool_name", "total_budget_aed", "available_aed", "utilization_pct"]
    cols = [c for c in cols if c in capital_df.columns]
    print(capital_df[cols].to_string(index=False))


def print_event_summary(events_df: pd.DataFrame) -> None:
    print("\n── Event Calendar ──────────────────────────────────────────────")
    cols = ["event_name", "demand_uplift_pct", "affected_categories", "planning_lead_days"]
    cols = [c for c in cols if c in events_df.columns]
    print(events_df[cols].to_string(index=False))


# ── Main ──────────────────────────────────────────────────────────────────────

def load_all() -> dict:
    """
    Load all 7 datasets and return as a dict of DataFrames.
    Called by db/init_db.py to load into SQLite.
    """
    return {
        "stores":        load_stores(),
        "skus":          load_skus(),
        "suppliers":     load_suppliers(),
        "inventory":     load_inventory(),
        "sales":         load_sales(),
        "capital_pools": load_capital_pools(),
        "events":        load_events(),
    }


if __name__ == "__main__":
    print("\n🚀  ORCA Data Loader — reading from real RCC Excel files\n")

    data = load_all()

    # ── Per-table previews ─────────────────────────────────────────
    print("\n── Stores sample ───────────────────────────────────────────────")
    store_cols = ["store_id", "store_name", "region", "tier", "store_format"]
    store_cols = [c for c in store_cols if c in data["stores"].columns]
    print(data["stores"][store_cols].head(5).to_string(index=False))

    print("\n── SKUs sample ─────────────────────────────────────────────────")
    sku_cols = ["sku_id", "sku_name", "category", "gross_margin_pct", "abc_class"]
    sku_cols = [c for c in sku_cols if c in data["skus"].columns]
    print(data["skus"][sku_cols].head(5).to_string(index=False))

    print("\n── Suppliers ───────────────────────────────────────────────────")
    sup_cols = ["supplier_id", "supplier_name", "country",
                "lead_time_days", "reliability_score", "allows_expedite"]
    sup_cols = [c for c in sup_cols if c in data["suppliers"].columns]
    print(data["suppliers"][sup_cols].to_string(index=False))

    print_inventory_summary(data["inventory"])
    print_sales_summary(data["sales"])
    print_capital_summary(data["capital_pools"])
    print_event_summary(data["events"])

    print("\n✅  All 7 datasets loaded successfully.\n")