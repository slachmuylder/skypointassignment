# Pipeline Run Report

Run at: 2026-07-07T19:19:43.180649+00:00 UTC  
Duration: 1.35s

## Bronze (incremental ingestion)

| Table | New files | Revised files (content changed) | Skipped (unchanged) | Rows ingested |
|---|---|---|---|---|
| pcc_residents | 0 | 0 | 6 | 0 |
| pcc_incidents | 0 | 0 | 6 | 0 |
| pcc_care_history | 0 | 0 | 6 | 0 |
| yardi_units | 0 | 0 | 6 | 0 |
| yardi_leases | 0 | 0 | 6 | 0 |
| adp_shifts | 0 | 0 | 6 | 0 |
| gbp_reviews | 0 | 0 | 6 | 0 |
| hubspot_leads | 0 | 0 | 6 | 0 |

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

| Table | Reason | Rows affected | Severity | Action |
|---|---|---|---|---|
| pcc_residents | acuity_score_out_of_range | 3 | medium | quarantine |
| pcc_residents | future_dated_discharge | 2 | medium | quarantine |
| yardi_units | unknown_community_id | 30 | medium | quarantine |
| hubspot_leads | duplicate_lead_id_conflicting_data | 2 | medium | quarantine |
