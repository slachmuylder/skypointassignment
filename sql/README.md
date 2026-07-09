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


## Keys: surrogate vs. natural

Every dimension except `dim_date` has a numeric surrogate primary key
(`community_key`, `resident_key`, `resident_care_level_key`, `unit_key`,
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

- **`dim_community`** conforms across every fact table (`fact_resident_day`, `fact_lease`, `fact_labor`, `fact_incident`, `fact_review`, `fact_lead`) via `community_key` — and also across `dim_unit.community_key`, `dim_employee.latest_community_key`, and `dim_resident.community_key`, each an "outrigger" dimension-to-dimension reference (a unit/employee/resident's current community, not a fact). These use the same surrogate-key convention as any fact FK, checked by `validation.checks.referential_integrity` alongside the fact FKs.
- **`dim_resident`** / **`dim_resident_care_level`** conform across `fact_resident_day`, `fact_lease`, `fact_incident` via `resident_key` / `resident_care_level_key`.
- **`dim_date`** is a role-playing dimension: `fact_resident_day.date`, `fact_labor.shift_date`, `fact_incident.incident_date`, `fact_review.review_date`/`responded_at`, `fact_lease.move_in_date`/`move_out_date`, and `fact_lead.created_date`/`tour_date`/`deposit_date`/`move_in_date` all join to it as separate roles. Facts store the raw `DATE` value rather than a surrogate date key, so Power BI (built separately, see `/powerbi`) should relate each of these columns to its own copy of `dim_date`, renamed per role (e.g. `dim_date (Shift Date)`), rather than a single bidirectional relationship.

