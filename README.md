# NIFTY Options Historical Data Pipeline

A collaborative Python tool to download 3 years of NIFTY options 
historical data (1-minute OHLCV + Open Interest) from the ICICI 
Direct Breeze API and store it in a format ready for backtesting.

---

## What This Does

- Downloads 1-minute candle data for NIFTY options (CE and PE)
- Covers ATM ± 50 strikes (101 strikes) for every expiry
- Covers weekly and monthly expiries going back 3 years
- Stores data in efficient Parquet format for fast querying
- Supports collaborative downloading — different people can 
  download different date slices and merge later

---

## What You Need Before Starting

1. **An ICICI Direct trading account**
2. **A Breeze API key** — register at https://api.icicidirect.com
3. **A Windows / Mac / Linux computer**
4. **Python 3.10 or above** — download from https://python.org
5. **VS Code** (recommended) — download from https://code.visualstudio.com

---

## Setup Guide (First Time Only)

### Step 1 — Download the code

Click the green **Code** button on this page → **Download ZIP**

Extract the ZIP to a simple folder path like:
- Windows: `C:\projects\breeze_options_pipeline\`
- Mac/Linux: `~/projects/breeze_options_pipeline/`

### Step 2 — Open in VS Code

Open VS Code → File → Open Folder → select the project folder

Open the terminal: **View → Terminal**

### Step 3 — Create virtual environment

```
python -m venv venv
```

**Windows:**
```
venv\Scripts\activate
```

**Mac/Linux:**
```
source venv/bin/activate
```

You should see `(venv)` appear in the terminal prompt.

### Step 4 — Install required libraries

```
python -m pip install -r requirements.txt
```

### Step 5 — Add your API credentials

Create a file called `.env` in the project folder (not inside any 
subfolder). Add these two lines with your actual credentials:

```
BREEZE_API_KEY=your_api_key_here
BREEZE_API_SECRET=your_api_secret_here
```

⚠️ Never share this file with anyone. It is already in `.gitignore`
so it will never be uploaded to GitHub.

### Step 6 — Set your assigned date slice

Open `config/config.yaml` and fill in your assigned dates:

```yaml
download_slice:
  start_expiry: "2024-01-01"   # your assigned start date
  end_expiry:   "2024-06-30"   # your assigned end date
```

Refer to the **Slice Assignment Table** below for your dates.

---

## Running the Pipeline

Every day, simply run:

```
python -m src.main
```

The pipeline will:
1. Open your browser for ICICI login
2. Download your assigned slice (up to 4,500 API calls/day)
3. Save data to `data/` folder
4. Stop automatically when daily limit is reached
5. Resume from where it left off next time you run it

**Estimated time:** 3 days of running per person (depending on slice size)

---

## Slice Assignment Table

| Person | Start Date | End Date |
|--------|-----------|----------|
| 1  | 2023-06-01 | 2023-08-15 |
| 2  | 2023-08-16 | 2023-10-31 |
| 3  | 2023-11-01 | 2024-01-15 |
| 4  | 2024-01-16 | 2024-03-31 |
| 5  | 2024-04-01 | 2024-06-15 |
| 6  | 2024-06-16 | 2024-08-31 |
| 7  | 2024-09-01 | 2024-11-15 |
| 8  | 2024-11-16 | 2025-01-31 |
| 9  | 2025-02-01 | 2025-04-15 |
| 10 | 2025-04-16 | 2025-06-30 |
| 11 | 2025-07-01 | 2025-09-15 |
| 12 | 2025-09-16 | 2025-11-30 |
| 13 | 2025-12-01 | 2026-01-31 |
| 14 | 2026-02-01 | 2026-03-31 |
| 15 | 2026-04-01 | 2026-05-30 |

---

## How to Share Your Data

Once your slice is complete:

1. Zip your `data/nifty/options/master/` folder
2. Name it `data_personN.zip` (replace N with your person number)
3. Share with the project lead via Google Drive / OneDrive

---

## Querying the Data

After merging, use Python + DuckDB to query:

```python
import duckdb

# Total candles downloaded
duckdb.query("SELECT COUNT(*) FROM 'data/merged/options/master/**/*.parquet'")

# All strikes at a specific moment
duckdb.query("""
    SELECT strike, option_type, close, volume, open_interest
    FROM 'data/merged/options/master/**/*.parquet'
    WHERE timestamp = '2025-01-15 10:15:00'
    AND option_type = 'CE'
    ORDER BY strike
""")

# Full price history of one contract
duckdb.query("""
    SELECT timestamp, open, high, low, close, volume, open_interest
    FROM 'data/merged/options/master/**/*.parquet'
    WHERE strike = 24400
    AND option_type = 'CE'
    AND expiry_date = '2025-01-30'
    ORDER BY timestamp
""")
```

---

## Common Issues

**"Public Key does not exist" in browser**
Your API key has special characters. Make sure you copied it 
exactly from the Breeze API portal.

**"ModuleNotFoundError"**
Run `python -m pip install -r requirements.txt` again and make 
sure `(venv)` is active in your terminal.

**Pipeline stops after a few hours**
Daily API limit reached. Run again tomorrow — it resumes automatically.

**Computer went to sleep mid-run**
No data loss. Just run again — it picks up from where it stopped.

---

## Data Format

Downloaded data is stored in Parquet format — a fast, compressed 
file format used by data engineers. Each file contains:

| Column | Description |
|--------|-------------|
| timestamp | Candle datetime (IST) |
| symbol | NIFTY |
| expiry_date | Contract expiry date |
| strike | Strike price |
| option_type | CE or PE |
| open | Open price |
| high | High price |
| low | Low price |
| close | Close price |
| volume | Traded volume |
| open_interest | Open interest |

---

## Project Structure

```
breeze_options_pipeline/
├── src/                    ← All Python modules
├── config/
│   ├── config.yaml         ← Settings + your slice dates
│   └── nse_holidays.csv    ← NSE holiday calendar
├── data/                   ← Downloaded data (not on GitHub)
├── logs/                   ← Run logs (not on GitHub)
├── merge.py                ← Merge slices from all contributors
├── requirements.txt        ← Python libraries needed
└── README.md               ← This file
```

---

## Contributing

Pull requests are welcome. For major changes, open an issue first.

If you want to add support for BANKNIFTY or SENSEX, refer to the 
Phase 2 section in the project documentation.

---

## Disclaimer

This tool is for personal research and educational purposes only.
Make sure you comply with ICICI Direct's API terms of service.