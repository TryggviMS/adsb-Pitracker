# systemd Setup – adsb-Pitracker (Production Configuration)

This setup uses:
- Separate environment files for API and ingest
- gunicorn for Flask (production-ready)
- Local binding (127.0.0.1) so only nginx can expose it later
- Least-privilege database users

====================================================================
ENVIRONMENT FILES
====================================================================

Create two environment files:

/home/trygg/Documents/adsb-Pitracker/.env.api
/home/trygg/Documents/adsb-Pitracker/.env.ingest

Example:

.env.api
PGHOST=127.0.0.1
PGPORT=5432
PGDATABASE=spatial_db
PGUSER=adsb_api
PGPASSWORD=STRONG_API_PASSWORD

.env.ingest
PGHOST=127.0.0.1
PGPORT=5432
PGDATABASE=spatial_db
PGUSER=adsb_ingest
PGPASSWORD=STRONG_INGEST_PASSWORD
ADSB_DATA_FILE=/home/trygg/Documents/adsb-Pitracker/web/static/data/aircraft.json

Secure them:
chmod 600 /home/trygg/Documents/adsb-Pitracker/.env.api
chmod 600 /home/trygg/Documents/adsb-Pitracker/.env.ingest

====================================================================
SERVICE FILES
====================================================================

adsb_flask.service

[Unit]
Description=ADS-B Flask API (gunicorn)
After=network.target docker.service
Requires=docker.service

[Service]
User=trygg
WorkingDirectory=/home/trygg/Documents/adsb-Pitracker
EnvironmentFile=/home/trygg/Documents/adsb-Pitracker/.env.api

ExecStart=/home/trygg/Documents/adsb-Pitracker/.venv/bin/gunicorn --workers 2 --threads 4 --timeout 30 --bind 172.17.0.1:5000 src.aircraft_digest_flask:app

Restart=always
RestartSec=5
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=full

[Install]
WantedBy=multi-user.target


adsb_ingest.service

[Unit]
Description=ADS-B Ingestion Worker
After=network.target docker.service
Requires=docker.service

[Service]
User=trygg
WorkingDirectory=/home/trygg/Documents/adsb-Pitracker
EnvironmentFile=/home/trygg/Documents/adsb-Pitracker/.env.ingest

ExecStart=/home/trygg/Documents/adsb-Pitracker/.venv/bin/python -u src/aircraft_ingest_pg.py

Restart=always
RestartSec=5
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=full
ReadWritePaths=/home/trygg/Documents/adsb-Pitracker

[Install]
WantedBy=multi-user.target

====================================================================
INSTALL SERVICES
====================================================================

sudo cp systemd/adsb_ingest.service /etc/systemd/system/
sudo cp systemd/adsb_flask.service /etc/systemd/system/
sudo systemctl daemon-reload

Enable at boot:
sudo systemctl enable adsb_ingest
sudo systemctl enable adsb_flask

Start services:
sudo systemctl start adsb_ingest
sudo systemctl start adsb_flask

====================================================================
RESTART / STOP SERVICES
====================================================================

Restart:
sudo systemctl restart adsb_ingest
sudo systemctl restart adsb_flask

Stop:
sudo systemctl stop adsb_ingest
sudo systemctl stop adsb_flask

Start:
sudo systemctl start adsb_ingest
sudo systemctl start adsb_flask

Check status:
systemctl status adsb_ingest
systemctl status adsb_flask

====================================================================
LOGS
====================================================================

Follow live logs:
sudo journalctl -u adsb_ingest -f
sudo journalctl -u adsb_flask -f

Show last 200 lines:
sudo journalctl -u adsb_ingest -n 200
sudo journalctl -u adsb_flask -n 200

====================================================================
AFTER CODE CHANGES
====================================================================

Restart services:
sudo systemctl restart adsb_ingest
sudo systemctl restart adsb_flask

If dependencies changed:
cd /home/trygg/Documents/adsb-Pitracker
source .venv/bin/activate
pip install -r requirements.txt
deactivate
sudo systemctl restart adsb_ingest adsb_flask

====================================================================
REMOVE SERVICES
====================================================================

sudo systemctl disable adsb_ingest adsb_flask
sudo rm /etc/systemd/system/adsb_ingest.service
sudo rm /etc/systemd/system/adsb_flask.service
sudo systemctl daemon-reload

====================================================================
CODE NOTES
====================================================================

Flask:
- Ensure debug=False
- Do not expose 0.0.0.0 when using gunicorn
- No dotenv needed (systemd injects env vars)

Ingest:
- No code change required
- Uses .env.ingest for DB credentials

====================================================================