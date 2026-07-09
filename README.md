# Pinewood Senior Living — Analytics Platform

Software Development Engineer take-home for Skypoint Cloud. Builds the
minimum viable version of Pinewood's occupancy/revenue/labor/care-quality
platform: a Python ingestion pipeline (Bronze/Silver/Gold), a star-schema SQL
layer, a FastAPI service with role-based access, a validation framework, a PowerBI report and
the two client-communication writeups. 

**Walkthrough video:** https://www.loom.com/share/653c0061ed3242919af60fd103001e8f

## Setup (fresh machine)

Requires Python 3.10+ and Homebrew (macOS) or an existing Python 3.10+ install.

```bash
# 1. Get a Python 3.10+ interpreter if you don't have one
brew install python@3.11

# 2. Create and activate a virtualenv
/opt/homebrew/bin/python3.11 -m venv .venv
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run the pipeline (Bronze -> Silver -> Gold)
python -m pipeline.run

# 5. Run the validation framework (reads the pipeline's run log)
python -m validation.run

# 6. Run the API
uvicorn api.main:app --reload
# Swagger UI: http://127.0.0.1:8000/docs

# 7. Generate demo JWTs (one per role) to exercise the API
python -m api.generate_tokens

# 8. Run tests
python -m pytest tests/ -v
```

Re-running `python -m pipeline.run` is safe at any time — it's idempotent
(re-running on unchanged source files reprocesses nothing) and incremental
(dropping a new `*_2025_07.csv` file into `candidate_package/data/` following
the existing naming convention only ingests that file, not the whole
history).

## Repo layout

```
/pipeline          Python ingestion: bronze.py, silver.py, gold.py, run.py, state.py
/sql               DDL for the star schema + the 6 required analytical views
/api               FastAPI service: auth.py (JWT), scope.py (RBAC), queries.py, main.py
/powerbi           skypointdemo.pbix
/validation        checks.py + run.py; latest_report.md is the COO-readable output
/communication     email-to-it.md, incident-response.md
/tests             pytest suite for the API's auth/RBAC behavior
```

## Design notes

- **Storage**: everything is Parquet on disk (`pipeline/data/{bronze,silver,gold}/`).
  DuckDB is used purely as an in-process SQL engine over those files (no
  persisted database file) — both the pipeline's Gold-building step and the
  API query straight off Parquet via DuckDB.
- **`fact_resident_day`** (grain: one row per resident per active day) is the
  central design decision in the Gold layer: rather than reverse-engineering
  occupancy from monthly snapshots, every resident's admit→discharge window
  is exploded into one row per day. Occupancy, labor-cost-per-resident-day,
  and incident-rate-per-100-resident-days are all just aggregations over this
  one table. See `sql/README.md` for full grain/conformance documentation.
- **SCD Type 2** for care level (`dim_resident_care_level`) is built primarily
  from `pcc_care_history`'s transactional change events; a resident with no
  recorded change event in the 6-month window gets a single open-ended
  version seeded from their admit_date snapshot.
- **API auth**: JWT (HS256), chosen over a raw API key because role + scope
  (region / community_id) travel inside the signed token itself — no separate
  lookup needed to know what a caller can see. RBAC is enforced server-side
  in `api/scope.py`: a request for a community_id or region outside what the
  token grants is a 403, never a silently-narrowed response. See
  `api/auth.py` for the full rationale.
- **Field-level vs. row-level quarantine**: a bad `acuity_score` or an
  impossible future `discharge_date` nulls out just that field rather than
  dropping the whole resident record. Dropping the row would have orphaned
  every fact table that references that resident (their incidents, leases,
  etc.) over a data-quality problem in one unrelated column. An unknown
  `community_id`, by contrast, is structural — there's no coherent place to
  put that record — so those rows are fully quarantined. See
  `pipeline/silver.py::clean_pcc_residents`.

## Assumptions

- **Community → state/region mapping is hard-coded** (`pipeline/config.py::COMMUNITY_STATE`).
  No source file links a community to a state — confirmed by inspecting
  every CSV's columns — so communities are split evenly across
  Oregon/Arizona/Texas in `community_id` order (C001–005 → OR, C006–010 →
  AZ, C011–014 → TX). This is the first thing to correct once real mapping
  data is available (see the [email to Pinewood IT](communication/email-to-it.md)).
