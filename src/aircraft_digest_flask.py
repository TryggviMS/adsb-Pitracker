# ============================================================
# 3) FLASK API UPDATE
# Endpoints:
#   - /live_aircraft
#   - /live_paths
# ============================================================

import json
import os
import time

import psycopg
from flask import Flask, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

conn = psycopg.connect(
    dbname=os.environ["PGDATABASE"],
    user=os.environ["PGUSER"],
    password=os.environ["PGPASSWORD"],
    host=os.environ.get("PGHOST", "localhost"),
    port=os.environ.get("PGPORT", "5432"),
)


@app.route("/live_aircraft")
def live_aircraft():
    """Return latest aircraft state for markers + sidebar."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
              hex,
              flight,
              category,
              lat,
              lon,
              alt_baro,
              track,
              EXTRACT(EPOCH FROM last_seen) AS last_seen_epoch
            FROM public.aircraft_live
            WHERE last_seen > now() - interval '60 seconds'
            ORDER BY last_seen DESC;
            """
        )

        aircraft = []
        for hex_, flight, category, lat, lon, alt_baro, track, last_seen_epoch in cur.fetchall():
            aircraft.append(
                {
                    "hex": hex_,
                    "flight": (flight or "").strip(),
                    "category": category,
                    "lat": lat,
                    "lon": lon,
                    "alt_baro": alt_baro,
                    "track": track,
                    "last_seen": last_seen_epoch,
                }
            )

    return jsonify({"generated_at": time.time(), "aircraft": aircraft})


@app.route("/live_paths")
def live_paths():
    """Return current live flight paths as GeoJSON FeatureCollection."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
              hex,
              flight,
              category,
              ST_AsGeoJSON(geom) AS geom
            FROM public.aircraft_paths_live;
            """
        )

        features = []
        for hex_, flight, category, geom_json in cur.fetchall():
            if not geom_json:
                continue

            features.append(
                {
                    "type": "Feature",
                    "properties": {
                        "hex": hex_,
                        "flight": (flight or "").strip(),
                        "category": category,
                    },
                    "geometry": json.loads(geom_json),
                }
            )

    return jsonify({"type": "FeatureCollection", "features": features})

@app.route("/paths_since_midnight")
def paths_since_midnight():
    """Return all aircraft paths that overlap today (since midnight) as GeoJSON."""
    with conn.cursor() as cur:
        cur.execute(
            """
            WITH midnight AS (
              SELECT date_trunc('day', now()) AS t0
            ),
            src AS (
              -- archived paths that overlap today
              SELECT
                hex,
                flight,
                category,
                start_time,
                end_time,
                geom
              FROM public.aircraft_paths_history, midnight
              WHERE end_time >= midnight.t0

              UNION ALL

              -- live paths that overlap today
              SELECT
                hex,
                flight,
                category,
                start_time,
                now() AS end_time,
                geom
              FROM public.aircraft_paths_live, midnight
              WHERE last_seen >= midnight.t0
            )
            SELECT
              hex,
              flight,
              category,
              MIN(start_time) AS start_time,
              MAX(end_time)   AS end_time,
              ST_AsGeoJSON(ST_LineMerge(ST_Collect(geom))) AS geom
            FROM src
            WHERE geom IS NOT NULL
            GROUP BY hex, flight, category
            ORDER BY MAX(end_time) DESC;
            """
        )

        features = []
        for hex_, flight, category, start_time, end_time, geom_json in cur.fetchall():
            if not geom_json:
                continue

            features.append(
                {
                    "type": "Feature",
                    "properties": {
                        "hex": hex_,
                        "flight": (flight or "").strip(),
                        "category": category,
                        "start_time": start_time.isoformat() if start_time else None,
                        "end_time": end_time.isoformat() if end_time else None,
                    },
                    "geometry": json.loads(geom_json),
                }
            )

    return jsonify({"type": "FeatureCollection", "features": features})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)