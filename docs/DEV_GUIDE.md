# Developer Guide – adsb-Pitracker

This guide covers how to set up a local development environment on Windows (via WSL2) and how to work with the project day-to-day.

---

## Prerequisites

- Windows 10/11 with WSL2 installed (Ubuntu)
- Docker Desktop for Windows with WSL2 integration enabled
- Git
- UV (Python package manager)

### Install UV

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.bashrc
```

### Install Docker Desktop

Download from docker.com. During install, enable "Use WSL2 based engine". After installing:

Docker Desktop → Settings → Resources → WSL Integration → enable Ubuntu → Apply & Restart

---

## First Time Setup

### 1. Clone the repo inside WSL2

Always clone inside WSL2, not on the Windows filesystem (`/mnt/c/...`). File performance and Docker volume mounts work much better this way.

```bash
cd ~
git clone <repo-url>
cd adsb-Pitracker
```

### 2. Create env files

Env files are gitignored and must be created manually on each machine. Use the example file as a reference:

```bash
cat .env.api.example
```

Create the three env files:

**.env.ingest**
```dotenv
PGHOST=db
PGPORT=5432
PGDATABASE=spatial_db
PGUSER=adsb_ingest
PGPASSWORD=adsb_ingest_password
ADSB_DATA_FILE=/app/web/static/data/aircraft.json
```

**.env.api**
```dotenv
PGHOST=db
PGPORT=5432
PGDATABASE=spatial_db
PGUSER=adsb_api
PGPASSWORD=adsb_api_password
```

**.env.postgres**
```dotenv
PGDATABASE=spatial_db
PGUSER=admin
PGPASSWORD=your_password
PGHOST=db
PGPORT=5432
```

> On the Pi, these files contain real production credentials and are never overwritten by git pull.

### 3. Create the shared Docker network

Only needed once per machine:

```bash
docker network create adsb_net
```

### 4. Start all containers

```bash
chmod +x scripts/recompose.sh
./scripts/recompose.sh --dev
```

This starts Postgres, Python (ingest + Flask), and nginx in dev mode with live source mounting and port 5433 exposed for external DB access.

---

## Daily Dev Workflow

### Start everything

```bash
./scripts/recompose.sh --dev
```

### Start with dummy aircraft data

```bash
./scripts/recompose.sh --dev --seed
```

### Simulate live aircraft movement

Run the simulator in a separate terminal — it writes to `aircraft.json` every 2 seconds, which the ingest container picks up via volume mount:

```bash
python scripts/simulate_aircraft.py 
or
uv run scripts/simulate_aircraft.py
```

Aircraft randomly appear and disappear to simulate real traffic. No dump1090 hardware needed.

### Test Flask endpoints

```bash
curl http://localhost:5000/live_aircraft
curl http://localhost:5000/healthz
curl http://localhost:5000/stats
curl http://localhost:5000/live_paths
curl http://localhost:5000/paths_since_midnight
```

### View logs

```bash
# Python containers
cd docker/python
docker compose logs -f

# Specific service
docker compose logs -f adsb-flask
docker compose logs -f adsb-ingest
```

### Connect to the database

From WSL2 terminal (uses port 5433 in dev):

```bash
PGPASSWORD=your_password psql -h localhost -p 5433 -U admin -d spatial_db
```

Or via pgAdmin on Windows:
- Host: `localhost`
- Port: `5433`
- Database: `spatial_db`
- Username: `admin`

Or directly inside the container:

```bash
docker exec -it postgis_db psql -U admin -d spatial_db
```

### Useful DB queries

```sql
-- Live aircraft
SELECT hex, flight, lat, lon, last_seen FROM public.aircraft_live;

-- Count live aircraft
SELECT COUNT(*) FROM public.aircraft_live;

-- Path history
SELECT hex, flight, start_time, end_time, total_length_km FROM public.aircraft_paths_history;

-- Count path history
SELECT COUNT(*) FROM public.aircraft_paths_history;
```

---

## Project Structure

```
adsb-Pitracker/
├── src/
│   ├── aircraft_ingest_pg.py     # reads aircraft.json, writes to postgres
│   └── aircraft_digest_flask.py  # Flask API serving the web UI
├── web/static/                   # frontend (HTML, JS, CSS, icons)
│   └── data/                     # aircraft.json written by dump1090 (gitignored)
├── docker/
│   ├── dump1090/                 # ADS-B receiver (Pi only)
│   ├── nginx/                    # web frontend + reverse proxy
│   ├── postgres/                 # PostGIS database
│   └── python/                   # ingest + Flask containers
├── scripts/
│   ├── recompose.sh              # bring all containers up/down
│   ├── simulate_aircraft.py      # fake aircraft for dev (no hardware needed)
│   └── seed_db.py                # one-shot DB population with dummy data
└── docs/                         # documentation
```

---

## Dev vs Prod Differences

| | Dev (WSL2) | Prod (Pi) |
|---|---|---|
| Aircraft data | `simulate_aircraft.py` or static file | dump1090 hardware |
| Postgres port | `5433` (external), `5432` (internal) | `5432` only |
| Flask | Debug mode, live reload | Gunicorn, 2 workers |
| Env files | Dev credentials | Real credentials |
| nginx | Direct Flask access on `:5000` | Proxies to `adsb-flask:5000` |

---

## Making Changes

### Python scripts

With `--dev` mode, `src/` is mounted as a volume. Flask restarts automatically on file changes. The ingest script requires a container restart:

```bash
cd docker/python
docker compose restart adsb-ingest
```

### nginx config

```bash
cd docker/nginx
docker compose down
docker compose up -d
```

### After changing requirements.txt

Rebuild the Python image:

```bash
cd docker/python
docker compose down
docker compose up -d --build
```

---

## Deploying to the Pi

```bash
# on WSL2
git push

# on Pi
git pull
./scripts/recompose.sh   # no --dev flag
```

The Pi env files are gitignored so they are never overwritten by git pull.

---

## Troubleshooting

See `docs/TROUBLESHOOTING.md` for common issues and fixes.
