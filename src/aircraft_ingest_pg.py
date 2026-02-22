"""
ADS-B ingestion worker reading dump1090 aircraft.json.

Single source of truth for time-based lifecycle:
- ARCHIVE_TIMEOUT_SECONDS controls everything
"""

import json
import os
import time
from pathlib import Path

import psycopg

# ============================================================
# CONFIG – SINGLE SOURCE OF TRUTH
# ============================================================

POLL_SECONDS = 2

# 🔥 ONE knob controls ALL archiving & pruning (seconds)
ARCHIVE_TIMEOUT_SECONDS = 30  # e.g. 30 seconds

# Only append to path if position is fresh
MAX_SEEN_POS_SECONDS_FOR_LINE = 30

# Path history acceptance thresholds ("truth policy")
MIN_DURATION_SECONDS = 20
MIN_POINTS = 4
MIN_DISTANCE_KM = 0.3

# --- Aircraft JSON location ---
DEFAULT_DATA_FILE = Path.cwd() / "web" / "static" / "data" / "aircraft.json"
DATA_FILE = Path(os.environ.get("ADSB_DATA_FILE", str(DEFAULT_DATA_FILE)))

# --- Database ---
DB_NAME = os.environ["PGDATABASE"]
DB_USER = os.environ["PGUSER"]
DB_PASS = os.environ["PGPASSWORD"]
DB_HOST = os.environ.get("PGHOST", "localhost")
DB_PORT = os.environ.get("PGPORT", "5432")

DB_DSN = (
    f"dbname={DB_NAME} user={DB_USER} password={DB_PASS} host={DB_HOST} port={DB_PORT}"
)

conn = psycopg.connect(DB_DSN)
conn.autocommit = False


# ============================================================
# HELPERS
# ============================================================

def _safe_float(v, default=0.0) -> float:
    try:
        return float(v)
    except Exception:
        return float(default)


def read_aircraft_file():
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            payload = json.load(f)
        return payload.get("aircraft", [])
    except Exception as e:
        print("read_aircraft_file failed:", repr(e))
        return []


# ============================================================
# DB WRITES
# ============================================================

def insert_position(cur, msg):
    lat = msg.get("lat")
    lon = msg.get("lon")

    geom_sql = (
        "ST_SetSRID(ST_MakePoint(%(lon)s, %(lat)s), 4326)"
        if lat is not None and lon is not None
        else "NULL"
    )

    cur.execute(
        f"""
        INSERT INTO public.aircraft_positions_history (
            hex, flight, observed_at, geom, data
        )
        VALUES (
            %(hex)s, %(flight)s, now(), {geom_sql}, %(data)s::jsonb
        );
        """,
        {
            "hex": msg.get("hex"),
            "flight": (msg.get("flight") or "").strip(),
            "lat": lat,
            "lon": lon,
            "data": json.dumps(msg),
        },
    )


def upsert_live_aircraft(cur, msg):
    hex_ = msg.get("hex")
    if not hex_:
        return

    seen = _safe_float(msg.get("seen"), 0.0)

    # Keep aircraft_live strictly "recent"
    if seen > ARCHIVE_TIMEOUT_SECONDS:
        return

    lat = msg.get("lat")
    lon = msg.get("lon")

    geom_sql = (
        "ST_SetSRID(ST_MakePoint(%(lon)s, %(lat)s), 4326)"
        if lat is not None and lon is not None
        else "NULL"
    )

    cur.execute(
        f"""
        INSERT INTO public.aircraft_live (
            hex, flight, category, last_seen,
            lat, lon, alt_baro, track,
            geom, data
        )
        VALUES (
            %(hex)s, %(flight)s, %(category)s,
            now() - make_interval(secs => %(seen)s),
            %(lat)s, %(lon)s, %(alt_baro)s, %(track)s,
            {geom_sql}, %(data)s::jsonb
        )
        ON CONFLICT (hex)
        DO UPDATE SET
            flight    = EXCLUDED.flight,
            category  = EXCLUDED.category,
            last_seen = EXCLUDED.last_seen,
            lat       = EXCLUDED.lat,
            lon       = EXCLUDED.lon,
            alt_baro  = EXCLUDED.alt_baro,
            track     = EXCLUDED.track,
            geom      = EXCLUDED.geom,
            data      = EXCLUDED.data;
        """,
        {
            "hex": hex_,
            "flight": (msg.get("flight") or "").strip(),
            "category": msg.get("category"),
            "seen": seen,
            "lat": lat,
            "lon": lon,
            "alt_baro": msg.get("alt_baro"),
            "track": msg.get("track"),
            "data": json.dumps(msg),
        },
    )


