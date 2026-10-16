-- Import file for drawsql.app (PostgreSQL dialect). Same tables and columns as schema.sql,
-- with the relationships declared as foreign keys so drawSQL draws the links.
-- (The SQLite database itself doesn't declare them; the data satisfies all of them.)

CREATE TABLE orbit_classes (
    code                 TEXT PRIMARY KEY,
    name                 TEXT,
    description          TEXT
);

CREATE TABLE asteroids (
    spkid                INTEGER PRIMARY KEY,
    designation          TEXT NOT NULL UNIQUE,
    name                 TEXT,
    full_name            TEXT,
    is_numbered          INTEGER,
    is_neo               INTEGER,
    is_pha               INTEGER,
    orbit_class          TEXT REFERENCES orbit_classes (code),
    abs_magnitude_h      DOUBLE PRECISION,
    diameter_km          DOUBLE PRECISION,
    diameter_est_km      DOUBLE PRECISION,
    albedo               DOUBLE PRECISION,
    rotation_period_h    DOUBLE PRECISION,
    eccentricity         DOUBLE PRECISION,
    semi_major_axis_au   DOUBLE PRECISION,
    perihelion_au        DOUBLE PRECISION,
    aphelion_au          DOUBLE PRECISION,
    inclination_deg      DOUBLE PRECISION,
    orbital_period_years DOUBLE PRECISION,
    moid_au              DOUBLE PRECISION,
    moid_km              DOUBLE PRECISION,
    moid_ld              DOUBLE PRECISION,
    first_observed       TEXT,
    last_observed        TEXT,
    observations         INTEGER
);

CREATE TABLE close_approaches (
    id                   INTEGER PRIMARY KEY,
    designation          TEXT NOT NULL REFERENCES asteroids (designation),
    full_name            TEXT,
    approach_time        TEXT NOT NULL,
    approach_date        TEXT NOT NULL,
    dist_au              DOUBLE PRECISION,
    dist_km              DOUBLE PRECISION,
    dist_ld              DOUBLE PRECISION,
    dist_min_km          DOUBLE PRECISION,
    dist_max_km          DOUBLE PRECISION,
    velocity_kms         DOUBLE PRECISION,
    abs_magnitude_h      DOUBLE PRECISION
);

CREATE TABLE impact_risk (
    designation          TEXT PRIMARY KEY REFERENCES asteroids (designation),
    full_name            TEXT,
    impact_probability   DOUBLE PRECISION,
    potential_impacts    INTEGER,
    first_year           INTEGER,
    last_year            INTEGER,
    palermo_scale_cum    DOUBLE PRECISION,
    palermo_scale_max    DOUBLE PRECISION,
    torino_scale_max     INTEGER,
    diameter_km          DOUBLE PRECISION,
    velocity_kms         DOUBLE PRECISION,
    abs_magnitude_h      DOUBLE PRECISION,
    last_observed        TEXT
);

CREATE TABLE dataset_info (
    key                  TEXT PRIMARY KEY,
    value                TEXT
);
