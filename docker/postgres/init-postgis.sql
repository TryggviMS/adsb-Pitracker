-- ============================================================
-- EXTENSIONS
-- ============================================================
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS postgis_topology;

-- ============================================================
-- ROLES
-- ============================================================
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'adsb_api') THEN
        CREATE ROLE adsb_api LOGIN PASSWORD 'adsb_api_password';
    END IF;
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'adsb_ingest') THEN
        CREATE ROLE adsb_ingest LOGIN PASSWORD 'adsb_ingest_password';
    END IF;
END
$$;

-- ============================================================
-- TABLE: aircraft_positions_history
-- ============================================================
CREATE TABLE IF NOT EXISTS public.aircraft_positions_history (
    id          BIGSERIAL PRIMARY KEY,
    hex         TEXT NOT NULL,
    flight      TEXT,
    observed_at TIMESTAMP NOT NULL DEFAULT now(),
    geom        geometry(Point, 4326),
    data        JSONB
);
CREATE INDEX IF NOT EXISTS idx_aircraft_positions_history_hex
    ON public.aircraft_positions_history(hex);
CREATE INDEX IF NOT EXISTS idx_aircraft_positions_history_observed_at
    ON public.aircraft_positions_history(observed_at);
CREATE INDEX IF NOT EXISTS idx_aircraft_positions_history_geom
    ON public.aircraft_positions_history USING GIST(geom);

-- ============================================================
-- TABLE: aircraft_live
-- ============================================================
CREATE TABLE IF NOT EXISTS public.aircraft_live (
    hex       TEXT PRIMARY KEY,
    flight    TEXT,
    category  TEXT,
    last_seen TIMESTAMP NOT NULL DEFAULT now(),
    lat       DOUBLE PRECISION,
    lon       DOUBLE PRECISION,
    alt_baro  TEXT,
    track     DOUBLE PRECISION,
    geom      geometry(Point, 4326),
    data      JSONB
);
CREATE INDEX IF NOT EXISTS idx_aircraft_live_last_seen
    ON public.aircraft_live(last_seen);
CREATE INDEX IF NOT EXISTS idx_aircraft_live_geom
    ON public.aircraft_live USING GIST(geom);

