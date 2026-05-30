# NIFTY Options Historical Data Pipeline

A collaborative Python tool to download 3 years of NIFTY options historical data (1-minute OHLCV + Open Interest) from the ICICI Direct Breeze API and store it in a format ready for backtesting.

---

## What This Does

- Downloads 1-minute candle data for NIFTY options (CE and PE)
- Covers ATM + or - 50 strikes (101 strikes) for every expiry
- Covers weekly and monthly expiries going back 3 years
- Stores data locally on your computer in an efficient format
- Supports collaborative downloading — different contributors download different date slices and merge later
- Includes a simple web interface — no command line knowledge needed

---

## What You Need Before Starting

1. An ICICI Direct trading account
2. A Breeze API key — register at https://api.icicidirect.com
3. A Windows / Mac / Linux computer
4. Python 3.10 or above — download from https://python.org
5. VS Code (recommended) — download from https://code.visualstudio.com

---

## Setup Guide (First Time Only)

### Step 1 — Download the code

Click the green Code button on this page and select Download ZIP.

Extract the ZIP to a simple folder path like:
- Windows: C:\projects\breeze_options_pipeline\
- Mac/Linux: ~/projects/breeze_options_pipeline/

### Step 2 — Open in VS Code

Open VS Code → File → Open Folder → select the project folder.

Open the terminal inside VS Code: View → Terminal.

### Step 3 — Create virtual environment

Run this in the terminal:

    python -m venv venv

Then activate it:

Windows:

    venv\Scripts\activate

Mac/Linux:

    source venv/bin/activate

You should see (venv) appear in the terminal prompt. Always make sure you see (venv) before running any command.

### Step 4 — Install required libraries

    python -m pip install -r requirements.txt

This may take 2 to 3 minutes. Wait until it finishes.

---

## Running the App

Once setup is done, every time you want to download data, run this in the terminal:

    streamlit run app.py

Your browser will automatically open at http://localhost:8501

---

## Using the Web App

The app walks you through 3 simple steps.

### Step 1 — Your Settings

- Enter your Breeze API Key and API Secret (from https://api.icicidirect.com)
- Enter your assigned start date and end date (see Slice Assignment Table below)
- Click Save Settings

### Step 2 — Login to Breeze

- Click Generate Login Link
- Your browser opens the ICICI Direct login page
- Log in with your ICICI Direct credentials
- After login, your browser redirects to a URL like: http://localhost:8080/?apisession=55788970
- Copy the number after ?apisession= and paste it into the app
- You need to do this every day before running

### Step 3 — Download Data

- Click Start Download
- Keep the browser tab open while downloading
- Live output will appear on screen showing progress
- The pipeline downloads up to 4,500 API calls per day and stops automatically
- Next day, repeat from Step 2 — it resumes where it left off
- When done, you will see: Nothing to download. Your slice is complete!

---

## Slice Assignment Table

The full 3-year dataset is divided into chunks. Contact the project lead to get your chunk assigned. One person can take multiple chunks if needed.

| Chunk | Start Date | End Date   | Assigned To |
|-------|------------|------------|-------------|
| 1     | 2023-06-01 | 2023-08-31 |             |
| 2     | 2023-09-01 | 2023-11-30 |             |
| 3     | 2023-12-01 | 2024-02-29 |             |
| 4     | 2024-03-01 | 2024-05-31 |             |
| 5     | 2024-06-01 | 2024-08-31 |             |
| 6     | 2024-09-01 | 2024-11-30 |             |
| 7     | 2024-12-01 | 2025-02-28 |             |
| 8     | 2025-03-01 | 2025-05-31 |             |
| 9     | 2025-06-01 | 2025-08-31 |             |
| 10    | 2025-09-01 | 2025-11-30 |             |
| 11    | 2025-12-01 | 2026-02-28 |             |
| 12    | 2026-03-01 | 2026-05-30 |             |

Notes:
- Each chunk covers approximately 3 months of data
- A single chunk typically takes 3 to 4 days to complete
- If more contributors are available, the project lead can split a chunk into smaller date ranges
- If fewer contributors are available, one person can be assigned multiple chunks

---

## How Long Will It Take?

| Chunk Size            | Estimated Days |
|-----------------------|----------------|
| 1 chunk (3 months)    | 3 to 4 days    |
| 2 chunks (6 months)   | 6 to 8 days    |
| Full dataset alone    | ~45 days       |

The app runs for 1 to 2 hours each day then stops automatically. Just open the app and click Start Download each morning.

---

## How to Share Your Data

Once your slice is complete:

1. Go to your project folder
2. Open the data/nifty/options/master/ folder
3. Zip the entire master folder
4. Name the zip file data_chunk_N.zip (replace N with your chunk number)
5. Share with the project lead via Google Drive or OneDrive

---

## Frequently Asked Questions

Do I need to keep my computer on all day?
No. The pipeline runs for about 1 to 2 hours, hits the daily API limit, and stops. You can then close everything. Repeat the next day.

What if my computer goes to sleep mid-run?
No data is lost. Just open the app and click Start Download again — it resumes from exactly where it stopped.

How do I know my slice is done?
The app will show: Nothing to download. Your slice is complete!

Can I close the browser while it runs?
No — keep the browser tab open while downloading. You can lock your screen, but do not close VS Code or the terminal.

Do I need to enter my API key every day?
No — it is saved after the first time. You only need to paste a fresh session token each day (Step 2 in the app).

What is the data used for?
Options backtesting and research. Data is stored only on your local computer and never uploaded anywhere.

---

## Data Format

Each downloaded candle contains:

| Column         | Description                            |
|----------------|----------------------------------------|
| timestamp      | Date and time of the candle (IST)      |
| symbol         | NIFTY                                  |
| expiry_date    | Contract expiry date                   |
| strike         | Strike price                           |
| option_type    | CE (Call) or PE (Put)                  |
| open           | Opening price                          |
| high           | Highest price in that minute           |
| low            | Lowest price in that minute            |
| close          | Closing price                          |
| volume         | Number of contracts traded             |
| open_interest  | Total open contracts                   |

---

## Project Structure

    breeze_options_pipeline/
    |-- app.py                  Web interface (run this)
    |-- src/                    Pipeline modules (do not edit)
    |-- config/
    |   |-- config.yaml         Settings (managed by the app)
    |   |-- nse_holidays.csv    NSE holiday calendar
    |-- data/                   Your downloaded data (not on GitHub)
    |-- logs/                   Run logs (not on GitHub)
    |-- merge.py                For project lead to merge all slices
    |-- requirements.txt        Python libraries needed
    |-- README.md               This file

---

## Common Issues

ModuleNotFoundError when running:
Make sure (venv) is visible in your terminal prompt. If not, run venv\Scripts\activate on Windows or source venv/bin/activate on Mac/Linux first.

Public Key does not exist in browser:
Your API key may have been copied incorrectly. Go back to https://api.icicidirect.com and copy it again carefully.

Browser does not open automatically:
Manually open your browser and go to http://localhost:8501

Pipeline stops after 1 to 2 hours:
This is normal — the daily API limit of 4,500 calls was reached. Run again tomorrow and it will resume automatically.

App shows an error after clicking Start Download:
Make sure you completed Step 1 (Save Settings) and Step 2 (paste session token) before clicking Start Download.

---

## Want to Help More?

If you finish your chunk early and want to contribute more, contact the project lead for an additional chunk assignment.

---

## Disclaimer

This tool is for personal research and educational purposes only. Please comply with ICICI Direct API terms of service. Data is stored locally and never shared without your knowledge.