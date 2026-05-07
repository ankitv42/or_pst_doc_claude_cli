"""
ORCA — data/scheduler.py
=========================
Simulates real-time inventory depletion and triggers the agent pipeline.

What it does:
    Every 60 seconds  -> deducts random sales from inventory (simulates a day passing)
    Every 5 minutes   -> runs stockout risk detection, updates stock_status
    On status change  -> writes alert to alerts table

CLI:
    python data/scheduler.py              # default 60s interval
    python data/scheduler.py --interval 10  # faster for testing
    python data/scheduler.py --once       # run one cycle and exit (for testing)

Logging:
    Logs to both console and logs/scheduler.log
"""

import sys
import random
import logging
import argparse
from datetime import datetime
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, text
from apscheduler.schedulers.blocking import BlockingScheduler

DB_PATH = Path(__file__).parent.parent / "db" / "orca.db"
LOG_DIR = Path(__file__).parent.parent / "logs"

LOG_DIR.mkdir(exist_ok=True)

engine = create_engine(f"sqlite:///{DB_PATH}", echo=False)


# ==============================================================================
# LOGGING SETUP
# ==============================================================================

def setup_logging() -> logging.Logger:
    logger = logging.getLogger("orca.scheduler")
    logger.setLevel(logging.INFO)

    # console handler
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(logging.Formatter(
        "%(asctime)s  %(levelname)-8s  %(message)s",
        datefmt="%H:%M:%S"
    ))

    # file handler
    fh = logging.FileHandler(LOG_DIR / "scheduler.log")
    fh.setLevel(logging.INFO)
    fh.setFormatter(logging.Formatter(
        "%(asctime)s  %(levelname)-8s  %(message)s"
    ))

    logger.addHandler(ch)
    logger.addHandler(fh)
    return logger


logger = setup_logging()


# ==============================================================================
# ALERTS TABLE SETUP
# ==============================================================================

