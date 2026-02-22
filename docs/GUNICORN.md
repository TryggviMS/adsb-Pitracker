cd /home/trygg/Documents/adsb-Pitracker
source .venv/bin/activate

python -m pip install --upgrade pip
pip install gunicorn

gunicorn --version
deactivate
