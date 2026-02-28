DROP TABLE IF EXISTS aircraft_categories;

CREATE TABLE aircraft_categories (
    code TEXT PRIMARY KEY,
    description_en TEXT,
    description_is TEXT
);

INSERT INTO aircraft_categories (code, description_en, description_is) VALUES
    ('A0', 'No ADS-B emitter category information',          'Engar ADS-B upplýsingar'),
    ('A1', 'Light (< 15500 lbs)',                            'Létt vél(< 15500 lbs)'),
    ('A2', 'Small (15500 to 75000 lbs)',                     'Smærri vél (15500 til 75000 lbs)'),
    ('A3', 'Large (75000 to 300000 lbs)',                    'Stór vél (75000 til 300000 lbs)'),
    ('A4', 'High vortex large (e.g. B-757)',                 'Hátt vindhringleflugvél (t.d. B-757)'),
    ('A5', 'Heavy (> 300000 lbs)',                           'Þung vél (> 300000 lbs)'),
    ('A6', 'High performance (> 5g and 400 kts)',            'Háafkastsflugvél (> 5g og 400 kn)'),
    ('A7', 'Rotorcraft',                                     'Þyrla'),
    ('B0', 'No ADS-B emitter category information',          'Engar ADS-B upplýsingar'),
    ('B1', 'Glider / sailplane',                             'Svifflugvél'),
    ('B2', 'Lighter-than-air',                               'Léttara en loft (loftskip eða blástur)'),
    ('B3', 'Parachutist / skydiver',                         'Fallhlífarstökkvari'),
    ('B4', 'Ultralight / hang-glider / paraglider',          'Léttflugvél / svifhjól / gliðruflugvél'),
    ('B5', 'Reserved',                                       'Frátekið'),
    ('B6', 'Unmanned aerial vehicle',                        'Mannlaust loftfar'),
    ('B7', 'Space / trans-atmospheric vehicle',              'Geimfar / þverloftfaratæki'),
    ('C0', 'No ADS-B emitter category information',          'Engar ADS-B upplýsingar'),
    ('C1', 'Surface vehicle – emergency vehicle',            'Yfirborðsfarartæki - neyðarfarartæki'),
    ('C2', 'Surface vehicle – service vehicle',              'Yfirborðsfarartæki - þjónustufarartæki'),
    ('C3', 'Point obstacle (includes tethered balloons)',    'Punkthindrun (þ.m.t. fest blástur)'),
    ('C4', 'Cluster obstacle',                               'Þyrpingarhindrun'),
    ('C5', 'Line obstacle',                                  'Línuhindrun'),
    ('C6', 'Reserved',                                       'Frátekið'),
    ('C7', 'Reserved',                                       'Frátekið');




CREATE TABLE aircraft_registry (
    icao24              TEXT PRIMARY KEY,
    timestamp           TEXT,
    acars               TEXT,
    adsb                TEXT,
    built               TEXT,
    categorydescription TEXT,
    country             TEXT,
    engines             TEXT,
    firstflightdate     TEXT,
    firstseen           TEXT,
    icaoaircraftclass   TEXT,
    linenumber          TEXT,
    manufacturericao    TEXT,
    manufacturername    TEXT,
    model               TEXT,
    modes               TEXT,
    nextreg             TEXT,
    notes               TEXT,
    operator            TEXT,
    operatorcallsign    TEXT,
    operatoriata        TEXT,
    operatoricao        TEXT,
    owner               TEXT,
    prevreg             TEXT,
    reguntil            TEXT,
    registered          TEXT,
    registration        TEXT,
    selcal              TEXT,
    serialnumber        TEXT,
    status              TEXT,
    typecode            TEXT,
    vdl                 TEXT
);

ALTER TABLE aircraft_registry
ADD COLUMN added_at TIMESTAMP;

UPDATE aircraft_registry
SET added_at = NOW();

--## (DEV) bashpsql -h localhost -p 5433 -U admin -d spatial_db
--Then once you're at the spatial_db=# prompt:
--> sql\copy aircraft_registry FROM '/home/trygg/adsb-Pitracker/ADSB/aircraft-database-complete-2025-08.csv' WITH (FORMAT csv, HEADER true, QUOTE '''', NULL '');
