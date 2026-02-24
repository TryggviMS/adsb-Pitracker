# Docker Setup – adsb-Pitracker

This project uses Docker for all services:

- dump1090 (ADS-B receiver)
- nginx (web frontend)
- PostgreSQL + PostGIS (database)
- Python services (aircraft_ingest_pg.py and aircraft_digest_flask.py)

All commands assume you are inside the project root:

    cd ~/Documents/adsb-Pitracker

---

## Shared Network

All containers communicate via a shared Docker network. Create it once:

    docker network create adsb_net

If postgres didn't join the network automatically:

    docker network connect adsb_net postgis_db

Verify all containers are on the network:

    docker network inspect adsb_net | grep Name

---

## 1. dump1090 (ADS-B Receiver)

### Build Image

    cd docker/dump1090
    sudo docker build -t dump1090-fa-arm64:latest .
    cd ../../

### Run Container

    sudo docker run -d \
      --name dump1090 \
      --restart unless-stopped \
      --privileged \
      --device /dev/bus/usb:/dev/bus/usb \
      -p 8080:8080 \
      -v $(pwd)/web/static/data:/data \
      dump1090-fa-arm64:latest

### View Logs

    sudo docker logs -f dump1090

---

## 2. nginx (Web Frontend)

    cd docker/nginx
    docker compose up -d
    cd ../../

### View Logs

    docker logs -f adsb-web

---

## 3. PostgreSQL

    cd docker/postgres
    docker compose --env-file ../../.env.postgres up -d
    cd ../../

### View Logs

    docker logs -f postgis_db

### Connect to Database

    docker exec -it postgis_db psql -U admin -d spatial_db

### Useful Queries

    -- Live aircraft count
    docker exec -it postgis_db psql -U admin -d spatial_db -c "SELECT COUNT(*) FROM public.aircraft_live;"

    -- Path history count
    docker exec -it postgis_db psql -U admin -d spatial_db -c "SELECT COUNT(*) FROM public.aircraft_paths_history;"
    docker exec -it postgis_db psql -U admin -d spatial_db -c "SELECT hex FROM public.aircraft_live;"

---

## 4. Python Services

    cd docker/python
    docker compose up -d --build
    cd ../../

### View Logs

    docker compose logs -f

### Rebuild After Code Changes

    docker compose down
    docker compose up -d --build

---

## Recompose Everything

Use the script to bring all containers down and back up in the correct order:

    ./scripts/recompose.sh
    ./scripts/recompose.sh --dev
    ./scripts/recompose.sh --dev --seed


---

## Dev on WSL2

Use the dev override to mount live source files and enable Flask debug mode:

    cd docker/python
    docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d

This mounts:
- `src/` for live Python code reloading
- `web/static/data/` for the local aircraft.json (gitignored, not in image)

Test Flask endpoints directly:

    curl http://localhost:5000/live_aircraft
    curl http://localhost:5000/healthz
    curl http://localhost:5000/stats

Note: nginx is not required for WSL2 dev — access Flask directly on port 5000.

---

## Docker Management

    # List running containers
    docker ps

    # Stop a container
    docker stop <container_name>

    # Restart a container
    docker restart <container_name>

    # Remove a container
    docker rm <container_name>

    # View logs
    docker logs -f <container_name>

---

## Notes

- Env files (.env.ingest, .env.api, .env.postgres) are gitignored and must be created manually on each machine.
- See .env.api.example for required variables.
- Python containers use restart: unless-stopped — they will start automatically on reboot.
- dump1090 only runs on the Pi with physical USB hardware.
- See docs/TROUBLESHOOTING.md for common issues and fixes.