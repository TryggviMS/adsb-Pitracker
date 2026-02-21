# adsb-Pitracker

A Raspberry Pi–based ADS-B aircraft tracker.

This project builds a usable airplane tracker using:

- A Raspberry Pi
- An ADS-B antenna/receiver
- PostgreSQL for storage
- Flask API for serving aircraft data
- A simple web frontend for visualization
- systemd for service management

---

## 📦 Requirements

- Raspberry Pi (Debian / Raspberry Pi OS)
- Python 3.9+
- PostgreSQL (local or Docker)
- Git

Check Python version:

```bash
python3 --version


git clone https://github.com/TryggviMS/adsb-Pitracker.git
cd adsb-Pitracker

chmod +x bootstrap.sh
./bootstrap.sh

source .venv/bin/activate