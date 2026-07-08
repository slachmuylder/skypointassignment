-- Labor cost per resident-day, by community, by month.
WITH labor AS (
    SELECT
        community_key,
        date_trunc('month', shift_date) AS month,
        SUM(labor_cost) AS total_labor_cost
    FROM 'pipeline/data/gold/fact_labor.parquet'
    GROUP BY community_key, month
),
resident_days AS (
    SELECT
        community_key,
        date_trunc('month', date) AS month,
        COUNT(*) AS resident_days
    FROM 'pipeline/data/gold/fact_resident_day.parquet'
    GROUP BY community_key, month
)
SELECT
    c.community_id,
    l.month,
    l.total_labor_cost,
    rd.resident_days,
    ROUND(l.total_labor_cost / NULLIF(rd.resident_days, 0), 2) AS labor_cost_per_resident_day
FROM labor l
JOIN resident_days rd USING (community_key, month)
JOIN 'pipeline/data/gold/dim_community.parquet' c USING (community_key)
ORDER BY c.community_id, l.month;
