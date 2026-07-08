-- Incident rate per 100 resident-days, by community and by care level.
WITH incidents AS (
    SELECT rd.community_id,
      rd.care_level,
      COUNT(*) AS incident_count
    FROM 'pipeline/data/gold/fact_incident.parquet' i
    JOIN 'pipeline/data/gold/fact_resident_day.parquet' rd
        ON rd.resident_id = i.resident_id AND rd.date = i.incident_date
    GROUP BY rd.community_id, rd.care_level
),
resident_days AS (
    SELECT community_id,
    care_level,
    COUNT(*) AS resident_days
    FROM 'pipeline/data/gold/fact_resident_day.parquet'
    GROUP BY community_id, care_level
)
SELECT
    rd.community_id,
    rd.care_level,
    COALESCE(i.incident_count, 0) AS incident_count,
    rd.resident_days,
    ROUND(100.0 * COALESCE(i.incident_count, 0) / rd.resident_days, 2) AS incidents_per_100_resident_days
FROM resident_days rd
LEFT JOIN incidents i USING (community_id, care_level)
ORDER BY rd.community_id, rd.care_level;
