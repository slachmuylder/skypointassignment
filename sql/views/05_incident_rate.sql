-- Incident rate per 100 resident-days, by community and by care level.
--
-- Resolves resident_care_level_key to the actual care_level TEXT (IL/AL/MC) before
-- grouping, rather than grouping by resident_care_level_key directly. This matters:
-- dim_resident_care_level's grain is resident x time-period, so two
-- different residents who are both currently AL have two DIFFERENT
-- resident_care_level_key values (one per SCD2 version) even though they share the
-- same category -- grouping by the key itself would fragment "AL" into as
-- many groups as there are residents/versions, instead of one AL bucket.
WITH resident_day_with_level AS (
    SELECT rd.community_key, rd.resident_key, rd.date, cl.care_level
    FROM 'pipeline/data/gold/fact_resident_day.parquet' rd
    -- resident_care_level_key can be NULL (documented gap, see sql/README.md), in
    -- which case this LEFT JOIN correctly leaves care_level NULL too rather
    -- than dropping the row.
    LEFT JOIN 'pipeline/data/gold/dim_resident_care_level.parquet' cl USING (resident_care_level_key)
),
incidents AS (
    SELECT rdw.community_key, rdw.care_level, COUNT(*) AS incident_count
    FROM 'pipeline/data/gold/fact_incident.parquet' i
    JOIN resident_day_with_level rdw
        ON rdw.resident_key = i.resident_key AND rdw.date = i.incident_date
    GROUP BY rdw.community_key, rdw.care_level
),
resident_days AS (
    SELECT community_key, care_level, COUNT(*) AS resident_days
    FROM resident_day_with_level
    GROUP BY community_key, care_level
)
SELECT
    c.community_id,
    rd.care_level,
    COALESCE(i.incident_count, 0) AS incident_count,
    rd.resident_days,
    ROUND(100.0 * COALESCE(i.incident_count, 0) / rd.resident_days, 2) AS incidents_per_100_resident_days
FROM resident_days rd
LEFT JOIN incidents i USING (community_key, care_level)
JOIN 'pipeline/data/gold/dim_community.parquet' c USING (community_key)
ORDER BY c.community_id, rd.care_level;
