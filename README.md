# btc-cent-forecast-01 — BTC 4-hour-ahead forecast

Forecasts Bitcoin's (cbBTC/USDC, Orca pool) price 240 minutes after each
checkpoint, from the 4,320 one-minute closes of the preceding 72 hours.

## Model

```
forecast = P * exp(0.125 * (240 / 4320) * ln(P / P_72h_ago))
```

i.e. persistence plus a heavily shrunk extrapolation of the 72-hour log
drift, with the forecast move capped at ±0.5% of the checkpoint close.

## Why this, and why so timid

Backtested before writing the model (see below). The honest finding is
that BTC's 4-hour return is almost unpredictable from price history alone:

- **Practice (Orca, 6 cases p00–p05):** persistence 44,521.58 cents;
  this model **44,278.31 cents (−0.55%)**.
- **Rolling backtest on the stitched Orca practice series** (64 windows,
  every 15 min): persistence 51,573.1; this model 51,422.7 (−0.29%).
- **Binance BTCUSDT 1m, Nov 1–14** (257 windows, out-of-sample proxy):
  persistence 48,866.8; this model 48,794.2 (−0.15%), winning 53.7% of
  windows head-to-head.
- **Binance BTCUSDT 1m, Oct 15–31** (333 windows): persistence 40,641.7;
  this model 40,784.2 (**+0.35%, i.e. worse**).

Everything stronger failed: short-window momentum (W=60/120/240) looks
great on the 6 practice cases (downtrend luck) but is far worse on both
backtests; EWMA momentum and mean reversion to 24–72 h means are worse
than persistence almost everywhere; multi-factor OLS on recent returns
has R² ≈ 0.03 in-sample and is much worse than persistence walk-forward
(its coefficients flip sign between data halves). Smoothing the anchor
(median of last 5/15/60 closes) also hurts everywhere — the last close
is the best anchor because the target is itself a single-minute close.

So the edge is real but small and regime-dependent (it helps in trending
regimes, hurts slightly in choppy ones). The tilt is deliberately tiny:
the univariate-OLS-optimal coefficient on the 72 h return is ≈ 0.005,
which corresponds to shrinkage ≈ 0.09; 0.125 is a slight round-up.
Pure persistence was rejected for one structural reason: it ties the
house baseline exactly, and a prize needs a score *strictly below* the
baseline — persistence can never win anything, while this tilt keeps the
downside to ~±0.5% and gives a roughly even chance of beating it.

## Run

```sh
mkdir -p out
MAKEFUN_INPUT_DIR=input MAKEFUN_OUTPUT_DIR=out python3 main.py
```

Standard library only, no network. Reads every `*.in` in the input dir,
writes `<id>.out` as `{"forecasts":[{"case":"<id>","price":<number>}]}`,
price rounded to 5 decimals and clamped to (0, 10,000,000).
Deterministic (pure arithmetic); ~0.05 s per case, far under the 8 s cap.

## Fallbacks

- Series shorter than 240 closes, or unusable prices → persistence
  (last finite positive close).
- No usable price at all, or a malformed/unreadable case file → still
  writes a valid output with price 1.0. The program never crashes on a
  case.
