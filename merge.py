# ─────────────────────────────────────────────────────────────
# merge.py
# Combines data from multiple contributors into one master dataset.
# Run this ONCE after collecting data/ folders from all contributors.
#
# Usage:
#   python merge.py
#
# Before running:
#   1. Copy each contributor's data/nifty/options/master/ folder
#      into a separate folder e.g.:
#        merge_input/person1/
#        merge_input/person2/
#        ...
#   2. Run this script
#   3. Output goes to data/merged/
# ─────────────────────────────────────────────────────────────

import pandas as pd
import glob
from pathlib import Path
from datetime import datetime

INPUT_ROOT  = Path("merge_input")   # Folder containing each person's data
OUTPUT_ROOT = Path("data/merged/options/master")


def merge_all():
    print("=" * 60)
    print("NIFTY Options Data Merge Script")
    print("=" * 60)

    # Find all parquet files across all contributor folders
    pattern = str(INPUT_ROOT / "**" / "*.parquet")
    all_files = glob.glob(pattern, recursive=True)

    if not all_files:
        print(f"No parquet files found in {INPUT_ROOT}/")
        print("Make sure contributor folders are placed inside merge_input/")
        return

    print(f"Found {len(all_files)} parquet files across all contributors")

    # Group files by partition (year/month)
    partitions = {}
    for f in all_files:
        path = Path(f)
        # Extract year and month from path
        parts = path.parts
        year_part  = next((p for p in parts if p.startswith("year=")),  None)
        month_part = next((p for p in parts if p.startswith("month=")), None)

        if year_part and month_part:
            key = f"{year_part}/{month_part}"
            if key not in partitions:
                partitions[key] = []
            partitions[key].append(f)

    print(f"Partitions to merge: {len(partitions)}")
    print()

    total_rows   = 0
    total_dupes  = 0

    for partition_key, files in sorted(partitions.items()):
        print(f"  Merging {partition_key} ({len(files)} files)...", end=" ")

        # Load all files for this partition
        dfs = [pd.read_parquet(f) for f in files]
        combined = pd.concat(dfs, ignore_index=True)

        rows_before = len(combined)

        # Deduplicate on natural key
        combined = combined.drop_duplicates(
            subset=["timestamp", "strike", "expiry_date", "option_type"]
        )
        combined = combined.sort_values("timestamp").reset_index(drop=True)

        rows_after = len(combined)
        dupes      = rows_before - rows_after

        # Save to output
        year_str, month_str = partition_key.split("/")
        out_path = (OUTPUT_ROOT / f"symbol=NIFTY" /
                    year_str / month_str / "part.parquet")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        combined.to_parquet(out_path, index=False)

        print(f"{rows_after:,} rows ({dupes} duplicates removed)")

        total_rows  += rows_after
        total_dupes += dupes

    print()
    print("=" * 60)
    print("MERGE COMPLETE")
    print("=" * 60)
    print(f"  Total candles    : {total_rows:,}")
    print(f"  Duplicates removed: {total_dupes:,}")
    print(f"  Output location  : {OUTPUT_ROOT}")
    print()
    print("Query merged data with:")
    print(f"  duckdb.query(\"SELECT * FROM '{OUTPUT_ROOT}/**/*.parquet'\")")


if __name__ == "__main__":
    merge_all()