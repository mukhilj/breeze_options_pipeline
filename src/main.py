# ─────────────────────────────────────────────────────────────
# main.py
# Pipeline orchestrator. Run this to download options data.
# ─────────────────────────────────────────────────────────────

import sys
import logging
import yaml
import pandas as pd
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, ".")

from src.auth             import create_session
from src.storage          import (ensure_folders, save_raw_chunk,
                                   append_to_master)
from src.atm_calculator   import update_spot_cache, compute_atm_for_expiry
from src.expiry_generator import get_expiries_for_nifty
from src.chunk_planner    import build_chunks
from src.rate_limiter     import rate_limiter, DailyBudgetExhausted
from src.downloader       import download_chunk
from src.validator        import validate_dataframe
from src.manifest         import (load_manifest, save_manifest,
                                   update_chunk_status,
                                   get_pending_chunks,
                                   print_manifest_summary,
                                   STATUS_DOWNLOADED, STATUS_VALIDATED,
                                   STATUS_FAILED,
                                   MANIFEST_COLUMNS)


def load_config(path="config/config.yaml"):
    """Loads config.yaml and returns as dict."""
    with open(path, "r") as f:
        return yaml.safe_load(f)


def setup_logging(run_id):
    Path("logs").mkdir(exist_ok=True)
    log_file = f"logs/run_{run_id}.log"
    logging.basicConfig(
        level    = logging.INFO,
        format   = "%(asctime)s | %(levelname)s | %(message)s",
        handlers = [
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ]
    )
    return log_file


def build_full_manifest(expiries, spot_df, existing_manifest,
                        run_id, config):
    """
    Builds manifest rows for all new expiries in one pass.
    Respects download_slice config.
    """
    log = logging.getLogger(__name__)

    symbol            = config["instruments"]["nifty"]["symbol"]
    strikes_each_side = config["instruments"]["nifty"]["strikes_each_side"]
    strike_interval   = config["instruments"]["nifty"]["strike_interval"]
    rights            = ["call", "put"]

    slice_cfg   = config.get("download_slice", {})
    start_str   = slice_cfg.get("start_expiry", "").strip()
    end_str     = slice_cfg.get("end_expiry",   "").strip()
    slice_start = date.fromisoformat(start_str) if start_str else None
    slice_end   = date.fromisoformat(end_str)   if end_str   else None

    if slice_start or slice_end:
        log.info(f"  Slice filter: {slice_start or 'beginning'} "
                 f"to {slice_end or 'today'}")

    existing_expiries = set()
    if not existing_manifest.empty:
        existing_expiries = set(
            existing_manifest[
                existing_manifest["symbol"] == symbol
            ]["expiry_date"]
        )

    today          = date.today()
    all_new_rows   = []
    expiries_added = 0
    skipped        = 0

    for i, (expiry_date, expiry_type) in enumerate(expiries):

        if i % 20 == 0:
            log.info(f"  Processing expiry {i+1}/{len(expiries)}: "
                     f"{expiry_date}...")

        if expiry_date > today:
            continue

        if slice_start and expiry_date < slice_start:
            continue
        if slice_end and expiry_date > slice_end:
            continue

        if str(expiry_date) in existing_expiries:
            skipped += 1
            continue

        try:
            atm_info = compute_atm_for_expiry(
                expiry_date, spot_df,
                strikes_each_side = strikes_each_side,
                interval          = strike_interval
            )
        except ValueError as e:
            log.warning(f"  Skipping {expiry_date}: {e}")
            continue

        strikes = atm_info["strikes"]

        for strike in strikes:
            for right in rights:
                chunks = build_chunks(expiry_date, expiry_type)
                for chunk in chunks:
                    all_new_rows.append({
                        "symbol":        symbol,
                        "expiry_date":   str(expiry_date),
                        "strike":        strike,
                        "right":         right,
                        "expiry_type":   expiry_type,
                        "chunk_index":   chunk["chunk_index"],
                        "from_dt":       chunk["from_dt"],
                        "to_dt":         chunk["to_dt"],
                        "status":        "pending",
                        "rows":          0,
                        "file_path":     "",
                        "attempts":      0,
                        "last_error":    "",
                        "source_run_id": run_id,
                        "updated_at":    str(datetime.now()),
                    })

        expiries_added += 1

    log.info(f"  New expiries added : {expiries_added}")
    log.info(f"  Already completed  : {skipped}")
    log.info(f"  New chunks queued  : {len(all_new_rows):,}")

    if not all_new_rows:
        return existing_manifest

    new_df   = pd.DataFrame(all_new_rows, columns=MANIFEST_COLUMNS)
    combined = pd.concat([existing_manifest, new_df], ignore_index=True)
    save_manifest(combined)
    log.info(f"  Manifest saved: {len(combined):,} total rows")
    return combined


