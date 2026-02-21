"""
ADS-B ingestion worker reading dump1090 aircraft.json.

Reads file repeatedly and processes aircraft list.
Prints debug info into console for each step.
"""

import os
import json
import time
import psycopg
from pathlib import Path

# --- Config (env first, then defaults) ------------------------

# --- Aircraft JSON location ---
DEFAULT_DATA_FILE = Path.cwd() / "web" / "static" / "data" / "aircraft.json"
DATA_FILE = Path(os.environ.get("ADSB_DATA_FILE", DEFAULT_DATA_FILE))

# --- Database (required) ---
DB_NAME = os.environ["PGDATABASE"]
DB_USER = os.environ["PGUSER"]
DB_PASS = os.environ["PGPASSWORD"]
DB_HOST = os.environ.get("PGHOST", "localhost")
DB_PORT = os.environ.get("PGPORT", "5432")


conn = psycopg.connect(
    f"dbname={DB_NAME} user={DB_USER} password={DB_PASS} host={DB_HOST} port={DB_PORT}"
)
conn.autocommit = False


def read_aircraft_file():
    """Read aircraft.json safely. Returns list of aircraft dicts."""
    try:
        with DATA_FILE.open("r") as f:
            data = json.load(f)
            return data.get("aircraft", [])
    except Exception:
        # File may be mid-write; skip this cycle
        return []


def insert_position(cur, msg):
    """Insert raw ADS-B message into history table."""
    lat = msg.get("lat")
    lon = msg.get("lon")

    # Build geom in SQL only if lat/lon exist
    geom_sql = (
        f"ST_SetSRID(ST_MakePoint({lon}, {lat}), 4326)"
        if lat is not None and lon is not None
        else "NULL"
    )

    cur.execute(
        f"""
        INSERT INTO public.aircraft_positions_history (
            hex,
            flight,
            observed_at,
            geom,
            data
        )
        VALUES (
            %(hex)s,
            %(flight)s,
            now(),
            {geom_sql},
            %(data)s::jsonb
        );
        """,
        {
            "hex": msg.get("hex"),
            "flight": (msg.get("flight") or "").strip(),
            "data": json.dumps(msg),
        },
    )
    print(f"  → inserted into aircraft_positions_history (hex={msg.get('hex')})")


def upsert_live_path(cur, msg):
    """Insert or append to live flight line if coordinates exist."""
    if msg.get("lat") is None or msg.get("lon") is None:
        return

    cur.execute(
        """
        INSERT INTO public.aircraft_paths_live (
            hex,
            flight,
            category,
            start_time,
            last_seen,
            geom
        )
        VALUES (
            %(hex)s,
            %(flight)s,
            %(category)s,
            now(),
            now(),
            ST_SetSRID(ST_MakeLine(ARRAY[ST_MakePoint(%(lon)s, %(lat)s)]), 4326)
        )
        ON CONFLICT (hex, flight)
        DO UPDATE
        SET
            geom = ST_AddPoint(
                aircraft_paths_live.geom,
                ST_SetSRID(ST_MakePoint(%(lon)s, %(lat)s), 4326)
            ),
            last_seen = now();
        """,
        {
            "hex": msg.get("hex"),
            "flight": (msg.get("flight") or "").strip(),
            "category": msg.get("category"),
            "lat": msg.get("lat"),
            "lon": msg.get("lon"),
        },
    )
    print(f"  → upserted into aircraft_paths_live (hex={msg.get('hex')})")


def archive_completed_flights(cur, timeout_minutes=3):
    """Move inactive flights from live to history table."""
    cur.execute(
        f"""
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
        WHERE last_seen < now() - interval '{timeout_minutes} minutes'
        RETURNING hex;
        """
    )
    moved = cur.fetchall()
    if moved:
        print(f"  → archived {len(moved)} flights into aircraft_paths_history")

        cur.execute(
            f"""
            DELETE FROM public.aircraft_paths_live
            WHERE last_seen < now() - interval '{timeout_minutes} minutes';
            """
        )


def run():
    """Main polling loop with debug prints."""
    with conn.cursor() as cur:
        while True:
            print("\n[LOOP RUNNING]")
            print(f"  Reading: {DATA_FILE}")

            aircraft_list = read_aircraft_file()
            print(f"  Found {len(aircraft_list)} aircraft in JSON")

            for aircraft in aircraft_list:
                insert_position(cur, aircraft)
                upsert_live_path(cur, aircraft)

            archive_completed_flights(cur)

            conn.commit()
            time.sleep(2)


if __name__ == "__main__":
    run()