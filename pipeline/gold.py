"""Gold layer: star-schema mart tables built from Silver.

Every dimension (except dim_date) gets a numeric
surrogate key as its primary key, with the source system's natural key
retained as a plain attribute column. Every fact table's foreign keys to
those dimensions are the surrogate keys.

Surrogate keys are recomputed fresh on every Gold rebuild (sorted by natural
key, then enumerated 1..n) rather than persisted across runs.
"""
import pandas as pd
from pipeline.columns import COMMUNITY_ID, RESIDENT_ID
from pipeline.config import COMMUNITY_STATE, GOLD_DIR, STATE_REGION, VALID_COMMUNITY_IDS, data_as_of_date, data_window


def _assign_surrogate_key(df: pd.DataFrame, natural_key_cols, key_name: str) -> pd.DataFrame:
    df = df.sort_values(natural_key_cols).reset_index(drop=True)
    df.insert(0, key_name, range(1, len(df) + 1))
    return df


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
    return _assign_surrogate_key(pd.DataFrame(rows), COMMUNITY_ID, "community_key")


def build_dim_resident(residents: pd.DataFrame, care_level_scd: pd.DataFrame, dim_community: pd.DataFrame) -> pd.DataFrame:
    current = _latest_per_resident(residents)
    current_level = care_level_scd[care_level_scd["is_current"]][[RESIDENT_ID, "care_level"]]
    dim = current.merge(current_level, on=RESIDENT_ID, how="left", suffixes=("_snapshot", ""))
    dim["care_level"] = dim["care_level"].fillna(dim["care_level_snapshot"])
    dim = dim.merge(dim_community[[COMMUNITY_ID, "community_key"]], on=COMMUNITY_ID, how="left")
    dim = dim[
        [
            RESIDENT_ID, "community_key", "first_name", "last_name", "dob", "gender",
            "admit_date", "discharge_date", "care_level", "acuity_score",
        ]
    ]
    return _assign_surrogate_key(dim, RESIDENT_ID, "resident_key")


def build_dim_resident_care_level_scd2(residents: pd.DataFrame, care_history: pd.DataFrame) -> pd.DataFrame:
    """SCD Type 2: a resident who changes care level gets a new row with
    effective/end dates rather than an overwrite. Built primarily from
    pcc_care_history (transactional change events); residents with no
    recorded change event get a single open-ended version seeded from their
    admit_date + snapshot care_level.

    A resident's earliest recorded change event only tells us their care
    level *from* change_date onward -- it says nothing about the period
    between admit_date and that first change. But the event itself also
    carries previous_level, which is exactly what the resident's care level
    was for that whole pre-history period, so it's used here to seed one
    additional opening version (admit_date -> first change_date) rather than
    leaving that period with no SCD2 row at all (which would otherwise surface
    as an unexplained NULL resident_care_level_key in fact_resident_day for every
    resident who has at least one recorded change event).

    Each SCD2 version -- not each resident -- gets its own surrogate key
    (resident_care_level_key), since this table's grain is resident x time-period,
    not resident alone; a resident who changed care level has multiple valid
    rows and therefore multiple keys."""
    events = care_history.dropna(subset=["change_date"]).sort_values([RESIDENT_ID, "change_date"])
    rows = []
    residents_with_history = set(events[RESIDENT_ID].unique())
    current_snapshot = _latest_per_resident(residents)
    admit_dates = current_snapshot.set_index(RESIDENT_ID)["admit_date"]

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

        first_event = grp.iloc[0]
        admit_date = admit_dates.get(resident_id)
        if pd.notna(admit_date) and pd.notna(first_event["previous_level"]) and first_event["change_date"] > admit_date:
            rows.append(
                {
                    RESIDENT_ID: resident_id,
                    "care_level": first_event["previous_level"],
                    "effective_date": admit_date,
                    "end_date": first_event["change_date"],
                    "is_current": False,
                    "change_reason": "Admission (opening balance, backfilled from earliest recorded change's previous_level)",
                }
            )

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

    dim = pd.DataFrame(rows)
    return _assign_surrogate_key(dim, [RESIDENT_ID, "effective_date"], "resident_care_level_key")


