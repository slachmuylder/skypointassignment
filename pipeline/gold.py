"""Gold layer: star-schema mart tables built from Silver.

Grain of each table is documented in sql/README.md -- this module is the
Python-side implementation of that same design (SCD2 for care level, the
resident-day fact that the required occupancy/labor/incident views are all
built from, etc). Output is one Parquet file per dimension/fact table.
"""
import pandas as pd

from pipeline.columns import COMMUNITY_ID, RESIDENT_ID
from pipeline.config import COMMUNITY_STATE, GOLD_DIR, STATE_REGION, VALID_COMMUNITY_IDS, data_as_of_date, data_window


def _latest_per_resident(residents: pd.DataFrame) -> pd.DataFrame:
    """pcc_residents is a monthly snapshot; take each resident's most recent
    known state as their Type-1 'current' attributes."""
    df = residents.copy()
    df["_month"] = df["_source_file"].str.extract(r"(\d{4}_\d{2})")
    return (
        df.sort_values("_month")
        .drop_duplicates(subset=RESIDENT_ID, keep="last")
        .drop(columns=["_month"])
    )


def build_dim_community() -> pd.DataFrame:
    rows = [
        {COMMUNITY_ID: cid, "state": COMMUNITY_STATE[cid], "region": STATE_REGION[COMMUNITY_STATE[cid]]}
        for cid in sorted(VALID_COMMUNITY_IDS)
    ]
    return pd.DataFrame(rows)


def build_dim_resident(residents: pd.DataFrame, care_level_scd: pd.DataFrame) -> pd.DataFrame:
    current = _latest_per_resident(residents)
    current_level = care_level_scd[care_level_scd["is_current"]][[RESIDENT_ID, "care_level"]]
    dim = current.merge(current_level, on=RESIDENT_ID, how="left", suffixes=("_snapshot", ""))
    dim["care_level"] = dim["care_level"].fillna(dim["care_level_snapshot"])
    return dim[
        [
            RESIDENT_ID, COMMUNITY_ID, "first_name", "last_name", "dob", "gender",
            "admit_date", "discharge_date", "care_level", "acuity_score",
        ]
    ]


def build_dim_resident_care_level_scd2(residents: pd.DataFrame, care_history: pd.DataFrame) -> pd.DataFrame:
    """SCD Type 2: a resident who changes care level gets a new row with
    effective/end dates rather than an overwrite. Built primarily from
    pcc_care_history (transactional change events); residents with no
    recorded change event get a single open-ended version seeded from their
    admit_date + snapshot care_level."""
    events = care_history.dropna(subset=["change_date"]).sort_values([RESIDENT_ID, "change_date"])
    rows = []
    residents_with_history = set(events[RESIDENT_ID].unique())

    for resident_id, grp in events.groupby(RESIDENT_ID):
        grp = grp.reset_index(drop=True)
        for i, row in grp.iterrows():
            end_date = grp.loc[i + 1, "change_date"] if i + 1 < len(grp) else None
            rows.append(
                {
                    RESIDENT_ID: resident_id,
                    "care_level": row["new_level"],
                    "effective_date": row["change_date"],
                    "end_date": end_date,
                    "is_current": end_date is None,
                    "change_reason": row["reason"],
                }
            )

    current_snapshot = _latest_per_resident(residents)
    no_history = current_snapshot[~current_snapshot[RESIDENT_ID].isin(residents_with_history)]
    for _, row in no_history.iterrows():
        if pd.isna(row["care_level"]):
            continue
        rows.append(
            {
                RESIDENT_ID: row[RESIDENT_ID],
                "care_level": row["care_level"],
                "effective_date": row["admit_date"],
                "end_date": None,
                "is_current": True,
                "change_reason": "Admission (no recorded change events in window)",
            }
        )

    return pd.DataFrame(rows)


def build_fact_acuity_snapshot(residents_history: pd.DataFrame) -> pd.DataFrame:
    """Periodic snapshot fact, grain: one row per resident per MONTH they had
    a valid acuity reading -- deliberately not collapsed down to "distinct
    values only".

    dim_resident only keeps each resident's latest (Type-1) acuity_score, so
    it can't answer "did this resident's acuity jump by 2+ points within 90
    days" -- that requires the history, which is what this table is for.
    Takes `residents_history` -- the cleaned-but-NOT-deduped companion to
    Silver's canonical pcc_residents (see
    pipeline/silver.py::clean_pcc_residents_history).

    Collapsing consecutive identical readings down to just their first (or
    just their last) occurrence was tried and is deliberately NOT done here:
    it actively breaks the 90-day-window check. If a resident held a value
    from January through June and changed in July, keeping only January's
    "first occurrence" of the old value makes the self-join in
    sql/views/06_acuity_increase_alerts.sql see a 181-day gap and correctly
    (per that collapsed view) exclude it -- even though the real gap that
    matters is June-to-July, 31 days, which should fire. Keeping every
    month's row lets that self-join find the closest actual qualifying pair
    on its own, which is what it's already designed to do."""
    df = residents_history.dropna(subset=["acuity_score"]).copy()
    df["_month"] = df["_source_file"].str.extract(r"(\d{4}_\d{2})")
    df["snapshot_date"] = pd.to_datetime(df["_month"], format="%Y_%m") + pd.offsets.MonthEnd(0)
    return df[[RESIDENT_ID, "snapshot_date", "acuity_score"]].sort_values([RESIDENT_ID, "snapshot_date"]).reset_index(drop=True)


