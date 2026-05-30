# ─────────────────────────────────────────────────────────────
# storage.py
# All file read/write operations for the pipeline.
#
# Three responsibilities:
#   1. Spot cache  — read/write nifty_spot.parquet
#   2. Raw layer   — write one Parquet file per contract
#   3. Master layer — merge validated data into monthly partitions
# ─────────────────────────────────────────────────────────────

import pandas as pd
from pathlib import Path
from datetime import date, datetime


# ── Folder paths ──────────────────────────────────────────────
SPOT_PATH   = Path("data/nifty/spot/nifty_spot.parquet")
RAW_ROOT    = Path("data/nifty/options/raw")
MASTER_ROOT = Path("data/nifty/options/master")


def ensure_folders():
    """
    Creates all required data folders if they don't already exist.
    Called once at the start of every pipeline run.
    """
    SPOT_PATH.parent.mkdir(parents=True, exist_ok=True)
    RAW_ROOT.mkdir(parents=True, exist_ok=True)
    MASTER_ROOT.mkdir(parents=True, exist_ok=True)
    Path("logs").mkdir(exist_ok=True)
    Path("exports").mkdir(exist_ok=True)
    print("Folders ready.")


# ─────────────────────────────────────────────────────────────
# SPOT CACHE
# ─────────────────────────────────────────────────────────────

def load_spot_cache():
    """
    Loads cached NIFTY spot prices from disk.
    Returns empty DataFrame if file doesn't exist.
    Columns: date | open | high | low | close | volume
    """
    if not SPOT_PATH.exists():
        return pd.DataFrame()

    df = pd.read_parquet(SPOT_PATH)
    df["date"] = pd.to_datetime(df["date"]).dt.date
    return df


def save_spot_cache(df):
    """Saves NIFTY spot DataFrame to disk as Parquet."""
    SPOT_PATH.parent.mkdir(parents=True, exist_ok=True)
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"])
    df.to_parquet(SPOT_PATH, index=False)
    print(f"Spot cache saved: {len(df)} rows → {SPOT_PATH}")


# ─────────────────────────────────────────────────────────────
# RAW LAYER
# ─────────────────────────────────────────────────────────────

def get_raw_file_path(symbol, strike, right, expiry_date):
    """
    Returns the file path for a raw contract Parquet file.

    Example:
      NIFTY, 23650, "call", 2026-05-19
      → data/nifty/options/raw/NIFTY_23650_CE_20260519.parquet
    """
    right_code   = "CE" if right == "call" else "PE"
    expiry_str   = expiry_date.strftime("%Y%m%d")
    filename     = f"{symbol}_{strike}_{right_code}_{expiry_str}.parquet"
    return RAW_ROOT / filename


def save_raw_chunk(df, symbol, strike, right, expiry_date):
    """
    Saves or appends a downloaded chunk to the raw layer.

    Raw files are per-contract (one file per strike+right+expiry).
    If the file already exists, the new chunk is appended and
    duplicates are removed.

    Raw files are immutable in spirit — they store exactly what
    Breeze returned, before any cleaning.

    Returns: file path as string
    """
    if df.empty:
        return ""

    file_path = get_raw_file_path(symbol, strike, right, expiry_date)

    if file_path.exists():
        # Append new chunk to existing file
        existing = pd.read_parquet(file_path)
        combined = pd.concat([existing, df], ignore_index=True)
        # Remove exact duplicates on datetime
        combined = combined.drop_duplicates(subset=["datetime"])
        combined = combined.sort_values("datetime").reset_index(drop=True)
        combined.to_parquet(file_path, index=False)
    else:
        # First chunk — create new file
        df_sorted = df.sort_values("datetime").reset_index(drop=True)
        df_sorted.to_parquet(file_path, index=False)

    return str(file_path)


def load_raw_file(symbol, strike, right, expiry_date):
    """
    Loads a raw contract file from disk.
    Returns empty DataFrame if file doesn't exist.
    """
    file_path = get_raw_file_path(symbol, strike, right, expiry_date)

    if not file_path.exists():
        return pd.DataFrame()

    return pd.read_parquet(file_path)