def build_dim_unit(units: pd.DataFrame, dim_community: pd.DataFrame) -> pd.DataFrame:
    df = units.copy()
    df["_month"] = df["_source_file"].str.extract(r"(\d{4}_\d{2})")
    latest = df.sort_values("_month").drop_duplicates(subset="unit_id", keep="last")
    latest = latest.merge(dim_community[[COMMUNITY_ID, "community_key"]], on=COMMUNITY_ID, how="left")
    dim = latest[["unit_id", "community_key", "unit_type", "monthly_rent"]]
    return _assign_surrogate_key(dim, "unit_id", "unit_key")


def build_dim_employee(shifts: pd.DataFrame, dim_community: pd.DataFrame) -> pd.DataFrame:
    df = shifts.sort_values("shift_date").drop_duplicates(subset="employee_id", keep="last")
    df = df.merge(dim_community[[COMMUNITY_ID, "community_key"]], on=COMMUNITY_ID, how="left")
    dim = df[["employee_id", "role", "community_key"]].rename(columns={"role": "latest_role", "community_key": "latest_community_key"})
    return _assign_surrogate_key(dim, "employee_id", "employee_key")


def build_dim_date(start: str, end: str) -> pd.DataFrame:
    """No surrogate key here -- the date itself is already unique, sortable,
    and meaningful, so a meaningless integer key wouldn't add anything."""
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


