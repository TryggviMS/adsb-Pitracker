# FLIGHTRADAR24 FEEDER

## Purpose

This Raspberry Pi ADS-B receiver shares aircraft data with Flightradar24 (FR24).

The FR24 feeder uses the existing dump1090 instance and does NOT access the RTL-SDR directly.

Current feeder:

```
Flightradar24 Radar ID: T-BIRK53
```

Current architecture:

```
RTL-SDR Blog V4
      |
      v
dump1090 (Docker)
      |
      | Beast TCP :30005
      v
fr24feed (host service)
      |
      | UDP
      v
Flightradar24
```

## IMPORTANT: DO NOT RUN A SECOND DUMP1090

The project already has dump1090 running in Docker and using the RTL-SDR.

FR24 must therefore connect to dump1090's network output rather than trying to access
the USB SDR itself.

The relevant dump1090 configuration is:

```
--net
```

This enables dump1090's network outputs.

The Docker container exposes:

```
8080 -> dump1090 web interface
30005 -> Beast TCP output
```

Check with:

```
sudo docker port dump1090
```

Expected:

```
8080/tcp -> 0.0.0.0:8080
8080/tcp -> [::]:8080
30005/tcp -> 0.0.0.0:30005
30005/tcp -> [::]:30005
```

## FR24 CONFIGURATION

FR24 is installed as a systemd service:

```
fr24feed.service
```

Configuration file:

```
/etc/fr24feed.ini
```

The important receiver configuration is:

```
receiver="beast-tcp"
host="127.0.0.1:30005"
```

MLAT is disabled because this receiver already shares ADS-B data through other
services:

```
mlat="no"
mlat-without-gps="no"
```

Other relevant settings include:

```
bs="no"
raw="no"
```

DO NOT commit /etc/fr24feed.ini or the FR24 sharing key to the repository.

## FR24 SERVICE COMMANDS

Check whether the service is running:

```
sudo systemctl status fr24feed --no-pager
```

Restart the feeder:

```
sudo systemctl restart fr24feed
```

Stop the feeder:

```
sudo systemctl stop fr24feed
```

Start the feeder:

```
sudo systemctl start fr24feed
```

View recent logs:

```
sudo journalctl -u fr24feed -n 50 --no-pager
```

Follow the logs live:

```
sudo journalctl -u fr24feed -f
```

## FR24 STATUS

The easiest way to check the feeder is:

```
sudo fr24feed-status
```

A healthy connection looks like:

```
FR24 Feeder/Decoder Process: running.
FR24 Link: connected [UDP].
FR24 Radar: T-BIRK53.
FR24 Tracked AC: X.
Receiver: connected (MSGS/SYNC).
```

"Tracked AC: 0" is normal when the receiver is not currently detecting any
aircraft.

The feeder does not need to be restarted when there are temporarily no aircraft.

## LOCAL FR24 WEB INTERFACE

fr24feed provides a local status/configuration web interface on port 8754.

From the Raspberry Pi itself:

```
http://localhost:8754
```

From another computer on the same LAN:

```
http://192.168.0.13:8754
```

This interface can be used to inspect the FR24 feeder status.

Port 8754 is a local service and is not intended to be publicly exposed through
the nesflug.com web site.

## VIEWING AIRCRAFT DATA

There are several different places to see aircraft data.

1. Existing dump1090 interface

   http://192.168.0.13:8080

This is the local dump1090 interface and shows the aircraft being received
directly by the SDR.

This is the best place to verify that the SDR and dump1090 are actually
receiving aircraft.

2. Existing NESFLUG map

The project's own map is served through the existing web service.

The public site is:

```
https://nesflug.com
```

The project map/API architecture is independent of the FR24 feeder.

FR24 receives a copy of the ADS-B stream; FR24 does not provide the data
back to the NESFLUG application.

3. Flightradar24

The feeder sends the received aircraft data to Flightradar24.

The FR24 feeder itself does not create a separate local aircraft database.

To see the feeder's contribution and account information, use the Flightradar24
account/data-sharing area associated with the FR24 account.

The local FR24 status page on port 8754 is the most useful place for checking
whether this particular Raspberry Pi is connected and sending data.

