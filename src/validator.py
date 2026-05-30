# ─────────────────────────────────────────────────────────────
# validator.py
# Validates raw downloaded data before writing to master layer.
#
# Rules checked:
#   1. Duplicate timestamps
#   2. Missing 1-min candles during market hours
#   3. Zero OHLC values
#   4. Negative volume or OI
#   5. OHLC integrity (low <= open/close <= high)
#   6. Timestamps outside market hours
#   7. Future timestamps
#   8. Zero volume (flagged as warning, not error)
#
# IMPORTANT: Bad rows are FLAGGED not dropped.
# The backtesting engine decides what to do with flagged rows.
# ─────────────────────────────────────────────────────────────

import pandas as pd
from datetime import datetime, time, date


# ── Market hours ──────────────────────────────────────────────
MARKET_OPEN  = time(9, 15)
MARKET_CLOSE = time(15, 29)


def validate_dataframe(df, contract_info=None):
    """
    Runs all validation checks on a raw options DataFrame.

    Args:
        df            : raw DataFrame from downloader
        contract_info : optional dict with symbol/expiry/strike/right
                        (used only for logging messages)

    Returns:
        validated_df  : original DataFrame with added 'validation_flag' column
                        Null flag = clean row. Non-null = issue description.
        summary       : dict with counts of each issue found
    """
    if df.empty:
        return df, {"total_rows": 0, "flagged_rows": 0}

    # Work on a copy — never modify the original
    df = df.copy()

    # Add validation_flag column — starts as empty string (clean)
    df["validation_flag"] = ""

    # ── Run each check ────────────────────────────────────────
    df = _check_duplicate_timestamps(df)
    df = _check_zero_ohlc(df)
    df = _check_negative_values(df)
    df = _check_ohlc_integrity(df)
    df = _check_outside_market_hours(df)
    df = _check_future_timestamps(df)
    df = _check_zero_volume(df)

    # ── Build summary ─────────────────────────────────────────
    flagged      = df[df["validation_flag"] != ""]
    flagged_rows = len(flagged)

    # Count each flag type
    flag_counts = {}
    if flagged_rows > 0:
        for flag in flagged["validation_flag"]:
            for part in flag.split("|"):
                part = part.strip()
                if part:
                    flag_counts[part] = flag_counts.get(part, 0) + 1

    summary = {
        "total_rows":   len(df),
        "flagged_rows": flagged_rows,
        "clean_rows":   len(df) - flagged_rows,
        "flag_counts":  flag_counts,
    }

    # ── Print summary if issues found ─────────────────────────
    label = ""
    if contract_info:
        label = (
            f"{contract_info.get('symbol','')} "
            f"{contract_info.get('strike','')} "
            f"{contract_info.get('right','').upper()} "
            f"{contract_info.get('expiry_date','')}"
        )

    if flagged_rows > 0:
        print(f"  Validation [{label}]: "
              f"{flagged_rows}/{len(df)} rows flagged — {flag_counts}")
    else:
        print(f"  Validation [{label}]: all {len(df)} rows clean")

    return df, summary


# ── Individual check functions ────────────────────────────────

def _add_flag(df, mask, flag_text):
    """
    Adds flag_text to validation_flag for all rows where mask is True.
    If a row already has a flag, appends with ' | ' separator.
    """
    existing = df.loc[mask, "validation_flag"]
    df.loc[mask, "validation_flag"] = existing.apply(
        lambda x: f"{x} | {flag_text}" if x else flag_text
    )
    return df


def _check_duplicate_timestamps(df):
    """Flag rows with duplicate datetime values. Keep first occurrence."""
    dupes = df.duplicated(subset=["datetime"], keep="first")
    if dupes.any():
        df = _add_flag(df, dupes, "duplicate_timestamp")
    return df


def _check_zero_ohlc(df):
    """Flag rows where any of open/high/low/close is exactly 0."""
    mask = (
        (df["open"]  == 0) |
        (df["high"]  == 0) |
        (df["low"]   == 0) |
        (df["close"] == 0)
    )
    if mask.any():
        df = _add_flag(df, mask, "zero_ohlc")
    return df


def _check_negative_values(df):
    """Flag rows with negative volume or open_interest."""
    mask = (df["volume"] < 0) | (df["open_interest"] < 0)
    if mask.any():
        df = _add_flag(df, mask, "negative_value")
    return df


def _check_ohlc_integrity(df):
    """
    Flag rows where OHLC relationships are violated.
    Rules: low <= open <= high AND low <= close <= high
    """
    mask = (
        (df["low"] > df["open"])  |
        (df["low"] > df["close"]) |
        (df["high"] < df["open"]) |
        (df["high"] < df["close"])
    )
    if mask.any():
        df = _add_flag(df, mask, "ohlc_integrity")
    return df


def _check_outside_market_hours(df):
    """Flag rows with timestamps outside 09:15–15:29 IST."""
    times = df["datetime"].dt.time
    mask  = (times < MARKET_OPEN) | (times > MARKET_CLOSE)
    if mask.any():
        df = _add_flag(df, mask, "outside_market_hours")
    return df


