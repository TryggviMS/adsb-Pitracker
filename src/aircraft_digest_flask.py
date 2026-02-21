from flask import Flask, jsonify
from flask_cors import CORS
import psycopg
import json
import os

app = Flask(__name__)
CORS(app)

# Database connection (read from environment)
conn = psycopg.connect(
    dbname=os.environ["PGDATABASE"],
    user=os.environ["PGUSER"],
    password=os.environ["PGPASSWORD"],
    host=os.environ.get("PGHOST", "localhost"),
    port=os.environ.get("PGPORT", "5432"),
)

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
                    "flight": (flight or "").strip(),
                    "category": category
                },
                "geometry": json.loads(geom_json) if geom_json else None
            })
        return jsonify({
            "type": "FeatureCollection",
            "features": features
        })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)