23.02.2026 - 
mOVING TO python docker containers,
1. Stale aircraft.json baked into image
The Dockerfile copies web/static/data/ into the image at build time, so the container had a static snapshot. Fixed by mounting the live dump1090 data directory as a volume:
yamlvolumes:
  - /home/trygg/Documents/adsb-Pitracker/web/static/data:/app/web/static/data
2. Postgres not on adsb_net
The postgres container was on its own postgres_default network and couldn't be reached by the Python containers. Fixed by adding adsb_net to the postgres compose file and connecting manually with:
bashdocker network connect adsb_net postgis_db
3. Wrong PGHOST in env files
Env files had PGHOST=127.0.0.1 which doesn't work inside Docker. Changed to PGHOST=db to use the service name on adsb_net.
4. ADSB_DATA_FILE pointing to Pi filesystem path
.env.ingest had /home/trygg/Documents/... which doesn't exist inside the container. Changed to /app/web/static/data/aircraft.json.
5. Missing gunicorn in requirements.txt
Gunicorn wasn't listed so the Flask container failed to start. Fixed by adding it to requirements.txt.