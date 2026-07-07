"""Query functions backing each endpoint. All read directly from the Gold
Parquet files with DuckDB. Every function takes `community_ids` (the
server-resolved, already-authorized scope from api/scope.py) and applies it
as a SQL filter -- callers never pass raw client input straight into a query.
"""
import duckdb

from pipeline.columns import COMMUNITY_ID
from pipeline.config import GOLD_DIR


def _community_filter(community_ids: list[str] | None, alias: str = "") -> tuple[str, list]:
    col = f"{alias}.{COMMUNITY_ID}" if alias else COMMUNITY_ID
    if community_ids is None:
        return "TRUE", []
    placeholders = ",".join(["?"] * len(community_ids))
    return f"{col} IN ({placeholders})", list(community_ids)


def occupancy(community_ids: list[str] | None, start: str | None, end: str | None):
    where_community, params = _community_filter(community_ids, "rd")
    date_clauses = []
    if start:
        date_clauses.append("d.date >= ?")
        params.append(start)
    if end:
        date_clauses.append("d.date <= ?")
        params.append(end)
    where_date = " AND ".join(date_clauses) if date_clauses else "TRUE"

    sql = f"""
        WITH resident_days AS (
            SELECT rd.community_id, date_trunc('month', rd.date) AS month, COUNT(*) AS occupied_resident_days
            FROM '{GOLD_DIR}/fact_resident_day.parquet' rd
            JOIN '{GOLD_DIR}/dim_date.parquet' d ON d.date = rd.date
            WHERE {where_community} AND {where_date}
            GROUP BY 1, 2
        ),
        unit_counts AS (
            SELECT community_id, COUNT(*) AS total_units
            FROM '{GOLD_DIR}/dim_unit.parquet'
            GROUP BY 1
        ),
        days_in_month AS (
            SELECT date_trunc('month', date) AS month, COUNT(*) AS days
            FROM '{GOLD_DIR}/dim_date.parquet'
            GROUP BY 1
        )
        SELECT
            rd.community_id, rd.month, rd.occupied_resident_days, uc.total_units, dim.days AS days_in_month,
            ROUND(100.0 * rd.occupied_resident_days / (uc.total_units * dim.days), 1) AS occupancy_rate_pct
        FROM resident_days rd
        JOIN unit_counts uc USING (community_id)
        JOIN days_in_month dim USING (month)
        ORDER BY rd.community_id, rd.month
    """
    return duckdb.sql(sql, params=params).df()


def moveout_reasons(community_ids: list[str] | None, period: str | None):
    """`period` is the trailing-12-months reference date; defaults to the
    latest move_out_date present in fact_lease."""
    where_community, community_params = _community_filter(community_ids)
    params = [period] + community_params

    sql = f"""
        WITH as_of AS (
            SELECT COALESCE(?, MAX(move_out_date)) AS ref_date FROM '{GOLD_DIR}/fact_lease.parquet'
        ),
        moveouts AS (
            SELECT community_id, move_out_reason
            FROM '{GOLD_DIR}/fact_lease.parquet', as_of
            WHERE {where_community}
              AND move_out_date IS NOT NULL
              AND move_out_date BETWEEN as_of.ref_date - INTERVAL 12 MONTH AND as_of.ref_date
        )
        SELECT
            community_id, move_out_reason, COUNT(*) AS reason_count,
            ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (PARTITION BY community_id), 1) AS pct_of_moveouts
        FROM moveouts
        GROUP BY community_id, move_out_reason
        ORDER BY community_id, reason_count DESC
    """
    return duckdb.sql(sql, params=params).df()


