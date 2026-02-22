# ============================================================
# 3) FLASK API UPDATE
# Endpoints:
#   - /live_aircraft
#   - /live_paths
# ============================================================

import json
import os
import time
import subprocess
from flask import jsonify
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
            a.hex,
            a.flight,
            a.category,
            a.lat,
            a.lon,
            a.alt_baro,
            a.track,
            EXTRACT(EPOCH FROM a.last_seen) AS last_seen_epoch,
            p.total_length_km
            FROM public.aircraft_live a
            LEFT JOIN public.aircraft_paths_live p
            ON p.hex = a.hex
            AND p.flight = a.flight
            WHERE a.last_seen > now() - interval '60 seconds'
            ORDER BY a.last_seen DESC;
            """
        )

        aircraft = []
        for hex_, flight, category, lat, lon, alt_baro, track, last_seen_epoch, total_length_km in cur.fetchall():
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
                    "total_length_km": total_length_km
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
  CASE
    WHEN COUNT(geom) = 0 THEN NULL
    ELSE ST_AsGeoJSON(ST_LineMerge(ST_Collect(geom)))
  END AS geom,
  CASE
    WHEN COUNT(geom) = 0 THEN NULL
    ELSE ROUND((ST_Length(ST_LineMerge(ST_Collect(geom))::geography) / 1000.0)::numeric, 1)::double precision
  END AS total_length_km
FROM src
GROUP BY hex, flight, category
ORDER BY MAX(end_time) DESC;
            """
        )

        features = []
        for hex_, flight, category, start_time, end_time, geom_json, total_length_km in cur.fetchall():
         

            features.append(
                {
                    "type": "Feature",
                    "properties": {
                        "hex": hex_,
                        "flight": (flight or "").strip(),
                        "category": category,
                        "start_time": start_time.isoformat() if start_time else None,
                        "end_time": end_time.isoformat() if end_time else None,
                        "total_length_km": total_length_km
                    },
                    "geometry": json.loads(geom_json) if geom_json else None,
                }
            )

    return jsonify({"type": "FeatureCollection", "features": features})


@app.route("/stats")
def stats():
    with conn.cursor() as cur:
        cur.execute(
            """
            WITH t AS (
              SELECT
                date_trunc('day',  now()) AS day0,
                date_trunc('week', now()) AS week0,
                now() - interval '1 hour' AS hour0
            ),

            src AS (
              -- archived paths
              SELECT
                hex,
                flight,
                category,
                start_time,
                end_time
              FROM public.aircraft_paths_history

              UNION ALL

              -- live paths: use last_seen as end_time (NOT now())
              SELECT
                p.hex,
                p.flight,
                p.category,
                p.start_time,
                p.last_seen AS end_time
              FROM public.aircraft_paths_live p
              WHERE p.last_seen > now() - interval '60 seconds'
            ),

            grouped AS (
              SELECT
                hex,
                flight,
                category,
                MIN(start_time) AS start_time,
                MAX(end_time)   AS end_time
              FROM src
              GROUP BY hex, flight, category
            )

            SELECT
              (SELECT COUNT(*) FROM public.aircraft_paths_history) AS total,
              COUNT(*) FILTER (WHERE end_time >= (SELECT week0 FROM t)) AS week,
              COUNT(*) FILTER (WHERE end_time >= (SELECT day0  FROM t)) AS today,
              COUNT(*) FILTER (WHERE end_time >= (SELECT hour0 FROM t)) AS hour,
              MAX(end_time) AS last_flight_at
            FROM grouped;
            """
        )

        total, week, today, hour, last_flight_at = cur.fetchone()

    return jsonify(
        {
            "total": int(total or 0),
            "week": int(week or 0),
            "today": int(today or 0),
            "hour": int(hour or 0),
            "last_flight_at": last_flight_at.isoformat() if last_flight_at else None,
        }
    )



if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)