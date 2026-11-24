#!/bin/sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
export PYTHONPATH="$ROOT/src"
DB=${OPPORTUNITY_RADAR_DB:-"$ROOT/state/opportunity_radar.sqlite3"}
OUTPUT=${OPPORTUNITY_RADAR_OUTPUT:-"$ROOT/output/radar.md"}
exec python3 -m opportunity_radar.cli render --db "$DB" --output "$OUTPUT"
