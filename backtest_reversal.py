"""Experiment #2 (price-only) — Short-term weekly mean reversion (fixed rules, no fitted parameters).

PEAD (the intended #2) is blocked on a missing earnings calendar (Finnhub key), so this is a
tractable price-only candidate run in the meantime. Rules locked BEFORE running — nothing tuned.

Rules:
  - Universe: 11 SPDR sector ETFs + SPY + QQQ (liquid, no survivorship games).
  - Weekly cadence (rebalance each Friday close).
  - Signal: prior-week (5 trading day) total return, dividend-adjusted.
  - Hold the bottom N=3 (worst performers = "oversold") equal-weight for the next week.
    Classic short-term reversal (Jegadeesh 1990; Lehmann 1990).
  - Absolute filter: only take a name if the broad market (SPY) prior-week return > -5%
    (skip reversal bets during fast crashes — reversal blows up in those).
  - Costs: 10 bps per unit weight traded per side (weekly turnover is high — honest haircut).
Convention: signal at Friday close, entered at that same close (slightly optimistic vs next-open;
noted). Benchmark: SPY buy & hold over the identical window.

Run: uv run --with pandas,requests backtest_reversal.py
"""
import os
import requests
import pandas as pd
import numpy as np

UNIVERSE = ["XLK", "XLF", "XLV", "XLE", "XLI", "XLP", "XLY", "XLU", "XLB", "XLRE", "XLC", "QQQ"]
BENCH = "SPY"
ALL = UNIVERSE + [BENCH]
START = "2016-01-01"
COST_PER_SIDE = 0.0010   # 10 bps/side — weekly turnover is high, be conservative
TOP_N = 3
CRASH_FILTER = -0.05     # skip week if SPY prior-week return < -5%
CACHE = os.path.join(os.path.dirname(__file__) or ".", "data", "cache", "closes_daily.csv")


def load_env(path):
    env = {}
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k] = v.strip().strip('"')
    return env


def fetch_closes():
    if os.path.exists(CACHE):
        df = pd.read_csv(CACHE, index_col=0, parse_dates=True)
        if set(ALL).issubset(df.columns):
            return df[ALL]
    env = load_env(os.path.join(os.path.dirname(__file__) or ".", ".env"))
    key = env["ALPACA_PAPER_KEY"]
    sec = env["ALPACA_PAPER_SECRET"]
    headers = {"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": sec}
    frames = {}
    for sym in ALL:
        url = "https://data.alpaca.markets/v2/stocks/bars"
        params = {
            "symbols": sym, "timeframe": "1Day", "start": START,
            "adjustment": "all", "feed": "sip", "limit": 10000,
        }
        rows = []
        page = None
        while True:
            if page:
                params["page_token"] = page
            r = requests.get(url, headers=headers, params=params, timeout=30)
            r.raise_for_status()
            j = r.json()
            bars = j.get("bars", {}).get(sym, [])
            rows.extend(bars)
            page = j.get("next_page_token")
            if not page:
                break
        s = pd.Series({pd.Timestamp(b["t"]).tz_convert(None).normalize(): b["c"] for b in rows})
        frames[sym] = s
        print(f"  fetched {sym}: {len(s)} bars")
    df = pd.DataFrame(frames).sort_index().dropna(how="all")
    os.makedirs(os.path.dirname(CACHE), exist_ok=True)
    df.to_csv(CACHE)
    return df[ALL]


def metrics(returns, periods_per_year=52):
    r = returns.dropna()
    if len(r) == 0:
        return {}
    cum = (1 + r).prod()
    yrs = len(r) / periods_per_year
    cagr = cum ** (1 / yrs) - 1
    vol = r.std() * np.sqrt(periods_per_year)
    sharpe = (r.mean() * periods_per_year) / vol if vol > 0 else float("nan")
    downside = r[r < 0].std() * np.sqrt(periods_per_year)
    sortino = (r.mean() * periods_per_year) / downside if downside > 0 else float("nan")
    eq = (1 + r).cumprod()
    maxdd = (eq / eq.cummax() - 1).min()
    return {"CAGR": cagr, "Vol": vol, "Sharpe": sharpe, "Sortino": sortino,
            "maxDD": maxdd, "grows_to": cum, "n": len(r)}


def main():
    print("Fetching daily closes (Alpaca SIP, dividend-adjusted)...")
    closes = fetch_closes()
    # Resample to weekly (Friday) closes
    wk = closes.resample("W-FRI").last().dropna(how="all")
    wk_ret = wk.pct_change()
    uni = wk_ret[UNIVERSE]
    bench_ret = wk_ret[BENCH]

    strat_rets = []
    prev_w = pd.Series(0.0, index=UNIVERSE)
    turnover_total = 0.0
    weeks_in = 0
    for i in range(1, len(wk) - 1):
        signal = uni.iloc[i]           # prior-week return known at week i close
        fwd = uni.iloc[i + 1]          # realized next-week return
        spy_prev = bench_ret.iloc[i]
        w = pd.Series(0.0, index=UNIVERSE)
        if pd.notna(spy_prev) and spy_prev >= CRASH_FILTER:
            picks = signal.dropna().nsmallest(TOP_N).index
            if len(picks) > 0:
                w[picks] = 1.0 / len(picks)
                weeks_in += 1
        gross = float((w * fwd).sum())
        turnover = float((w - prev_w).abs().sum())
        turnover_total += turnover
        net = gross - turnover * COST_PER_SIDE
        strat_rets.append((wk.index[i + 1], net))
        prev_w = w
    sr = pd.Series(dict(strat_rets))
    br = bench_ret.reindex(sr.index)

    m_s = metrics(sr)
    m_b = metrics(br)
    print("\n=== Short-term weekly mean reversion vs SPY ===")
    print(f"Window: {sr.index[0].date()} → {sr.index[-1].date()}  ({m_s['n']} weeks, "
          f"{weeks_in} invested)")
    print(f"Avg weekly turnover: {turnover_total/max(1,len(sr)):.2f}  "
          f"(annualized ~{turnover_total/max(1,len(sr))*52:.0f}x)")
    hdr = f"{'':<12}{'CAGR':>8}{'Vol':>8}{'Sharpe':>8}{'Sortino':>9}{'maxDD':>9}{'$1→':>8}"
    print(hdr)
    for name, m in [("Reversal", m_s), ("SPY B&H", m_b)]:
        print(f"{name:<12}{m['CAGR']*100:>7.1f}%{m['Vol']*100:>7.1f}%{m['Sharpe']:>8.2f}"
              f"{m['Sortino']:>9.2f}{m['maxDD']*100:>8.1f}%{m['grows_to']:>7.2f}")


if __name__ == "__main__":
    main()
