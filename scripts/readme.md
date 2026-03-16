# PostgreSQL Backup Strategy (External SSD)

This project performs nightly PostgreSQL backups to an external SSD to ensure safe recovery of the `spatial_db` database.

---

## Storage Location

Backups are stored on:

/media/trygg/tryggvi_flakkari/adsb_backups

The external SSD must be mounted before the backup runs.

---

## Backup Script

Script location:

/home/trygg/Documents/adsb-Pitracker/scripts/backup_postgres.sh

### What the script does

- Verifies the external drive is mounted
- Creates a compressed PostgreSQL dump using `pg_dump -Fc`
- Writes to a temporary file first (prevents partial/corrupt backups)
- Validates the dump is not empty
- Moves it into place atomically
- Sets secure file permissions (`600`)
- Deletes backups older than 30 days

---

Manual Backup

Run manually:

/home/trygg/Documents/adsb-Pitracker/scripts/backup_postgres.sh
Automated Nightly Backup (Cron)

Runs every night at 02:30:

30 2 * * * /home/trygg/Documents/adsb-Pitracker/scripts/backup_postgres.sh >> /home/trygg/adsb_backup.log 2>&1
Restore Procedure

Create a test database:

createdb restore_test

Restore a backup:

pg_restore -d restore_test /media/trygg/tryggvi_flakkari/adsb_backups/adsb_YYYY-MM-DD.dump
Security Notes

Backup files are saved with permission 600

Only the Docker container postgis_db performs the dump

Retention policy: 30 days

External SSD is not publicly exposed

This provides safe, rotating, compressed backups suitable for production use.



### Resompose 

./scripts/recompose.sh