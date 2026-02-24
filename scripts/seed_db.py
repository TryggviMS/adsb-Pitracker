#!/usr/bin/env python3
"""
scripts/seed_db.py
Populates the database with dummy aircraft data for local development.
Usage: python scripts/seed_db.py
"""

import json
import os
import random
import time
from datetime import datetime, timedelta
from pathlib import Path

import psycopg
from dotenv import load_dotenv

# Load from .env.ingest
load_dotenv(Path(__file__).parent.parent / ".env.ingest")

DB_DSN = (
    f"dbname={os.environ['PGDATABASE']} "
    f"user={os.environ['PGUSER']} "
    f"password={os.environ['PGPASSWORD']} "
    f"host={os.environ.get('PGHOST', 'localhost')} "
    f"port={os.environ.get('PGPORT', '5432')} "
    f"sslmode=prefer"
)

# Reykjavik area bounding box
LAT_MIN, LAT_MAX = 63.8, 64.4
LON_MIN, LON_MAX = -22.8, -21.2

DUMMY_AIRCRAFT = [
    {"hex": "4cc581", "flight": "ICE501", "category": "A3"},
    {"hex": "4cc4d1", "flight": "ICE48R", "category": "A2"},
    {"hex": "4cc2a6", "flight": "ICE63L", "category": "A4"},
    {"hex": "4cc547", "flight": "ICE202", "category": "A3"},
    {"hex": "4ac8a8", "flight": "BAW123", "category": "A5"},
    {"hex": "3c6444", "flight": "DLH456", "category": "A3"},
    {"hex": "a12345", "flight": "AAL789", "category": "A3"},
    {"hex": "e12345", "flight": "RYR001", "category": "A2"},
]


def random_position(center_lat=64.13, center_lon=-21.94, radius=0.3):
    lat = center_lat + random.uniform(-radius, radius)
    lon = center_lon + random.uniform(-radius, radius)
    return round(lat, 6), round(lon, 6)


def random_altitude():
    return random.choice([1000, 2000, 3000, 5000, 8000, 10000, 15000, 30000, 35000])


def seed(conn):
    now = datetime.utcnow()

    with conn.cursor() as cur:
        for ac in DUMMY_AIRCRAFT:
            lat, lon = random_position()
            alt = random_altitude()
            track = round(random.uniform(0, 360), 1)
            seen = round(random.uniform(0, 5), 1)

            data = {
                "hex": ac["hex"],
                "flight": ac["flight"],
                "category": ac["category"],
                "lat": lat,
                "lon": lon,
                "alt_baro": alt,
                "track": track,
                "seen": seen,
                "seen_pos": seen,
                "gs": round(random.uniform(200, 500), 1),
                "messages": random.randint(100, 1000),
                "rssi": round(random.uniform(-30, -10), 1),
                "mlat": [],
                "tisb": [],
            }

            # Insert into aircraft_live
            cur.execute(
                """
                INSERT INTO public.aircraft_live (
                    hex, flight, category, last_seen,
                    lat, lon, alt_baro, track, geom, data
                )
                VALUES (
                    %(hex)s, %(flight)s, %(category)s,
                    now() - make_interval(secs => %(seen)s),
                    %(lat)s, %(lon)s, %(alt_baro)s, %(track)s,
                    ST_SetSRID(ST_MakePoint(%(lon)s, %(lat)s), 4326),
                    %(data)s::jsonb
                )
                ON CONFLICT (hex) DO UPDATE SET
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
                    "hex": ac["hex"],
                    "flight": ac["flight"],
                    "category": ac["category"],
                    "seen": seen,
                    "lat": lat,
                    "lon": lon,
                    "alt_baro": alt,
                    "track": track,
                    "data": json.dumps(data),
                },
            )

            # Insert a path into aircraft_paths_history
            start_time = now - timedelta(minutes=random.randint(10, 60))
            end_time = now - timedelta(minutes=random.randint(1, 9))

            points = []
            for _ in range(random.randint(5, 20)):
                plat, plon = random_position()
                points.append(f"{plon} {plat}")

            linestring = f"LINESTRING({', '.join(points)})"

            cur.execute(
                """
                INSERT INTO public.aircraft_paths_history (
                    hex, flight, category, start_time, end_time, geom
                )
                VALUES (
                    %(hex)s, %(flight)s, %(category)s,
                    %(start_time)s, %(end_time)s,
                    ST_GeomFromText(%(geom)s, 4326)
                );
                """,
                {
                    "hex": ac["hex"],
                    "flight": ac["flight"],
                    "category": ac["category"],
                    "start_time": start_time,
                    "end_time": end_time,
                    "geom": linestring,
                },
            )

            print(f"  seeded {ac['flight']} ({ac['hex']}) at {lat}, {lon} alt={alt}ft")

        conn.commit()
        print(f"\nDone — seeded {len(DUMMY_AIRCRAFT)} aircraft.")


if __name__ == "__main__":
    print("Connecting to DB...")
    conn = psycopg.connect(DB_DSN)
    print("Seeding dummy aircraft data...\n")
    seed(conn)
    conn.close()