def upsert_live_path(cur, msg):
    lat = msg.get("lat")
    lon = msg.get("lon")

    seen = _safe_float(msg.get("seen"), 0.0)
    seen_pos = _safe_float(msg.get("seen_pos"), 999.0)

    # We ALWAYS upsert the row so "no-position" aircraft are still tracked/archived.
    # But we only touch geom when we have a valid position and it's fresh.
    has_pos = (lat is not None and lon is not None)
    can_use_pos = has_pos and (seen_pos <= MAX_SEEN_POS_SECONDS_FOR_LINE)

    cur.execute(
        """
        INSERT INTO public.aircraft_paths_live (
            hex, flight, category,
            start_time, last_seen, geom
        )
        VALUES (
            %(hex)s, %(flight)s, %(category)s,
            now(),
            now() - make_interval(secs => %(seen)s),
            CASE
              WHEN %(can_use_pos)s THEN
                ST_SetSRID(
                  ST_MakeLine(ARRAY[ST_MakePoint(%(lon)s, %(lat)s)]),
                  4326
                )
              ELSE NULL
            END
        )
        ON CONFLICT (hex, flight)
        DO UPDATE SET
            category  = EXCLUDED.category,
            last_seen = EXCLUDED.last_seen,
            geom = CASE
              -- no usable position this tick -> keep existing geom as-is
              WHEN NOT %(can_use_pos)s THEN aircraft_paths_live.geom

              -- first usable position for this row -> start the line
              WHEN aircraft_paths_live.geom IS NULL THEN
                ST_SetSRID(
                  ST_MakeLine(ARRAY[ST_MakePoint(%(lon)s, %(lat)s)]),
                  4326
                )

              -- otherwise append point
              ELSE
                ST_AddPoint(
                  aircraft_paths_live.geom,
                  ST_SetSRID(ST_MakePoint(%(lon)s, %(lat)s), 4326)
                )
            END;
        """,
        {
            "hex": msg.get("hex"),
            "flight": (msg.get("flight") or "").strip(),
            "category": msg.get("category"),
            "lat": lat,
            "lon": lon,
            "seen": seen,
            "can_use_pos": bool(can_use_pos),
        },
    )


# ============================================================
# ARCHIVING / PRUNING (ONE CLOCK)
# ============================================================

def archive_and_prune(cur):
    # Archive only stale paths that pass truth policy
    cur.execute(
        f"""
        WITH stale AS (
            SELECT
                hex,
                flight,
                category,
                start_time,
                last_seen AS end_time,
                geom,
                EXTRACT(EPOCH FROM (last_seen - start_time)) AS duration_s,
                CASE WHEN geom IS NULL THEN 0 ELSE ST_NPoints(geom) END AS n_points,
                CASE
                    WHEN geom IS NULL THEN 0
                    ELSE ST_Length(geom::geography) / 1000.0
                END AS dist_km
            FROM public.aircraft_paths_live
            WHERE last_seen < now() - interval '{ARCHIVE_TIMEOUT_SECONDS} seconds'
        )
        INSERT INTO public.aircraft_paths_history (
            hex, flight, category, start_time, end_time, geom
        )
        SELECT
            hex, flight, category, start_time, end_time, geom
        FROM stale
        WHERE duration_s >= {MIN_DURATION_SECONDS}
          AND n_points   >= {MIN_POINTS}
          AND dist_km    >= {MIN_DISTANCE_KM}
        RETURNING hex;
        """
    )
    archived = cur.rowcount  # number inserted
    if archived:
        print(f"  → archived {archived} paths (passed thresholds)")

    # Remove stale paths from live regardless (so live stays clean)
    cur.execute(
        f"""
        DELETE FROM public.aircraft_paths_live
        WHERE last_seen < now() - interval '{ARCHIVE_TIMEOUT_SECONDS} seconds';
        """
    )

    # Prune aircraft_live as before
    cur.execute(
        f"""
        DELETE FROM public.aircraft_live
        WHERE last_seen < now() - interval '{ARCHIVE_TIMEOUT_SECONDS} seconds';
        """
    )

# ============================================================
# MAIN LOOP
# ============================================================

def run():
    print("DATA_FILE =", DATA_FILE)
    print("ARCHIVE_TIMEOUT_SECONDS =", ARCHIVE_TIMEOUT_SECONDS)

    with conn.cursor() as cur:
        while True:
            aircraft_list = read_aircraft_file()
            print(f"[LOOP] aircraft in JSON: {len(aircraft_list)}")

            for ac in aircraft_list:
                hex_ = ac.get("hex")
                if not hex_:
                    # dump1090 sometimes includes objects without hex; skip safely
                    continue

                cur.execute("SAVEPOINT sp_aircraft")

                try:
                    insert_position(cur, ac)
                    upsert_live_aircraft(cur, ac)  # writes even if lat/lon missing
                    upsert_live_path(cur, ac)      # only writes if lat/lon exists
                    cur.execute("RELEASE SAVEPOINT sp_aircraft")
                except Exception as e:
                    print("DB error:", repr(e), "hex=", hex_)
                    # Roll back only this aircraft, not the whole loop
                    cur.execute("ROLLBACK TO SAVEPOINT sp_aircraft")
                    cur.execute("RELEASE SAVEPOINT sp_aircraft")
                    continue

            archive_and_prune(cur)
            conn.commit()
            time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    run()