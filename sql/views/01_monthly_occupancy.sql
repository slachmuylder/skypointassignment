-- Monthly occupancy rate by community.
-- occupancy_rate = occupied resident-days in the month / (total units * days in month).
-- fact_resident_day is exactly resident-days, so this is a straight aggregation.
WITH resident_days AS (
    SELECT
        community_key,
        date_trunc('month', date) AS month,
        COUNT(*) AS occupied_resident_days
    FROM 'pipeline/data/gold/fact_resident_day.parquet'
    GROUP BY community_key, month
),
unit_counts AS (
    -- dim_unit isn't linked to dim_community by a formal relationship (see
    -- sql/README.md), so this join is by the natural community_id both
    -- still carry as a plain attribute -- the one place that's needed.
    SELECT c.community_key, COUNT(*) AS total_units
    FROM 'pipeline/data/gold/dim_unit.parquet' u
    JOIN 'pipeline/data/gold/dim_community.parquet' c USING (community_id)
    GROUP BY c.community_key
),
days_in_month AS (
    SELECT date_trunc('month', date) AS month, COUNT(*) AS days
    FROM 'pipeline/data/gold/dim_date.parquet'
    WHERE date BETWEEN (SELECT MIN(date) FROM 'pipeline/data/gold/fact_resident_day.parquet')
                    AND (SELECT MAX(date) FROM 'pipeline/data/gold/fact_resident_day.parquet')
    GROUP BY 1
)
SELECT
    c.community_id,
    c.state,
    c.region,
    rd.month,
    rd.occupied_resident_days,
    uc.total_units,
    dim.days AS days_in_month,
    ROUND(100.0 * rd.occupied_resident_days / (uc.total_units * dim.days), 1) AS occupancy_rate_pct
FROM resident_days rd
JOIN unit_counts uc USING (community_key)
JOIN days_in_month dim USING (month)
JOIN 'pipeline/data/gold/dim_community.parquet' c USING (community_key)
ORDER BY c.community_id, rd.month;
