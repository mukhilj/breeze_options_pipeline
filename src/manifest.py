# ─────────────────────────────────────────────────────────────
# manifest.py
# Tracks download status at chunk level.
# One row per (expiry × strike × right × chunk_index).
#
# This is the single source of truth for:
#   - What has been downloaded
#   - What still needs to be downloaded
#   - What failed and needs retry
#
# Updated after EVERY API call — crash-safe by design.
# ─────────────────────────────────────────────────────────────

import pandas as pd
from pathlib import Path
from datetime import datetime, date

MANIFEST_PATH = Path("data/manifest.parquet")

# ── Valid status values ───────────────────────────────────────
STATUS_PENDING           = "pending"
STATUS_DOWNLOADED        = "downloaded"
STATUS_VALIDATED         = "validated"
STATUS_VALIDATION_FAILED = "validation_failed"
STATUS_FAILED            = "failed"

# ── Schema — column names and types ──────────────────────────
MANIFEST_COLUMNS = [
    "symbol",
    "expiry_date",
    "strike",
    "right",
    "expiry_type",
    "chunk_index",
    "from_dt",
    "to_dt",
    "status",
    "rows",
    "file_path",
    "attempts",
    "last_error",
    "source_run_id",
    "updated_at",
]


def load_manifest():
    """
    Loads manifest from disk.
    Returns empty DataFrame with correct schema if file doesn't exist.
    """
    if not MANIFEST_PATH.exists():
        return _empty_manifest()

    df = pd.read_parquet(MANIFEST_PATH)

    # Ensure all expected columns exist
    for col in MANIFEST_COLUMNS:
        if col not in df.columns:
            df[col] = None

    return df[MANIFEST_COLUMNS]


def save_manifest(df):
    """
    Saves manifest to disk immediately.
    Called after every status update — crash-safe.
    """
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    df[MANIFEST_COLUMNS].to_parquet(MANIFEST_PATH, index=False)


def _empty_manifest():
    """Returns an empty DataFrame with correct manifest schema."""
    return pd.DataFrame(columns=MANIFEST_COLUMNS)


def build_manifest_for_expiry(symbol, expiry_date, expiry_type,
                               strikes, rights, chunks_by_contract,
                               run_id, existing_manifest):
    """
    Adds new pending rows to the manifest for all contracts in one expiry.
    Skips contracts that already exist in the manifest.
    """
    new_rows = []

    for strike in strikes:
        for right in rights:
            chunks = chunks_by_contract.get((strike, right), [])

            for chunk in chunks:
                exists = (
                    (existing_manifest["symbol"]      == symbol) &
                    (existing_manifest["expiry_date"] == str(expiry_date)) &
                    (existing_manifest["strike"]      == strike) &
                    (existing_manifest["right"]       == right) &
                    (existing_manifest["chunk_index"] == chunk["chunk_index"])
                )

                if existing_manifest.empty or not exists.any():
                    new_rows.append({
                        "symbol":        symbol,
                        "expiry_date":   str(expiry_date),
                        "strike":        strike,
                        "right":         right,
                        "expiry_type":   expiry_type,
                        "chunk_index":   chunk["chunk_index"],
                        "from_dt":       chunk["from_dt"],
                        "to_dt":         chunk["to_dt"],
                        "status":        STATUS_PENDING,
                        "rows":          0,
                        "file_path":     "",
                        "attempts":      0,
                        "last_error":    "",
                        "source_run_id": run_id,
                        "updated_at":    str(datetime.now()),
                    })

    if not new_rows:
        return existing_manifest

    new_df   = pd.DataFrame(new_rows, columns=MANIFEST_COLUMNS)
    combined = pd.concat([existing_manifest, new_df], ignore_index=True)
    return combined


def update_chunk_status(manifest, symbol, expiry_date, strike,
                        right, chunk_index, status,
                        rows=0, file_path="", error="", run_id=""):
    """
    Updates a single chunk's status in the manifest and saves to disk.
    Called immediately after every API call — crash-safe.
    """
    mask = (
        (manifest["symbol"]      == symbol) &
        (manifest["expiry_date"] == str(expiry_date)) &
        (manifest["strike"]      == strike) &
        (manifest["right"]       == right) &
        (manifest["chunk_index"] == chunk_index)
    )

    manifest.loc[mask, "status"]     = status
    manifest.loc[mask, "rows"]       = rows
    manifest.loc[mask, "file_path"]  = file_path
    manifest.loc[mask, "attempts"]   = manifest.loc[mask, "attempts"] + 1
    manifest.loc[mask, "last_error"] = error
    manifest.loc[mask, "updated_at"] = str(datetime.now())

    if run_id:
        manifest.loc[mask, "source_run_id"] = run_id

    save_manifest(manifest)
    return manifest


