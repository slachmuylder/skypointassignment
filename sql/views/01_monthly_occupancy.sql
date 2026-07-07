-- Monthly occupancy rate by community.
-- occupancy_rate = occupied resident-days in the month / (total units * days in month).
-- fact_resident_day is exactly resident-days, so this is a straight aggregation.
WITH resident_days AS (
    SELECT
        community_id,
        date_trunc('month', date) AS month,
        COUNT(*) AS occupied_resident_days
    FROM 'pipeline/data/gold/fact_resident_day.parquet'
    GROUP BY 1, 2
),
unit_counts AS (
    SELECT community_id, COUNT(*) AS total_units
    FROM 'pipeline/data/gold/dim_unit.parquet'
    GROUP BY 1
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
JOIN unit_counts uc USING (community_id)
JOIN days_in_month dim USING (month)
JOIN 'pipeline/data/gold/dim_community.parquet' c USING (community_id)
ORDER BY c.community_id, rd.month;
