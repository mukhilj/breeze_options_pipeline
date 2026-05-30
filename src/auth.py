# ─────────────────────────────────────────────────────────────
# auth.py
# Handles Breeze API authentication.
# Reads credentials from .env file — never from config directly.
# ─────────────────────────────────────────────────────────────

import os
import webbrowser
from urllib.parse import quote
from dotenv import load_dotenv
from breeze_connect import BreezeConnect


def create_session():
    # Load credentials from .env file
    load_dotenv()
    api_key    = os.getenv("BREEZE_API_KEY")
    api_secret = os.getenv("BREEZE_API_SECRET")

    # Make sure credentials are present
    if not api_key or not api_secret:
        raise ValueError(
            "API credentials not found. "
            "Check your .env file has BREEZE_API_KEY and BREEZE_API_SECRET."
        )

    # Create Breeze object
    breeze = BreezeConnect(api_key=api_key)

    # URL-encode the api_key so special characters like # ! ~ don't break the URL
    encoded_key = quote(api_key, safe="")
    login_url = "https://api.icicidirect.com/apiuser/login?api_key=" + encoded_key

    print("")
    print("============================================================")
    print("ACTION REQUIRED:")
    print("============================================================")
    print("1. Your browser will open the ICICI Direct login page.")
    print("2. Log in with your ICICI Direct credentials.")
    print("3. After login, your browser will redirect to a URL like:")
    print("     http://localhost:8080/?apisession=XXXXXXXXXX&...")
    print("4. Copy the value after ?apisession= and paste it below.")
    print("============================================================")
    print("")

    webbrowser.open(login_url)

    # Get session token from user
    session_token = input("Paste session token here and press Enter: ").strip()

    if not session_token:
        raise ValueError("Session token cannot be empty.")

    # Activate the session
    breeze.generate_session(
        api_secret=api_secret,
        session_token=session_token
    )

    print("")
    print("Session created successfully!")
    print("")
    return breeze


def test_connection(breeze):
    # Make one test API call to confirm session is working
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
            print("Connection test passed. Breeze API is responding.")
            print("")
        else:
            print("Connection test returned empty response.")
            print("Session may still be valid. Proceeding.")
            print("")

    except Exception as e:
        print("Connection test failed: " + str(e))
        print("")


# ─────────────────────────────────────────────────────────────
# Run this file directly to test auth:
# python src/auth.py
# ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    breeze = create_session()
    test_connection(breeze)