# ─────────────────────────────────────────────────────────────
# auth.py
# Handles Breeze API authentication.
# Supports two modes:
#   1. Interactive  — used when running from terminal
#   2. Non-interactive — used when running from web app
#      (reads session token from environment variable)
# ─────────────────────────────────────────────────────────────

import os
import webbrowser
from urllib.parse import quote
from dotenv import load_dotenv
from breeze_connect import BreezeConnect


def get_login_url():
    """Returns the Breeze login URL for the current API key."""
    load_dotenv()
    api_key = os.getenv("BREEZE_API_KEY", "").strip()
    if not api_key:
        raise ValueError("BREEZE_API_KEY not found in .env file.")
    encoded_key = quote(api_key, safe="")
    return f"https://api.icicidirect.com/apiuser/login?api_key={encoded_key}"


def create_session(session_token=None):
    """
    Creates and returns an authenticated Breeze session.

    Args:
        session_token : if provided, skips interactive login.
                        Used by the web app.
                        If None, opens browser and asks for input.
    """
    load_dotenv()
    api_key    = os.getenv("BREEZE_API_KEY",    "").strip()
    api_secret = os.getenv("BREEZE_API_SECRET", "").strip()

    if not api_key or not api_secret:
        raise ValueError(
            "API credentials not found. "
            "Check your .env file has BREEZE_API_KEY and BREEZE_API_SECRET."
        )

    breeze = BreezeConnect(api_key=api_key)

    # Non-interactive mode — token provided by web app
    if session_token:
        breeze.generate_session(
            api_secret=api_secret,
            session_token=session_token.strip()
        )
        print("Session created successfully!")
        return breeze

    # Interactive mode — open browser and ask for input
    login_url = get_login_url()

    print("")
    print("=" * 60)
    print("ACTION REQUIRED:")
    print("=" * 60)
    print("1. Your browser will open the ICICI Direct login page.")
    print("2. Log in with your ICICI Direct credentials.")
    print("3. After login, your browser redirects to a URL like:")
    print("     http://localhost:8080/?apisession=XXXXXXXXXX&...")
    print("4. Copy the value after ?apisession= and paste below.")
    print("=" * 60)
    print("")

    webbrowser.open(login_url)
    session_token = input("Paste session token here and press Enter: ").strip()

    if not session_token:
        raise ValueError("Session token cannot be empty.")

    breeze.generate_session(
        api_secret=api_secret,
        session_token=session_token
    )

    print("")
    print("Session created successfully!")
    print("")
    return breeze


def test_connection(breeze):
    """Makes one test API call to confirm session is working."""
    print("Testing connection...")
    try:
        response = breeze.get_quotes(
            stock_code="NIFTY",
            exchange_code="NSE",
            product_type="cash",
            expiry_date="",
            right="",
            strike_price=""
        )
        if response and response.get("Success"):
            print("Connection test passed.")
        else:
            print("Connection test returned empty. Session may still be valid.")
    except Exception as e:
        print(f"Connection test failed: {e}")


if __name__ == "__main__":
    breeze = create_session()
    test_connection(breeze)