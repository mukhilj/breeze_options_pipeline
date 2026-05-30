# ─────────────────────────────────────────────────────────────
# downloader.py
# Makes a single Breeze API call for one (contract × chunk).
# Handles retries, backoff, empty responses, and API errors.
#
# Breeze API parameters for options:
#   stock_code    : "NIFTY"
#   exchange_code : "NFO"
#   product_type  : "options"
#   expiry_date   : "2026-05-19T07:00:00.000Z"
#   strike_price  : "24400"
#   right         : "call" or "put"
#   interval      : "1minute"
#   from_date     : "2026-05-12T09:15:00.000Z"
#   to_date       : "2026-05-13T15:29:00.000Z"
# ─────────────────────────────────────────────────────────────

import time
import pandas as pd
from src.rate_limiter import rate_limiter, DailyBudgetExhausted


# ── Retry settings ────────────────────────────────────────────
MAX_RETRIES      = 3       # Try up to 3 times before giving up
BACKOFF_BASE_SEC = 2       # Wait 2s, 4s, 8s between retries


def download_chunk(breeze, symbol, expiry_date, strike, right, chunk):
    """
    Downloads one chunk of 1-min OHLCV+OI data for one options contract.

    Args:
        breeze      : authenticated BreezeConnect object
        symbol      : "NIFTY"
        expiry_date : date object — contract expiry
        strike      : int — strike price e.g. 24400
        right       : "call" or "put"
        chunk       : dict from chunk_planner with from_dt, to_dt, chunk_index

    Returns:
        pd.DataFrame with columns:
          datetime | open | high | low | close | volume | open_interest
        Returns empty DataFrame if no data available for this chunk.

    Raises:
        DailyBudgetExhausted — propagated up, stops the pipeline for today
        Exception            — after all retries exhausted
    """

    # Format expiry date for Breeze API
    expiry_str = f"{expiry_date}T07:00:00.000Z"

    # Log what we are about to download
    print(
        f"    Chunk {chunk['chunk_index']:2d} | "
        f"{symbol} {strike} {right.upper()} {expiry_date} | "
        f"{chunk['from_date']} → {chunk['to_date']}",
        end=" ... "
    )

    last_error = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            # Ask rate limiter for permission — blocks if needed
            rate_limiter.acquire()

            # Make the API call
            response = breeze.get_historical_data_v2(
                interval      = "1minute",
                from_date     = chunk["from_dt"],
                to_date       = chunk["to_dt"],
                stock_code    = symbol,
                exchange_code = "NFO",
                product_type  = "options",
                expiry_date   = expiry_str,
                strike_price  = str(strike),
                right         = right   # "call" or "put"
            )

            # ── Handle HTTP 429 ────────────────────────────────
            if isinstance(response, dict) and response.get("Status") == 429:
                rate_limiter.on_429()
                continue  # retry after backoff

            # ── Handle empty / error response ──────────────────
            if not response:
                print(f"empty response (attempt {attempt})")
                last_error = "Empty response from API"
                _backoff(attempt)
                continue

            # ── Check for error status ─────────────────────────
            if isinstance(response, dict) and response.get("Status") not in (None, 200, "200"):
                error_msg = response.get("Error", str(response))
                print(f"API error: {error_msg} (attempt {attempt})")
                last_error = error_msg
                _backoff(attempt)
                continue

            # ── Extract data ───────────────────────────────────
            raw_data = response.get("Success", [])

            if not raw_data:
                # No data for this chunk — option may not have been
                # listed yet, or deep OTM with zero trades
                print("no data (option not listed or no trades)")
                return pd.DataFrame()

            # ── Build DataFrame ────────────────────────────────
            df = pd.DataFrame(raw_data)
            df = _clean_dataframe(df)

            print(f"OK — {len(df)} candles")
            return df

        except DailyBudgetExhausted:
            # Don't retry — propagate immediately
            raise

        except Exception as e:
            last_error = str(e)
            print(f"error: {e} (attempt {attempt})")
            _backoff(attempt)

    # All retries exhausted
    print(f"FAILED after {MAX_RETRIES} attempts. Last error: {last_error}")
    raise Exception(
        f"Download failed for {symbol} {strike} {right} {expiry_date} "
        f"chunk {chunk['chunk_index']}: {last_error}"
    )


