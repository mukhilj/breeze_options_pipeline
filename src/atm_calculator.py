# ─────────────────────────────────────────────────────────────
# atm_calculator.py
# Two responsibilities:
#   1. Fetch and cache NIFTY daily spot prices from Breeze
#   2. For each expiry, calculate ATM strike and ± 50 strikes
# ─────────────────────────────────────────────────────────────

import pandas as pd
from datetime import date, timedelta
from src.storage import load_spot_cache, save_spot_cache


def fetch_spot_data(breeze, start_date, end_date):
    """
    Downloads NIFTY daily (EOD) spot prices from Breeze API.
    Returns empty DataFrame if no data (holiday/weekend) — not an error.
    """
    print(f"Fetching NIFTY spot data: {start_date} to {end_date}...")

    response = breeze.get_historical_data_v2(
        interval      = "1day",
        from_date     = f"{start_date}T07:00:00.000Z",
        to_date       = f"{end_date}T07:00:00.000Z",
        stock_code    = "NIFTY",
        exchange_code = "NSE",
        product_type  = "cash"
    )

    if not response:
        raise ValueError("Breeze API did not respond. Check session.")

    raw_data = response.get("Success", [])
    if not raw_data:
        print(f"  No trading data for {start_date} to {end_date} (holiday/weekend).")
        return pd.DataFrame()

    df = pd.DataFrame(raw_data)
    df = df.rename(columns={"datetime": "date"})
    df["date"]   = pd.to_datetime(df["date"]).dt.date
    df["open"]   = pd.to_numeric(df["open"],   errors="coerce")
    df["high"]   = pd.to_numeric(df["high"],   errors="coerce")
    df["low"]    = pd.to_numeric(df["low"],    errors="coerce")
    df["close"]  = pd.to_numeric(df["close"],  errors="coerce")
    df["volume"] = pd.to_numeric(df["volume"], errors="coerce").fillna(0).astype(int)

    df = df[["date", "open", "high", "low", "close", "volume"]]
    df = df.sort_values("date").reset_index(drop=True)
    df = df.dropna(subset=["close"])

    print(f"  Fetched {len(df)} trading days of spot data.")
    return df


def update_spot_cache(breeze):
    """
    Downloads only missing spot data and merges with existing cache.
    """
    today      = date.today()
    years_back = date(today.year - 3, today.month, today.day)
    existing   = load_spot_cache()

    if existing.empty:
        print("Spot cache is empty. Downloading 3 years of data...")
        start_date = years_back
    else:
        last_date  = existing["date"].max()
        start_date = last_date + timedelta(days=1)
        print(f"Spot cache has data till {last_date}. Fetching from {start_date}...")
        if start_date > today:
            print("Spot cache is already up to date.")
            return existing

    new_data = fetch_spot_data(breeze, start_date, today)

    if new_data.empty:
        print("Spot cache is up to date. No new data to add.")
        return existing

    combined = new_data if existing.empty else pd.concat([existing, new_data], ignore_index=True)
    combined = combined.drop_duplicates(subset=["date"])
    combined = combined.sort_values("date").reset_index(drop=True)
    save_spot_cache(combined)
    return combined


def get_spot_on_date(spot_df, target_date):
    """
    Returns NIFTY close price nearest to target_date.

    Search order:
    1. Walk BACK up to 7 days (covers weekends/holidays before target)
    2. Walk FORWARD up to 7 days (handles edge case: target before cache start)
    """
    # Try walking back first (normal case)
    check_date = target_date
    for _ in range(7):
        row = spot_df[spot_df["date"] == check_date]
        if not row.empty:
            return check_date, float(row.iloc[0]["close"])
        check_date = check_date - timedelta(days=1)

    # Fallback: walk forward (handles dates before cache start)
    check_date = target_date + timedelta(days=1)
    for _ in range(7):
        row = spot_df[spot_df["date"] == check_date]
        if not row.empty:
            return check_date, float(row.iloc[0]["close"])
        check_date = check_date + timedelta(days=1)

    raise ValueError(
        f"No spot data found within 7 days of {target_date}. "
        f"Cache range: {spot_df['date'].min()} to {spot_df['date'].max()}"
    )


def calculate_atm_strike(spot_price, interval=50):
    """Rounds spot price to nearest strike interval."""
    return round(spot_price / interval) * interval


def get_strike_list(atm_strike, strikes_each_side=50, interval=50):
    """Generates 101 strikes centred around ATM."""
    low  = atm_strike - (strikes_each_side * interval)
    high = atm_strike + (strikes_each_side * interval)
    return list(range(low, high + interval, interval))


def compute_atm_for_expiry(expiry_date, spot_df, strikes_each_side=50, interval=50):
    """Calculates ATM strike using spot on Monday of expiry week."""
    days_since_monday = expiry_date.weekday()
    monday            = expiry_date - timedelta(days=days_since_monday)
    ref_date, spot    = get_spot_on_date(spot_df, monday)
    atm_strike        = calculate_atm_strike(spot, interval)
    strike_list       = get_strike_list(atm_strike, strikes_each_side, interval)

    return {
        "expiry_date":  expiry_date,
        "atm_ref_date": ref_date,
        "spot_used":    spot,
        "atm_strike":   atm_strike,
        "strike_low":   strike_list[0],
        "strike_high":  strike_list[-1],
        "strikes":      strike_list,
        "method":       "first_week_trading_day"
    }