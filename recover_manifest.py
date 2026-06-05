# ─────────────────────────────────────────────────────────────
# recover_manifest.py
# Rebuilds manifest.parquet from existing raw downloaded files.
# Run this when manifest.parquet is corrupted.
#
# Usage: python recover_manifest.py
# ─────────────────────────────────────────────────────────────

import pandas as pd
from pathlib import Path
from datetime import datetime

RAW_ROOT      = Path("data/nifty/options/raw")
MANIFEST_PATH = Path("data/manifest.parquet")

MANIFEST_COLUMNS = [
    "symbol", "expiry_date", "strike", "right", "expiry_type",
    "chunk_index", "from_dt", "to_dt", "status", "rows",
    "file_path", "attempts", "last_error", "source_run_id", "updated_at"
]


def recover():
    print("")
    print("=" * 55)
    print("Manifest Recovery Tool")
    print("=" * 55)

    # Step 1: Backup corrupted manifest
    if MANIFEST_PATH.exists():
        backup_path = Path("data/manifest_corrupted_backup.parquet")
        MANIFEST_PATH.rename(backup_path)
        print(f"Corrupted manifest backed up to: {backup_path}")

    # Step 2: Scan all raw parquet files
    raw_files = sorted(RAW_ROOT.glob("*.parquet"))
    print(f"Raw contract files found: {len(raw_files)}")

    if not raw_files:
        print("No raw files found. Starting with empty manifest.")
        pd.DataFrame(columns=MANIFEST_COLUMNS).to_parquet(
            MANIFEST_PATH, index=False
        )
        return

    # Step 3: Build manifest rows from raw files
    rows   = []
    errors = 0

    for i, f in enumerate(raw_files):

        if i % 500 == 0:
            print(f"  Processing file {i+1}/{len(raw_files)}...")

        try:
            # Parse filename: NIFTY_21500_CE_20260529.parquet
            parts      = f.stem.split("_")
            symbol     = parts[0]                          # NIFTY
            strike     = int(parts[1])                     # 21500
            right_code = parts[2]                          # CE or PE
            expiry_raw = parts[3]                          # 20260529

            right      = "call" if right_code == "CE" else "put"
            expiry_date = (f"{expiry_raw[:4]}-"
                           f"{expiry_raw[4:6]}-"
                           f"{expiry_raw[6:]}")            # 2026-05-29

            # Read raw file
            df     = pd.read_parquet(f)
            n_rows = len(df)

            if n_rows > 0 and "datetime" in df.columns:
                from_dt = str(df["datetime"].min())
                to_dt   = str(df["datetime"].max())
            else:
                from_dt = ""
                to_dt   = ""

            rows.append({
                "symbol":        symbol,
                "expiry_date":   expiry_date,
                "strike":        strike,
                "right":         right,
                "expiry_type":   "unknown",
                "chunk_index":   0,
                "from_dt":       from_dt,
                "to_dt":         to_dt,
                "status":        "validated",
                "rows":          n_rows,
                "file_path":     str(f),
                "attempts":      1,
                "last_error":    "",
                "source_run_id": "recovered",
                "updated_at":    str(datetime.now()),
            })

        except Exception as e:
            print(f"  Could not process {f.name}: {e}")
            errors += 1

    # Step 4: Save recovered manifest
    manifest = pd.DataFrame(rows, columns=MANIFEST_COLUMNS)
    manifest.to_parquet(MANIFEST_PATH, index=False)

    print("")
    print("=" * 55)
    print("Recovery Complete")
    print("=" * 55)
    print(f"  Contracts recovered : {len(rows):,}")
    print(f"  Files with errors   : {errors}")
    print(f"  Manifest saved to   : {MANIFEST_PATH}")
    print("")
    print("Next step: run the pipeline normally.")
    print("  python -m src.auth")
    print("  python -m src.main")
    print("")
    print("The pipeline will automatically detect which contracts")
    print("are missing and download only those.")


if __name__ == "__main__":
    recover()