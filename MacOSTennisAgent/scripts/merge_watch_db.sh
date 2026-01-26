#!/usr/bin/env bash
set -euo pipefail

SRC_DB=${1:-/tmp/tennis_docs/Documents/tennis_watch.db}
DEST_DB=${2:-/Volumes/NO\ NAME/tennis_watch.db}

if [[ ! -f "$SRC_DB" ]]; then
  echo "Source DB not found: $SRC_DB" >&2
  exit 1
fi

if [[ ! -f "$DEST_DB" ]]; then
  echo "Destination DB not found: $DEST_DB" >&2
  exit 1
fi

src_count=$(sqlite3 "$SRC_DB" "SELECT COUNT(*) FROM sessions;")
dest_count=$(sqlite3 "$DEST_DB" "SELECT COUNT(*) FROM sessions;")

if [[ "$src_count" -eq 0 ]]; then
  echo "Source DB has 0 sessions; refusing to merge to avoid wiping USB." >&2
  exit 1
fi

backup_dir="$(dirname "$DEST_DB")/backups"
mkdir -p "$backup_dir"
backup_path="$backup_dir/tennis_watch_$(date +%Y%m%d_%H%M%S).db"
cp -f "$DEST_DB" "$backup_path"

sqlite3 "$DEST_DB" <<SQL
ATTACH '$SRC_DB' AS srcdb;

-- Insert sessions first, then dependent tables
INSERT OR IGNORE INTO sessions SELECT * FROM srcdb.sessions;
INSERT OR IGNORE INTO raw_sensor_buffer SELECT * FROM srcdb.raw_sensor_buffer;
INSERT OR IGNORE INTO shots SELECT * FROM srcdb.shots;
INSERT OR IGNORE INTO calculated_metrics SELECT * FROM srcdb.calculated_metrics;
INSERT OR IGNORE INTO devices SELECT * FROM srcdb.devices;

DETACH srcdb;
SQL

new_dest_count=$(sqlite3 "$DEST_DB" "SELECT COUNT(*) FROM sessions;")

cat <<MSG
Merge complete.
- Source sessions: $src_count
- Destination sessions before: $dest_count
- Destination sessions after: $new_dest_count
- Backup created: $backup_path
MSG
