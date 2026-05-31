# NIFTY Options Historical Data Pipeline

A collaborative Python tool to download 3 years of NIFTY options
historical data (1-minute OHLCV + Open Interest) from the ICICI
Direct Breeze API and store it in a format ready for backtesting.

---

## What This Does

- Downloads 1-minute candle data for NIFTY options (CE and PE)
- Covers ATM + or - 50 strikes (101 strikes) for every expiry
- Covers weekly and monthly expiries going back 3 years
- Stores data locally on your computer in an efficient format
- Supports collaborative downloading — different contributors
  download different date slices and merge later

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

### Step 2 — Open terminal in VS Code

Open VS Code, go to File, open the project folder.
Then open the terminal: View, then Terminal.

### Step 3 — Create virtual environment

    python -m venv venv

Activate it:

Windows:

    venv\Scripts\activate

Mac/Linux:

    source venv/bin/activate

You should see (venv) in the terminal prompt.
Always check for (venv) before running any command.

### Step 4 — Install required libraries

    python -m pip install -r requirements.txt

### Step 5 — Run setup

    python setup.py

This asks for your API credentials and assigned date slice,
and saves everything automatically. You only need to do this once.

---

## Daily Download Routine

Every day, run these two commands:

Step 1 — Login to Breeze (generates a fresh session):

    python -m src.auth

Your browser opens the ICICI Direct login page.
Log in, copy the token from the redirect URL, paste it in the terminal.

Step 2 — Run the pipeline:

    python -m src.main

The pipeline downloads your assigned slice, up to 4,500 API calls
per day, then stops automatically. Keep the terminal open while
it runs (1 to 2 hours). Next day, repeat from Step 1.

When your slice is complete, you will see:

    Nothing to download. Your slice is complete!

---

## Slice Assignment Table

The full 3-year dataset is divided into chunks.
Contact the project lead to get your chunk assigned.
One person can take multiple chunks if needed.

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
- If more contributors are available, the project lead can
  split a chunk into smaller date ranges
- If fewer contributors are available, one person can be
  assigned multiple chunks

---

## How Long Will It Take?

| Chunk Size          | Estimated Days |
|---------------------|----------------|
| 1 chunk (3 months)  | 3 to 4 days    |
| 2 chunks (6 months) | 6 to 8 days    |
| Full dataset alone  | ~45 days       |

The pipeline runs for 1 to 2 hours each day then stops.
Just run the two daily commands each morning.

---

## How to Share Your Data

Once your slice is complete:

1. Go to your project folder
2. Open the data/nifty/options/master/ folder
3. Zip the entire master folder
4. Name the zip file data_chunk_N.zip (replace N with your chunk number)
5. Share with the project lead via Google Drive or OneDrive

---

## Monitoring Progress

To check how much has been downloaded, run:

    python -c "import pandas as pd; df=pd.read_parquet('data/manifest.parquet'); print(df['status'].value_counts())"

This shows counts of pending, validated, and failed chunks.

---

## Frequently Asked Questions

Do I need to keep my computer on all day?
No. The pipeline runs for 1 to 2 hours, hits the daily API limit,
and stops. Close everything and repeat the next day.

What if my computer goes to sleep mid-run?
No data is lost. Run the two daily commands again and it resumes
from exactly where it stopped.

How do I know my slice is done?
The terminal will print: Nothing to download. Your slice is complete!

Do I need to enter my API key every day?
No. It is saved after running setup.py. You only need to run
python -m src.auth each day to get a fresh session token.

Can I close the terminal while it runs?
No. Keep the terminal open while the pipeline is running.
You can lock your screen but do not close VS Code or the terminal.

---

## Querying the Data (Advanced)

After the project lead merges all slices, query data using Python:

    import duckdb

    duckdb.query("""
        SELECT strike, option_type, close, volume, open_interest
        FROM 'data/merged/options/master/**/*.parquet'
        WHERE timestamp = '2025-01-15 10:15:00'
        AND option_type = 'CE'
        ORDER BY strike
    """).df()

---

## Data Format

| Column         | Description                       |
|----------------|-----------------------------------|
| timestamp      | Date and time of candle (IST)     |
| symbol         | NIFTY                             |
| expiry_date    | Contract expiry date              |
| strike         | Strike price                      |
| option_type    | CE (Call) or PE (Put)             |
| open           | Opening price                     |
| high           | Highest price in that minute      |
| low            | Lowest price in that minute       |
| close          | Closing price                     |
| volume         | Number of contracts traded        |
| open_interest  | Total open contracts              |

---

## Project Structure

    breeze_options_pipeline/
    |-- setup.py                Run this first (one time only)
    |-- src/                    Pipeline modules (do not edit)
    |-- config/
    |   |-- config.yaml         Settings (managed by setup.py)
    |   |-- nse_holidays.csv    NSE holiday calendar
    |-- data/                   Your downloaded data (not on GitHub)
    |-- logs/                   Run logs (not on GitHub)
    |-- merge.py                For project lead to merge all slices
    |-- requirements.txt        Python libraries needed
    |-- README.md               This file

---

## Common Issues

(venv) not showing in terminal:
Run venv\Scripts\activate on Windows or source venv/bin/activate
on Mac/Linux before any command.

Session key expired error:
Run python -m src.auth again to get a fresh session token.
This needs to be done each time you start a new run.

Pipeline stops after 1 to 2 hours:
Normal. Daily API limit reached. Run again tomorrow.

Public Key does not exist in browser:
API key copied incorrectly. Re-run setup.py and enter it again.

---

## Want to Help More?

If you finish your chunk early, contact the project lead for
an additional chunk assignment.

---

## Disclaimer

This tool is for personal research and educational purposes only.
Please comply with ICICI Direct API terms of service.
Data is stored locally and never shared without your knowledge.