import duckdb
import pandas as pd
from datetime import date

# ── Master layer dates ────────────────────────────────────────
master = duckdb.query("""
    SELECT
        CAST(timestamp AS DATE) as trade_date,
        COUNT(*)                as candles
    FROM 'data/nifty/options/master/**/*.parquet'
    GROUP BY CAST(timestamp AS DATE)
    ORDER BY trade_date
""").df()

# ── Spot cache = all valid trading days ───────────────────────
spot = pd.read_parquet("data/nifty/spot/nifty_spot.parquet")
spot["date"] = pd.to_datetime(spot["date"]).dt.date

# Filter to your slice
slice_start = date(2023, 6, 1)
slice_end   = date(2024, 5, 31)
spot_slice  = spot[
    (spot["date"] >= slice_start) &
    (spot["date"] <= slice_end)
]

# ── Compare ───────────────────────────────────────────────────
downloaded_dates = set(master["trade_date"].dt.date
                        if hasattr(master["trade_date"], "dt")
                        else pd.to_datetime(master["trade_date"]).dt.date)

all_trading_days  = set(spot_slice["date"])
pending_days      = all_trading_days - downloaded_dates
extra_days        = downloaded_dates - all_trading_days

print("=" * 55)
print("Data Coverage Report")
print("=" * 55)
print(f"Slice period       : {slice_start} to {slice_end}")
print(f"Total trading days : {len(all_trading_days)}")
print(f"Days with data     : {len(downloaded_dates & all_trading_days)}")
print(f"Days pending       : {len(pending_days)}")
print(f"Days outside slice : {len(extra_days)}")
print(f"Coverage           : {len(downloaded_dates & all_trading_days) / len(all_trading_days) * 100:.1f}%")
print()
print("First 10 pending trading days:")
for d in sorted(pending_days)[:10]:
    print(f"  {d}")
print()
print("Last 10 pending trading days:")
for d in sorted(pending_days)[-10:]:
    print(f"  {d}")
    