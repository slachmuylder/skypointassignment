"""Silver layer: cleaned, deduplicated, typed, business keys resolved.

Each function takes the concatenated Bronze rows for one source table and
returns a cleaned DataFrame plus a `rejects` DataFrame (rows quarantined for a
business-rule violation, e.g. an out-of-range acuity score or a phantom
community_id). Rejected rows are are written out separately."""

import pandas as pd
from pipeline.columns import COMMUNITY_ID, RESIDENT_ID
from pipeline.config import ACUITY_MAX, ACUITY_MIN, CARE_LEVEL_MAP, VALID_COMMUNITY_IDS, data_as_of_date
from pipeline.utils import parse_mixed_date

BUSINESS_COLS = {
    "pcc_residents": [RESIDENT_ID, COMMUNITY_ID, "admit_date", "discharge_date", "care_level", "acuity_score"],
    "pcc_incidents": ["incident_id"],
    "pcc_care_history": [RESIDENT_ID, "change_date", "new_level"],
    "yardi_units": ["unit_id", "snapshot_date"],
    "yardi_leases": ["lease_id"],
    "adp_shifts": ["shift_id"],
    "gbp_reviews": ["review_id"],
    "hubspot_leads": ["lead_id"],
}


def _normalize_care_level(series: pd.Series) -> pd.Series:
    #Handles where care levels are recorded inconsistently
    return series.str.strip().str.lower().map(CARE_LEVEL_MAP)


def _dedupe_by_business_key(df: pd.DataFrame, table: str) -> pd.DataFrame:
    keys = BUSINESS_COLS[table]
    # Keep the row from the most recently ingested source file for each business key
    # so re-running the pipeline (or a corrected re-export) is idempotent.
    return (
        df.sort_values("_ingested_at")
        .drop_duplicates(subset=keys, keep="last")
        .reset_index(drop=True)
    )


