-- Candidate list for a care-level review: residents whose acuity score
-- increased by 2 or more points within any 90-day window.
-- Self-joins fact_acuity_snapshot (the periodic-snapshot fact holding acuity
-- history -- dim_resident only keeps the current value) against itself,
-- looking for any earlier/later pair of readings for the same resident that
-- qualifies.
WITH pairs AS (
    SELECT
        a.resident_id,
        a.snapshot_date AS from_date,
        a.acuity_score AS from_score,
        b.snapshot_date AS to_date,
        b.acuity_score AS to_score,
        b.acuity_score - a.acuity_score AS score_increase
    FROM 'pipeline/data/gold/fact_acuity_snapshot.parquet' a
    JOIN 'pipeline/data/gold/fact_acuity_snapshot.parquet' b
        ON a.resident_id = b.resident_id
        AND b.snapshot_date > a.snapshot_date
        AND b.snapshot_date <= a.snapshot_date + INTERVAL 90 DAY
    WHERE b.acuity_score - a.acuity_score >= 2
)
SELECT
    p.resident_id,
    r.community_id,
    r.first_name,
    r.last_name,
    p.from_date,
    p.from_score,
    p.to_date,
    p.to_score,
    p.score_increase
FROM pairs p
JOIN 'pipeline/data/gold/dim_resident.parquet' r USING (resident_id)
-- Keep only the single largest-jump window per resident so each candidate
-- appears once in the review list.
QUALIFY ROW_NUMBER() OVER (PARTITION BY p.resident_id ORDER BY p.score_increase DESC, p.to_date) = 1
ORDER BY p.score_increase DESC, p.resident_id;
