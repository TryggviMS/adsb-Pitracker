# Docker Setup – adsb-Pitracker

This project uses Docker for:

- dump1090 (ADS-B receiver)
- nginx (web frontend)
- PostgreSQL (database)

Python services (aircraft_ingest_pg.py and aircraft_digest_flask.py) run via systemd and are NOT containerized.

All commands assume you are inside the project root directory:

cd ~/Documents/adsb-Pitracker

---

# 1. dump1090 (ADS-B Receiver)

## Build Image

cd docker/dump1090
sudo docker build -t dump1090-fa-arm64:latest .

Return to project root:

cd ../../

## Run Container (Portable – No Absolute Paths)

sudo docker run -d \
  --name dump1090 \
  --restart unless-stopped \
  --privileged \
  --device /dev/bus/usb:/dev/bus/usb \
  -p 8080:8080 \
  -v $(pwd)/web/static/data:/data \
  dump1090-fa-arm64:latest

## View Logs

sudo docker logs -f dump1090

---

# 2. nginx (Web Frontend)

## Start via Docker Compose

cd docker/nginx
sudo docker compose up -d

sudo docker compose restart adsb-web

Return to project root:

cd ../../

## View Logs

sudo docker logs -f adsb-web

---

# 3. PostgreSQL

## Start Database (using root level env file)

cd docker/postgres
sudo docker compose --env-file ../../.env.postgres up -d


Return to project root:

cd ../../

## View Logs

sudo docker logs -f postgis_db

(Adjust container name if different.)

---

# Docker Management Commands

## List Running Containers

sudo docker ps

## Stop Container

sudo docker stop <container_name>

## Restart Container

sudo docker restart <container_name>

## Remove Container

sudo docker rm <container_name>

---

# Notes

- No absolute filesystem paths are used.
- The project can now be moved anywhere without changing Docker commands.


# Python

cd docker/python
docker compose up -d

# Shared network
the key to cross-compose communication
Since you're using separate compose files, create one shared network once:
bashdocker network create adsb_net