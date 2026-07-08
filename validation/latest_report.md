# Pinewood Data Refresh — Validation Summary

Generated 2026-07-08T18:05:24.699170+00:00 UTC · based on the pipeline run at 2026-07-08T18:05:22.771073+00:00 UTC

### ✅ Safe to approve — all 49 accuracy and completeness checks passed.

**What was checked:**

- Row count reconciliation from the raw source (Bronze layer) to the final output (Gold layer).
- Total revenue, total shift hours, and total resident-days match exactly between the raw exports and what's on the dashboard.
- Business rule checks:No overlapping leases for the same resident, no negative occupancy, no discharge before admits, no future dataed events, acuity scores within range.Every reference between tables resolves correctly (e.g. every incident, lease, and shift points to a real resident/community that actually exists).

**10 data-quality issues found in this month's source exports, handled automatically -- none require action from you:**

- 3 residents had an invalid acuity score in PCC (outside the 1-10 scale) -- the score was set aside pending correction; the rest of the resident's data is unaffected. (source: pcc_residents_2025_06.csv)
- 2 residents had an impossible future discharge date in PCC -- set aside pending correction. (source: pcc_residents_2025_06.csv)
- 5 records in Yardi were tagged to a community that doesn't exist in our 14-community list -- excluded from reporting. (source: yardi_units_2025_01.csv)
- 5 records in Yardi were tagged to a community that doesn't exist in our 14-community list -- excluded from reporting. (source: yardi_units_2025_02.csv)
- 5 records in Yardi were tagged to a community that doesn't exist in our 14-community list -- excluded from reporting. (source: yardi_units_2025_03.csv)
- 5 records in Yardi were tagged to a community that doesn't exist in our 14-community list -- excluded from reporting. (source: yardi_units_2025_04.csv)
- 5 records in Yardi were tagged to a community that doesn't exist in our 14-community list -- excluded from reporting. (source: yardi_units_2025_05.csv)
- 5 records in Yardi were tagged to a community that doesn't exist in our 14-community list -- excluded from reporting. (source: yardi_units_2025_06.csv)
- 1 lead in HubSpot shared a duplicate ID with conflicting data -- set aside pending manual review with HubSpot's data team. (source: hubspot_leads_2025_03.csv)
- 1 lead in HubSpot shared a duplicate ID with conflicting data -- set aside pending manual review with HubSpot's data team. (source: hubspot_leads_2025_06.csv)

---

## Full technical detail (for engineering / audit review)

