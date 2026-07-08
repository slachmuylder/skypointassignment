# Gold layer — star schema

All tables are Parquet files under `pipeline/data/gold/`, built by `pipeline/gold.py`
from the Silver layer (see `/pipeline`). This directory holds the SQL
deliverables required by Part 2: DDL describing that schema, and the 6
required analytical views/queries, all runnable directly against the Parquet
files with DuckDB (no separate database server needed):

```bash
source .venv/bin/activate
python -c "import duckdb; print(duckdb.sql(open('sql/views/01_monthly_occupancy.sql').read()).df())"
```

(no separate DuckDB CLI install needed -- the `duckdb` Python package in `requirements.txt` is a full query engine on its own).

## Grain of each table

| Table | Grain |
|---|---|
| `dim_community` | one row per community (14) |
| `dim_resident` | one row per resident — current (Type 1) attributes |
| `dim_resident_care_level` | **SCD Type 2** — one row per resident per care-level-in-effect period |
| `dim_unit` | one row per unit — latest known snapshot |
| `dim_employee` | one row per employee — latest known role/community |
| `dim_date` | one row per calendar day, 2024-01-01 through 2025-12-31 |
| `fact_resident_day` | one row per resident per calendar day they were an active resident (admit_date ≤ day ≤ discharge_date, or ≤ data as-of date if still resident) |
| `fact_acuity_snapshot` | periodic snapshot — one row per resident per distinct acuity reading (dated to the month that reading first appeared), built from Silver's cleaned-but-not-deduped `pcc_residents_history` rather than the canonical deduped table, so a fast transition isn't measured against a dedup-collapsed "last confirmed" date |
| `fact_lease` | one row per lease |
| `fact_labor` | one row per shift worked |
| `fact_incident` | one row per incident |
| `fact_review` | one row per review |
| `fact_lead` | one row per sales lead |

`fact_resident_day` is the deliberate design choice here: rather than trying
to reverse-engineer occupancy from monthly snapshots, every resident's
admit→discharge window is exploded into one row per day (with their
SCD2 care level as of that day). Occupancy, labor-cost-per-resident-day, and
incident-rate-per-100-resident-days are all just aggregations over this one
table — it's the resident-days denominator the assessment asks for in three
different views.

## Conformed dimensions

- **`dim_community`** conforms across every fact table (`fact_resident_day`, `fact_lease`, `fact_labor`, `fact_incident`, `fact_review`, `fact_lead`) via `community_id`.
- **`dim_resident`** / **`dim_resident_care_level`** conform across `fact_resident_day`, `fact_lease`, `fact_incident` via `resident_id`.
- **`dim_date`** is a role-playing dimension: `fact_resident_day.date`, `fact_labor.shift_date`, `fact_incident.incident_date`, `fact_review.review_date`/`responded_at`, `fact_lease.move_in_date`/`move_out_date`, and `fact_lead.created_date`/`tour_date`/`deposit_date`/`move_in_date` all join to it as separate roles. Facts store the raw `DATE` value rather than a surrogate date key, so Power BI (built separately, see `/powerbi`) should relate each of these columns to its own copy of `dim_date`, renamed per role (e.g. `dim_date (Shift Date)`), rather than a single bidirectional relationship.

## Notes on the required views

- **`06_acuity_increase_alerts.sql`** returns 0 rows against this dataset — verified this is a genuine finding, not a query bug: no resident's acuity score ever increases at all in the 6-month export (every change is flat or downward). The self-join logic itself was checked against a hand-built synthetic series with an obvious jump before confirming the real data has none.
- **`05_incident_rate.sql`** includes some `care_level = NULL` resident-day buckets. This is a genuine data gap, not a defect: `dim_resident_care_level` (SCD2) is only complete back to each resident's earliest recorded change event *within the 6-month export window* — a resident admitted years before the window with no in-window care-level change has no recorded starting state, so those pre-first-event resident-days are correctly left unattributed rather than guessed at.

## Assumptions

- **Community → state/region mapping is hard-coded** (`pipeline/config.py::COMMUNITY_STATE`). No source file links a community to a state (confirmed by inspecting every CSV's columns), so communities are split evenly across Oregon/Arizona/Texas in `community_id` order (C001–005 → OR, C006–010 → AZ, C011–014 → TX). In a real engagement this would be one of the first questions in the [email to Pinewood IT](../communication/email-to-it.md).
- Records with a `community_id` outside `C001`–`C014` (5 phantom IDs found in `yardi_units`) are quarantined in Silver and never reach Gold — see the pipeline run log for counts.
