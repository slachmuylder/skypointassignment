-- Average length of stay (days), by care level, for residents discharged in
-- the trailing 12 months. This dataset only spans 6 months, so "trailing 12
-- months" ends up covering every discharge in the data -- the window is
-- computed relative to the latest date actually present, not wall-clock
-- today, so this stays correct if more months are added later.
WITH as_of AS (
    SELECT MAX(discharge_date) AS max_discharge 
    FROM 'pipeline/data/gold/dim_resident.parquet'
)
SELECT
    care_level,
    COUNT(*) AS discharged_residents,
    ROUND(AVG(date_diff('day', admit_date, discharge_date)), 1) AS avg_length_of_stay_days
FROM 'pipeline/data/gold/dim_resident.parquet', as_of
WHERE discharge_date IS NOT NULL
  AND discharge_date >= as_of.max_discharge - INTERVAL 12 MONTH
GROUP BY care_level
ORDER BY care_level;
