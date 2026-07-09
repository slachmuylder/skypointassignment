"""Individual validation checks. Each returns a dict with a pass/fail
verdict plus enough detail to act on it -- these get assembled into the
report by validation/run.py."""
import pandas as pd
from pipeline.config import ACUITY_MAX, ACUITY_MIN, GOLD_DIR, SILVER_DIR, data_as_of_date


def _read(layer_dir, name):
    path = layer_dir / f"{name}.parquet"
    return pd.read_parquet(path) if path.exists() else pd.DataFrame()


def _result(check, passed, detail, severity="low", action="none"):
    return {
        "check": check,
        "status": "pass" if passed else "fail",
        "detail": detail,
        "severity": severity if not passed else "n/a",
        "action": action if not passed else "n/a",
    }


# ---------------------------------------------------------------------------
# Row-count reconciliation
# ---------------------------------------------------------------------------

def row_count_reconciliation(bronze_summary: dict, silver_summary: dict) -> list[dict]:
    """Bronze -> Silver: rows_in must equal rows_out + rows_dropped exactly
    (rows_flagged is not part of this identity -- some anomalies are handled
    by nulling a field rather than dropping the row, see
    pipeline/silver.py::clean_pcc_residents). Any gap is a real accounting
    bug in the pipeline."""
    results = []
    for table, silver_stats in silver_summary.items():
        expected_out = silver_stats["rows_in"] - silver_stats["rows_dropped"]
        actual_out = silver_stats["rows_out"]
        results.append(
            _result(
                f"row_count_reconciliation[{table}]",
                expected_out == actual_out,
                {"rows_in": silver_stats["rows_in"], "rows_dropped": silver_stats["rows_dropped"], "expected_out": expected_out, "actual_out": actual_out},
                severity="high",
                action="fix_in_pipeline",
            )
        )
    return results


# ---------------------------------------------------------------------------
# Aggregate reconciliation (exact -- these are deterministic derivations /
# pass-throughs, not aggregations with expected noise, so 0 tolerance)
# ---------------------------------------------------------------------------

def aggregate_reconciliation() -> list[dict]:
    results = []

    silver_leases = _read(SILVER_DIR, "yardi_leases")
    gold_leases = _read(GOLD_DIR, "fact_lease")
    silver_revenue = silver_leases["monthly_rate"].sum()
    gold_revenue = gold_leases["monthly_rate"].sum()
    results.append(
        _result(
            "aggregate_reconciliation[total_lease_revenue]",
            silver_revenue == gold_revenue,
            {"silver_total": float(silver_revenue), "gold_total": float(gold_revenue)},
            severity="high",
            action="fix_in_pipeline",
        )
    )

    silver_shifts = _read(SILVER_DIR, "adp_shifts")
    gold_labor = _read(GOLD_DIR, "fact_labor")
    silver_hours = silver_shifts["hours_worked"].sum()
    gold_hours = gold_labor["hours_worked"].sum()
    results.append(
        _result(
            "aggregate_reconciliation[total_shift_hours]",
            silver_hours == gold_hours,
            {"silver_total": float(silver_hours), "gold_total": float(gold_hours)},
            severity="high",
            action="fix_in_pipeline",
        )
    )

    dim_resident = _read(GOLD_DIR, "dim_resident")
    fact_resident_day = _read(GOLD_DIR, "fact_resident_day")
    as_of = pd.Timestamp(data_as_of_date())
    expected_days = 0
    for _, r in dim_resident.dropna(subset=["admit_date"]).iterrows():
        stop = pd.Timestamp(r["discharge_date"]) if pd.notna(r["discharge_date"]) else as_of
        start = pd.Timestamp(r["admit_date"])
        if stop >= start:
            expected_days += (stop - start).days + 1
    actual_days = len(fact_resident_day)
    results.append(
        _result(
            "aggregate_reconciliation[total_resident_days]",
            expected_days == actual_days,
            {"expected_from_dim_resident": expected_days, "actual_in_fact_resident_day": actual_days},
            severity="high",
            action="fix_in_pipeline",
        )
    )
    return results


# ---------------------------------------------------------------------------
# Business rule checks
# ---------------------------------------------------------------------------

