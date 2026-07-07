-- Top 3 move-out reasons by community, trailing 12 months, as a percentage
-- of that community's total move-outs in the window.
WITH as_of AS (
    SELECT MAX(move_out_date) AS max_move_out FROM 'pipeline/data/gold/fact_lease.parquet'
),
moveouts AS (
    SELECT community_id, move_out_reason
    FROM 'pipeline/data/gold/fact_lease.parquet', as_of
    WHERE move_out_date IS NOT NULL
      AND move_out_date >= as_of.max_move_out - INTERVAL 12 MONTH
),
counted AS (
    SELECT
        community_id,
        move_out_reason,
        COUNT(*) AS reason_count,
        SUM(COUNT(*)) OVER (PARTITION BY community_id) AS total_moveouts,
        RANK() OVER (PARTITION BY community_id ORDER BY COUNT(*) DESC) AS reason_rank
    FROM moveouts
    GROUP BY community_id, move_out_reason
)
SELECT
    community_id,
    move_out_reason,
    reason_count,
    total_moveouts,
    ROUND(100.0 * reason_count / total_moveouts, 1) AS pct_of_moveouts
FROM counted
WHERE reason_rank <= 3
ORDER BY community_id, reason_rank;
