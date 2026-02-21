USB SDR
   ↓
dump1090 (Docker)
   ↓ writes JSON
web/data/
   ↓
aircraft_ingest_pg.py (systemd)
   ↓
PostgreSQL (Docker)
   ↓
aircraft_digest_flask.py (systemd)
   ↓
nginx (Docker)
   ↓
Browser