def build_fact_resident_day(
    residents: pd.DataFrame, care_level_scd: pd.DataFrame, dim_resident: pd.DataFrame, dim_community: pd.DataFrame
) -> pd.DataFrame:
    """Grain: one row per resident per calendar day they were active
    (admit_date <= day <= discharge_date, or day <= today if still resident).
    This is the base fact that occupancy, labor-cost-per-resident-day, and
    incident-rate-per-100-resident-days are all computed against.
"""
    import duckdb

    current = _latest_per_resident(residents)[
        [RESIDENT_ID, COMMUNITY_ID, "admit_date", "discharge_date"]
    ].dropna(subset=["admit_date"]).copy()
    as_of = data_as_of_date()
    current["stop_date"] = current["discharge_date"].fillna(as_of)
    current = current[current["stop_date"] >= current["admit_date"]]

    scd = care_level_scd.copy()
    scd["end_date"] = scd["end_date"].fillna("2200-01-01")

    spine = duckdb.sql(
        """
        SELECT
            c.resident_id,
            c.community_id,
            CAST(d.date AS VARCHAR) AS date,
            scd.resident_care_level_key
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

    spine = spine.merge(dim_resident[[RESIDENT_ID, "resident_key"]], on=RESIDENT_ID, how="left")
    spine = spine.merge(dim_community[[COMMUNITY_ID, "community_key"]], on=COMMUNITY_ID, how="left")
    return spine[["resident_key", "community_key", "date", "resident_care_level_key"]]


def build_fact_acuity_snapshot(residents_history: pd.DataFrame, dim_resident: pd.DataFrame) -> pd.DataFrame:
    """Periodic snapshot fact, grain: one row per resident per MONTH they had
    a valid acuity reading -- deliberately not collapsed down to "distinct
    values only".

    dim_resident only keeps each resident's latest (Type-1) acuity_score, so
    it can't answer "did this resident's acuity jump by 2+ points within 90
    days" .
    """
    df = residents_history.dropna(subset=["acuity_score"]).copy()
    df["_month"] = df["_source_file"].str.extract(r"(\d{4}_\d{2})")
    df["snapshot_date"] = pd.to_datetime(df["_month"], format="%Y_%m") + pd.offsets.MonthEnd(0)
    df = df.merge(dim_resident[[RESIDENT_ID, "resident_key"]], on=RESIDENT_ID, how="left")
    return df[["resident_key", "snapshot_date", "acuity_score"]].sort_values(["resident_key", "snapshot_date"]).reset_index(drop=True)


def build_fact_lease(leases: pd.DataFrame, dim_resident: pd.DataFrame, dim_unit: pd.DataFrame, dim_community: pd.DataFrame) -> pd.DataFrame:
    df = leases.merge(dim_resident[[RESIDENT_ID, "resident_key"]], on=RESIDENT_ID, how="left")
    df = df.merge(dim_unit[["unit_id", "unit_key"]], on="unit_id", how="left")
    df = df.merge(dim_community[[COMMUNITY_ID, "community_key"]], on=COMMUNITY_ID, how="left")
    return df[
        ["lease_id", "resident_key", "unit_key", "community_key", "move_in_date", "move_out_date", "move_out_reason", "monthly_rate"]
    ].copy()


def build_fact_labor(shifts: pd.DataFrame, dim_employee: pd.DataFrame, dim_community: pd.DataFrame) -> pd.DataFrame:
    df = shifts.copy()
    df["labor_cost"] = df["hours_worked"] * df["hourly_rate"]
    df = df.merge(dim_employee[["employee_id", "employee_key"]], on="employee_id", how="left")
    df = df.merge(dim_community[[COMMUNITY_ID, "community_key"]], on=COMMUNITY_ID, how="left")
    return df[["shift_id", "community_key", "employee_key", "role", "shift_date", "hours_worked", "hourly_rate", "labor_cost"]]


def build_fact_incident(incidents: pd.DataFrame, dim_resident: pd.DataFrame, dim_community: pd.DataFrame, dim_employee: pd.DataFrame) -> pd.DataFrame:
    """Confirmed anomaly: PCC's pcc_incidents.reported_by IDs are all 4-digit
    ("E1000"-"E9982") while ADP's adp_shifts.employee_id IDs are all 5-digit
    ("E10104"-"E99915") -- zero overlap across all 411 incidents / 68,071
    shifts, with no exceptions on either side. These are two entirely
    separate employee-ID systems that were never reconciled between PCC and
    ADP. Original source key left until this inconsistency is resolved"""
    df = incidents.merge(dim_resident[[RESIDENT_ID, "resident_key"]], on=RESIDENT_ID, how="left")
    df = df.merge(dim_community[[COMMUNITY_ID, "community_key"]], on=COMMUNITY_ID, how="left")
    return df[["incident_id", "resident_key", "community_key", "incident_date", "incident_type", "severity", "reported_by"]].copy()


def build_fact_review(reviews: pd.DataFrame, dim_community: pd.DataFrame) -> pd.DataFrame:
    df = reviews.copy()
    df["has_response"] = df["response_text"].notna()
    df = df.merge(dim_community[[COMMUNITY_ID, "community_key"]], on=COMMUNITY_ID, how="left")
    return df[["review_id", "community_key", "review_date", "rating", "has_response", "responded_at"]]


def build_fact_lead(leads: pd.DataFrame, dim_community: pd.DataFrame) -> pd.DataFrame:
    df = leads.merge(dim_community[[COMMUNITY_ID, "community_key"]], on=COMMUNITY_ID, how="left")
    return df[
        ["lead_id", "community_key", "lead_source", "created_date", "tour_date", "deposit_date", "move_in_date", "status", "lost_reason"]
    ].copy()


def write_gold_table(df: pd.DataFrame, name: str) -> int:
    df = df.copy()
    for col in df.columns:
        if col in ("date", "dob") or col.endswith("_date"):
            df[col] = pd.to_datetime(df[col]).dt.date
    GOLD_DIR.mkdir(parents=True, exist_ok=True)
    df.to_parquet(GOLD_DIR / f"{name}.parquet", index=False)
    return len(df)