def build_dim_unit(units: pd.DataFrame) -> pd.DataFrame:
    df = units.copy()
    df["_month"] = df["_source_file"].str.extract(r"(\d{4}_\d{2})")
    latest = df.sort_values("_month").drop_duplicates(subset="unit_id", keep="last")
    return latest[["unit_id", COMMUNITY_ID, "unit_type", "monthly_rent"]].drop(columns=[], errors="ignore")


def build_dim_employee(shifts: pd.DataFrame) -> pd.DataFrame:
    df = shifts.sort_values("shift_date").drop_duplicates(subset="employee_id", keep="last")
    return df[["employee_id", "role", COMMUNITY_ID]].rename(columns={"role": "latest_role", COMMUNITY_ID: "latest_community_id"})


def build_dim_date(start: str, end: str) -> pd.DataFrame:
    dates = pd.date_range(start, end, freq="D")
    return pd.DataFrame(
        {
            "date": dates.strftime("%Y-%m-%d"),
            "year": dates.year,
            "month": dates.month,
            "day": dates.day,
            "month_name": dates.strftime("%B"),
            "quarter": dates.quarter,
            "day_of_week": dates.strftime("%A"),
        }
    )


def build_fact_resident_day(residents: pd.DataFrame, care_level_scd: pd.DataFrame) -> pd.DataFrame:
    """Grain: one row per resident per calendar day they were active
    (admit_date <= day <= discharge_date, or day <= today if still resident).
    This is the base fact that occupancy, labor-cost-per-resident-day, and
    incident-rate-per-100-resident-days are all computed against.

    Built as a single vectorized DuckDB query (spine of resident x day via
    generate_series, joined to the SCD2 care-level range) -- a row-by-row
    Python loop over ~800k resident-days took 2+ minutes; this takes under a
    second."""
    import duckdb

    current = _latest_per_resident(residents)[
        [RESIDENT_ID, COMMUNITY_ID, "admit_date", "discharge_date"]
    ].dropna(subset=["admit_date"]).copy()
    as_of = data_as_of_date()
    current["stop_date"] = current["discharge_date"].fillna(as_of)
    current = current[current["stop_date"] >= current["admit_date"]]

    scd = care_level_scd.copy()
    scd["end_date"] = scd["end_date"].fillna("2200-01-01")

    return duckdb.sql(
        """
        SELECT
            c.resident_id,
            c.community_id,
            CAST(d.date AS VARCHAR) AS date,
            scd.care_level
        FROM current c
        CROSS JOIN LATERAL UNNEST(
            generate_series(c.admit_date::DATE, c.stop_date::DATE, INTERVAL 1 DAY)
        ) AS d(date)
        LEFT JOIN scd
            ON scd.resident_id = c.resident_id
            AND d.date >= scd.effective_date::DATE
            AND d.date < scd.end_date::DATE
        """
    ).df()


def build_fact_lease(leases: pd.DataFrame) -> pd.DataFrame:
    return leases[
        ["lease_id", RESIDENT_ID, "unit_id", COMMUNITY_ID, "move_in_date", "move_out_date", "move_out_reason", "monthly_rate"]
    ].copy()


def build_fact_labor(shifts: pd.DataFrame) -> pd.DataFrame:
    df = shifts.copy()
    df["labor_cost"] = df["hours_worked"] * df["hourly_rate"]
    return df[["shift_id", COMMUNITY_ID, "employee_id", "role", "shift_date", "hours_worked", "hourly_rate", "labor_cost"]]


def build_fact_incident(incidents: pd.DataFrame) -> pd.DataFrame:
    return incidents[["incident_id", RESIDENT_ID, COMMUNITY_ID, "incident_date", "incident_type", "severity", "reported_by"]].copy()


def build_fact_review(reviews: pd.DataFrame) -> pd.DataFrame:
    df = reviews.copy()
    df["has_response"] = df["response_text"].notna()
    return df[["review_id", COMMUNITY_ID, "review_date", "rating", "has_response", "responded_at"]]


def build_fact_lead(leads: pd.DataFrame) -> pd.DataFrame:
    return leads[
        ["lead_id", COMMUNITY_ID, "lead_source", "created_date", "tour_date", "deposit_date", "move_in_date", "status", "lost_reason"]
    ].copy()


def write_gold_table(df: pd.DataFrame, name: str) -> int:
    df = df.copy()
    for col in df.columns:
        if col in ("date", "dob") or col.endswith("_date"):
            df[col] = pd.to_datetime(df[col]).dt.date
    GOLD_DIR.mkdir(parents=True, exist_ok=True)
    df.to_parquet(GOLD_DIR / f"{name}.parquet", index=False)
    return len(df)
