-- Top 3 move-out reasons by community, trailing 12 months, as a percentage
-- of that community's total move-outs in the window.
WITH as_of AS (
    SELECT MAX(move_out_date) AS max_move_out
    FROM 'pipeline/data/gold/fact_lease.parquet'
),
counted AS (
    SELECT
        community_key,
        move_out_reason,
        COUNT(*) AS reason_count,
        SUM(COUNT(*)) OVER (PARTITION BY community_key) AS total_moveouts,
        RANK() OVER (PARTITION BY community_key ORDER BY COUNT(*) DESC) AS reason_rank
    FROM 'pipeline/data/gold/fact_lease.parquet', as_of
    WHERE move_out_date IS NOT NULL
      AND move_out_date >= as_of.max_move_out - INTERVAL 12 MONTH
    GROUP BY community_key, move_out_reason
)
SELECT
    c.community_id,
    counted.move_out_reason,
    counted.reason_count,
    counted.total_moveouts,
    ROUND(100.0 * counted.reason_count / counted.total_moveouts, 1) AS pct_of_moveouts
FROM counted
JOIN 'pipeline/data/gold/dim_community.parquet' c USING (community_key)
WHERE reason_rank <= 3
ORDER BY c.community_id, reason_rank;