def no_overlapping_leases() -> dict:
    leases = _read(GOLD_DIR, "fact_lease").copy()
    leases["move_in_date"] = pd.to_datetime(leases["move_in_date"])
    leases["move_out_date"] = pd.to_datetime(leases["move_out_date"]).fillna(pd.Timestamp("2200-01-01"))

    overlaps = []
    for resident_key, grp in leases.sort_values("move_in_date").groupby("resident_key"):
        prev_end = None
        for _, row in grp.iterrows():
            if prev_end is not None and row["move_in_date"] < prev_end:
                overlaps.append(resident_key)
            prev_end = max(prev_end, row["move_out_date"]) if prev_end is not None else row["move_out_date"]

    # Report the natural resident_id (not the surrogate resident_key) in the
    # detail, since this is a human-facing check -- a bare integer key isn't
    # something anyone reading the report could act on.
    dim_resident = _read(GOLD_DIR, "dim_resident")
    key_to_natural = dict(zip(dim_resident["resident_key"], dim_resident["resident_id"]))
    residents_with_overlap = sorted({key_to_natural.get(k, k) for k in overlaps})

    return _result(
        "no_overlapping_leases_per_resident",
        len(overlaps) == 0,
        {"residents_with_overlap": residents_with_overlap},
        severity="high",
        action="raise_to_client",
    )


def no_negative_or_impossible_occupancy() -> dict:
    from api.queries import occupancy  # reuse the same query the API serves

    df = occupancy(None, None, None)
    bad = df[(df["occupancy_rate_pct"] < 0) | (df["occupancy_rate_pct"] > 100)]
    return _result(
        "no_negative_or_over_100_occupancy",
        bad.empty,
        {"violating_rows": bad.to_dict(orient="records")},
        severity="high",
        action="fix_in_pipeline",
    )


def no_discharge_before_admit() -> dict:
    df = _read(GOLD_DIR, "dim_resident")
    bad = df[df["discharge_date"].notna() & (pd.to_datetime(df["discharge_date"]) < pd.to_datetime(df["admit_date"]))]
    return _result(
        "no_discharge_before_admit",
        bad.empty,
        {"resident_ids": bad["resident_id"].tolist()},
        severity="high",
        action="fix_in_pipeline",
    )


def no_future_dated_events() -> dict:
    as_of = pd.Timestamp(data_as_of_date())
    violations = {}
    checks = {
        "fact_incident": "incident_date",
        "fact_review": "review_date",
        "fact_lease": "move_in_date",
        "fact_labor": "shift_date",
        "fact_lead": "created_date",
        "dim_resident": "discharge_date",
    }
    for table, col in checks.items():
        df = _read(GOLD_DIR, table)
        if df.empty or col not in df.columns:
            continue
        bad = df[df[col].notna() & (pd.to_datetime(df[col]) > as_of)]
        if not bad.empty:
            violations[f"{table}.{col}"] = len(bad)
    return _result(
        "no_future_dated_events",
        len(violations) == 0,
        {"violations_by_column": violations, "as_of_date": str(as_of.date())},
        severity="high",
        action="raise_to_client",
    )


def acuity_scores_within_range() -> dict:
    """NULL is the expected, intentional state for a resident whose raw
    acuity_score was quarantined (see pipeline/silver.py) -- only a
    non-null out-of-range value here would indicate a real pipeline bug."""
    df = _read(GOLD_DIR, "dim_resident")
    bad = df[df["acuity_score"].notna() & ~df["acuity_score"].between(ACUITY_MIN, ACUITY_MAX)]
    return _result(
        "acuity_scores_within_range",
        bad.empty,
        {"resident_ids": bad["resident_id"].tolist()},
        severity="high",
        action="fix_in_pipeline",
    )


def severity_and_rating_within_range() -> list[dict]:
    results = []
    incidents = _read(GOLD_DIR, "fact_incident")
    bad_severity = incidents[~incidents["severity"].between(1, 5)]
    results.append(
        _result("incident_severity_within_1_5", bad_severity.empty, {"incident_ids": bad_severity["incident_id"].tolist()}, severity="medium", action="fix_in_pipeline")
    )

    reviews = _read(GOLD_DIR, "fact_review")
    bad_rating = reviews[~reviews["rating"].between(1, 5)]
    results.append(
        _result("review_rating_within_1_5", bad_rating.empty, {"review_ids": bad_rating["review_id"].tolist()}, severity="medium", action="fix_in_pipeline")
    )
    return results


