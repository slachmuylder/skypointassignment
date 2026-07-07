# Pinewood Data Validation Report

Generated: 2026-07-07T20:13:25.303215+00:00 UTC  
Based on pipeline run: 2026-07-07T20:13:23.135088+00:00 UTC

**36/36 checks passed.**

No failing checks this run. Safe to approve this refresh.

## Checks

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
| referential_integrity[fact_lease.community_id] | PASS | n/a | n/a | `{"orphan_rows": 0}` |
| referential_integrity[fact_labor.community_id] | PASS | n/a | n/a | `{"orphan_rows": 0}` |
| referential_integrity[fact_incident.community_id] | PASS | n/a | n/a | `{"orphan_rows": 0}` |
| referential_integrity[fact_review.community_id] | PASS | n/a | n/a | `{"orphan_rows": 0}` |
| referential_integrity[fact_lead.community_id] | PASS | n/a | n/a | `{"orphan_rows": 0}` |
| referential_integrity[fact_resident_day.community_id] | PASS | n/a | n/a | `{"orphan_rows": 0}` |
| referential_integrity[fact_lease.resident_id] | PASS | n/a | n/a | `{"orphan_rows": 0}` |
| referential_integrity[fact_incident.resident_id] | PASS | n/a | n/a | `{"orphan_rows": 0}` |
| referential_integrity[fact_resident_day.resident_id] | PASS | n/a | n/a | `{"orphan_rows": 0}` |
| primary_key_uniqueness[dim_community.community_id] | PASS | n/a | n/a | `{"duplicate_count": 0}` |
| primary_key_uniqueness[dim_resident.resident_id] | PASS | n/a | n/a | `{"duplicate_count": 0}` |
| primary_key_uniqueness[dim_unit.unit_id] | PASS | n/a | n/a | `{"duplicate_count": 0}` |
| primary_key_uniqueness[dim_employee.employee_id] | PASS | n/a | n/a | `{"duplicate_count": 0}` |
| primary_key_uniqueness[fact_lease.lease_id] | PASS | n/a | n/a | `{"duplicate_count": 0}` |
| primary_key_uniqueness[fact_labor.shift_id] | PASS | n/a | n/a | `{"duplicate_count": 0}` |
| primary_key_uniqueness[fact_incident.incident_id] | PASS | n/a | n/a | `{"duplicate_count": 0}` |
| primary_key_uniqueness[fact_review.review_id] | PASS | n/a | n/a | `{"duplicate_count": 0}` |
| primary_key_uniqueness[fact_lead.lead_id] | PASS | n/a | n/a | `{"duplicate_count": 0}` |

## Anomalies detected during ingestion (from the pipeline run log)

| Table | Reason | Rows affected | Severity | Action |
|---|---|---|---|---|
| pcc_residents | acuity_score_out_of_range | 3 | medium | quarantine |
| pcc_residents | future_dated_discharge | 2 | medium | quarantine |
| yardi_units | unknown_community_id | 30 | medium | quarantine |
| hubspot_leads | duplicate_lead_id_conflicting_data | 2 | medium | quarantine |
