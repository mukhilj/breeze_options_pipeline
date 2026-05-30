# ─────────────────────────────────────────────────────────────
# chunk_planner.py
# Splits one options contract's date range into chunks of
# max 1,000 candles each (Breeze API hard cap).
#
# 1-min data = 375 candles per trading day (09:15 to 15:29)
# 1,000 candles ÷ 375 = 2.67 days → use 2 trading days per chunk
# This gives ~750 candles per chunk — safely within the 1,000 cap
#
# Listing date logic:
#   Weekly option  → goes back 10 calendar days (safe buffer for 1 week)
#   Monthly option → goes back 35 calendar days (safe buffer for 4 weeks)
# ─────────────────────────────────────────────────────────────

from datetime import date, timedelta


# Market open/close times in Breeze API format
MARKET_OPEN  = "09:15:00"
MARKET_CLOSE = "15:29:00"

# Trading days per chunk — 2 days × 375 candles = 750 (under 1,000 cap)
TRADING_DAYS_PER_CHUNK = 2

# How far back to estimate listing date
WEEKLY_LOOKBACK_DAYS  = 10   # weekly option: ~1 week life
MONTHLY_LOOKBACK_DAYS = 35   # monthly option: ~4 week life


def get_listing_date(expiry_date, expiry_type="weekly"):
    """
    Estimates the listing date of a NIFTY options contract.

    Weekly options  : listed ~7 days before expiry (we use 10 for buffer)
    Monthly options : listed ~28 days before expiry (we use 35 for buffer)

    If we request data before actual listing, Breeze returns empty —
    handled cleanly in the downloader.
    """
    if expiry_type == "monthly":
        return expiry_date - timedelta(days=MONTHLY_LOOKBACK_DAYS)
    else:
        return expiry_date - timedelta(days=WEEKLY_LOOKBACK_DAYS)


def get_trading_days_in_range(start_date, end_date, holidays=None):
    """
    Returns list of all trading days (Mon–Fri, excluding holidays)
    between start_date and end_date inclusive.
    """
    if holidays is None:
        holidays = set()

    trading_days = []
    current = start_date

    while current <= end_date:
        # Skip weekends (Sat=5, Sun=6) and holidays
        if current.weekday() < 5 and current not in holidays:
            trading_days.append(current)
        current += timedelta(days=1)

    return trading_days


def build_chunks(expiry_date, expiry_type="weekly", holidays=None):
    """
    Builds a list of date-range chunks for one contract.

    Steps:
    1. Find listing date based on expiry type
    2. Get all trading days from listing to expiry (or today if still live)
    3. Split into groups of TRADING_DAYS_PER_CHUNK (2 days)
    4. Format each group as Breeze API datetime strings

    Args:
        expiry_date  : date object — contract expiry date
        expiry_type  : "weekly" or "monthly"
        holidays     : set of date objects (NSE holidays)

    Returns:
        List of dicts, each containing:
          chunk_index : 0, 1, 2, ...
          from_dt     : Breeze API format string e.g. "2026-05-19T09:15:00.000Z"
          to_dt       : Breeze API format string
          from_date   : date object (for display/logging)
          to_date     : date object (for display/logging)
    """
    if holidays is None:
        holidays = set()

    listing_date = get_listing_date(expiry_date, expiry_type)
    today        = date.today()

    # If contract is still live, only fetch up to today
    end_date = min(expiry_date, today)

    # Get all valid trading days in this contract's life
    trading_days = get_trading_days_in_range(listing_date, end_date, holidays)

    if not trading_days:
        return []

    # Split into groups of TRADING_DAYS_PER_CHUNK
    chunks = []
    for i in range(0, len(trading_days), TRADING_DAYS_PER_CHUNK):
        group = trading_days[i : i + TRADING_DAYS_PER_CHUNK]

        from_date = group[0]
        to_date   = group[-1]

        chunks.append({
            "chunk_index": len(chunks),
            "from_dt":     f"{from_date}T{MARKET_OPEN}.000Z",
            "to_dt":       f"{to_date}T{MARKET_CLOSE}.000Z",
            "from_date":   from_date,
            "to_date":     to_date,
        })

    return chunks


# ─────────────────────────────────────────────────────────────
# Run this file directly to test:
# python -m src.chunk_planner
# ─────────────────────────────────────────────────────────────
if __name__ == "__main__":

    print("=" * 55)
    print("Test 1: Weekly expiry — 2026-05-19")
    print("=" * 55)
    chunks = build_chunks(date(2026, 5, 19), expiry_type="weekly")
    print(f"Total chunks : {len(chunks)}  (expected: ~2)")
    for c in chunks:
        print(f"  Chunk {c['chunk_index']} : {c['from_date']} to {c['to_date']}")

    print()
    print("=" * 55)
    print("Test 2: Monthly expiry — 2026-04-28")
    print("=" * 55)
    chunks = build_chunks(date(2026, 4, 28), expiry_type="monthly")
    print(f"Total chunks : {len(chunks)}  (expected: ~8)")
    for c in chunks:
        print(f"  Chunk {c['chunk_index']} : {c['from_date']} to {c['to_date']}")

    print()
    print("=" * 55)
    print("Test 3: API format check — first 2 chunks of monthly")
    print("=" * 55)
    chunks = build_chunks(date(2026, 4, 28), expiry_type="monthly")
    for c in chunks[:2]:
        print(f"  Chunk {c['chunk_index']}:")
        print(f"    from_dt : {c['from_dt']}")
        print(f"    to_dt   : {c['to_dt']}")

    print()
    print("=" * 55)
    print("Test 4: API call count estimate for 3 years")
    print("=" * 55)
    # Weekly: 121 expiries × ~2 chunks × 202 contracts
    # Monthly: 36 expiries × ~8 chunks × 202 contracts
    weekly_calls  = 121 * 2 * 202
    monthly_calls = 36  * 8 * 202
    total_calls   = weekly_calls + monthly_calls
    days_needed   = total_calls / 4500
    print(f"  Weekly  : 121 × 2 chunks × 202 contracts = {weekly_calls:,} calls")
    print(f"  Monthly :  36 × 8 chunks × 202 contracts = {monthly_calls:,} calls")
    print(f"  Total   : {total_calls:,} calls")
    print(f"  Days to complete initial seed (@4500/day) : ~{days_needed:.0f} days")