## IMPORTANT DISTINCTION: FEEDING VS VIEWING FR24 DATA

This setup sends ADS-B data TO Flightradar24.

It does not automatically provide the FR24 aircraft data back to this project.

The data flow is:

```
SDR
  |
  v
dump1090
  |
  +----> NESFLUG ingest / PostGIS / map
  |
  +----> fr24feed ----> Flightradar24
```

Therefore:

```
dump1090 / aircraft.json
    = locally received ADS-B data

FR24
    = external service receiving a copy of that data
```

If the goal is to use the FR24 network's aircraft data inside the NESFLUG
application, that is a separate integration and should not be confused with
the feeder described here.

## TROUBLESHOOTING

FR24 says:

```
Receiver: down
```

Check:

```
sudo fr24feed-status
```

Then inspect:

```
sudo journalctl -u fr24feed -n 50 --no-pager
```

Verify that dump1090 exposes port 30005:

```
sudo docker port dump1090
```

Expected:

```
30005/tcp -> 0.0.0.0:30005
30005/tcp -> [::]:30005
```

Test the TCP connection:

```
sudo nc -vz 127.0.0.1 30005
```

A successful result should indicate that the connection succeeded.

## If FR24 tries to connect to port 30002

The automatic FR24 configuration may detect dump1090 as an AVR receiver and
configure:

```
receiver="avr-tcp"
host="127.0.0.1:30002"
```

That is incorrect for this Dockerized setup.

Use:

```
receiver="beast-tcp"
host="127.0.0.1:30005"
```

Then restart:

```
sudo systemctl restart fr24feed
```

## If "Tracked AC" is 0

First check the dump1090 interface:

```
http://192.168.0.13:8080
```

If dump1090 also shows zero aircraft, there may simply be no aircraft currently
within reception range.

Check again later:

```
sudo fr24feed-status
```

The feeder can remain running while there are no aircraft.

If dump1090 shows aircraft but FR24 remains at zero, inspect:

```
sudo journalctl -u fr24feed -n 50 --no-pager
```

and verify:

```
receiver="beast-tcp"
host="127.0.0.1:30005"
```

## FR24 ACCOUNT / FEED STATUS

During registration FR24 assigned:

```
Radar ID: T-BIRK53
```

The FR24 service may initially report account or feed provisioning messages
shortly after registration. Once the feeder successfully connects, it should
maintain a network connection and periodically synchronize with FR24.

If the feeder reports a persistent:

```
Feed not found
```

or similar account provisioning error despite a working receiver connection,
check the FR24 account/data-sharing page or contact FR24 support.

Do not repeatedly reinstall the feeder just because the FR24 account takes
some time to become fully active.

## SECURITY

The FR24 sharing key is stored in:

```
/etc/fr24feed.ini
```

Never commit this file to Git.

Never put the sharing key in:

```
.env
README files
Docker Compose files
Git history
public documentation
```

If a sharing key is accidentally exposed, treat it as compromised and use the
FR24 account controls/support to replace it if possible.

## MAINTENANCE

Check feeder status:

```
sudo fr24feed-status
```

Check service:

```
sudo systemctl status fr24feed --no-pager
```

Check logs:

```
sudo journalctl -u fr24feed -n 50 --no-pager
```

Check dump1090:

```
sudo docker ps
```

Check dump1090 port mappings:

```
sudo docker port dump1090
```

Check the local dump1090 web interface:

```
http://192.168.0.13:8080
```

Check the FR24 local interface:

```
http://192.168.0.13:8754
```

## CURRENT SETUP SUMMARY

Hardware:

```
Raspberry Pi 5 Model B
RTL-SDR Blog V4
```

ADS-B decoder:

```
dump1090
Docker container: dump1090
```

dump1090 network output:

```
Beast TCP
Port: 30005
```

FR24 feeder:

```
fr24feed
Host systemd service
```

FR24 receiver:

```
beast-tcp
127.0.0.1:30005
```

MLAT:

```
Disabled
```

FR24 local status:

```
http://192.168.0.13:8754
```

dump1090 local status:

```
http://192.168.0.13:8080
```

Project:

```
NESFLUG
https://nesflug.com
```