def run_pipeline():

    config   = load_config()
    run_id   = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = setup_logging(run_id)
    log      = logging.getLogger(__name__)

    symbol       = config["instruments"]["nifty"]["symbol"]
    daily_budget = config["rate_limits"]["calls_per_day"]

    # Read slice from config
    slice_cfg   = config.get("download_slice", {})
    start_str   = slice_cfg.get("start_expiry", "").strip()
    end_str     = slice_cfg.get("end_expiry",   "").strip()
    slice_start = date.fromisoformat(start_str) if start_str else None
    slice_end   = date.fromisoformat(end_str)   if end_str   else None

    log.info("=" * 60)
    log.info(f"NIFTY Options Pipeline -- Run {run_id}")
    log.info("=" * 60)

    if slice_start or slice_end:
        log.info(f"Slice assigned: {slice_start or 'beginning'} "
                 f"to {slice_end or 'today'}")

    # Step 1: Auth
    log.info("Step 1: Authenticating...")
    session_token = __import__("os").environ.get(
        "BREEZE_SESSION_TOKEN", ""
    ).strip()
    breeze = create_session(
        session_token=session_token if session_token else None
    )
    ensure_folders()

    # Step 2: Spot cache
    log.info("Step 2: Updating spot cache...")
    spot_df = update_spot_cache(breeze)
    log.info(f"  Spot cache: {len(spot_df)} days "
             f"({spot_df['date'].min()} to {spot_df['date'].max()})")

    # Step 3: Expiries
    log.info("Step 3: Generating expiry list...")
    expiries = get_expiries_for_nifty(years_back=3)

    # Step 4: Build manifest
    log.info("Step 4: Building manifest...")
    manifest = load_manifest()
    manifest = build_full_manifest(
        expiries, spot_df, manifest, run_id, config
    )
    print_manifest_summary(manifest)

    # Step 5: Download queue — apply slice filter here too
    log.info("Step 5: Building download queue...")
    pending = get_pending_chunks(manifest, limit=None)

    # ── Apply slice filter to existing manifest rows ──────────
    # This handles the case where manifest was built before
    # slice config was set — ensures only assigned slice downloads
    if slice_start:
        pending = pending[
            pending["expiry_date"] >= str(slice_start)
        ]
    if slice_end:
        pending = pending[
            pending["expiry_date"] <= str(slice_end)
        ]

    # Cap to daily budget after filtering
    pending = pending.head(daily_budget)

    log.info(f"  Slice range  : {slice_start or 'all'} to "
             f"{slice_end or 'all'}")
    log.info(f"  Chunks queued: {len(pending):,}")

    if pending.empty:
        log.info("Nothing to download. Your slice is complete!")
        return

    # Step 6: Download loop
    log.info("Step 6: Downloading...")
    chunks_done   = 0
    chunks_failed = 0
    candles_added = 0

    for _, chunk_row in pending.iterrows():

        expiry_date = date.fromisoformat(chunk_row["expiry_date"])
        strike      = int(chunk_row["strike"])
        right       = chunk_row["right"]
        chunk_index = int(chunk_row["chunk_index"])

        chunk = {
            "chunk_index": chunk_index,
            "from_dt":     chunk_row["from_dt"],
            "to_dt":       chunk_row["to_dt"],
            "from_date":   date.fromisoformat(chunk_row["from_dt"][:10]),
            "to_date":     date.fromisoformat(chunk_row["to_dt"][:10]),
        }

        try:
            raw_df = download_chunk(
                breeze, symbol, expiry_date, strike, right, chunk
            )

            if raw_df.empty:
                manifest = update_chunk_status(
                    manifest, symbol, expiry_date, strike,
                    right, chunk_index, STATUS_DOWNLOADED,
                    rows=0, run_id=run_id
                )
                chunks_done += 1
                continue

            file_path = save_raw_chunk(
                raw_df, symbol, strike, right, expiry_date
            )
            manifest = update_chunk_status(
                manifest, symbol, expiry_date, strike,
                right, chunk_index, STATUS_DOWNLOADED,
                rows=len(raw_df), file_path=file_path,
                run_id=run_id
            )

            contract_info = {
                "symbol": symbol, "strike": strike,
                "right": right, "expiry_date": expiry_date
            }
            validated_df, summary = validate_dataframe(
                raw_df, contract_info
            )
            append_to_master(
                validated_df, symbol, strike, right, expiry_date
            )
            manifest = update_chunk_status(
                manifest, symbol, expiry_date, strike,
                right, chunk_index, STATUS_VALIDATED,
                rows=len(validated_df), file_path=file_path,
                run_id=run_id
            )

            chunks_done   += 1
            candles_added += len(raw_df)

        except DailyBudgetExhausted:
            log.warning(f"Daily budget exhausted. "
                        f"{chunks_done} chunks done today.")
            break

        except Exception as e:
            log.error(f"  FAILED: {symbol} {strike} {right} "
                      f"{expiry_date} chunk {chunk_index}: {e}")
            manifest = update_chunk_status(
                manifest, symbol, expiry_date, strike,
                right, chunk_index, STATUS_FAILED,
                error=str(e), run_id=run_id
            )
            chunks_failed += 1

    # Summary
    log.info("=" * 60)
    log.info("RUN SUMMARY")
    log.info("=" * 60)
    log.info(f"  Chunks downloaded : {chunks_done:,}")
    log.info(f"  Chunks failed     : {chunks_failed:,}")
    log.info(f"  Candles added     : {candles_added:,}")
    rate_limiter.print_stats()
    print_manifest_summary(manifest)
    log.info(f"  Log saved to      : {log_file}")


if __name__ == "__main__":
    run_pipeline()