-- ============================================================
-- TABLE: aircraft_paths_live
-- ============================================================
CREATE TABLE IF NOT EXISTS public.aircraft_paths_live (
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
CREATE INDEX IF NOT EXISTS idx_aircraft_paths_live_hex
    ON public.aircraft_paths_live(hex);
CREATE INDEX IF NOT EXISTS idx_aircraft_paths_live_last_seen
    ON public.aircraft_paths_live(last_seen);
CREATE INDEX IF NOT EXISTS idx_aircraft_paths_live_geom
    ON public.aircraft_paths_live USING GIST(geom);

-- ============================================================
-- TABLE: aircraft_paths_history
-- ============================================================
CREATE TABLE IF NOT EXISTS public.aircraft_paths_history (
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
CREATE INDEX IF NOT EXISTS idx_aircraft_paths_history_hex
    ON public.aircraft_paths_history(hex);
CREATE INDEX IF NOT EXISTS idx_aircraft_paths_history_flight
    ON public.aircraft_paths_history(flight);
CREATE INDEX IF NOT EXISTS idx_aircraft_paths_history_start_time
    ON public.aircraft_paths_history(start_time);
CREATE INDEX IF NOT EXISTS idx_aircraft_paths_history_end_time
    ON public.aircraft_paths_history(end_time);
CREATE INDEX IF NOT EXISTS idx_aircraft_paths_history_geom
    ON public.aircraft_paths_history USING GIST(geom);

-- ============================================================
-- TABLE: aircraft_categories
-- ============================================================
CREATE TABLE IF NOT EXISTS public.aircraft_categories (
    code           TEXT PRIMARY KEY,
    description_en TEXT,
    description_is TEXT
);
INSERT INTO public.aircraft_categories (code, description_en, description_is) VALUES
    ('A0', 'No ADS-B emitter category information',          'Engar ADS-B upplýsingar'),
    ('A1', 'Light (< 15500 lbs)',                            'Létt vél(< 15500 lbs)'),
    ('A2', 'Small (15500 to 75000 lbs)',                     'Smærri vél (15500 til 75000 lbs)'),
    ('A3', 'Large (75000 to 300000 lbs)',                    'Stór vél (75000 til 300000 lbs)'),
    ('A4', 'High vortex large (e.g. B-757)',                 'Hátt vindhringleflugvél (t.d. B-757)'),
    ('A5', 'Heavy (> 300000 lbs)',                           'Þung vél (> 300000 lbs)'),
    ('A6', 'High performance (> 5g and 400 kts)',            'Háafkastsflugvél (> 5g og 400 kn)'),
    ('A7', 'Rotorcraft',                                     'Þyrla'),
    ('B0', 'No ADS-B emitter category information',          'Engar ADS-B upplýsingar'),
    ('B1', 'Glider / sailplane',                             'Svifflugvél'),
    ('B2', 'Lighter-than-air',                               'Léttara en loft (loftskip eða blástur)'),
    ('B3', 'Parachutist / skydiver',                         'Fallhlífarstökkvari'),
    ('B4', 'Ultralight / hang-glider / paraglider',          'Léttflugvél / svifhjól / gliðruflugvél'),
    ('B5', 'Reserved',                                       'Frátekið'),
    ('B6', 'Unmanned aerial vehicle',                        'Mannlaust loftfar'),
    ('B7', 'Space / trans-atmospheric vehicle',              'Geimfar / þverloftfaratæki'),
    ('C0', 'No ADS-B emitter category information',          'Engar ADS-B upplýsingar'),
    ('C1', 'Surface vehicle – emergency vehicle',            'Yfirborðsfarartæki - neyðarfarartæki'),
    ('C2', 'Surface vehicle – service vehicle',              'Yfirborðsfarartæki - þjónustufarartæki'),
    ('C3', 'Point obstacle (includes tethered balloons)',    'Punkthindrun (þ.m.t. fest blástur)'),
    ('C4', 'Cluster obstacle',                               'Þyrpingarhindrun'),
    ('C5', 'Line obstacle',                                  'Línuhindrun'),
    ('C6', 'Reserved',                                       'Frátekið'),
    ('C7', 'Reserved',                                       'Frátekið')
ON CONFLICT (code) DO NOTHING;

-- ============================================================
-- TABLE: aircraft_registry
-- ============================================================
CREATE TABLE IF NOT EXISTS public.aircraft_registry (
    icao24              TEXT PRIMARY KEY,
    timestamp           TEXT,
    acars               TEXT,
    adsb                TEXT,
    built               TEXT,
    categorydescription TEXT,
    country             TEXT,
    engines             TEXT,
    firstflightdate     TEXT,
    firstseen           TEXT,
    icaoaircraftclass   TEXT,
    linenumber          TEXT,
    manufacturericao    TEXT,
    manufacturername    TEXT,
    model               TEXT,
    modes               TEXT,
    nextreg             TEXT,
    notes               TEXT,
    operator            TEXT,
    operatorcallsign    TEXT,
    operatoriata        TEXT,
    operatoricao        TEXT,
    owner               TEXT,
    prevreg             TEXT,
    reguntil            TEXT,
    registered          TEXT,
    registration        TEXT,
    selcal              TEXT,
    serialnumber        TEXT,
    status              TEXT,
    typecode            TEXT,
    vdl                 TEXT
);

-- ============================================================
-- GRANTS
-- ============================================================
GRANT CONNECT ON DATABASE spatial_db TO adsb_api, adsb_ingest;
GRANT USAGE ON SCHEMA public TO adsb_api, adsb_ingest;

GRANT SELECT ON TABLE
    public.aircraft_live,
    public.aircraft_paths_live,
    public.aircraft_paths_history
TO adsb_api;

GRANT SELECT, INSERT ON TABLE
    public.aircraft_positions_history
TO adsb_ingest;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE
    public.aircraft_live,
    public.aircraft_paths_live
TO adsb_ingest;
GRANT SELECT, INSERT ON TABLE
    public.aircraft_paths_history
TO adsb_ingest;

GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO adsb_ingest;

ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT ON TABLES TO adsb_api;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO adsb_ingest;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT USAGE, SELECT ON SEQUENCES TO adsb_ingest;