BEGIN;

-- 1) roles
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

COMMIT;