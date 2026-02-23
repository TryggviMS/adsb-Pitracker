CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS postgis_topology;


/* ============================================================
   TABLE: aircraft_positions_history
   Raw aircraft position messages (Insert Only)
   ============================================================ */

CREATE TABLE public.aircraft_positions_history (
    id          BIGSERIAL PRIMARY KEY,
    hex         TEXT NOT NULL,
    flight      TEXT,
    observed_at TIMESTAMP NOT NULL DEFAULT now(),
    geom        geometry(Point, 4326),
    data        JSONB
);

CREATE INDEX idx_aircraft_positions_history_hex
    ON public.aircraft_positions_history(hex);

CREATE INDEX idx_aircraft_positions_history_observed_at
    ON public.aircraft_positions_history(observed_at);

CREATE INDEX idx_aircraft_positions_history_geom
    ON public.aircraft_positions_history USING GIST(geom);


/* ============================================================
   TABLE: aircraft_live
   Latest known state per aircraft (Upsert)
   ============================================================ */

CREATE TABLE IF NOT EXISTS public.aircraft_live (
    hex      TEXT PRIMARY KEY,
    flight   TEXT,
    category TEXT,
    last_seen TIMESTAMP NOT NULL DEFAULT now(),
    lat      DOUBLE PRECISION,
    lon      DOUBLE PRECISION,
    alt_baro TEXT,
    track    DOUBLE PRECISION,
    geom     geometry(Point, 4326),
    data     JSONB
);

CREATE INDEX IF NOT EXISTS idx_aircraft_live_last_seen
    ON public.aircraft_live(last_seen);

CREATE INDEX IF NOT EXISTS idx_aircraft_live_geom
    ON public.aircraft_live USING GIST(geom);


/* ============================================================
   TABLE: aircraft_paths_live
   Active flight paths (Insert + Update)
   ============================================================ */

CREATE TABLE public.aircraft_paths_live (
    hex             TEXT NOT NULL,
    flight          TEXT NOT NULL,
    category        TEXT,
    start_time      TIMESTAMP NOT NULL,
    last_seen       TIMESTAMP NOT NULL DEFAULT now(),
    geom            geometry(LineString, 4326),
    total_length_km DOUBLE PRECISION GENERATED ALWAYS AS (
        ROUND((ST_Length(geom::geography) / 1000.0)::numeric, 1)::double precision
    ) STORED,

    PRIMARY KEY (hex, flight)
);

CREATE INDEX idx_aircraft_paths_live_hex
    ON public.aircraft_paths_live(hex);

CREATE INDEX idx_aircraft_paths_live_last_seen
    ON public.aircraft_paths_live(last_seen);

CREATE INDEX idx_aircraft_paths_live_geom
    ON public.aircraft_paths_live USING GIST(geom);


/* ============================================================
   TABLE: aircraft_paths_history
   Completed flight paths (Insert Only)
   ============================================================ */

CREATE TABLE public.aircraft_paths_history (
    id              BIGSERIAL PRIMARY KEY,
    hex             TEXT NOT NULL,
    flight          TEXT NOT NULL,
    category        TEXT,
    start_time      TIMESTAMP NOT NULL,
    end_time        TIMESTAMP NOT NULL,
    geom            geometry(LineString, 4326),
    total_length_km DOUBLE PRECISION GENERATED ALWAYS AS (
        ROUND((ST_Length(geom::geography) / 1000.0)::numeric, 1)::double precision
    ) STORED
);

CREATE INDEX idx_aircraft_paths_history_hex
    ON public.aircraft_paths_history(hex);

CREATE INDEX idx_aircraft_paths_history_flight
    ON public.aircraft_paths_history(flight);

CREATE INDEX idx_aircraft_paths_history_start_time
    ON public.aircraft_paths_history(start_time);

CREATE INDEX idx_aircraft_paths_history_end_time
    ON public.aircraft_paths_history(end_time);

CREATE INDEX idx_aircraft_paths_history_geom
    ON public.aircraft_paths_history USING GIST(geom);




    CREATE ROLE adsb_api LOGIN PASSWORD 'adsb_api_password'; -- CHANGE THIS PASSWORD
CREATE ROLE adsb_ingest LOGIN PASSWORD 'adsb_ingest_password'; -- CHANGE THIS PASSWORD

-- 2) allow connect
GRANT CONNECT ON DATABASE spatial_db TO adsb_api, adsb_ingest;

-- 3) schema usage
GRANT USAGE ON SCHEMA public TO adsb_api, adsb_ingest;

-- 4) API: read-only
GRANT SELECT ON TABLE
  public.aircraft_live,
  public.aircraft_paths_live,
  public.aircraft_paths_history
TO adsb_api;

-- (optional) API might also read stats from history; already included above

-- 5) INGEST: write privileges per table
GRANT SELECT, INSERT ON TABLE public.aircraft_positions_history TO adsb_ingest;

GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.aircraft_live TO adsb_ingest;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.aircraft_paths_live TO adsb_ingest;

GRANT SELECT, INSERT ON TABLE public.aircraft_paths_history TO adsb_ingest;

-- 6) if any of those tables use sequences / identity columns:
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO adsb_ingest;

-- 7) (optional) future-proof defaults (only if you want this behavior)
ALTER DEFAULT PRIVILEGES IN SCHEMA public
GRANT SELECT ON TABLES TO adsb_api;

ALTER DEFAULT PRIVILEGES IN SCHEMA public
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO adsb_ingest;

ALTER DEFAULT PRIVILEGES IN SCHEMA public
GRANT USAGE, SELECT ON SEQUENCES TO adsb_ingest;
