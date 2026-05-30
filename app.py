# ─────────────────────────────────────────────────────────────
# app.py
# Web interface for the NIFTY Options Pipeline.
# Run with: streamlit run app.py
# ─────────────────────────────────────────────────────────────

import streamlit as st
import os
import sys
import yaml
import subprocess
from pathlib import Path
from datetime import date
from dotenv import load_dotenv

# ── Page config ───────────────────────────────────────────────
st.set_page_config(
    page_title = "NIFTY Options Downloader",
    page_icon  = "📈",
    layout     = "centered"
)

st.title("📈 NIFTY Options Data Downloader")
st.caption("Powered by ICICI Direct Breeze API")
st.divider()


# ── Helper functions ──────────────────────────────────────────

def save_env(api_key, api_secret):
    """Saves API credentials to .env file."""
    with open(".env", "w") as f:
        f.write(f"BREEZE_API_KEY={api_key}\n")
        f.write(f"BREEZE_API_SECRET={api_secret}\n")


def save_config(start_date, end_date):
    """Saves date slice to config.yaml."""
    with open("config/config.yaml", "r") as f:
        config = yaml.safe_load(f)
    config["download_slice"]["start_expiry"] = str(start_date)
    config["download_slice"]["end_expiry"]   = str(end_date)
    with open("config/config.yaml", "w") as f:
        yaml.dump(config, f, default_flow_style=False)


def get_login_url(api_key):
    """Generates Breeze login URL."""
    from urllib.parse import quote
    return f"https://api.icicidirect.com/apiuser/login?api_key={quote(api_key, safe='')}"


def load_existing_config():
    """Loads existing config values if available."""
    config = {}
    try:
        with open("config/config.yaml", "r") as f:
            config = yaml.safe_load(f)
    except Exception:
        pass

    load_dotenv()
    return {
        "api_key":    os.getenv("BREEZE_API_KEY",    ""),
        "api_secret": os.getenv("BREEZE_API_SECRET", ""),
        "start":      config.get("download_slice", {}).get("start_expiry", ""),
        "end":        config.get("download_slice", {}).get("end_expiry",   ""),
    }


# ── Load existing settings ────────────────────────────────────
existing = load_existing_config()


# ── STEP 1: Credentials & Date Slice ─────────────────────────
st.header("Step 1 — Your Settings")

col1, col2 = st.columns(2)

with col1:
    api_key = st.text_input(
        "Breeze API Key",
        value    = existing["api_key"],
        type     = "password",
        help     = "From your Breeze API portal"
    )

with col2:
    api_secret = st.text_input(
        "Breeze API Secret",
        value    = existing["api_secret"],
        type     = "password",
        help     = "From your Breeze API portal"
    )

st.caption("Get your API key at https://api.icicidirect.com")
st.divider()

st.subheader("Your Assigned Date Slice")
st.caption("Contact the project lead if you don't have a slice assigned yet.")

col3, col4 = st.columns(2)

with col3:
    try:
        default_start = date.fromisoformat(existing["start"]) if existing["start"] else date(2024, 1, 1)
    except Exception:
        default_start = date(2024, 1, 1)

    start_date = st.date_input(
        "Start Date",
        value = default_start,
        min_value = date(2023, 6, 1),
        max_value = date(2026, 5, 30)
    )

with col4:
    try:
        default_end = date.fromisoformat(existing["end"]) if existing["end"] else date(2024, 6, 30)
    except Exception:
        default_end = date(2024, 6, 30)

    end_date = st.date_input(
        "End Date",
        value = default_end,
        min_value = date(2023, 6, 1),
        max_value = date(2026, 5, 30)
    )

if st.button("💾 Save Settings", use_container_width=True):
    if not api_key or not api_secret:
        st.error("Please enter both API Key and API Secret.")
    elif start_date >= end_date:
        st.error("End date must be after start date.")
    else:
        save_env(api_key, api_secret)
        save_config(start_date, end_date)
        st.success("✅ Settings saved successfully!")

st.divider()


# ── STEP 2: Breeze Login ──────────────────────────────────────
st.header("Step 2 — Login to Breeze")
st.write(
    "Every day before running, you need to generate a fresh "
    "session token from ICICI Direct."
)

if st.button("🔗 Generate Login Link", use_container_width=True):
    if not api_key:
        st.error("Please enter your API Key in Step 1 first.")
    else:
        login_url = get_login_url(api_key)
        st.info(
            "Click the link below, log in with your ICICI Direct "
            "credentials, then copy the token from the redirected URL."
        )
        st.markdown(f"### [👉 Click here to login to Breeze]({login_url})")
        st.caption(
            "After login, your browser redirects to: "
            "`http://localhost:8080/?apisession=XXXXXXXX`  "
            "Copy the value after `?apisession=` and paste below."
        )

session_token = st.text_input(
    "Paste Session Token here",
    placeholder = "e.g. 55788970",
    help        = "The number/code from the redirected URL after ?apisession="
)

st.divider()


# ── STEP 3: Run Pipeline ──────────────────────────────────────
st.header("Step 3 — Download Data")
st.write(
    "Once settings are saved and session token is entered, "
    "click Run. Keep this browser tab open while downloading."
)

if st.button("▶️ Start Download", use_container_width=True, type="primary"):

    if not session_token.strip():
        st.error("Please paste your session token in Step 2 first.")

    else:
        st.info(
            "⏳ Pipeline is running. This may take 1–3 hours depending "
            "on your slice size. Do not close this tab."
        )

        # Set session token as environment variable for the subprocess
        env = os.environ.copy()
        env["BREEZE_SESSION_TOKEN"] = session_token.strip()

        # Run the pipeline as a subprocess
        process = subprocess.Popen(
            [sys.executable, "-m", "src.main"],
            stdout    = subprocess.PIPE,
            stderr    = subprocess.STDOUT,
            text      = True,
            cwd       = str(Path.cwd()),
            env       = env
        )

        # Stream output to the UI
        output_lines = []
        output_box   = st.empty()
        status_box   = st.empty()

        for line in process.stdout:
            output_lines.append(line)

            # Show last 60 lines to avoid overwhelming the browser
            visible = "".join(output_lines[-60:])
            output_box.text_area(
                "Live Output",
                value  = visible,
                height = 400
            )

            # Show last line as status
            status_box.caption(f"Latest: {line.strip()}")

        process.wait()

        if process.returncode == 0:
            st.success("✅ Run complete! Check the summary above.")
        else:
            st.warning(
                "⚠️ Run ended. Check the output above for details. "
                "If it hit the daily API limit, just run again tomorrow."
            )

        st.balloons()

st.divider()

# ── Footer ────────────────────────────────────────────────────
st.caption(
    "Data is stored locally on your computer in the `data/` folder. "
    "Nothing is uploaded anywhere."
)
st.caption("GitHub: https://github.com/mukhilj/breeze_options_pipeline")