- **"As of" date is derived from the data, not wall-clock time**
  (`pipeline/config.py::data_as_of_date`). Using the real current date
  for "is this resident still active" logic would extend every still-active
  resident's day-level fact rows years past the actual data.
- **Trailing-12-month views** (`sql/views/02`, `03`, and the `/move-outs/reasons`
  endpoint's `period` param) compute their window relative to the latest
  date actually present in the relevant fact table, not wall-clock today —
  with only 6 months of data, this means the window captures the whole
  export, which is the correct behavior once more months land.

## Anomalies found and how they were handled

1. **Inconsistent care-level labels.** `pcc_residents` / `pcc_care_history`
   mix `AL`/`Assisted`/`Assisted Living`, `IL`/`Independent`/`Independent Living`,
   `MC`/`Memory`/`Memory Care` — sometimes for the *same resident* across
   different monthly files. **Handled:** normalized to a canonical 3-letter
   code (`pipeline/config.py::CARE_LEVEL_MAP`) before any deduping or
   comparison happens.

2. **Non-monotonic schema drift.** `pcc_residents_2025_04.csv` has an extra
   `mobility_status` column absent from every other month, including the
   ones *after* April. **Handled:** Bronze concatenates files by column
   union (pandas `concat(sort=False)`), so an extra or missing column in any
   single month never breaks ingestion — no code change needed when this
   happens again.

3. **Out-of-range acuity scores.** Values like `50`, `-5`, `99` where the
   valid range is 1–10. **Handled:** the specific field is nulled (not the
   whole resident record — see Design notes above) and logged as an anomaly
   with severity `medium`, action `quarantine`.

4. **Corrupted `hourly_rate` in `adp_shifts`.** Instead of a scalar, the
   column holds a stringified Python dict of *every* role's rate for that
   employee (e.g. `"{'Caregiver': 16, 'Med Tech': 21, ...}"`), identical
   across all of that employee's shifts in a month. **Handled:** parsed with
   `ast.literal_eval` and the correct rate is looked up by the row's own
   `role` (`pipeline/silver.py::_resolve_hourly_rate`). Rows where this
   fails to resolve are quarantined as `high` severity.

5. **Phantom community IDs.** `yardi_units` includes units in `C905`,
   `C934`, `C936`, `C951`, `C969` — none of which exist anywhere else in the
   dataset (valid range is `C001`–`C014`). **Handled:** quarantined at
   Silver; never reach Gold.

6. **Mixed date formats.** `dob`, `admit_date`, `discharge_date` in
   `pcc_residents` mix `YYYY-MM-DD` and `MM/DD/YYYY` — including for the
   *same resident* across different monthly files. This one mattered more
   than it looks: deduping on raw strings before normalizing would treat
   `"03/19/2024"` and `"2024-03-19"` as different states and fail to
   collapse a resident's unchanged month-to-month snapshot. **Handled:**
   normalize with `pd.to_datetime(..., format="mixed")` *before* deduping,
   not after.

7. **Duplicate `lead_id` with conflicting data.** `HL385264` appears twice
   in `hubspot_leads` with a different community, source, and status (one
   `Lost`, one `Won`) — a genuine ID collision, not a re-export of the same
   record. **Handled:** detected before the generic re-ingestion dedup step
   (which would have silently kept whichever row happened to sort last) and
   quarantined both conflicting rows as `medium` severity.

8. **Future-dated discharge events.** Two residents carry a `discharge_date`
   over a year past the end of the 6-month export (e.g. `2026-09-17`) — a
   genuine future-dated event relative to the data itself, not just to
   whenever the pipeline happens to run. **Handled:** field nulled (resident
   treated as still active) and logged, `medium` severity.


## Running the validation report

`python -m validation.run` reads the most recent pipeline run log and
produces `validation/latest_report.md` — row-count reconciliation
(Bronze→Silver), aggregate reconciliation (total lease revenue, total shift
hours, total resident-days — computed two independent ways and compared
exactly, since these are deterministic derivations with no expected noise),
business-rule checks (no overlapping leases, no negative occupancy, no
discharge-before-admit, no future-dated events, acuity in range, referential
integrity, primary-key uniqueness), and the anomaly list above with severity
and recommended action for each.
