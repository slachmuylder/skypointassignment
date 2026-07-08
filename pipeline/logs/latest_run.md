# Pipeline Run Report

Run at: 2026-07-08T02:42:54.366604+00:00 UTC  
Duration: 1.67s

## Bronze (incremental ingestion)

| Table | New files | Revised files (content changed) | Skipped (unchanged) | Rows ingested |
|---|---|---|---|---|
| pcc_residents | 6 | 0 | 0 | 4152 |
| pcc_incidents | 6 | 0 | 0 | 411 |
| pcc_care_history | 6 | 0 | 0 | 303 |
| yardi_units | 6 | 0 | 0 | 5490 |
| yardi_leases | 6 | 0 | 0 | 346 |
| adp_shifts | 6 | 0 | 0 | 68071 |
| gbp_reviews | 6 | 0 | 0 | 424 |
| hubspot_leads | 6 | 0 | 0 | 830 |

## Silver (cleaning)

| Table | Rows in | Rows out | Rows dropped | Rows flagged |
|---|---|---|---|---|
| pcc_residents | 4152 | 826 | 3326 | 5 |
| pcc_incidents | 411 | 411 | 0 | 0 |
| pcc_care_history | 303 | 303 | 0 | 0 |
| yardi_units | 5490 | 5460 | 30 | 30 |
| yardi_leases | 346 | 302 | 44 | 0 |
| adp_shifts | 68071 | 68071 | 0 | 0 |
| gbp_reviews | 424 | 424 | 0 | 0 |
| hubspot_leads | 830 | 828 | 2 | 2 |

## Gold (mart tables)

| Table | Rows |
|---|---|
| dim_community | 14 |
| dim_resident | 823 |
| dim_resident_care_level | 841 |
| dim_unit | 910 |
| dim_employee | 617 |
| dim_date | 181 |
| fact_resident_day | 543015 |
| fact_acuity_snapshot | 823 |
| fact_lease | 302 |
| fact_labor | 68071 |
| fact_incident | 411 |
| fact_review | 424 |
| fact_lead | 828 |

## Anomalies detected this run

| Table | Reason | Source file | Rows affected | Severity | Action |
|---|---|---|---|---|---|
| pcc_residents | acuity_score_out_of_range | pcc_residents_2025_06.csv | 3 | medium | quarantine |
| pcc_residents | future_dated_discharge | pcc_residents_2025_06.csv | 2 | medium | quarantine |
| yardi_units | unknown_community_id | yardi_units_2025_01.csv | 5 | medium | quarantine |
| yardi_units | unknown_community_id | yardi_units_2025_02.csv | 5 | medium | quarantine |
| yardi_units | unknown_community_id | yardi_units_2025_03.csv | 5 | medium | quarantine |
| yardi_units | unknown_community_id | yardi_units_2025_04.csv | 5 | medium | quarantine |
| yardi_units | unknown_community_id | yardi_units_2025_05.csv | 5 | medium | quarantine |
| yardi_units | unknown_community_id | yardi_units_2025_06.csv | 5 | medium | quarantine |
| hubspot_leads | duplicate_lead_id_conflicting_data | hubspot_leads_2025_03.csv | 1 | medium | quarantine |
| hubspot_leads | duplicate_lead_id_conflicting_data | hubspot_leads_2025_06.csv | 1 | medium | quarantine |
