# ─────────────────────────────────────────────────────────────
# setup.py
# Run this once before your first download to configure
# your API credentials and assigned date slice.
#
# Usage: python setup.py
# ─────────────────────────────────────────────────────────────

import yaml
import os
from pathlib import Path
from datetime import date


def save_env(api_key, api_secret):
    """Saves API credentials to .env file."""
    with open(".env", "w") as f:
        f.write(f"BREEZE_API_KEY={api_key}\n")
        f.write(f"BREEZE_API_SECRET={api_secret}\n")
    print("  Credentials saved to .env")


def save_config(start_date, end_date):
    """Saves date slice to config.yaml."""
    with open("config/config.yaml", "r") as f:
        config = yaml.safe_load(f)
    config["download_slice"]["start_expiry"] = start_date
    config["download_slice"]["end_expiry"]   = end_date
    with open("config/config.yaml", "w") as f:
        yaml.dump(config, f, default_flow_style=False)
    print("  Date slice saved to config/config.yaml")


def validate_date(date_str):
    """Checks if date string is in YYYY-MM-DD format."""
    try:
        date.fromisoformat(date_str)
        return True
    except ValueError:
        return False


def main():
    print("")
    print("=" * 55)
    print("  NIFTY Options Pipeline — Setup")
    print("=" * 55)
    print("")

    # ── API Credentials ───────────────────────────────────────
    print("Step 1: Enter your Breeze API credentials")
    print("  (Get these from https://api.icicidirect.com)")
    print("")

    api_key = input("  Breeze API Key    : ").strip()
    if not api_key:
        print("  ERROR: API Key cannot be empty.")
        return

    api_secret = input("  Breeze API Secret : ").strip()
    if not api_secret:
        print("  ERROR: API Secret cannot be empty.")
        return

    print("")

    # ── Date Slice ────────────────────────────────────────────
    print("Step 2: Enter your assigned date slice")
    print("  (Check the slice assignment table in README)")
    print("  Format: YYYY-MM-DD  e.g. 2024-01-01")
    print("")

    while True:
        start_date = input("  Start Date : ").strip()
        if validate_date(start_date):
            break
        print("  Invalid format. Use YYYY-MM-DD e.g. 2023-06-01")

    while True:
        end_date = input("  End Date   : ").strip()
        if validate_date(end_date):
            if end_date > start_date:
                break
            print("  End date must be after start date.")
        else:
            print("  Invalid format. Use YYYY-MM-DD e.g. 2024-05-31")

    print("")

    # ── Save ──────────────────────────────────────────────────
    print("Saving settings...")
    save_env(api_key, api_secret)
    save_config(start_date, end_date)

    print("")
    print("=" * 55)
    print("  Setup complete!")
    print("=" * 55)
    print("")
    print("Next steps:")
    print("")
    print("  1. Run auth to login to Breeze:")
    print("       python -m src.auth")
    print("")
    print("  2. Run the pipeline:")
    print("       python -m src.main")
    print("")
    print("  Repeat step 2 every day until your slice is done.")
    print("")


if __name__ == "__main__":
    main()