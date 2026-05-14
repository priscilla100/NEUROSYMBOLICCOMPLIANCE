#!/usr/bin/env bash
# run_example.sh — Compile and run the Soufflé family-tree example.
# Usage: ./run_example.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DL_FILE="$SCRIPT_DIR/family.dl"
OUT_DIR="$SCRIPT_DIR/output"

# Clean previous output
rm -rf "$OUT_DIR"
mkdir -p "$OUT_DIR"

echo "=== Running Soufflé on family.dl ==="
souffle -D "$OUT_DIR" "$DL_FILE"

echo ""
echo "=== Results ==="

for f in "$OUT_DIR"/*.csv; do
    relation="$(basename "$f" .csv)"
    count=$(wc -l < "$f" | tr -d ' ')
    echo ""
    echo "--- $relation ($count tuples) ---"
    # Print with a readable column format
    column -t -s $'\t' "$f"
done

echo ""
echo "=== Done. Output files are in $OUT_DIR/ ==="
