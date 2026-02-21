# systemd Setup – adsb-Pitracker


## Install Services

Copy the service files into systemd and reload:

sudo cp systemd/adsb_ingest.service /etc/systemd/system/
sudo cp systemd/adsb_flask.service /etc/systemd/system/
sudo systemctl daemon-reload

Enable services at boot:

sudo systemctl enable adsb_ingest
sudo systemctl enable adsb_flask

Start services:

sudo systemctl start adsb_ingest
sudo systemctl start adsb_flask

---

## Restart / Stop Services

Restart:

sudo systemctl restart adsb_ingest
sudo systemctl restart adsb_flask

Stop:

sudo systemctl stop adsb_ingest
sudo systemctl stop adsb_flask

Check status:

systemctl status adsb_ingest
systemctl status adsb_flask

---

## Logs

Follow live logs:

sudo journalctl -u adsb_ingest -f
sudo journalctl -u adsb_flask -f

Show last 200 lines:

sudo journalctl -u adsb_ingest -n 200
sudo journalctl -u adsb_flask -n 200

---

## After Code Changes

Restart services:

sudo systemctl restart adsb_ingest
sudo systemctl restart adsb_flask

If dependencies changed:

cd /home/trygg/Documents/HindberjaPi
source .venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart adsb_ingest adsb_flask

---

## Remove Services

sudo systemctl disable adsb_ingest adsb_flask
sudo rm /etc/systemd/system/adsb_ingest.service
sudo rm /etc/systemd/system/adsb_flask.service
sudo systemctl daemon-reload