def incidents_summary(community_ids: list[str] | None, start: str | None, end: str | None):
    where_community, params = _community_filter(community_ids, "rd")
    date_clauses = []
    if start:
        date_clauses.append("rd.date >= ?")
        params.append(start)
    if end:
        date_clauses.append("rd.date <= ?")
        params.append(end)
    where_date = " AND ".join(date_clauses) if date_clauses else "TRUE"

    sql = f"""
        WITH resident_days AS (
            SELECT rd.community_id, COUNT(*) AS resident_days
            FROM '{GOLD_DIR}/fact_resident_day.parquet' rd
            WHERE {where_community} AND {where_date}
            GROUP BY 1
        ),
        incidents AS (
            SELECT rd.community_id, COUNT(*) AS incident_count
            FROM '{GOLD_DIR}/fact_incident.parquet' i
            JOIN '{GOLD_DIR}/fact_resident_day.parquet' rd
                ON rd.resident_id = i.resident_id AND rd.date = i.incident_date
            WHERE {where_community} AND {where_date}
            GROUP BY 1
        )
        SELECT
            rd.community_id, COALESCE(i.incident_count, 0) AS incident_count, rd.resident_days,
            ROUND(100.0 * COALESCE(i.incident_count, 0) / rd.resident_days, 2) AS incidents_per_100_resident_days
        FROM resident_days rd
        LEFT JOIN incidents i USING (community_id)
        ORDER BY rd.community_id
    """
    # where_community/where_date are reused for both CTEs, so params need to repeat
    return duckdb.sql(sql, params=params + params).df()


def labor_cost(community_ids: list[str] | None, start: str | None, end: str | None):
    where_labor, params_l = _community_filter(community_ids, "")
    date_clauses = []
    if start:
        date_clauses.append("shift_date >= ?")
        params_l.append(start)
    if end:
        date_clauses.append("shift_date <= ?")
        params_l.append(end)
    where_labor = where_labor + (" AND " + " AND ".join(date_clauses) if date_clauses else "")

    where_rd, params_rd = _community_filter(community_ids, "")
    date_clauses_rd = []
    if start:
        date_clauses_rd.append("date >= ?")
        params_rd.append(start)
    if end:
        date_clauses_rd.append("date <= ?")
        params_rd.append(end)
    where_rd = where_rd + (" AND " + " AND ".join(date_clauses_rd) if date_clauses_rd else "")

    sql = f"""
        WITH labor AS (
            SELECT community_id, date_trunc('month', shift_date) AS month, SUM(labor_cost) AS total_labor_cost
            FROM '{GOLD_DIR}/fact_labor.parquet'
            WHERE {where_labor}
            GROUP BY 1, 2
        ),
        resident_days AS (
            SELECT community_id, date_trunc('month', date) AS month, COUNT(*) AS resident_days
            FROM '{GOLD_DIR}/fact_resident_day.parquet'
            WHERE {where_rd}
            GROUP BY 1, 2
        )
        SELECT
            l.community_id, l.month, l.total_labor_cost, rd.resident_days,
            ROUND(l.total_labor_cost / NULLIF(rd.resident_days, 0), 2) AS labor_cost_per_resident_day
        FROM labor l
        JOIN resident_days rd USING (community_id, month)
        ORDER BY l.community_id, l.month
    """
    return duckdb.sql(sql, params=params_l + params_rd).df()


def reviews_summary(community_ids: list[str] | None, start: str | None, end: str | None):
    where_community, params = _community_filter(community_ids)
    date_clauses = []
    if start:
        date_clauses.append("review_date >= ?")
        params.append(start)
    if end:
        date_clauses.append("review_date <= ?")
        params.append(end)
    where_date = " AND ".join(date_clauses) if date_clauses else "TRUE"

    sql = f"""
        SELECT
            community_id,
            COUNT(*) AS review_count,
            ROUND(AVG(rating), 2) AS avg_rating,
            ROUND(100.0 * SUM(CASE WHEN has_response THEN 1 ELSE 0 END) / COUNT(*), 1) AS response_rate_pct
        FROM '{GOLD_DIR}/fact_review.parquet'
        WHERE {where_community} AND {where_date}
        GROUP BY community_id
        ORDER BY community_id
    """
    return duckdb.sql(sql, params=params).df()