def clean_pcc_residents(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    # Normalize BEFORE deduping since some of the columns are part of the 
    # business key
    df = df.copy()
    df["dob"] = parse_mixed_date(df["dob"])
    df["admit_date"] = parse_mixed_date(df["admit_date"])
    df["discharge_date"] = parse_mixed_date(df["discharge_date"])
    df["care_level"] = _normalize_care_level(df["care_level"])
    df["acuity_score"] = pd.to_numeric(df["acuity_score"], errors="coerce")
    df = _dedupe_by_business_key(df, "pcc_residents")

    # Clean data
    as_of = data_as_of_date()
    bad_acuity = ~df["acuity_score"].between(ACUITY_MIN, ACUITY_MAX)
    bad_community = ~df[COMMUNITY_ID].isin(VALID_COMMUNITY_IDS)
    bad_discharge = df["discharge_date"].notna() & (df["discharge_date"] > as_of)

    rejects = df[bad_acuity | bad_community | bad_discharge].copy()
    if not rejects.empty:
        def reason(i):
            if bad_acuity[i]:
                return "acuity_score_out_of_range"
            if bad_discharge[i]:
                return "future_dated_discharge"
            if bad_community[i]:
                return "unknown_community_id"
            raise AssertionError(
                f"row {i} is in rejects but matched none of bad_acuity/bad_discharge/bad_community "
                "-- is_reject and reason() have drifted out of sync"
            )

        rejects["reject_reason"] = [reason(i) for i in rejects.index]

    df.loc[bad_acuity, "acuity_score"] = None
    df.loc[bad_discharge, "discharge_date"] = None
    return df[~bad_community].reset_index(drop=True), rejects


def clean_pcc_incidents(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    df = _dedupe_by_business_key(df, "pcc_incidents")
    df["incident_date"] = parse_mixed_date(df["incident_date"])
    df["severity"] = pd.to_numeric(df["severity"], errors="coerce")
    bad_community = ~df[COMMUNITY_ID].isin(VALID_COMMUNITY_IDS)
    rejects = df[bad_community].copy()
    if not rejects.empty:
        rejects["reject_reason"] = "unknown_community_id"
    return df[~bad_community].reset_index(drop=True), rejects


def clean_pcc_care_history(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    df = df.copy()
    df["change_date"] = parse_mixed_date(df["change_date"])
    df["previous_level"] = df["previous_level"].where(
        df["previous_level"].isna(), _normalize_care_level(df["previous_level"])
    )
    df["new_level"] = _normalize_care_level(df["new_level"])
    df = _dedupe_by_business_key(df, "pcc_care_history")
    return df.reset_index(drop=True), pd.DataFrame()


def clean_yardi_units(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    df = _dedupe_by_business_key(df, "yardi_units")
    df["snapshot_date"] = parse_mixed_date(df["snapshot_date"])
    df["monthly_rent"] = pd.to_numeric(df["monthly_rent"], errors="coerce")
    bad_community = ~df[COMMUNITY_ID].isin(VALID_COMMUNITY_IDS)
    rejects = df[bad_community].copy()
    if not rejects.empty:
        rejects["reject_reason"] = "unknown_community_id"
    return df[~bad_community].reset_index(drop=True), rejects


def clean_yardi_leases(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    df = _dedupe_by_business_key(df, "yardi_leases")
    df["move_in_date"] = parse_mixed_date(df["move_in_date"])
    df["move_out_date"] = parse_mixed_date(df["move_out_date"])
    df["monthly_rate"] = pd.to_numeric(df["monthly_rate"], errors="coerce")
    bad_community = ~df[COMMUNITY_ID].isin(VALID_COMMUNITY_IDS)
    rejects = df[bad_community].copy()
    if not rejects.empty:
        rejects["reject_reason"] = "unknown_community_id"
    return df[~bad_community].reset_index(drop=True), rejects


def _resolve_hourly_rate(df: pd.DataFrame) -> pd.Series:
    """hourly_rate is a stringified per-employee {role: rate} dict on every
    row instead of a scalar (confirmed anomaly). The correct rate for the
    row is the value keyed by that row's own `role`."""
    import ast

    def resolve(row):
        try:
            rate_map = ast.literal_eval(row["hourly_rate"])
            return rate_map.get(row["role"])
        except (ValueError, SyntaxError, AttributeError):
            return None

    return df.apply(resolve, axis=1)


def clean_adp_shifts(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    df = _dedupe_by_business_key(df, "adp_shifts")
    df["shift_date"] = parse_mixed_date(df["shift_date"])
    df["hours_worked"] = pd.to_numeric(df["hours_worked"], errors="coerce")
    df["hourly_rate"] = _resolve_hourly_rate(df)
    bad_community = ~df[COMMUNITY_ID].isin(VALID_COMMUNITY_IDS)
    bad_rate = df["hourly_rate"].isna()
    is_reject = bad_community | bad_rate
    rejects = df[is_reject].copy()
    if not rejects.empty:
        def reason(i):
            if bad_community[i]:
                return "unknown_community_id"
            if bad_rate[i]:
                return "unresolvable_hourly_rate"
            raise AssertionError(
                f"row {i} is in rejects but matched neither bad_community nor bad_rate "
                "-- is_reject and reason() have drifted out of sync"
            )

        rejects["reject_reason"] = [reason(i) for i in rejects.index]
    return df[~is_reject].reset_index(drop=True), rejects


def clean_gbp_reviews(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    df = _dedupe_by_business_key(df, "gbp_reviews")
    df["review_date"] = parse_mixed_date(df["review_date"])
    df["responded_at"] = parse_mixed_date(df["responded_at"])
    df["rating"] = pd.to_numeric(df["rating"], errors="coerce")
    bad_community = ~df[COMMUNITY_ID].isin(VALID_COMMUNITY_IDS)
    rejects = df[bad_community].copy()
    if not rejects.empty:
        rejects["reject_reason"] = "unknown_community_id"
    return df[~bad_community].reset_index(drop=True), rejects


def clean_hubspot_leads(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    # lead_id should be unique. Must be detected BEFORE the generic
    # drop_duplicates-by-key step below, which would otherwise silently
    # collapse the collision down to one arbitrary row.
    colliding_ids = df.loc[df["lead_id"].duplicated(keep=False), "lead_id"].unique()
    is_collision = df["lead_id"].isin(colliding_ids)
    collisions = df[is_collision].copy()
    collisions["reject_reason"] = "duplicate_lead_id_conflicting_data"

    df = _dedupe_by_business_key(df[~is_collision], "hubspot_leads")
    df["created_date"] = parse_mixed_date(df["created_date"])
    df["tour_date"] = parse_mixed_date(df["tour_date"])
    df["deposit_date"] = parse_mixed_date(df["deposit_date"])
    df["move_in_date"] = parse_mixed_date(df["move_in_date"])

    bad_community = ~df[COMMUNITY_ID].isin(VALID_COMMUNITY_IDS)
    community_rejects = df[bad_community].copy()
    if not community_rejects.empty:
        community_rejects["reject_reason"] = "unknown_community_id"

    rejects = pd.concat([collisions, community_rejects], ignore_index=True, sort=False)
    return df[~bad_community].reset_index(drop=True), rejects


CLEANERS = {
    "pcc_residents": clean_pcc_residents,
    "pcc_incidents": clean_pcc_incidents,
    "pcc_care_history": clean_pcc_care_history,
    "yardi_units": clean_yardi_units,
    "yardi_leases": clean_yardi_leases,
    "adp_shifts": clean_adp_shifts,
    "gbp_reviews": clean_gbp_reviews,
    "hubspot_leads": clean_hubspot_leads,
}
