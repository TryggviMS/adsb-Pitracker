# adsb-Pitracker

A Raspberry Pi–based ADS-B aircraft tracker that receives, stores, and visualises live aircraft data.

This project builds a usable airplane tracker using:

- A Raspberry Pi + RTL-SDR receiver
- dump1090 for ADS-B signal decoding
- PostgreSQL + PostGIS for storage
- Flask + gunicorn API for serving aircraft data
- nginx (Docker) as a reverse proxy
- A Leaflet.js web frontend for live visualisation
- Cloudflare Tunnel for public access
- systemd for service management

---

## 📦 Requirements

- Raspberry Pi 4 (Debian / Raspberry Pi OS 64-bit)
- Python 3.9+
- PostgreSQL with PostGIS extension
- Docker + Docker Compose
- Git

---

## 🚀 Quick Start
```bash
git clone https://github.com/TryggviMS/adsb-Pitracker.git
cd adsb-Pitracker

chmod +x bootstrap.sh
./bootstrap.sh

source .venv/bin/activate
```

---

## 🗂 Project Structure
```
adsb-Pitracker/
├── src/                  # Flask API
├── web/static/           # Frontend (HTML, JS, CSS)
├── docker/nginx/         # nginx config + docker-compose
├── systemd/              # systemd service files
├── scripts/              # Maintenance scripts
└── .env.api              # Environment variables (not committed)
```

---

## 🔧 Services

| Service | How it runs | Port |
|---|---|---|
| dump1090 | Docker | — |
| PostgreSQL + PostGIS | Docker | 5432 |
| Flask + gunicorn | systemd | 172.17.0.1:5000 |
| nginx | Docker | 8081 |
| Cloudflare Tunnel | systemd | — |

---

## 🛠 Useful Commands
```bash
# Check all services
sudo systemctl status adsb_flask
docker ps

# Restart Flask
sudo systemctl restart adsb_flask

# Restart nginx
docker compose -f docker/nginx/docker-compose.yml restart adsb-web

# View Flask logs
sudo journalctl -u adsb_flask -f

# View nginx logs
docker logs adsb-web -f

# Run maintenance cleanup
./scripts/cleanup_pi.sh
```

---

## 🌍 Public Access

The tracker is publicly accessible via Cloudflare Tunnel at [geoform.work](https://geoform.work).

---

## 📝 Environment Variables

Copy `.env.api.example` to `.env.api` and fill in your values:
```
PGDATABASE=
PGUSER=
PGPASSWORD=
PGHOST=
PGPORT=
```


## 🏗 Architecture
```
USB SDR
   ↓
dump1090 (Docker)
   ↓ writes JSON
web/static/data/
   ↓
aircraft_ingest_pg.py (systemd)
   ↓
PostgreSQL + PostGIS (Docker)
   ↓
aircraft_digest_flask.py / gunicorn (systemd)
   ↓
nginx (Docker) :8081
   ↓
Cloudflare Tunnel
   ↓
Browser (geoform.work)
```


## 🏗 To-Do

- Categories
- Hex codes
- Landhelgisgæslan
- Airlines
- Quality of signal

- Fix docker/postgres/init-registry.sh