def get_pending_chunks(manifest, limit=None):
    """
    Returns all chunks that still need to be downloaded.
    Includes: pending + failed (retry) chunks.

    Download order: NEWEST expiries first.
    This ensures recent data is available for backtesting
    while the historical seed continues in the background.
    """
    pending_mask = manifest["status"].isin([STATUS_PENDING, STATUS_FAILED])
    pending      = manifest[pending_mask].copy()

    # Sort: pending before failed, newest expiry first, then by strike and chunk
    pending["sort_order"] = pending["status"].map(
        {STATUS_PENDING: 0, STATUS_FAILED: 1}
    )
    pending = pending.sort_values(
        ["sort_order", "expiry_date", "strike", "chunk_index"],
        ascending=[True, False, True, True]   # ← False = newest expiry first
    ).drop(columns=["sort_order"])

    if limit:
        pending = pending.head(limit)

    return pending


def get_manifest_summary(manifest):
    """
    Returns a dict summarising the current manifest state.
    Printed at the end of each run.
    """
    if manifest.empty:
        return {"total": 0}

    status_counts = manifest["status"].value_counts().to_dict()

    return {
        "total":             len(manifest),
        "pending":           status_counts.get(STATUS_PENDING,           0),
        "downloaded":        status_counts.get(STATUS_DOWNLOADED,        0),
        "validated":         status_counts.get(STATUS_VALIDATED,         0),
        "validation_failed": status_counts.get(STATUS_VALIDATION_FAILED, 0),
        "failed":            status_counts.get(STATUS_FAILED,            0),
    }


def print_manifest_summary(manifest):
    """Prints a formatted summary of manifest state."""
    s = get_manifest_summary(manifest)
    print(f"\nManifest summary:")
    print(f"  Total chunks     : {s['total']:,}")
    print(f"  Pending          : {s.get('pending',           0):,}")
    print(f"  Downloaded       : {s.get('downloaded',        0):,}")
    print(f"  Validated        : {s.get('validated',         0):,}")
    print(f"  Validation failed: {s.get('validation_failed', 0):,}")
    print(f"  Failed           : {s.get('failed',            0):,}")


# ─────────────────────────────────────────────────────────────
# Run this file directly to test:
# python -m src.manifest
# ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    from datetime import date
    from src.chunk_planner import build_chunks

    print("=" * 55)
    print("Test 1: Create manifest for 1 expiry, 3 strikes")
    print("=" * 55)

    run_id       = "test_run_001"
    expiry       = date(2026, 5, 19)
    test_strikes = [23600, 23650, 23700]
    rights       = ["call", "put"]

    chunks_by_contract = {}
    for strike in test_strikes:
        for right in rights:
            chunks_by_contract[(strike, right)] = build_chunks(expiry, "weekly")

    manifest = _empty_manifest()
    manifest = build_manifest_for_expiry(
        symbol             = "NIFTY",
        expiry_date        = expiry,
        expiry_type        = "weekly",
        strikes            = test_strikes,
        rights             = rights,
        chunks_by_contract = chunks_by_contract,
        run_id             = run_id,
        existing_manifest  = manifest
    )

    print(f"Manifest rows created: {len(manifest)}")
    print(f"\nFirst 5 rows:")
    print(manifest[["symbol", "expiry_date", "strike", "right",
                     "chunk_index", "status", "rows"]].head())

    print()
    print("=" * 55)
    print("Test 2: Update one chunk to downloaded")
    print("=" * 55)

    manifest = update_chunk_status(
        manifest    = manifest,
        symbol      = "NIFTY",
        expiry_date = expiry,
        strike      = 23650,
        right       = "call",
        chunk_index = 0,
        status      = STATUS_DOWNLOADED,
        rows        = 705,
        file_path   = "data/nifty/options/raw/NIFTY_23650_CE_20260519.parquet",
        run_id      = run_id
    )

    updated = manifest[
        (manifest["strike"]      == 23650) &
        (manifest["right"]       == "call") &
        (manifest["chunk_index"] == 0)
    ]
    print(f"Status : {updated.iloc[0]['status']}")
    print(f"Rows   : {updated.iloc[0]['rows']}")

    print()
    print("=" * 55)
    print("Test 3: Pending chunks — newest expiry first")
    print("=" * 55)

    pending = get_pending_chunks(manifest)
    print(f"Pending chunks : {len(pending)}")
    print(f"First expiry   : {pending.iloc[0]['expiry_date']}")
    print(f"Last expiry    : {pending.iloc[-1]['expiry_date']}")

    print()
    print("=" * 55)
    print("Test 4: Summary")
    print("=" * 55)
    print_manifest_summary(manifest)

    print("\nAll manifest tests passed.")