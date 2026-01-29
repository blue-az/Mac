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

table_exists() {
  local db="$1"
  local table="$2"
  sqlite3 "$db" "SELECT 1 FROM sqlite_master WHERE type='table' AND name='$table' LIMIT 1;" | grep -q 1
}

sql="ATTACH '$SRC_DB' AS srcdb;
INSERT OR IGNORE INTO sessions SELECT * FROM srcdb.sessions;
INSERT OR IGNORE INTO raw_sensor_buffer SELECT * FROM srcdb.raw_sensor_buffer;"

for table in shots calculated_metrics devices; do
  if table_exists "$DEST_DB" "$table" && table_exists "$SRC_DB" "$table"; then
    sql="$sql
INSERT OR IGNORE INTO $table SELECT * FROM srcdb.$table;"
  fi
done

sql="$sql
DETACH srcdb;"

sqlite3 "$DEST_DB" "$sql"

new_dest_count=$(sqlite3 "$DEST_DB" "SELECT COUNT(*) FROM sessions;")

cat <<MSG
Merge complete.
- Source sessions: $src_count
- Destination sessions before: $dest_count
- Destination sessions after: $new_dest_count
- Backup created: $backup_path
MSG