def _backoff(attempt):
    """
    Waits for exponential backoff time before the next retry.
    Attempt 1 → wait 2s
    Attempt 2 → wait 4s
    Attempt 3 → wait 8s
    """
    wait = BACKOFF_BASE_SEC ** attempt
    print(f"  Backing off {wait}s before retry...")
    time.sleep(wait)


def _clean_dataframe(df):
    """
    Standardises the raw DataFrame returned by Breeze.
    Renames columns, converts types, sorts by datetime.
    """
    # Rename columns to our standard names
    rename_map = {
        "datetime":       "datetime",
        "open":           "open",
        "high":           "high",
        "low":            "low",
        "close":          "close",
        "volume":         "volume",
        "open_interest":  "open_interest",
    }

    # Keep only columns that exist in the response
    existing = {k: v for k, v in rename_map.items() if k in df.columns}
    df = df[list(existing.keys())].rename(columns=existing)

    # Add open_interest column if Breeze did not return it
    if "open_interest" not in df.columns:
        df["open_interest"] = 0

    # Convert types
    df["datetime"]      = pd.to_datetime(df["datetime"])
    df["open"]          = pd.to_numeric(df["open"],         errors="coerce")
    df["high"]          = pd.to_numeric(df["high"],         errors="coerce")
    df["low"]           = pd.to_numeric(df["low"],          errors="coerce")
    df["close"]         = pd.to_numeric(df["close"],        errors="coerce")
    df["volume"]        = pd.to_numeric(df["volume"],       errors="coerce").fillna(0).astype(int)
    df["open_interest"] = pd.to_numeric(df["open_interest"],errors="coerce").fillna(0).astype(int)

    # Sort by datetime ascending
    df = df.sort_values("datetime").reset_index(drop=True)

    return df


# ─────────────────────────────────────────────────────────────
# Run this file directly to test:
# python -m src.downloader
#
# Downloads ONE real chunk from Breeze to verify end-to-end.
# Uses the most recent expired weekly expiry as test contract.
# ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    sys.path.insert(0, ".")

    from datetime import date
    from src.auth            import create_session
    from src.storage         import ensure_folders, load_spot_cache
    from src.atm_calculator  import update_spot_cache, compute_atm_for_expiry
    from src.chunk_planner   import build_chunks
    from src.expiry_generator import get_expiries_for_nifty

    # Connect to Breeze
    breeze = create_session()
    ensure_folders()

    # Load spot cache
    spot_df = update_spot_cache(breeze)

    # Pick the most recent expired weekly expiry for testing
    expiries = get_expiries_for_nifty()
    today    = date.today()

    test_expiry = None
    for expiry_date, expiry_type in reversed(expiries):
        if expiry_date < today and expiry_type == "weekly":
            test_expiry      = expiry_date
            test_expiry_type = expiry_type
            break

    if not test_expiry:
        print("No past weekly expiry found. Exiting.")
        sys.exit(1)

    print(f"\nTest contract: NIFTY ATM CE — expiry {test_expiry} ({test_expiry_type})")

    # Get ATM strike for this expiry
    atm_info = compute_atm_for_expiry(test_expiry, spot_df)
    atm_strike = atm_info["atm_strike"]
    print(f"ATM strike: {atm_strike}")

    # Get chunks for this contract
    chunks = build_chunks(test_expiry, test_expiry_type)
    print(f"Total chunks: {len(chunks)}")

    # Download only the FIRST chunk as a test
    print(f"\nDownloading chunk 0 only (test)...")
    df = download_chunk(
        breeze      = breeze,
        symbol      = "NIFTY",
        expiry_date = test_expiry,
        strike      = atm_strike,
        right       = "call",
        chunk       = chunks[0]
    )

    if df.empty:
        print("Empty DataFrame returned (option may not have been listed yet).")
        print("Try chunk 1 or 2 — they are closer to expiry date.")
    else:
        print(f"\nData sample (first 5 rows):")
        print(df.head())
        print(f"\nData sample (last 5 rows):")
        print(df.tail())
        print(f"\nTotal candles in this chunk: {len(df)}")
        print(f"Columns: {list(df.columns)}")