# ─────────────────────────────────────────────────────────────
# MASTER LAYER
# ─────────────────────────────────────────────────────────────

def get_master_partition_path(year, month):
    """
    Returns the path for a master layer monthly partition.

    Example: year=2026, month=5
      → data/nifty/options/master/symbol=NIFTY/year=2026/month=05/part.parquet
    """
    return MASTER_ROOT / f"symbol=NIFTY" / f"year={year}" / f"month={month:02d}" / "part.parquet"


def build_master_row(row, symbol, strike, right, expiry_date, ingested_at):
    """
    Converts one raw candle row into the master layer schema.
    Called row by row when building master from raw data.
    """
    right_code = "CE" if right == "call" else "PE"
    return {
        "timestamp":      row["datetime"],
        "symbol":         symbol,
        "expiry_date":    str(expiry_date),
        "strike":         strike,
        "option_type":    right_code,
        "open":           row["open"],
        "high":           row["high"],
        "low":            row["low"],
        "close":          row["close"],
        "volume":         row["volume"],
        "open_interest":  row["open_interest"],
        "validation_flag":row.get("validation_flag", ""),
        "source":         "breeze_api",
        "ingested_at":    ingested_at,
    }


def append_to_master(validated_df, symbol, strike, right, expiry_date):
    """
    Merges a validated contract DataFrame into the master layer.

    Steps:
    1. Convert to master schema (long format)
    2. Group rows by trade month (partition key = timestamp month)
    3. For each partition, append new rows and deduplicate
    4. Save each partition back to disk

    Master layer is partitioned by TRADE DATE (timestamp month),
    not expiry date. This is optimal for backtesting queries like
    "give me all options at 10:15 on May 12".
    """
    if validated_df.empty:
        return

    ingested_at = str(datetime.now())
    right_code  = "CE" if right == "call" else "PE"

    # Build master rows
    master_rows = []
    for _, row in validated_df.iterrows():
        master_rows.append({
            "timestamp":       row["datetime"],
            "symbol":          symbol,
            "expiry_date":     str(expiry_date),
            "strike":          strike,
            "option_type":     right_code,
            "open":            row["open"],
            "high":            row["high"],
            "low":             row["low"],
            "close":           row["close"],
            "volume":          row["volume"],
            "open_interest":   row["open_interest"],
            "validation_flag": row.get("validation_flag", ""),
            "source":          "breeze_api",
            "ingested_at":     ingested_at,
        })

    master_df = pd.DataFrame(master_rows)
    master_df["timestamp"] = pd.to_datetime(master_df["timestamp"])

    # Group by year+month of trade date and write each partition
    master_df["_year"]  = master_df["timestamp"].dt.year
    master_df["_month"] = master_df["timestamp"].dt.month

    for (year, month), group in master_df.groupby(["_year", "_month"]):
        group = group.drop(columns=["_year", "_month"])
        partition_path = get_master_partition_path(year, month)
        partition_path.parent.mkdir(parents=True, exist_ok=True)

        if partition_path.exists():
            # Load existing partition and merge
            existing = pd.read_parquet(partition_path)
            combined = pd.concat([existing, group], ignore_index=True)
            # Deduplicate on the natural key
            combined = combined.drop_duplicates(
                subset=["timestamp", "strike", "expiry_date", "option_type"]
            )
            combined = combined.sort_values("timestamp").reset_index(drop=True)
            combined.to_parquet(partition_path, index=False)
        else:
            # New partition
            group_sorted = group.sort_values("timestamp").reset_index(drop=True)
            group_sorted.to_parquet(partition_path, index=False)


