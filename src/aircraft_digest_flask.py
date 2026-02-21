# ============================================================
# 3) FLASK API UPDATE
# Add endpoint: /live_aircraft
# ============================================================

from flask import Flask, jsonify
from flask_cors import CORS
import psycopg
import json
import os
import time

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
        cur.execute("""
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
        """)
        aircraft = []
        for row in cur.fetchall():
            hex, flight, category, lat, lon, alt_baro, track, last_seen_epoch = row
            aircraft.append({
                "hex": hex,
                "flight": (flight or "").strip(),
                "category": category,
                "lat": lat,
                "lon": lon,
                "alt_baro": alt_baro,
                "track": track,
                "last_seen": last_seen_epoch,
            })

        return jsonify({
            "generated_at": time.time(),
            "aircraft": aircraft
        })
@app.route("/live_paths")
def live_paths():
    """Return current live flight paths as GeoJSON."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT
                hex,
                flight,
                category,
                ST_AsGeoJSON(geom) AS geom
            FROM public.aircraft_paths_live;
        """)
        features = []
        for row in cur.fetchall():
            hex, flight, category, geom_json = row
            features.append({
                "type": "Feature",
                "properties": {
                    "hex": hex,
                    "flight": flight.strip(),
                    "category": category
                },
                "geometry": json.loads(geom_json)
            })
        return jsonify({
            "type": "FeatureCollection",
            "features": features
        })
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)