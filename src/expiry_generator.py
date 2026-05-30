# ─────────────────────────────────────────────────────────────
# expiry_generator.py
# Generates all valid NIFTY expiry dates for the last N years.
#
# NIFTY expiry day history:
#   Up to Aug 28, 2025  → every Thursday (weekly + monthly)
#   Sep 1, 2025 onwards → every Tuesday  (weekly + monthly)
#
# If expiry falls on NSE holiday → shift to previous trading day
# ─────────────────────────────────────────────────────────────

import csv
from datetime import date, timedelta
from pathlib import Path

# Python weekday numbers: Monday=0, Tuesday=1, Wednesday=2,
#                         Thursday=3, Friday=4, Sat=5, Sun=6
THURSDAY = 3
TUESDAY  = 1

# Last Thursday-based expiry
LAST_THURSDAY_EXPIRY = date(2025, 8, 28)

# First Tuesday-based expiry
FIRST_TUESDAY_EXPIRY = date(2025, 9, 2)


def load_holidays(holidays_path="config/nse_holidays.csv"):
    """
    Reads nse_holidays.csv and returns a Python set of holiday dates.
    A set lets us check "is this date a holiday?" instantly.
    """
    holidays = set()
    path = Path(holidays_path)

    if not path.exists():
        print("Warning: config/nse_holidays.csv not found.")
        print("Expiry dates will not be adjusted for holidays.")
        return holidays

    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                # Convert the date string "2026-01-26" into a Python date object
                holidays.add(date.fromisoformat(row["date"].strip()))
            except Exception:
                pass  # Skip any malformed rows

    print(f"Loaded {len(holidays)} NSE holidays from {holidays_path}")
    return holidays


def adjust_for_holiday(expiry_date, holidays):
    """
    If an expiry date lands on a holiday or weekend,
    keep moving one day back until we find a valid trading day.

    Example:
      Thursday April 10, 2025 = Ram Navami (holiday)
      → move back to Wednesday April 9, 2025
    """
    while expiry_date in holidays or expiry_date.weekday() >= 5:
        expiry_date -= timedelta(days=1)
    return expiry_date


def is_last_weekday_of_month(d):
    """
    Returns True if date d is the last occurrence of its weekday
    in that calendar month.

    Example: Is Thursday May 29 the last Thursday of May? Yes.
    Logic:   Add 7 days. If that lands in the next month → yes.
    """
    return (d + timedelta(days=7)).month != d.month


def get_all_expiries(start_date, end_date, holidays):
    """
    Core function. Walks every calendar day from start to end.
    On each day, checks:
      1. Is this the target expiry weekday?
         (Thursday before Sep 1 2025, Tuesday from Sep 1 2025)
      2. Is this a weekly or monthly expiry?
      3. Adjust for holidays.

    Returns a sorted list of tuples: [(date, "weekly"/"monthly"), ...]
    """
    # Use a dict to store expiries — key=date, value=type
    # Dict automatically handles duplicates (two expiries collapsing
    # to same date after holiday adjustment)
    expiries = {}

    current = start_date
    while current <= end_date:

        # Decide which weekday is expiry day for this date
        if current <= LAST_THURSDAY_EXPIRY:
            target_weekday = THURSDAY
        else:
            target_weekday = TUESDAY

        # Check if today is the target expiry weekday
        if current.weekday() == target_weekday:

            # Is this the last occurrence of this weekday in the month?
            expiry_type = "monthly" if is_last_weekday_of_month(current) else "weekly"

            # Shift back if this day is a holiday
            adjusted_date = adjust_for_holiday(current, holidays)

            # Handle collision: if two dates adjust to same day,
            # always prefer "monthly" over "weekly"
            if adjusted_date in expiries:
                if expiry_type == "monthly":
                    expiries[adjusted_date] = "monthly"
            else:
                expiries[adjusted_date] = expiry_type

        # Move to next day
        current += timedelta(days=1)

    # Sort by date and return as list of tuples
    return sorted(expiries.items())


def get_expiries_for_nifty(years_back=3):
    """
    Main entry point for the pipeline.
    Returns all NIFTY expiries from (today minus years_back) to today.

    Usage:
        from src.expiry_generator import get_expiries_for_nifty
        expiries = get_expiries_for_nifty()
    """
    today      = date.today()
    start_date = date(today.year - years_back, today.month, today.day)

    print(f"\nGenerating NIFTY expiries from {start_date} to {today}...")

    holidays = load_holidays()
    expiries = get_all_expiries(start_date, today, holidays)

    weekly_count  = sum(1 for _, t in expiries if t == "weekly")
    monthly_count = sum(1 for _, t in expiries if t == "monthly")

    print(f"\nTotal expiries : {len(expiries)}")
    print(f"  Weekly       : {weekly_count}")
    print(f"  Monthly      : {monthly_count}")
    print(f"  First expiry : {expiries[0][0]}")
    print(f"  Last expiry  : {expiries[-1][0]}")

    return expiries


# ─────────────────────────────────────────────────────────────
# Run this file directly to test:
# python src/expiry_generator.py
# ─────────────────────────────────────────────────────────────
if __name__ == "__main__":

    expiries = get_expiries_for_nifty()

    # Print first 10
    print("\nFirst 10 expiries:")
    print(f"  {'Date':<15} {'Day':<12} {'Type'}")
    print(f"  {'-'*35}")
    for d, t in expiries[:10]:
        print(f"  {str(d):<15} {d.strftime('%A'):<12} {t}")

    # Print last 10
    print("\nLast 10 expiries:")
    print(f"  {'Date':<15} {'Day':<12} {'Type'}")
    print(f"  {'-'*35}")
    for d, t in expiries[-10:]:
        print(f"  {str(d):<15} {d.strftime('%A'):<12} {t}")

    # Print the Thursday → Tuesday transition window
    print("\nTransition window (Aug–Sep 2025):")
    print(f"  {'Date':<15} {'Day':<12} {'Type'}")
    print(f"  {'-'*35}")
    for d, t in expiries:
        if date(2025, 8, 1) <= d <= date(2025, 9, 30):
            print(f"  {str(d):<15} {d.strftime('%A'):<12} {t}")