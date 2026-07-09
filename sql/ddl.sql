-- Gold layer DDL — documents the star schema built by pipeline/gold.py.
--
-- The Gold layer physically lives as Parquet files (pipeline/data/gold/*.parquet),
-- written by pandas/DuckDB rather than a persisted database, so Parquet has no
-- enforced constraints -- PK/FK/NOT NULL below are the *logical* contract of
-- the model (asserted by the validation framework in /validation, not by the
-- storage engine). These CREATE TABLE statements are runnable as-is against
-- an in-memory DuckDB connection for schema inspection / documentation:
--
--   python -c "import duckdb; duckdb.connect().execute(open('sql/ddl.sql').read())"
--
-- Every dimension (except dim_date -- the date itself is already a unique,
-- sortable, meaningful key) has a numeric surrogate key as its primary key,
-- with the source system's natural/business key retained as a plain
-- attribute column (e.g. dim_resident.resident_key is the PK,
-- dim_resident.resident_id is PCC's own ID, kept for traceability). Every
-- fact table's foreign keys to those dimensions are the surrogate keys, not
-- the natural keys -- a fact still carries its OWN natural business key
-- (lease_id, shift_id, incident_id, etc.), since that identifies the fact
-- row itself, not a reference to a dimension. See pipeline/gold.py's module
-- docstring for the surrogate-key assignment scheme and its tradeoffs.

-- ============================================================
-- DIMENSIONS
-- ============================================================

CREATE OR REPLACE TABLE dim_community (
    community_key  BIGINT PRIMARY KEY,   -- surrogate key
    community_id   VARCHAR NOT NULL,     -- natural key, C001-C014
    state          VARCHAR NOT NULL,     -- OR / AZ / TX (hard-coded assumption, see sql/README.md)
    region         VARCHAR NOT NULL      -- Pacific Northwest / Southwest / South
);

CREATE OR REPLACE TABLE dim_resident (
    resident_key    BIGINT PRIMARY KEY,   -- surrogate key
    resident_id     VARCHAR NOT NULL,     -- natural key, PCC's own resident ID
    community_key   BIGINT REFERENCES dim_community(community_key),   -- outrigger reference to dim_community (current community)
    first_name      VARCHAR,
    last_name       VARCHAR,
    dob             DATE,
    gender          VARCHAR,
    admit_date      DATE,
    discharge_date  DATE,             -- null if still resident
    care_level      VARCHAR,          -- current care level, denormalized from dim_resident_care_level
    acuity_score    BIGINT            -- 1-10, out-of-range values quarantined in Silver
);

-- SCD Type 2: a resident who changes care level gets a new row with valid
-- effective/end dates rather than an overwrite. Each SCD2 VERSION gets its
-- own surrogate key (not each resident), since this table's grain is
-- resident x time-period.
CREATE OR REPLACE TABLE dim_resident_care_level (
    resident_care_level_key  BIGINT PRIMARY KEY,   -- surrogate key, one per SCD2 version
    resident_id     VARCHAR NOT NULL,     -- natural key
    care_level      VARCHAR NOT NULL,     -- IL / AL / MC (canonicalized)
    effective_date  DATE NOT NULL,
    end_date        DATE,                 -- null = current version
    is_current      BOOLEAN NOT NULL,
    change_reason   VARCHAR
);

CREATE OR REPLACE TABLE dim_unit (
    unit_key      BIGINT PRIMARY KEY,   -- surrogate key
    unit_id       VARCHAR NOT NULL,     -- natural key
    community_key BIGINT REFERENCES dim_community(community_key),   -- outrigger reference to dim_community
    unit_type     VARCHAR,   -- IL / AL / MC
    monthly_rent  BIGINT     -- latest known list rent
);

CREATE OR REPLACE TABLE dim_employee (
    employee_key           BIGINT PRIMARY KEY,   -- surrogate key
    employee_id            VARCHAR NOT NULL,     -- natural key, ADP's own employee ID
    latest_role            VARCHAR,   -- Caregiver / Med Tech / LPN / RN / Admin / Maintenance / Dining
    latest_community_key    BIGINT REFERENCES dim_community(community_key)   -- outrigger reference to dim_community
);

CREATE OR REPLACE TABLE dim_date (
    date         DATE PRIMARY KEY,   -- no surrogate key -- the date itself is already the ideal key
    year         INTEGER,
    month        INTEGER,
    day          INTEGER,
    month_name   VARCHAR,
    quarter      INTEGER,
    day_of_week  VARCHAR
);

-- ============================================================
-- FACTS
-- ============================================================

-- Grain: one row per resident per calendar day they were an active resident.
CREATE OR REPLACE TABLE fact_resident_day (
    resident_key    BIGINT REFERENCES dim_resident(resident_key),
    community_key   BIGINT REFERENCES dim_community(community_key),
    date            DATE REFERENCES dim_date(date),
    resident_care_level_key  BIGINT REFERENCES dim_resident_care_level(resident_care_level_key),  -- as of this day; see sql/README.md on the opening-balance version that covers pre-first-event days
    PRIMARY KEY (resident_key, date)
);

-- Periodic snapshot fact. Grain: one row per resident per MONTH they had a
-- valid acuity reading (deliberately not collapsed to "distinct values
-- only" -- see pipeline/gold.py::build_fact_acuity_snapshot for why).
-- Needed for the acuity-jump alert view.
CREATE OR REPLACE TABLE fact_acuity_snapshot (
    resident_key   BIGINT REFERENCES dim_resident(resident_key),
    snapshot_date  DATE,
    acuity_score   BIGINT,
    PRIMARY KEY (resident_key, snapshot_date)
);

-- Grain: one row per lease.
CREATE OR REPLACE TABLE fact_lease (
    lease_id          VARCHAR PRIMARY KEY,   -- fact's own natural key, not a dimension reference
    resident_key      BIGINT REFERENCES dim_resident(resident_key),
    unit_key          BIGINT REFERENCES dim_unit(unit_key),
    community_key     BIGINT REFERENCES dim_community(community_key),
    move_in_date      DATE REFERENCES dim_date(date),
    move_out_date     DATE,             -- null if still active
    move_out_reason   VARCHAR,
    monthly_rate      BIGINT            -- actual rate paid, may differ from dim_unit.monthly_rent
);

-- Grain: one row per shift worked.
CREATE OR REPLACE TABLE fact_labor (
    shift_id       VARCHAR PRIMARY KEY,   -- fact's own natural key
    community_key  BIGINT REFERENCES dim_community(community_key),
    employee_key   BIGINT REFERENCES dim_employee(employee_key),
    role           VARCHAR,
    shift_date     DATE REFERENCES dim_date(date),
    hours_worked   BIGINT,
    hourly_rate    BIGINT,      -- resolved from the corrupted per-employee rate dict, see pipeline/silver.py
    labor_cost     BIGINT       -- hours_worked * hourly_rate
);

-- Grain: one row per incident.
CREATE OR REPLACE TABLE fact_incident (
    incident_id       VARCHAR PRIMARY KEY,   -- fact's own natural key
    resident_key      BIGINT REFERENCES dim_resident(resident_key),
    community_key     BIGINT REFERENCES dim_community(community_key),
    incident_date     DATE REFERENCES dim_date(date),
    incident_type     VARCHAR,   -- Fall / Medication Error / Behavioral / Skin Tear / Elopement / Other
    severity          BIGINT,    -- 1-5
    reported_by       VARCHAR    -- PCC's raw, unresolved staff ID -- NOT a dim_employee FK: PCC's
                                  -- reported_by IDs and ADP's employee_id IDs are two disjoint ID
                                  -- systems that were never reconciled -- see pipeline/gold.py::build_fact_incident
);

-- Grain: one row per review.
CREATE OR REPLACE TABLE fact_review (
    review_id      VARCHAR PRIMARY KEY,   -- fact's own natural key
    community_key  BIGINT REFERENCES dim_community(community_key),
    review_date    DATE REFERENCES dim_date(date),
    rating         BIGINT,     -- 1-5
    has_response   BOOLEAN,
    responded_at   DATE
);

-- Grain: one row per sales lead.
CREATE OR REPLACE TABLE fact_lead (
    lead_id        VARCHAR PRIMARY KEY,   -- fact's own natural key
    community_key  BIGINT REFERENCES dim_community(community_key),
    lead_source    VARCHAR,
    created_date   DATE REFERENCES dim_date(date),
    tour_date      DATE,
    deposit_date   DATE,
    move_in_date   DATE,
    status         VARCHAR,   -- Won / Lost / Open
    lost_reason    VARCHAR
);