| Check | Status | Severity | Recommended action | Detail |
|---|---|---|---|---|
| row_count_reconciliation[pcc_residents] | PASS | n/a | n/a | `{"rows_in": 4152, "rows_dropped": 3326, "expected_out": 826, "actual_out": 826}` |
| row_count_reconciliation[pcc_incidents] | PASS | n/a | n/a | `{"rows_in": 411, "rows_dropped": 0, "expected_out": 411, "actual_out": 411}` |
| row_count_reconciliation[pcc_care_history] | PASS | n/a | n/a | `{"rows_in": 303, "rows_dropped": 0, "expected_out": 303, "actual_out": 303}` |
| row_count_reconciliation[yardi_units] | PASS | n/a | n/a | `{"rows_in": 5490, "rows_dropped": 30, "expected_out": 5460, "actual_out": 5460}` |
| row_count_reconciliation[yardi_leases] | PASS | n/a | n/a | `{"rows_in": 346, "rows_dropped": 44, "expected_out": 302, "actual_out": 302}` |
| row_count_reconciliation[adp_shifts] | PASS | n/a | n/a | `{"rows_in": 68071, "rows_dropped": 0, "expected_out": 68071, "actual_out": 68071}` |
| row_count_reconciliation[gbp_reviews] | PASS | n/a | n/a | `{"rows_in": 424, "rows_dropped": 0, "expected_out": 424, "actual_out": 424}` |
| row_count_reconciliation[hubspot_leads] | PASS | n/a | n/a | `{"rows_in": 830, "rows_dropped": 2, "expected_out": 828, "actual_out": 828}` |
| aggregate_reconciliation[total_lease_revenue] | PASS | n/a | n/a | `{"silver_total": 1753467.0, "gold_total": 1753467.0}` |
| aggregate_reconciliation[total_shift_hours] | PASS | n/a | n/a | `{"silver_total": 565188.0, "gold_total": 565188.0}` |
| aggregate_reconciliation[total_resident_days] | PASS | n/a | n/a | `{"expected_from_dim_resident": 543015, "actual_in_fact_resident_day": 543015}` |
| no_overlapping_leases_per_resident | PASS | n/a | n/a | `{"residents_with_overlap": []}` |
| no_negative_or_over_100_occupancy | PASS | n/a | n/a | `{"violating_rows": []}` |
| no_discharge_before_admit | PASS | n/a | n/a | `{"resident_ids": []}` |
| no_future_dated_events | PASS | n/a | n/a | `{"violations_by_column": {}, "as_of_date": "2025-06-30"}` |
| acuity_scores_within_range | PASS | n/a | n/a | `{"resident_ids": []}` |
| incident_severity_within_1_5 | PASS | n/a | n/a | `{"incident_ids": []}` |
| review_rating_within_1_5 | PASS | n/a | n/a | `{"review_ids": []}` |
| referential_integrity[fact_lease.community_key] | PASS | n/a | n/a | `{"orphan_rows": 0}` |
| referential_integrity[fact_labor.community_key] | PASS | n/a | n/a | `{"orphan_rows": 0}` |
| referential_integrity[fact_incident.community_key] | PASS | n/a | n/a | `{"orphan_rows": 0}` |
| referential_integrity[fact_review.community_key] | PASS | n/a | n/a | `{"orphan_rows": 0}` |
| referential_integrity[fact_lead.community_key] | PASS | n/a | n/a | `{"orphan_rows": 0}` |
| referential_integrity[fact_resident_day.community_key] | PASS | n/a | n/a | `{"orphan_rows": 0}` |
| referential_integrity[dim_unit.community_key] | PASS | n/a | n/a | `{"orphan_rows": 0}` |
| referential_integrity[dim_employee.latest_community_key] | PASS | n/a | n/a | `{"orphan_rows": 0}` |
| referential_integrity[fact_lease.resident_key] | PASS | n/a | n/a | `{"orphan_rows": 0}` |
| referential_integrity[fact_incident.resident_key] | PASS | n/a | n/a | `{"orphan_rows": 0}` |
| referential_integrity[fact_resident_day.resident_key] | PASS | n/a | n/a | `{"orphan_rows": 0}` |
| referential_integrity[fact_acuity_snapshot.resident_key] | PASS | n/a | n/a | `{"orphan_rows": 0}` |
| referential_integrity[fact_lease.unit_key] | PASS | n/a | n/a | `{"orphan_rows": 0}` |
| referential_integrity[fact_labor.employee_key] | PASS | n/a | n/a | `{"orphan_rows": 0}` |
| referential_integrity[fact_incident.reported_by_key] | PASS | n/a | n/a | `{"orphan_rows": 0}` |
| referential_integrity[fact_resident_day.resident_care_level_key] | PASS | n/a | n/a | `{"orphan_rows": 0}` |
| primary_key_uniqueness[dim_community.community_key] | PASS | n/a | n/a | `{"duplicate_count": 0}` |
| primary_key_uniqueness[dim_resident.resident_key] | PASS | n/a | n/a | `{"duplicate_count": 0}` |
| primary_key_uniqueness[dim_resident_care_level.resident_care_level_key] | PASS | n/a | n/a | `{"duplicate_count": 0}` |
| primary_key_uniqueness[dim_unit.unit_key] | PASS | n/a | n/a | `{"duplicate_count": 0}` |
| primary_key_uniqueness[dim_employee.employee_key] | PASS | n/a | n/a | `{"duplicate_count": 0}` |
| primary_key_uniqueness[fact_lease.lease_id] | PASS | n/a | n/a | `{"duplicate_count": 0}` |
| primary_key_uniqueness[fact_labor.shift_id] | PASS | n/a | n/a | `{"duplicate_count": 0}` |
| primary_key_uniqueness[fact_incident.incident_id] | PASS | n/a | n/a | `{"duplicate_count": 0}` |
| primary_key_uniqueness[fact_review.review_id] | PASS | n/a | n/a | `{"duplicate_count": 0}` |
| primary_key_uniqueness[fact_lead.lead_id] | PASS | n/a | n/a | `{"duplicate_count": 0}` |
| natural_key_uniqueness[dim_community.community_id] | PASS | n/a | n/a | `{"duplicate_count": 0}` |
| natural_key_uniqueness[dim_resident.resident_id] | PASS | n/a | n/a | `{"duplicate_count": 0}` |
| natural_key_uniqueness[dim_resident_care_level.resident_id+effective_date] | PASS | n/a | n/a | `{"duplicate_count": 0}` |
| natural_key_uniqueness[dim_unit.unit_id] | PASS | n/a | n/a | `{"duplicate_count": 0}` |
| natural_key_uniqueness[dim_employee.employee_id] | PASS | n/a | n/a | `{"duplicate_count": 0}` |

### Anomalies detected during ingestion (raw log)

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