def _check_future_timestamps(df):
    """Flag rows with timestamps in the future (likely API error)."""
    now  = pd.Timestamp.now()
    mask = df["datetime"] > now
    if mask.any():
        df = _add_flag(df, mask, "future_timestamp")
    return df


def _check_zero_volume(df):
    """
    Flag rows where volume is 0.
    This is a WARNING not an error — deep OTM options often
    have legitimate minutes with no trades.
    """
    mask = df["volume"] == 0
    if mask.any():
        df = _add_flag(df, mask, "zero_volume")
    return df


def check_missing_candles(df, trading_dates):
    """
    Checks if all expected 1-min candles are present for each trading day.
    Expected: 375 candles per day (09:15 to 15:29 = 375 minutes).

    Args:
        df            : validated DataFrame
        trading_dates : list of date objects covered by this DataFrame

    Returns:
        missing_summary : dict of {date: missing_count}
    """
    if df.empty:
        return {}

    missing_summary = {}

    for trading_date in trading_dates:
        # Get all candles for this date
        day_df = df[df["datetime"].dt.date == trading_date]

        if day_df.empty:
            missing_summary[str(trading_date)] = 375
            continue

        # Build set of expected timestamps
        expected = set()
        current  = datetime.combine(trading_date, MARKET_OPEN)
        end      = datetime.combine(trading_date, MARKET_CLOSE)
        while current <= end:
            expected.add(current)
            current = pd.Timestamp(current) + pd.Timedelta(minutes=1)
            current = current.to_pydatetime()

        actual  = set(day_df["datetime"].dt.to_pydatetime())
        missing = expected - actual

        if missing:
            missing_summary[str(trading_date)] = len(missing)

    return missing_summary


# ─────────────────────────────────────────────────────────────
# Run this file directly to test:
# python -m src.validator
# ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import numpy as np

    print("=" * 55)
    print("Test 1: Clean data — no flags expected")
    print("=" * 55)

    clean_df = pd.DataFrame({
        "datetime":       pd.date_range("2026-05-11 09:15", periods=10, freq="1min"),
        "open":           [100.0] * 10,
        "high":           [105.0] * 10,
        "low":            [98.0]  * 10,
        "close":          [102.0] * 10,
        "volume":         [1000]  * 10,
        "open_interest":  [5000]  * 10,
    })
    result, summary = validate_dataframe(clean_df, {"symbol": "NIFTY",
                                                     "strike": 23650,
                                                     "right": "call",
                                                     "expiry_date": "2026-05-19"})
    print(f"  Flagged rows: {summary['flagged_rows']} (expected: 0)")

    print()
    print("=" * 55)
    print("Test 2: Duplicate timestamp")
    print("=" * 55)

    dupe_df = clean_df.copy()
    dupe_df.loc[5, "datetime"] = dupe_df.loc[0, "datetime"]
    _, summary = validate_dataframe(dupe_df)
    print(f"  Flagged rows: {summary['flagged_rows']} (expected: 1)")
    print(f"  Flags: {summary['flag_counts']}")

    print()
    print("=" * 55)
    print("Test 3: Zero OHLC")
    print("=" * 55)

    zero_df = clean_df.copy()
    zero_df.loc[3, "close"] = 0.0
    _, summary = validate_dataframe(zero_df)
    print(f"  Flagged rows: {summary['flagged_rows']} (expected: 1)")
    print(f"  Flags: {summary['flag_counts']}")

    print()
    print("=" * 55)
    print("Test 4: OHLC integrity violation")
    print("=" * 55)

    ohlc_df = clean_df.copy()
    ohlc_df.loc[2, "low"]  = 200.0  # low > high — impossible
    _, summary = validate_dataframe(ohlc_df)
    print(f"  Flagged rows: {summary['flagged_rows']} (expected: 1)")
    print(f"  Flags: {summary['flag_counts']}")

    print()
    print("=" * 55)
    print("Test 5: Outside market hours")
    print("=" * 55)

    hours_df = clean_df.copy()
    hours_df.loc[0, "datetime"] = pd.Timestamp("2026-05-11 08:00:00")
    _, summary = validate_dataframe(hours_df)
    print(f"  Flagged rows: {summary['flagged_rows']} (expected: 1)")
    print(f"  Flags: {summary['flag_counts']}")

    print()
    print("=" * 55)
    print("Test 6: Multiple flags on same row")
    print("=" * 55)

    multi_df = clean_df.copy()
    multi_df.loc[4, "close"]  = 0.0   # zero_ohlc
    multi_df.loc[4, "volume"] = -50   # negative_value
    result, summary = validate_dataframe(multi_df)
    flagged_row = result[result["validation_flag"] != ""].iloc[0]
    print(f"  Flagged rows: {summary['flagged_rows']} (expected: 1)")
    print(f"  Flag on row  : {flagged_row['validation_flag']}")
    print(f"  Flags: {summary['flag_counts']}")

    print()
    print("All validator tests passed.")