def create_alerts_table() -> None:
    """
    Creates the alerts table if it does not exist.
    This is the trigger table the LangGraph agent will watch in Sprint 2.

    Each row = one at-risk event for one store + SKU combination.
    resolved = 0 means nobody has picked it up yet.
    resolved = 1 means the agent has started working on it.
    """
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS alerts (
                alert_id        INTEGER PRIMARY KEY AUTOINCREMENT,
                sku_id          TEXT    NOT NULL,
                store_id        TEXT    NOT NULL,
                stock_status    TEXT    NOT NULL,
                days_of_cover   REAL,
                risk_score      REAL,
                previous_status TEXT,
                triggered_at    TEXT    NOT NULL,
                pipeline_id     TEXT,
                resolved        INTEGER DEFAULT 0
            )
        """))
    logger.info("alerts table ready")


# ==============================================================================
# JOB 1 — SIMULATE SALES (runs every N seconds)
# ==============================================================================

def simulate_sales() -> None:
    """
    Picks 50 random inventory positions and deducts a small random
    number of units from each — simulating real sales activity.
    """
    try:
        with engine.begin() as conn:

            positions = conn.execute(text("""
                SELECT record_id, store_id, sku_id, current_stock_units
                FROM   curated_inventory
                WHERE  current_stock_units > 0
                ORDER BY RANDOM()
                LIMIT 50
            """)).fetchall()

            updated = 0
            for row in positions:
                record_id     = row[0]
                current_stock = row[3]

                # sell between 0 and 8% of current stock
                units_sold = random.randint(0, max(1, int(current_stock * 0.08)))
                new_stock  = max(0, current_stock - units_sold)

                if units_sold > 0:
                    conn.execute(text("""
                        UPDATE curated_inventory
                        SET    current_stock_units = :new_stock
                        WHERE  record_id = :record_id
                    """), {"new_stock": new_stock, "record_id": record_id})
                    updated += 1

        logger.info(f"Sales simulation -- {updated} positions updated")

    except Exception as e:
        logger.error(f"simulate_sales error: {e}")


# ==============================================================================
# JOB 2 — RISK DETECTION (runs every 5 minutes)
# ==============================================================================

def run_risk_detection() -> None:
    """
    Step 1: Recalculate days_of_cover using latest stock levels.
    Step 2: Recalculate risk_score.
    Step 3: Recalculate stock_status using dynamic threshold.
    Step 4: Find new Critical/At Risk positions and write alerts.

    KEY FIX: All steps including alert inserts run inside the SAME
    database connection. This prevents the SQLite 'database is locked'
    error that occurs when two connections try to write simultaneously.
    """
    try:
        with engine.begin() as conn:

            # Step 1: recalculate days_of_cover
            conn.execute(text("""
                UPDATE curated_inventory
                SET    days_of_cover = CASE
                           WHEN avg_daily_demand > 0
                           THEN ROUND(current_stock_units / avg_daily_demand, 1)
                           ELSE 999
                       END
                WHERE  avg_daily_demand IS NOT NULL
            """))

            # Step 2: recalculate risk_score
            # 60% weight on store stock vs reorder point
            # 40% weight on warehouse backup stock
            conn.execute(text("""
                UPDATE curated_inventory
                SET    risk_score = ROUND(
                    0.6 * MAX(0.0, MIN(1.0,
                        1.0 - CAST(current_stock_units AS REAL) / NULLIF(reorder_point, 0)
                    )) +
                    0.4 * MAX(0.0, MIN(1.0,
                        1.0 - CAST(warehouse_stock_units AS REAL) / NULLIF(reorder_point * 3, 0)
                    )), 4)
            """))

            # Step 3: recalculate stock_status with dynamic At Risk threshold
            # threshold = effective_lead_time / 10 + 5
            # e.g. lead 14 days -> threshold 6.4 days
            # e.g. lead 45 days -> threshold 9.5 days
            conn.execute(text("""
                UPDATE curated_inventory
                SET    stock_status = CASE
                    WHEN current_stock_units = 0
                        THEN 'Critical'
                    WHEN days_of_cover < 3
                        THEN 'Critical'
                    WHEN days_of_cover < (
                        SELECT COALESCE(cs.effective_lead_time / 10.0 + 5, 7)
                        FROM   curated_skus cs
                        WHERE  cs.sku_id = curated_inventory.sku_id
                    )
                        THEN 'At Risk'
                    WHEN current_stock_units > reorder_point * 3
                        THEN 'Overstock'
                    ELSE
                        'Healthy'
                END
            """))

            # Step 4: detect new alerts and insert them
            # IMPORTANT: pass conn into the function so we stay in the same
            # transaction and avoid the database locked error
            new_alerts = _detect_new_alerts(conn)

        # logging happens AFTER the connection closes
        if new_alerts:
            logger.warning(
                f"Risk detection -- {len(new_alerts)} NEW alerts detected"
            )
            for alert in new_alerts:
                logger.warning(
                    f"  ALERT -> {alert['sku_id']} | "
                    f"{alert['store_id']} | "
                    f"{alert['stock_status']} | "
                    f"doc={alert['days_of_cover']}d | "
                    f"risk={alert['risk_score']}"
                )
        else:
            logger.info("Risk detection -- no new alerts")

    except Exception as e:
        logger.error(f"run_risk_detection error: {e}")


def _detect_new_alerts(conn) -> list[dict]:
    """
    Finds positions that are Critical or At Risk but do not yet
    have an unresolved alert. Inserts new alert rows.

    Takes conn as a parameter — uses the SAME connection that
    run_risk_detection() already has open. This is the fix for
    the database locked error.

    Returns list of new alert dicts for logging.
    """
    # find at-risk positions with no existing unresolved alert
    at_risk = conn.execute(text("""
        SELECT
            ci.sku_id,
            ci.store_id,
            ci.record_id,
            ci.stock_status,
            ci.days_of_cover,
            ci.risk_score
        FROM   curated_inventory ci
        WHERE  ci.stock_status IN ('Critical', 'At Risk')
        AND    NOT EXISTS (
            SELECT 1
            FROM   alerts a
            WHERE  a.sku_id   = ci.sku_id
            AND    a.store_id = ci.store_id
            AND    a.resolved = 0
        )
        ORDER BY ci.risk_score DESC
        LIMIT 20
    """)).fetchall()

    if not at_risk:
        return []

    new_alerts = []
    for row in at_risk:
        sku_id, store_id, record_id, stock_status, days_of_cover, risk_score = row
        triggered_at = str(datetime.now())

        conn.execute(text("""
            INSERT INTO alerts
                (sku_id, store_id, stock_status, days_of_cover,
                 risk_score, triggered_at)
            VALUES
                (:sku_id, :store_id, :stock_status, :days_of_cover,
                 :risk_score, :triggered_at)
        """), {
            "sku_id":        sku_id,
            "store_id":      store_id,
            "stock_status":  stock_status,
            "days_of_cover": days_of_cover,
            "risk_score":    risk_score,
            "triggered_at":  triggered_at,
        })

        new_alerts.append({
            "sku_id":        sku_id,
            "store_id":      store_id,
            "stock_status":  stock_status,
            "days_of_cover": days_of_cover,
            "risk_score":    risk_score,
        })

    return new_alerts


# ==============================================================================
# STATUS REPORT (runs every 5 minutes)
# ==============================================================================

def print_status_report() -> None:
    """
    Prints a one-line health summary to console and log file.
    Shows current count of each stock_status and pending alerts.
    """
    try:
        with engine.connect() as conn:

            kpis = conn.execute(text("""
                SELECT
                    COUNT(*)                                                   AS total,
                    COUNT(CASE WHEN stock_status = 'Critical'  THEN 1 END)    AS critical,
                    COUNT(CASE WHEN stock_status = 'At Risk'   THEN 1 END)    AS at_risk,
                    COUNT(CASE WHEN stock_status = 'Healthy'   THEN 1 END)    AS healthy,
                    COUNT(CASE WHEN stock_status = 'Overstock' THEN 1 END)    AS overstock
                FROM curated_inventory
            """)).fetchone()

            pending = conn.execute(text("""
                SELECT COUNT(*) FROM alerts WHERE resolved = 0
            """)).scalar()

        logger.info(
            f"STATUS | Critical={kpis[1]} | At Risk={kpis[2]} | "
            f"Healthy={kpis[3]} | Overstock={kpis[4]} | "
            f"Pending alerts={pending}"
        )

    except Exception as e:
        logger.error(f"print_status_report error: {e}")


# ==============================================================================
# ONE-CYCLE RUN — for testing
# ==============================================================================

def run_once() -> None:
    """
    Runs one complete cycle and exits.
    Use this to test: python data/scheduler.py --once
    """
    logger.info("Running one cycle (--once mode)")
    simulate_sales()
    run_risk_detection()
    print_status_report()
    logger.info("One cycle complete")


# ==============================================================================
# MAIN
# ==============================================================================

def main() -> None:
    parser = argparse.ArgumentParser(description="ORCA inventory scheduler")
    parser.add_argument(
        "--interval", type=int, default=60,
        help="Sales simulation interval in seconds (default: 60)"
    )
    parser.add_argument(
        "--once", action="store_true",
        help="Run one cycle and exit (for testing)"
    )
    args = parser.parse_args()

    create_alerts_table()

    if args.once:
        run_once()
        return

    logger.info(f"ORCA Scheduler starting | sales interval={args.interval}s")
    logger.info(f"DB: {DB_PATH}")
    logger.info(f"Logs: {LOG_DIR / 'scheduler.log'}")
    logger.info("Press Ctrl+C to stop")

    scheduler = BlockingScheduler()

    # Job 1: simulate sales every N seconds
    scheduler.add_job(
        simulate_sales,
        trigger="interval",
        seconds=args.interval,
        id="simulate_sales",
        name="Sales Simulation",
    )

    # Job 2: risk detection every 5 minutes
    scheduler.add_job(
        run_risk_detection,
        trigger="interval",
        minutes=5,
        id="risk_detection",
        name="Risk Detection",
    )

    # Job 3: status report every 5 minutes
    # offset by 30 seconds so it runs after risk detection finishes
    scheduler.add_job(
        print_status_report,
        trigger="interval",
        minutes=5,
        seconds=30,
        id="status_report",
        name="Status Report",
    )

    # run once immediately on startup so you see current state right away
    run_risk_detection()
    print_status_report()

    try:
        scheduler.start()
    except KeyboardInterrupt:
        logger.info("Scheduler stopped by user")
        scheduler.shutdown()


if __name__ == "__main__":
    main()