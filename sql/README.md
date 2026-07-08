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

## Keys: surrogate vs. natural

Every dimension except `dim_date` has a numeric surrogate primary key
(`community_key`, `resident_key`, `care_level_key`, `unit_key`,
`employee_key`) — a plain `BIGINT` identity assigned by
`_assign_surrogate_key()` in `pipeline/gold.py` (sort by natural key, then
enumerate). The source system's natural key (`community_id`, `resident_id`,
etc.) is kept on the dimension as a plain attribute column, not as the key.

Every fact table's foreign keys to a dimension are the dimension's
**surrogate** key, resolved by `pipeline/gold.py`'s `build_fact_*` functions
merging against the relevant `dim_*` DataFrame at build time. A fact keeps
its **own** natural key as its primary key, since that identifies the fact
row itself, not a dimension reference (`fact_lease.lease_id`,
`fact_labor.shift_id`, `fact_incident.incident_id`, `fact_review.review_id`,
`fact_lead.lead_id`). `fact_resident_day` and `fact_acuity_snapshot` have no
natural key of their own — grain is `(resident_key, date)`.

`dim_date` is exempted from the surrogate-key treatment: `date` (an actual
`DATE`, not a smart integer key like `20250115`) is already a natural,
sortable, human-readable key, and every fact column that references it
(`fact_resident_day.date`, `fact_labor.shift_date`, etc.) needs to support
range predicates (`BETWEEN`, `>=`) directly — a surrogate int key would just
add a join for no benefit.

Surrogate keys are **not** persisted across pipeline runs — see
"Assumptions" below.

## Conformed dimensions

- **`dim_community`** conforms across every fact table (`fact_resident_day`, `fact_lease`, `fact_labor`, `fact_incident`, `fact_review`, `fact_lead`) via `community_key` — and also across `dim_unit.community_key` and `dim_employee.latest_community_key`, an "outrigger" dimension-to-dimension reference (a unit or employee's community, not a fact). These use the same surrogate-key convention as any fact FK, checked by `validation.checks.referential_integrity` alongside the fact FKs.
- **`dim_resident`** / **`dim_resident_care_level`** conform across `fact_resident_day`, `fact_lease`, `fact_incident` via `resident_key` / `care_level_key`.
- **`dim_date`** is a role-playing dimension: `fact_resident_day.date`, `fact_labor.shift_date`, `fact_incident.incident_date`, `fact_review.review_date`/`responded_at`, `fact_lease.move_in_date`/`move_out_date`, and `fact_lead.created_date`/`tour_date`/`deposit_date`/`move_in_date` all join to it as separate roles. Facts store the raw `DATE` value rather than a surrogate date key, so Power BI (built separately, see `/powerbi`) should relate each of these columns to its own copy of `dim_date`, renamed per role (e.g. `dim_date (Shift Date)`), rather than a single bidirectional relationship.

## Notes on the required views

- **`06_acuity_increase_alerts.sql`** returns 0 rows against this dataset — verified this is a genuine finding, not a query bug: no resident's acuity score ever increases at all in the 6-month export (every change is flat or downward). The self-join logic itself was checked against a hand-built synthetic series with an obvious jump before confirming the real data has none.
- **`05_incident_rate.sql`** has no `care_level = NULL` resident-day buckets: `dim_resident_care_level` (SCD2) covers every resident-day, including the period before their earliest recorded change event. That period isn't just left unattributed — `build_dim_resident_care_level_scd2` (`pipeline/gold.py`) seeds an opening version running from `admit_date` to the first recorded `change_date`, using that same event's `previous_level` (which is exactly what the resident's care level was for the whole pre-history period). Only a resident with zero recorded change events who is *also* missing a current `care_level` in their latest snapshot could still produce a NULL — not observed in this dataset.

## Anomaly: `fact_incident.reported_by_key` is always NULL

`fact_incident.reported_by` (PCC's staff identifier for who filed the
incident report) never matches any `dim_employee.employee_id` (ADP's staff
identifier): PCC's `reported_by` values are all 4-digit (`E1000`–`E9982`),
ADP's `employee_id` values are all 5-digit (`E10104`–`E99915`) — zero
overlap across all 411 incidents / 68,071 shifts. The two source systems
appear to use disjoint ID spaces for staff. `reported_by_key` is kept as a
column (rather than dropped) so the gap is visible rather than silently
absent, and `validation.checks.referential_integrity` explicitly excludes
it from FK-violation checks since a NULL FK here means "no reconcilable
relationship exists," not "broken join." Flagged as a candidate cross-system
identity question for [the email to Pinewood IT](../communication/email-to-it.md).

## Assumptions

- **Community → state/region mapping is hard-coded** (`pipeline/config.py::COMMUNITY_STATE`). No source file links a community to a state (confirmed by inspecting every CSV's columns), so communities are split evenly across Oregon/Arizona/Texas in `community_id` order (C001–005 → OR, C006–010 → AZ, C011–014 → TX). In a real engagement this would be one of the first questions in the [email to Pinewood IT](../communication/email-to-it.md).
- Records with a `community_id` outside `C001`–`C014` (5 phantom IDs found in `yardi_units`) are quarantined in Silver and never reach Gold — see the pipeline run log for counts.
- **Surrogate keys are assigned fresh on every run**, not persisted across runs in a lookup/crosswalk table. Since Gold is fully rebuilt from Silver on every `pipeline.run` invocation (Silver dedupes across full history, not incrementally — see `/pipeline`), a given natural key gets a stable surrogate key *within* one run's output, but the same natural key's integer value can shift between runs if the underlying set of natural keys changes (e.g. a new resident is added, shifting the sort-order enumeration). This is fine for this Parquet-file-per-run deliverable, but a production warehouse loading Gold incrementally into a persistent table would need a durable key-assignment table (e.g. an identity column in the target DB, or a maintained natural-key → surrogate-key crosswalk) so keys don't change out from under existing fact rows or BI reports between loads.
