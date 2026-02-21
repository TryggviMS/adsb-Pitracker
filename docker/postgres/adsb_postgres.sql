/* ============================================================
   ADS-B PostgreSQL Schema
   Database Structure for Aircraft Position & Flight Path Data
   ============================================================ */


/* ============================================================
   QUICK INSPECTION QUERIES
   ============================================================ */

-- Latest aircraft positions
SELECT *
FROM public.aircraft_positions_history
ORDER BY id DESC;

-- Approximate result size (subset)
SELECT pg_size_pretty(SUM(pg_column_size(t))) AS approx_result_size
FROM (
    SELECT *
    FROM public.aircraft_positions_history
    ORDER BY id DESC
    LIMIT 1000
) t;

-- Sample live paths
SELECT *
FROM public.aircraft_paths_live
LIMIT 10;

-- Latest historical paths
SELECT *
FROM public.aircraft_paths_history
ORDER BY id DESC
LIMIT 10;


/* ============================================================
   MAINTENANCE
   ============================================================ */

TRUNCATE TABLE aircraft_positions_history RESTART IDENTITY;
TRUNCATE TABLE aircraft_paths_live RESTART IDENTITY;
TRUNCATE TABLE aircraft_paths_history RESTART IDENTITY;


/* ============================================================
   TABLE 1 – aircraft_positions_history
   Stores raw aircraft position messages (Insert Only)
   ============================================================ */

CREATE TABLE public.aircraft_positions_history (
    id BIGSERIAL PRIMARY KEY,
    hex TEXT NOT NULL,
    flight TEXT,
    observed_at TIMESTAMP NOT NULL DEFAULT now(),
    geom geometry(Point, 4326),      -- nullable
    data JSONB                      -- raw message
);


-- Monthly partitions (example)
CREATE TABLE public.aircraft_positions_history_2026_01
PARTITION OF public.aircraft_positions_history
FOR VALUES FROM ('2026-01-01') TO ('2026-02-01');

CREATE TABLE public.aircraft_positions_history_2026_02
PARTITION OF public.aircraft_positions_history
FOR VALUES FROM ('2026-02-01') TO ('2026-03-01');


/* ============================================================
   TABLE 2 – aircraft_paths_live
   Active flight paths (Insert + Update)
   ============================================================ */

CREATE TABLE public.aircraft_paths_live (
    hex TEXT NOT NULL,
    flight TEXT NOT NULL,
    category TEXT,
    start_time TIMESTAMP NOT NULL,
    last_seen TIMESTAMP NOT NULL DEFAULT now(),
    geom geometry(LineString, 4326),
    PRIMARY KEY (hex, flight)
);

-- Spatial & time indexes
CREATE INDEX idx_aircraft_paths_live_geom
ON public.aircraft_paths_live USING GIST(geom);

CREATE INDEX idx_aircraft_paths_live_last_seen
ON public.aircraft_paths_live(last_seen);


/* ============================================================
   TABLE 3 – aircraft_paths_history
   Completed flight paths (Insert Only)
   ============================================================ */

CREATE TABLE public.aircraft_paths_history (
    id BIGSERIAL PRIMARY KEY,
    hex TEXT NOT NULL,
    flight TEXT NOT NULL,
    category TEXT,
    start_time TIMESTAMP NOT NULL,
    end_time TIMESTAMP NOT NULL,
    geom geometry(LineString, 4326)
);

-- Indexes
CREATE INDEX idx_aircraft_paths_history_geom
ON public.aircraft_paths_history USING GIST(geom);

CREATE INDEX idx_aircraft_paths_history_hex
ON public.aircraft_paths_history(hex);

CREATE INDEX idx_aircraft_paths_history_time
ON public.aircraft_paths_history(start_time);


/* ============================================================
   INSERT LOGIC – TABLE 1
   Insert Raw Position Message
   ============================================================ */

INSERT INTO public.aircraft_positions_history (
    hex,
    flight,
    observed_at,
    geom,
    data
)
VALUES (
    :hex,
    :flight,
    now(),

    CASE
        WHEN :lat IS NOT NULL AND :lon IS NOT NULL
        THEN ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)
        ELSE NULL
    END,

    :json_payload::jsonb
);


/* ============================================================
   UPSERT LOGIC – TABLE 2
   Update or Append Active Flight Path
   ============================================================ */

INSERT INTO public.aircraft_paths_live (
    hex,
    flight,
    category,
    start_time,
    last_seen,
    geom
)
VALUES (
    :hex,
    :flight,
    :category,
    now(),
    now(),
    ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)
)
ON CONFLICT (hex, flight)
DO UPDATE
SET
    geom = ST_AddPoint(
        aircraft_paths_live.geom,
        ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)
    ),
    last_seen = now();


/* ============================================================
   ARCHIVE LOGIC – TABLE 3
   Move Timed-Out Flights to History
   ============================================================ */

BEGIN;

INSERT INTO public.aircraft_paths_history (
    hex,
    flight,
    category,
    start_time,
    end_time,
    geom
)
SELECT
    hex,
    flight,
    category,
    start_time,
    last_seen,
    geom
FROM public.aircraft_paths_live
WHERE last_seen < now() - interval '10 minutes';

DELETE FROM public.aircraft_paths_live
WHERE last_seen < now() - interval '10 minutes';

COMMIT;



/* ============================================================
   TABLE 1B – aircraft_live   (NEW)
   Latest known state per aircraft (Upsert)
   Used for map markers + sidebar so it stays in sync with /live_paths
   ============================================================ */

CREATE TABLE IF NOT EXISTS public.aircraft_live (
    hex TEXT PRIMARY KEY,
    flight TEXT,
    category TEXT,
    last_seen TIMESTAMP NOT NULL DEFAULT now(),

    -- latest state (nullable)
    lat DOUBLE PRECISION,
    lon DOUBLE PRECISION,
    alt_baro TEXT,                   -- dump1090 may return 'ground'
    track DOUBLE PRECISION,

    geom geometry(Point, 4326),       -- derived from lat/lon
    data JSONB                        -- optional: latest raw payload
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_aircraft_live_last_seen
ON public.aircraft_live(last_seen);

CREATE INDEX IF NOT EXISTS idx_aircraft_live_geom
ON public.aircraft_live USING GIST(geom);

/* ============================================================
   LOGICAL FLOW SUMMARY
   ============================================================

Incoming message:
    → Insert into aircraft_positions_history

If lat/lon exists:
    → Upsert into aircraft_paths_live

Background worker:
    → Move timed-out rows to aircraft_paths_history

Table Behavior Summary:

aircraft_positions_history  → Insert only
aircraft_paths_live         → Insert + Update
aircraft_paths_history      → Insert only

============================================================ */