def referential_integrity() -> list[dict]:
    """Every fact's surrogate-key foreign columns must resolve to a real row
    in the dimension they reference. NULL is excluded from the check itself
    (it means "no relationship", a different thing from "an invalid
    reference"). fact_incident.reported_by is intentionally NOT checked here
    -- it's PCC's raw, unresolved staff ID, not a dim_employee FK, since
    PCC's and ADP's employee-ID systems are confirmed disjoint (see
    pipeline/gold.py::build_fact_incident)."""
    results = []
    dim_community_keys = set(_read(GOLD_DIR, "dim_community")["community_key"])
    dim_resident_keys = set(_read(GOLD_DIR, "dim_resident")["resident_key"])
    dim_unit_keys = set(_read(GOLD_DIR, "dim_unit")["unit_key"])
    dim_employee_keys = set(_read(GOLD_DIR, "dim_employee")["employee_key"])
    dim_resident_care_level_keys = set(_read(GOLD_DIR, "dim_resident_care_level")["resident_care_level_key"])

    fk_checks = [
        ("fact_lease", "community_key", dim_community_keys),
        ("fact_labor", "community_key", dim_community_keys),
        ("fact_incident", "community_key", dim_community_keys),
        ("fact_review", "community_key", dim_community_keys),
        ("fact_lead", "community_key", dim_community_keys),
        ("fact_resident_day", "community_key", dim_community_keys),
        ("dim_unit", "community_key", dim_community_keys),
        ("dim_employee", "latest_community_key", dim_community_keys),
        ("dim_resident", "community_key", dim_community_keys),
        ("fact_lease", "resident_key", dim_resident_keys),
        ("fact_incident", "resident_key", dim_resident_keys),
        ("fact_resident_day", "resident_key", dim_resident_keys),
        ("fact_acuity_snapshot", "resident_key", dim_resident_keys),
        ("fact_lease", "unit_key", dim_unit_keys),
        ("fact_labor", "employee_key", dim_employee_keys),
        ("fact_resident_day", "resident_care_level_key", dim_resident_care_level_keys),
    ]
    for table, col, valid_keys in fk_checks:
        df = _read(GOLD_DIR, table)
        if df.empty or col not in df.columns:
            continue
        bad = df[df[col].notna() & ~df[col].isin(valid_keys)]
        results.append(
            _result(f"referential_integrity[{table}.{col}]", bad.empty, {"orphan_rows": len(bad)}, severity="high", action="fix_in_pipeline")
        )
    return results


def primary_key_uniqueness() -> list[dict]:
    """key is a single column name, or a list of column names for a
    composite key. Dimensions are keyed by their surrogate key
    (community_key, resident_key, etc.) -- but a dimension's NATURAL key
    must also be unique (one surrogate key per resident_id, not two), which
    is a distinct thing worth checking on its own: if it weren't, the
    surrogate-key assignment itself would have a bug, silently giving one
    real-world resident two different resident_key values."""
    results = []
    pk_map: dict[str, str | list[str]] = {
        "dim_community": "community_key",
        "dim_resident": "resident_key",
        "dim_resident_care_level": "resident_care_level_key",
        "dim_unit": "unit_key",
        "dim_employee": "employee_key",
        "fact_lease": "lease_id",
        "fact_labor": "shift_id",
        "fact_incident": "incident_id",
        "fact_review": "review_id",
        "fact_lead": "lead_id",
    }
    natural_key_map = {
        "dim_community": "community_id",
        "dim_resident": "resident_id",
        "dim_resident_care_level": ["resident_id", "effective_date"],
        "dim_unit": "unit_id",
        "dim_employee": "employee_id",
    }
    for table, key in pk_map.items():
        df = _read(GOLD_DIR, table)
        if df.empty:
            continue
        dupes = df[df.duplicated(subset=key)]
        key_label = "+".join(key) if isinstance(key, list) else key
        results.append(
            _result(f"primary_key_uniqueness[{table}.{key_label}]", dupes.empty, {"duplicate_count": len(dupes)}, severity="high", action="fix_in_pipeline")
        )

    for table, key in natural_key_map.items():
        df = _read(GOLD_DIR, table)
        if df.empty:
            continue
        dupes = df[df.duplicated(subset=key)]
        key_label = "+".join(key) if isinstance(key, list) else key
        results.append(
            _result(f"natural_key_uniqueness[{table}.{key_label}]", dupes.empty, {"duplicate_count": len(dupes)}, severity="high", action="fix_in_pipeline")
        )
    return results


def run_all_checks(bronze_summary: dict, silver_summary: dict) -> list[dict]:
    results = []
    results += row_count_reconciliation(bronze_summary, silver_summary)
    results += aggregate_reconciliation()
    results.append(no_overlapping_leases())
    results.append(no_negative_or_impossible_occupancy())
    results.append(no_discharge_before_admit())
    results.append(no_future_dated_events())
    results.append(acuity_scores_within_range())
    results += severity_and_rating_within_range()
    results += referential_integrity()
    results += primary_key_uniqueness()
    return results
