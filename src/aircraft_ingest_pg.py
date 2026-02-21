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
    if lat is None or lon is None:
        return

    seen = _safe_float(msg.get("seen"), 0.0)
    seen_pos = _safe_float(msg.get("seen_pos"), 999.0)

    if seen_pos > MAX_SEEN_POS_SECONDS_FOR_LINE:
        return

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
            ST_SetSRID(
              ST_MakeLine(ARRAY[ST_MakePoint(%(lon)s, %(lat)s)]),
              4326
            )
        )
        ON CONFLICT (hex, flight)
        DO UPDATE SET
            geom = ST_AddPoint(
                aircraft_paths_live.geom,
                ST_SetSRID(ST_MakePoint(%(lon)s, %(lat)s), 4326)
            ),
            last_seen = EXCLUDED.last_seen;
        """,
        {
            "hex": msg.get("hex"),
            "flight": (msg.get("flight") or "").strip(),
            "category": msg.get("category"),
            "lat": lat,
            "lon": lon,
            "seen": seen,
        },
    )


# ============================================================
# ARCHIVING / PRUNING (ONE CLOCK)
# ============================================================

def archive_and_prune(cur):
    # Archive paths
    cur.execute(
        f"""
        INSERT INTO public.aircraft_paths_history (
            hex, flight, category, start_time, end_time, geom
        )
        SELECT
            hex, flight, category, start_time, last_seen, geom
        FROM public.aircraft_paths_live
        WHERE last_seen < now() - interval '{ARCHIVE_TIMEOUT_SECONDS} seconds'
        RETURNING hex;
        """
    )
    moved = cur.fetchall()
    if moved:
        print(f"  → archived {len(moved)} flight paths")

    # Remove archived paths from live
    cur.execute(
        f"""
        DELETE FROM public.aircraft_paths_live
        WHERE last_seen < now() - interval '{ARCHIVE_TIMEOUT_SECONDS} seconds';
        """
    )

    # Prune aircraft_live
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