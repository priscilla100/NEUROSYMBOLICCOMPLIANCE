"""
data/fix_sox_splitting.py
─────────────────────────────────────────────────────────────────────────────
Adds parent-child hierarchy fields to sox_rag_db.csv and exports both a
hierarchical flat CSV and a nested JSON tree.

The SOX CSV uses IDs like:
    sox-2-a-3        → section 2(a)(3)      hierarchy_level = 3
    sox-2-a-3-A      → section 2(a)(3)(A)   hierarchy_level = 4
    sox-2-a-3-A-i    → section 2(a)(3)(A)(i) hierarchy_level = 5

Parent derivation rule:
    Strip the last "-<segment>" from the id.
    sox-2-a-3-A → parent sox-2-a-3
    sox-2      → parent sox   (top-level sections have parent "sox")
    sox        → no parent (root)

Outputs:
    data/sox_rag_db_hierarchical.csv  — flat CSV with parent_id, hierarchy_level, is_leaf
    data/sox_rag_db_tree.json         — nested JSON tree for RAG consumption
"""

import csv
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
INPUT_CSV = ROOT / "sox_rag_db.csv"
OUTPUT_CSV = ROOT / "sox_rag_db_hierarchical.csv"
OUTPUT_JSON = ROOT / "sox_rag_db_tree.json"


def derive_parent_id(row_id: str) -> str:
    """Strip the last hyphen-segment from an id to get the parent id."""
    parts = row_id.split("-")
    if len(parts) <= 1:
        return ""
    return "-".join(parts[:-1])


def derive_hierarchy_level(row_id: str) -> int:
    """Count hyphen-separated segments after the 'sox' prefix."""
    parts = row_id.split("-")
    # 'sox' alone = level 0; 'sox-2' = level 1; 'sox-2-a' = level 2; etc.
    return len(parts) - 1


def main():
    # Read input
    rows = []
    with open(INPUT_CSV, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
        for row in reader:
            rows.append(row)

    # Build set of all IDs to determine is_leaf
    all_ids = {r["id"] for r in rows}
    parent_ids_used = set()
    for r in rows:
        pid = derive_parent_id(r["id"])
        if pid:
            parent_ids_used.add(pid)

    # Enrich rows
    enriched = []
    for r in rows:
        row_id = r["id"]
        parent_id = derive_parent_id(row_id)
        level = derive_hierarchy_level(row_id)
        is_leaf = row_id not in parent_ids_used
        enriched.append({
            **r,
            "parent_id": parent_id,
            "hierarchy_level": level,
            "is_leaf": str(is_leaf),
        })

    # Write hierarchical CSV
    out_fields = list(fieldnames) + ["parent_id", "hierarchy_level", "is_leaf"]
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=out_fields)
        writer.writeheader()
        writer.writerows(enriched)

    print(f"Written: {OUTPUT_CSV}  ({len(enriched)} rows)")

    # Build nested JSON tree
    # Index by id for fast lookup
    by_id = {r["id"]: {
        "id": r["id"],
        "section_number": r["section_number"],
        "category": r["category"],
        "policy_type": r["policy_type"],
        "original_text": r["original_text"],
        "hierarchy_level": derive_hierarchy_level(r["id"]),
        "children": [],
    } for r in rows}

    roots = []
    for r in rows:
        row_id = r["id"]
        parent_id = derive_parent_id(row_id)
        if parent_id and parent_id in by_id:
            by_id[parent_id]["children"].append(by_id[row_id])
        else:
            roots.append(by_id[row_id])

    tree = {"regulation": "SOX", "full_name": "Sarbanes-Oxley Act of 2002", "sections": roots}

    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(tree, f, indent=2, ensure_ascii=False)

    print(f"Written: {OUTPUT_JSON}  ({len(roots)} top-level sections)")

    # Spot-check
    print("\nSpot-check: sox-2-a-3-A")
    target = next((r for r in enriched if r["id"] == "sox-2-a-3-A"), None)
    if target:
        print(f"  parent_id       = {target['parent_id']}")
        print(f"  hierarchy_level = {target['hierarchy_level']}")
        print(f"  is_leaf         = {target['is_leaf']}")
        print(f"  policy_type     = {target['policy_type']}")
    else:
        print("  NOT FOUND")

    # Summary stats
    leaf_count = sum(1 for r in enriched if r["is_leaf"] == "True")
    max_level = max(derive_hierarchy_level(r["id"]) for r in rows)
    print(f"\nSummary: {len(enriched)} rows total | {leaf_count} leaves | max depth = {max_level}")
    level_counts = {}
    for r in enriched:
        lv = int(r["hierarchy_level"])
        level_counts[lv] = level_counts.get(lv, 0) + 1
    for lv in sorted(level_counts):
        print(f"  Level {lv}: {level_counts[lv]} rows")


if __name__ == "__main__":
    main()
