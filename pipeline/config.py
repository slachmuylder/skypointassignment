"""Shared paths and reference data for the Pinewood pipeline.

Community-to-state mapping is not present anywhere in the source data (confirmed
by inspection of every CSV's columns) so it is hard-coded here as a documented
assumption -- see README.md "Assumptions" section.
"""
import re
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
RAW_DATA_DIR = REPO_ROOT / "candidate_package" / "data"


def _source_months() -> set[tuple[int, int]]:
    months = set()
    for f in RAW_DATA_DIR.glob("*.csv"):
        m = re.search(r"(\d{4})_(\d{2})\.csv$", f.name)
        if m:
            months.add((int(m.group(1)), int(m.group(2))))
    return months


def data_as_of_date() -> str:
    """Last day of the most recent YYYY_MM month present in the raw source
    files. Used as the cutoff for 'still active as of today' logic instead
    of the real wall-clock date -- the dataset is a fixed 6-month historical
    export (2025-01 through 2025-06 at the time this was built), so using
    actual today() would extend every still-active resident's fact_resident_day
    rows years past the end of the real data."""
    year, month = max(_source_months())
    next_month = pd.Timestamp(year=year, month=month, day=1) + pd.DateOffset(months=1)
    return (next_month - pd.Timedelta(days=1)).strftime("%Y-%m-%d")


def data_window() -> tuple[str, str]:
    """(first day, last day) of the reporting window actually covered by the
    raw exports -- i.e. the first and last YYYY_MM month present. dim_date is
    built to exactly this span rather than an arbitrary wide range, so that
    monthly views (occupancy, labor cost) aren't silently missing months --
    joining resident-days against dim_date naturally excludes a resident's
    pre-window tenure history (admit dates can be years before the export
    window) rather than trying to report occupancy for years the exports
    don't cover."""
    months = _source_months()
    start_year, start_month = min(months)
    end_year, end_month = max(months)
    start = pd.Timestamp(year=start_year, month=start_month, day=1)
    end = pd.Timestamp(year=end_year, month=end_month, day=1) + pd.DateOffset(months=1) - pd.Timedelta(days=1)
    return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")

BRONZE_DIR = REPO_ROOT / "pipeline" / "data" / "bronze"
SILVER_DIR = REPO_ROOT / "pipeline" / "data" / "silver"
GOLD_DIR = REPO_ROOT / "pipeline" / "data" / "gold"
LOG_DIR = REPO_ROOT / "pipeline" / "logs"
STATE_FILE = REPO_ROOT / "pipeline" / "data" / "_pipeline_state.parquet"

SQL_DIR = REPO_ROOT / "sql"

# Source table -> filename glob pattern, keyed the way DATA_DICTIONARY.md names them.
SOURCE_TABLES = {
    "pcc_residents": "pcc_residents_*.csv",
    "pcc_incidents": "pcc_incidents_*.csv",
    "pcc_care_history": "pcc_care_history_*.csv",
    "yardi_units": "yardi_units_*.csv",
    "yardi_leases": "yardi_leases_*.csv",
    "adp_shifts": "adp_shifts_*.csv",
    "gbp_reviews": "gbp_reviews_*.csv",
    "hubspot_leads": "hubspot_leads_*.csv",
}

# The 14 real Pinewood communities. Anything outside this set found in the raw
# data (e.g. C905/C934/C936/C951/C969 in yardi_units) is a phantom record that
# gets quarantined rather than joined into Gold.
VALID_COMMUNITY_IDS = {f"C{i:03d}" for i in range(1, 15)}

# Hard-coded because the source data never links a community to a state.
# Assumption, documented in README: split evenly across the three states in
# community_id order.
COMMUNITY_STATE = {
    "C001": "OR", "C002": "OR", "C003": "OR", "C004": "OR", "C005": "OR",
    "C006": "AZ", "C007": "AZ", "C008": "AZ", "C009": "AZ", "C010": "AZ",
    "C011": "TX", "C012": "TX", "C013": "TX", "C014": "TX",
}

STATE_REGION = {
    "OR": "Pacific Northwest",
    "AZ": "Southwest",
    "TX": "South",
}

# Canonical care-level values. Source systems use inconsistent labels
# (AL/Assisted/Assisted Living, IL/Independent/Independent Living,
# MC/Memory/Memory Care) -- normalize everything to the 3-letter code that
# yardi_units.unit_type already uses cleanly.
CARE_LEVEL_MAP = {
    "il": "IL", "independent": "IL", "independent living": "IL",
    "al": "AL", "assisted": "AL", "assisted living": "AL",
    "mc": "MC", "memory": "MC", "memory care": "MC",
}

ACUITY_MIN, ACUITY_MAX = 1, 10
