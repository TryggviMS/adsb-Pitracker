#!/bin/bash
set -e

psql -v ON_ERROR_STOP=1 --username "$PGUSER" --dbname "$PGDATABASE" <<-EOSQL
    \copy aircraft_registry FROM '/ADSB/aircraft-database-complete-2025-08.csv' WITH (FORMAT csv, HEADER true, QUOTE '''' , NULL '');
EOSQL