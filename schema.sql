-- NASA/JPL asteroid database (SQLite). Units are in the column names.
-- 1 au = 149,597,870.7 km. 1 lunar distance (LD) = 384,400 km (Earth-Moon distance).
-- Flags (is_*) are 1 = yes, 0 = no. Dates are ISO text 'YYYY-MM-DD'.

-- Every known asteroid (JPL Small-Body Database). Includes dwarf planets JPL lists as asteroids (Ceres, Pluto, Eris).
CREATE TABLE asteroids (
    spkid               INTEGER PRIMARY KEY,  -- JPL id
    designation         TEXT NOT NULL,        -- primary designation, e.g. '433' or '2024 YR4'; joins to close_approaches.designation and impact_risk.designation
    name                TEXT,                 -- proper name if it has one, e.g. 'Eros', 'Apophis', 'Bennu' (NULL for most)
    full_name           TEXT,                 -- e.g. '433 Eros (A898 PA)', '99942 Apophis (2004 MN4)'
    is_numbered         INTEGER,              -- 1 = has a permanent number (well-determined orbit)
    is_neo              INTEGER,              -- 1 = near-Earth object (perihelion < 1.3 au)
    is_pha              INTEGER,              -- 1 = potentially hazardous asteroid (moid_au <= 0.05 and abs_magnitude_h <= 22)
    orbit_class         TEXT,                 -- code, see orbit_classes.code (e.g. 'APO' Apollo, 'MBA' main belt)
    abs_magnitude_h     REAL,                 -- absolute magnitude H (smaller = bigger/brighter)
    diameter_km         REAL,                 -- measured diameter in km (NULL for most asteroids)
    diameter_est_km     REAL,                 -- measured diameter if known, else estimated from H; use this for size questions
    albedo              REAL,                 -- surface reflectivity 0-1
    rotation_period_h   REAL,                 -- spin period in hours
    eccentricity        REAL,
    semi_major_axis_au  REAL,
    perihelion_au       REAL,                 -- closest distance to the Sun
    aphelion_au         REAL,                 -- farthest distance from the Sun
    inclination_deg     REAL,
    orbital_period_years REAL,
    moid_au             REAL,                 -- minimum orbit intersection distance with Earth's orbit (how close the orbits come, not an actual flyby)
    moid_km             REAL,
    moid_ld             REAL,                 -- same in lunar distances
    first_observed      TEXT,                 -- date of first observation
    last_observed       TEXT,
    observations        INTEGER               -- number of observations used in the orbit fit
);

-- Close approaches (flybys) of asteroids to Earth, 1900-2200, within 0.2 au. Past and predicted future events.
CREATE TABLE close_approaches (
    id                  INTEGER PRIMARY KEY,
    designation         TEXT NOT NULL,        -- references asteroids.designation
    full_name           TEXT,
    approach_time       TEXT NOT NULL,        -- 'YYYY-MM-DD HH:MM' (TDB, close to UTC)
    approach_date       TEXT NOT NULL,        -- 'YYYY-MM-DD'
    dist_au             REAL,                 -- nominal distance from Earth's center at closest approach
    dist_km             REAL,
    dist_ld             REAL,                 -- in lunar distances
    dist_min_km         REAL,                 -- 3-sigma minimum possible distance
    dist_max_km         REAL,
    velocity_kms        REAL,                 -- speed relative to Earth, km/s
    abs_magnitude_h     REAL
);

-- NASA Sentry impact-risk list: asteroids with a non-zero chance of hitting Earth in the next ~100 years.
CREATE TABLE impact_risk (
    designation         TEXT PRIMARY KEY,     -- references asteroids.designation
    full_name           TEXT,
    impact_probability  REAL,                 -- cumulative probability of impact (0-1)
    potential_impacts   INTEGER,              -- number of possible impact dates found
    first_year          INTEGER,              -- first year with a possible impact
    last_year           INTEGER,
    palermo_scale_cum   REAL,                 -- Palermo hazard scale (higher = more concerning; < -2 means no concern)
    palermo_scale_max   REAL,
    torino_scale_max    INTEGER,              -- Torino scale 0-10 (0 = no hazard)
    diameter_km         REAL,                 -- estimated diameter
    velocity_kms        REAL,                 -- impact velocity
    abs_magnitude_h     REAL,
    last_observed       TEXT
);

-- Lookup for asteroids.orbit_class.
CREATE TABLE orbit_classes (
    code                TEXT PRIMARY KEY,     -- e.g. 'APO'
    name                TEXT,                 -- e.g. 'Apollo'
    description         TEXT
);

-- Facts about this dataset (key/value), e.g. key = 'fetched_utc'.
CREATE TABLE dataset_info (
    key                 TEXT PRIMARY KEY,
    value               TEXT
);
