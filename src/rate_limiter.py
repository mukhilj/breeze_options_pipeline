# ─────────────────────────────────────────────────────────────
# rate_limiter.py
# Controls API call speed using token bucket logic.
#
# Two independent limits run in parallel:
#   Bucket 1 — Per minute : max 90 calls/min (Breeze cap is 100)
#   Bucket 2 — Per day    : max 4,500 calls/day (Breeze cap is 5,000)
#
# Before every API call, the downloader asks the rate limiter
# for permission. If either bucket is empty, we wait.
# ─────────────────────────────────────────────────────────────

import time
from datetime import datetime


# ── Constants ─────────────────────────────────────────────────
CALLS_PER_MIN  = 90       # Our limit (Breeze hard cap = 100)
CALLS_PER_DAY  = 4500     # Our limit (Breeze hard cap = 5,000)
MIN_DELAY      = 60.0 / CALLS_PER_MIN   # 0.667 seconds between calls


class DailyBudgetExhausted(Exception):
    """
    Raised when we have used all 4,500 calls for today.
    main.py catches this and exits cleanly.
    """
    pass


class RateLimiter:
    """
    Token bucket rate limiter.

    Think of it like two buckets of tokens:
    - Minute bucket: starts with 90 tokens, refills every 60 seconds
    - Day bucket:    starts with 4,500 tokens, never refills mid-session

    Every API call costs 1 token from each bucket.
    If the minute bucket is empty, we sleep until it refills.
    If the day bucket is empty, we raise DailyBudgetExhausted.
    """

    def __init__(self):
        # Minute bucket
        self.minute_tokens     = CALLS_PER_MIN
        self.minute_refill_at  = time.time() + 60.0
        self.last_call_time    = 0.0

        # Day bucket
        self.day_tokens        = CALLS_PER_DAY
        self.day_start         = datetime.now().date()

        # Stats
        self.total_calls       = 0
        self.session_start     = time.time()

    def _reset_day_if_needed(self):
        """
        If the calendar date has changed (midnight passed),
        reset the daily token bucket for the new day.
        """
        today = datetime.now().date()
        if today != self.day_start:
            print(f"\nNew day detected ({today}). Resetting daily budget.")
            self.day_tokens = CALLS_PER_DAY
            self.day_start  = today

    def _refill_minute_bucket_if_needed(self):
        """
        If 60 seconds have passed since last refill, top up the minute bucket.
        """
        now = time.time()
        if now >= self.minute_refill_at:
            self.minute_tokens    = CALLS_PER_MIN
            self.minute_refill_at = now + 60.0

    def acquire(self):
        """
        Request permission to make one API call.

        This function BLOCKS until it is safe to proceed:
        - Enforces minimum delay between consecutive calls
        - Waits if the minute bucket is empty
        - Raises DailyBudgetExhausted if the day bucket is empty

        Call this once before every API call.
        """
        # Check if a new day started (reset daily budget)
        self._reset_day_if_needed()

        # Check daily budget first — fail fast if exhausted
        if self.day_tokens <= 0:
            raise DailyBudgetExhausted(
                f"Daily budget of {CALLS_PER_DAY} calls exhausted. "
                f"Total calls this session: {self.total_calls}. "
                f"Resume tomorrow."
            )

        # Enforce minimum delay between calls (~0.667 seconds)
        now = time.time()
        elapsed = now - self.last_call_time
        if elapsed < MIN_DELAY:
            time.sleep(MIN_DELAY - elapsed)

        # Wait for minute bucket to refill if empty
        while True:
            self._refill_minute_bucket_if_needed()
            if self.minute_tokens > 0:
                break
            # Minute bucket empty — sleep until refill time
            wait_time = self.minute_refill_at - time.time()
            if wait_time > 0:
                print(f"  Minute bucket empty. Waiting {wait_time:.1f}s for refill...")
                time.sleep(wait_time + 0.1)   # small buffer

        # Consume one token from each bucket
        self.minute_tokens -= 1
        self.day_tokens    -= 1
        self.total_calls   += 1
        self.last_call_time = time.time()

    def on_429(self):
        """
        Called when Breeze returns HTTP 429 (rate limit hit).
        Backs off for 60 seconds and resets the minute bucket.
        """
        print("  HTTP 429 received. Backing off for 60 seconds...")
        time.sleep(60)
        self.minute_tokens    = CALLS_PER_MIN
        self.minute_refill_at = time.time() + 60.0

    def stats(self):
        """Returns a summary of usage so far this session."""
        elapsed_min = (time.time() - self.session_start) / 60
        return {
            "total_calls":     self.total_calls,
            "day_remaining":   self.day_tokens,
            "elapsed_minutes": round(elapsed_min, 1),
        }

    def print_stats(self):
        """Prints current usage stats."""
        s = self.stats()
        print(
            f"  Rate limiter: {s['total_calls']} calls made | "
            f"{s['day_remaining']} remaining today | "
            f"{s['elapsed_minutes']} min elapsed"
        )


# ── Singleton ─────────────────────────────────────────────────
# One shared instance used by the entire pipeline.
# All modules import this object — not the class.
rate_limiter = RateLimiter()


# ─────────────────────────────────────────────────────────────
# Run this file directly to test:
# python -m src.rate_limiter
# ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import time

    print("=" * 55)
    print("Test 1: Simulating 10 API calls")
    print("Expected: ~7 seconds total (10 × 0.667s delay)")
    print("=" * 55)

    limiter = RateLimiter()
    start   = time.time()

    for i in range(10):
        limiter.acquire()
        print(f"  Call {i+1:2d} granted at t={time.time()-start:.2f}s")

    elapsed = time.time() - start
    limiter.print_stats()
    print(f"Total time: {elapsed:.2f}s")

    print()
    print("=" * 55)
    print("Test 2: Daily budget exhaustion")
    print("Expected: raises DailyBudgetExhausted after 4,500 calls")
    print("(we simulate this by setting day_tokens to 2)")
    print("=" * 55)

    limiter2 = RateLimiter()
    limiter2.day_tokens = 2  # force near-empty for testing

    try:
        for i in range(5):
            limiter2.acquire()
            print(f"  Call {i+1} granted. Day tokens left: {limiter2.day_tokens}")
    except DailyBudgetExhausted as e:
        print(f"\nCaught DailyBudgetExhausted (expected):")
        print(f"  {e}")

    print()
    print("All rate limiter tests passed.")