def export_to_csv(symbol, expiry_date, strike, right, output_dir="exports"):
    """
    Exports one contract's full data from the master layer to CSV.
    Use this on demand — CSV is not stored permanently.
    """
    right_code = "CE" if right == "call" else "PE"
    filename   = f"{symbol}_{strike}_{right_code}_{expiry_date}.csv"
    output_path = Path(output_dir) / filename

    # Load from master layer using pandas filter
    import glob
    parquet_files = glob.glob(str(MASTER_ROOT / "**" / "*.parquet"), recursive=True)

    if not parquet_files:
        print("Master layer is empty. Run the pipeline first.")
        return

    dfs = []
    for f in parquet_files:
        df = pd.read_parquet(f)
        filtered = df[
            (df["symbol"]      == symbol) &
            (df["expiry_date"] == str(expiry_date)) &
            (df["strike"]      == strike) &
            (df["option_type"] == right_code)
        ]
        if not filtered.empty:
            dfs.append(filtered)

    if not dfs:
        print(f"No data found for {symbol} {strike} {right_code} {expiry_date}")
        return

    result = pd.concat(dfs).sort_values("timestamp").reset_index(drop=True)
    Path(output_dir).mkdir(exist_ok=True)
    result.to_csv(output_path, index=False)
    print(f"Exported {len(result)} rows → {output_path}")
    return str(output_path)


# ─────────────────────────────────────────────────────────────
# Run this file directly to test:
# python -m src.storage
# ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    sys.path.insert(0, ".")

    from src.auth            import create_session
    from src.atm_calculator  import update_spot_cache, compute_atm_for_expiry
    from src.expiry_generator import get_expiries_for_nifty
    from src.chunk_planner   import build_chunks
    from src.downloader      import download_chunk
    from src.validator       import validate_dataframe
    from datetime            import date

    # Connect
    breeze = create_session()
    ensure_folders()
    spot_df = update_spot_cache(breeze)

    # Pick most recent expired weekly expiry
    expiries    = get_expiries_for_nifty()
    today       = date.today()
    test_expiry = None
    for expiry_date, expiry_type in reversed(expiries):
        if expiry_date < today and expiry_type == "weekly":
            test_expiry      = expiry_date
            test_expiry_type = expiry_type
            break

    atm_info   = compute_atm_for_expiry(test_expiry, spot_df)
    atm_strike = atm_info["atm_strike"]
    chunks     = build_chunks(test_expiry, test_expiry_type)

    print(f"\nTest contract: NIFTY {atm_strike} CE expiry {test_expiry}")
    print(f"Chunks: {len(chunks)}")

    # Download first NON-EMPTY chunk
    print("\nDownloading chunks until we get data...")
    raw_df = pd.DataFrame()
    for chunk in chunks:
        raw_df = download_chunk(breeze, "NIFTY", test_expiry,
                                atm_strike, "call", chunk)
        if not raw_df.empty:
            print(f"Got {len(raw_df)} candles from chunk {chunk['chunk_index']}")
            break

    if raw_df.empty:
        print("All chunks returned empty. Try a different expiry.")
        sys.exit(1)

    # Save to raw layer
    print("\nTest 1: Save to raw layer")
    file_path = save_raw_chunk(raw_df, "NIFTY", atm_strike, "call", test_expiry)
    print(f"  Saved → {file_path}")

    # Reload and verify
    reloaded = load_raw_file("NIFTY", atm_strike, "call", test_expiry)
    print(f"  Reloaded: {len(reloaded)} rows (expected: {len(raw_df)})")

    # Validate
    print("\nTest 2: Validate raw data")
    contract_info = {"symbol": "NIFTY", "strike": atm_strike,
                     "right": "call", "expiry_date": test_expiry}
    validated_df, summary = validate_dataframe(raw_df, contract_info)
    print(f"  Clean rows  : {summary['clean_rows']}")
    print(f"  Flagged rows: {summary['flagged_rows']}")

    # Append to master layer
    print("\nTest 3: Append to master layer")
    append_to_master(validated_df, "NIFTY", atm_strike, "call", test_expiry)

    # Verify master partition was created
    year  = test_expiry.year
    month = test_expiry.month
    master_path = get_master_partition_path(year, month)
    master_df   = pd.read_parquet(master_path)
    print(f"  Master partition: {master_path}")
    print(f"  Rows in partition: {len(master_df)}")
    print(f"\nSample from master layer:")
    print(master_df[["timestamp","strike","option_type",
                      "close","volume","open_interest"]].head())

    # Test CSV export
    print("\nTest 4: CSV export")
    export_to_csv("NIFTY", test_expiry, atm_strike, "call")

    print("\nAll storage tests passed.")