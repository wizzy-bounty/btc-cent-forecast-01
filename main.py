#!/usr/bin/env python3
"""btc-cent-forecast-01: forecast BTC's price 240 minutes ahead.

Model (chosen by backtest, see README.md):
  forecast = P * exp(SHRINK * (H / W) * ln(P / P[-W]))
where P is the checkpoint close, W = 4320 (the full 72 h window), H = 240
(the horizon), and SHRINK = 0.125.  That is a heavily shrunk extrapolation
of the 72-hour log drift: the honest conditional median is close to
persistence, and every stronger signal we tested (short-window momentum,
EWMA, mean reversion, multi-factor OLS) failed walk-forward validation --
its coefficients flip sign between halves of the data.  The 72 h drift with
shrinkage 0.125 was the only tilt that beat persistence on the Orca practice
series, on the 6 practice cases, and on out-of-sample Binance BTCUSDT
(Nov 1-7 and Nov 8-14), while never being far behind it anywhere; the
October Binance window slightly favours pure persistence, so the tilt is
kept tiny on purpose.  The forecast move is capped at +-0.5% of the
checkpoint price, so a pathological series can never produce a wild guess.

Fallbacks (never crash, never an invalid case): if the price list is
missing/empty/unusable, fall back to the last finite positive price; if
there is none at all, fall back to 1.0.  Output is rounded to the grid's
5 decimals and clamped to (0, 10_000_000).

Standard library only, no network, fully deterministic (pure arithmetic,
no randomness, no time or environment dependence beyond the input dir).
"""

import json
import math
import os
import sys

INPUT_DIR = os.environ.get("MAKEFUN_INPUT_DIR", "/input")
OUTPUT_DIR = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")

MIN_PRICE = 0.00001
MAX_PRICE = 9_999_999.99999

# Full 72 h window (4,320 one-minute closes) and the shrinkage applied to
# its log drift when extrapolating over the horizon.
WINDOW = 4320
SHRINK = 0.125
# Hard cap on the forecast's log move away from the checkpoint close.
MAX_LOG_MOVE = 0.005  # +-0.5%


def price5(x):
    """Keep x on the price grid's 5 decimals and inside (0, 10_000_000)."""
    if not isinstance(x, (int, float)) or not math.isfinite(x):
        return 1.0
    return round(min(MAX_PRICE, max(MIN_PRICE, x)) * 1e5) / 1e5


def clean_prices(raw):
    """Finite positive closes only, in order; drops bad entries."""
    out = []
    if isinstance(raw, list):
        for v in raw:
            if isinstance(v, (int, float)) and math.isfinite(v) and v > 0:
                out.append(float(v))
    return out


def drift_move(prices, horizon_minutes):
    """Capped log drift to extrapolate over the horizon, or 0.0 (persistence).

    Uses the full 72 h window (WINDOW minutes) and the shrinkage factor
    SHRINK, scaled by horizon/window; the result is capped at
    +-MAX_LOG_MOVE.  Returns 0.0 when the window is too short to estimate
    a drift worth extrapolating (the H/W scaling would amplify minutes of
    noise) or a price is unusable, i.e. the forecast falls back to
    persistence.
    """
    if len(prices) < 2 or horizon_minutes <= 0:
        return 0.0
    w = min(WINDOW, len(prices) - 1)
    if w < 240:
        return 0.0
    base = prices[-1 - w]
    last = prices[-1]
    if base <= 0 or last <= 0:
        return 0.0
    move = SHRINK * (horizon_minutes / float(w)) * math.log(last / base)
    if move > MAX_LOG_MOVE:
        return MAX_LOG_MOVE
    if move < -MAX_LOG_MOVE:
        return -MAX_LOG_MOVE
    return move


def forecast(prices, horizon_minutes):
    """One forecast price from a list of cleaned closes (last = checkpoint)."""
    if not prices:
        return 1.0
    last = prices[-1]
    return price5(last * math.exp(drift_move(prices, horizon_minutes)))


def process_case(case):
    """Return (case_id, forecast price) for one parsed case object."""
    case_id = None
    if isinstance(case, dict):
        cid = case.get("case")
        if isinstance(cid, str) and cid:
            case_id = cid
    markets = case.get("markets") if isinstance(case, dict) else None
    prices = []
    if isinstance(markets, list) and markets:
        m0 = markets[0]
        if isinstance(m0, dict):
            prices = clean_prices(m0.get("prices"))
    horizon = 240
    if isinstance(case, dict):
        h = case.get("horizon_minutes")
        if isinstance(h, (int, float)) and math.isfinite(h) and h > 0:
            horizon = h
    return case_id, forecast(prices, horizon)


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    if not os.path.isdir(INPUT_DIR):
        return  # No cases to process; still exit cleanly with valid state.
    inputs = sorted(f for f in os.listdir(INPUT_DIR) if f.endswith(".in"))
    for fname in inputs:
        case_id = fname[: -len(".in")]
        try:
            with open(os.path.join(INPUT_DIR, fname), "r", encoding="utf-8") as fh:
                case = json.load(fh)
            cid, price = process_case(case)
            if cid is None:
                cid = case_id
        except Exception:
            # Any unreadable / malformed case still gets a valid output:
            # persistence is impossible without prices, so guess 1.0.
            cid, price = case_id, 1.0
        payload = {"forecasts": [{"case": cid, "price": price}]}
        out_path = os.path.join(OUTPUT_DIR, case_id + ".out")
        with open(out_path, "w", encoding="utf-8") as fh:
            fh.write(json.dumps(payload, separators=(",", ":")) + "\n")


if __name__ == "__main__":
    main()
