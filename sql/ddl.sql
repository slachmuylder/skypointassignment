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

-- ============================================================
-- DIMENSIONS
-- ============================================================

CREATE OR REPLACE TABLE dim_community (
    community_id VARCHAR PRIMARY KEY,   -- C001-C014
    state        VARCHAR NOT NULL,      -- OR / AZ / TX (hard-coded assumption, see sql/README.md)
    region       VARCHAR NOT NULL       -- Pacific Northwest / Southwest / South
);

CREATE OR REPLACE TABLE dim_resident (
    resident_id     VARCHAR PRIMARY KEY,
    community_id    VARCHAR REFERENCES dim_community(community_id),  -- current community
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
-- effective/end dates rather than an overwrite.
CREATE OR REPLACE TABLE dim_resident_care_level (
    resident_id     VARCHAR REFERENCES dim_resident(resident_id),
    care_level      VARCHAR NOT NULL,    -- IL / AL / MC (canonicalized)
    effective_date  DATE NOT NULL,
    end_date        DATE,                -- null = current version
    is_current      BOOLEAN NOT NULL,
    change_reason   VARCHAR,
    PRIMARY KEY (resident_id, effective_date)
);

CREATE OR REPLACE TABLE dim_unit (
    unit_id       VARCHAR PRIMARY KEY,
    community_id  VARCHAR REFERENCES dim_community(community_id),
    unit_type     VARCHAR,   -- IL / AL / MC
    monthly_rent  BIGINT     -- latest known list rent
);

CREATE OR REPLACE TABLE dim_employee (
    employee_id           VARCHAR PRIMARY KEY,
    latest_role           VARCHAR,   -- Caregiver / Med Tech / LPN / RN / Admin / Maintenance / Dining
    latest_community_id   VARCHAR REFERENCES dim_community(community_id)
);

CREATE OR REPLACE TABLE dim_date (
    date         DATE PRIMARY KEY,
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
    resident_id   VARCHAR REFERENCES dim_resident(resident_id),
    community_id  VARCHAR REFERENCES dim_community(community_id),
    date          DATE REFERENCES dim_date(date),
    care_level    VARCHAR,   -- as of this day, from dim_resident_care_level
    PRIMARY KEY (resident_id, date)
);

-- Periodic snapshot fact. Grain: one row per resident per distinct acuity
-- reading (dated to the last month that reading held), since dim_resident
-- only keeps the current value. Needed for the acuity-jump alert view.
CREATE OR REPLACE TABLE fact_acuity_snapshot (
    resident_id    VARCHAR REFERENCES dim_resident(resident_id),
    snapshot_date  DATE,
    acuity_score   BIGINT,
    PRIMARY KEY (resident_id, snapshot_date)
);

-- Grain: one row per lease.
CREATE OR REPLACE TABLE fact_lease (
    lease_id          VARCHAR PRIMARY KEY,
    resident_id       VARCHAR REFERENCES dim_resident(resident_id),
    unit_id           VARCHAR REFERENCES dim_unit(unit_id),
    community_id      VARCHAR REFERENCES dim_community(community_id),
    move_in_date      DATE REFERENCES dim_date(date),
    move_out_date     DATE,             -- null if still active
    move_out_reason   VARCHAR,
    monthly_rate      BIGINT            -- actual rate paid, may differ from dim_unit.monthly_rent
);

-- Grain: one row per shift worked.
CREATE OR REPLACE TABLE fact_labor (
    shift_id      VARCHAR PRIMARY KEY,
    community_id  VARCHAR REFERENCES dim_community(community_id),
    employee_id   VARCHAR REFERENCES dim_employee(employee_id),
    role          VARCHAR,
    shift_date    DATE REFERENCES dim_date(date),
    hours_worked  BIGINT,
    hourly_rate   BIGINT,      -- resolved from the corrupted per-employee rate dict, see pipeline/silver.py
    labor_cost    BIGINT       -- hours_worked * hourly_rate
);

-- Grain: one row per incident.
CREATE OR REPLACE TABLE fact_incident (
    incident_id     VARCHAR PRIMARY KEY,
    resident_id     VARCHAR REFERENCES dim_resident(resident_id),
    community_id    VARCHAR REFERENCES dim_community(community_id),
    incident_date   DATE REFERENCES dim_date(date),
    incident_type   VARCHAR,   -- Fall / Medication Error / Behavioral / Skin Tear / Elopement / Other
    severity        BIGINT,    -- 1-5
    reported_by     VARCHAR    -- employee_id
);

-- Grain: one row per review.
CREATE OR REPLACE TABLE fact_review (
    review_id      VARCHAR PRIMARY KEY,
    community_id   VARCHAR REFERENCES dim_community(community_id),
    review_date    DATE REFERENCES dim_date(date),
    rating         BIGINT,     -- 1-5
    has_response   BOOLEAN,
    responded_at   DATE
);

-- Grain: one row per sales lead.
CREATE OR REPLACE TABLE fact_lead (
    lead_id        VARCHAR PRIMARY KEY,
    community_id   VARCHAR REFERENCES dim_community(community_id),
    lead_source    VARCHAR,
    created_date   DATE REFERENCES dim_date(date),
    tour_date      DATE,
    deposit_date   DATE,
    move_in_date   DATE,
    status         VARCHAR,   -- Won / Lost / Open
    lost_reason    VARCHAR
);
