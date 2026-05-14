#!/usr/bin/env bash
# run_hipaa.sh — Compile and run the HIPAA compliance checker
# Usage: ./run_hipaa.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DL_FILE="$SCRIPT_DIR/hipaa_main.dl"
OUT_DIR="$SCRIPT_DIR/output_hipaa"

# Clean previous output
rm -rf "$OUT_DIR"
mkdir -p "$OUT_DIR"

echo "=== Compiling and running HIPAA compliance checker ==="
echo "    Entry point: $DL_FILE"
echo ""

souffle -D "$OUT_DIR" "$DL_FILE"

echo ""
echo "=== DISCLOSURE DECISIONS ==="

# Show allowed disclosures
echo ""
echo "--- ALLOWED disclosures (is_disclosure_allowed) ---"
if [ -s "$OUT_DIR/is_disclosure_allowed.csv" ]; then
    echo "sender	receiver	subject	message	attribute	purpose	explanation" | column -t -s $'\t'
    column -t -s $'\t' "$OUT_DIR/is_disclosure_allowed.csv"
else
    echo "(none)"
fi

# Show denied disclosures
echo ""
echo "--- DENIED disclosures (is_disclosure_denied) ---"
if [ -s "$OUT_DIR/is_disclosure_denied.csv" ]; then
    echo "sender	receiver	subject	message	attribute	purpose" | column -t -s $'\t'
    column -t -s $'\t' "$OUT_DIR/is_disclosure_denied.csv"
else
    echo "(none)"
fi

# Show diagnostic info
echo ""
echo "=== DIAGNOSTICS ==="
for f in "$OUT_DIR"/*.csv; do
    relation="$(basename "$f" .csv)"
    # Skip the main output relations (already shown above)
    if [ "$relation" = "is_disclosure_allowed" ] || [ "$relation" = "is_disclosure_denied" ] || [ "$relation" = "disclosure_attempted" ]; then
        continue
    fi
    count=$(wc -l < "$f" | tr -d ' ')
    if [ "$count" -gt 0 ]; then
        echo ""
        echo "--- $relation ($count tuples) ---"
        column -t -s $'\t' "$f" | head -20
        if [ "$count" -gt 20 ]; then
            echo "  ... ($count total, showing first 20)"
        fi
    fi
done

echo ""
echo "=== Done. Output files in $OUT_DIR/ ==="
