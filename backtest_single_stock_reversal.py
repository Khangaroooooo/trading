"""Experiment R6 — Single-stock daily reversal check (locked rules, see Evervault
research/finance/backtests/results/r6-single-stock-reversal.md for full spec).

R2 rejected short-term weekly reversal on sector ETFs. Literature says reversal lives
at the single-stock level, not diversified ETFs. This moves the same "buy the losers"
logic to 15 liquid mega-caps at daily frequency (one horizon faster than R2).

Rules (locked before running, nothing tuned after):
  - Universe: AAPL, MSFT, GOOGL, AMZN, NVDA, META, JPM, V, JNJ, PG, HD, XOM, UNH, KO, DIS
  - Daily rebalance. Signal = prior-day close-to-close return.
  - Long bottom N=3 (most oversold) equal-weight, held 1 day.
  - Crash filter: skip day if SPY prior-day return < -3%.
  - Costs: 15 bps/side per unit weight traded.
  - Benchmark: SPY buy-and-hold, same window.

Pure stdlib (no pandas/requests available in this unattended environment) — fetches
via urllib.request (same pattern as smoke_test.py), caches to data/cache/closes_stocks_daily.csv.

Run: cd ~/Documents/trading && python3 backtest_single_stock_reversal.py
"""
import csv
import json
import os
import statistics
import urllib.request
import urllib.parse
from datetime import date as Date

UNIVERSE = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "JPM", "V",
            "JNJ", "PG", "HD", "XOM", "UNH", "KO", "DIS"]
BENCH = "SPY"
ALL_SYMS = UNIVERSE + [BENCH]
START = "2016-01-01"
COST_PER_SIDE = 0.0015   # 15 bps/side — single-stock, high daily turnover
TOP_N = 3
CRASH_FILTER = -0.03     # skip day if SPY prior-day return < -3%
CACHE = os.path.join(os.path.dirname(__file__) or ".", "data", "cache", "closes_stocks_daily.csv")
ENV_PATH = os.path.join(os.path.dirname(__file__) or ".", ".env")


def load_env(path):
    env = {}
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k] = v.strip().strip('"')
    return env


def fetch_json(url, headers):
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def fetch_closes():
    if os.path.exists(CACHE):
        with open(CACHE, newline="") as f:
            reader = csv.reader(f)
            header = next(reader)
            if set(ALL_SYMS).issubset(set(header[1:])):
                dates, data = _read_cache()
                return dates, data
    env = load_env(ENV_PATH)
    key, sec = env["ALPACA_PAPER_KEY"], env["ALPACA_PAPER_SECRET"]
    headers = {"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": sec}
    all_data = {}
    for sym in ALL_SYMS:
        params = {
            "symbols": sym, "timeframe": "1Day", "start": START,
            "adjustment": "all", "feed": "sip", "limit": 10000,
        }
        rows = []
        page = None
        while True:
            if page:
                params["page_token"] = page
            url = "https://data.alpaca.markets/v2/stocks/bars?" + urllib.parse.urlencode(params)
            j = fetch_json(url, headers)
            bars = j.get("bars", {}).get(sym, [])
            rows.extend(bars)
            page = j.get("next_page_token")
            if not page:
                break
        for b in rows:
            d = Date.fromisoformat(b["t"][:10])
            all_data.setdefault(d, {})[sym] = b["c"]
        print(f"  fetched {sym}: {len(rows)} bars")
    dates = sorted(all_data.keys())
    os.makedirs(os.path.dirname(CACHE), exist_ok=True)
    with open(CACHE, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow([""] + ALL_SYMS)
        for d in dates:
            row = [d.isoformat()] + [all_data[d].get(s, "") for s in ALL_SYMS]
            w.writerow(row)
    return dates, all_data


def _read_cache():
    with open(CACHE, newline="") as f:
        reader = csv.reader(f)
        header = next(reader)
        cols = header[1:]
        data = {}
        for row in reader:
            if not row:
                continue
            d = Date.fromisoformat(row[0][:10])
            prices = {}
            for sym, val in zip(cols, row[1:]):
                if val != "":
                    prices[sym] = float(val)
            data[d] = prices
    dates = sorted(data.keys())
    return dates, data


def pct_change_series(dates, data, sym):
    out = [None]
    prev = data[dates[0]].get(sym)
    for i in range(1, len(dates)):
        cur = data[dates[i]].get(sym)
        if prev is not None and cur is not None and prev != 0:
            out.append(cur / prev - 1)
        else:
            out.append(None)
        prev = cur if cur is not None else prev
    return out


def metrics(returns_by_date, periods_per_year=252):
    rets = [r for _, r in returns_by_date]
    dates = [d for d, _ in returns_by_date]
    eq = []
    acc = 1.0
    for r in rets:
        acc *= (1 + r)
        eq.append(acc)
    n = len(rets)
    years = n / periods_per_year
    cagr = eq[-1] ** (1 / years) - 1
    vol = statistics.stdev(rets) * (periods_per_year ** 0.5)
    mean = statistics.mean(rets)
    sharpe = (mean * periods_per_year) / vol if vol > 0 else float("nan")
    neg = [r for r in rets if r < 0]
    downside = statistics.stdev(neg) * (periods_per_year ** 0.5) if len(neg) > 1 else float("nan")
    sortino = (mean * periods_per_year) / downside if downside else float("nan")
    running_max = -float("inf")
    maxdd = 0.0
    for e in eq:
        running_max = max(running_max, e)
        dd = e / running_max - 1
        maxdd = min(maxdd, dd)
    return dict(cagr=cagr, vol=vol, sharpe=sharpe, sortino=sortino, maxdd=maxdd,
                final=eq[-1], n=n, dates=dates)


def main():
    print("Fetching daily closes (Alpaca SIP, dividend-adjusted)...")
    dates, data = fetch_closes()
    print(f"  {len(dates)} trading days: {dates[0]} -> {dates[-1]}")

    ret = {s: pct_change_series(dates, data, s) for s in ALL_SYMS}
    bench_ret = ret[BENCH]

    strat_rets = []
    gross_rets = []
    prev_w = {}
    turnover_total = 0.0
    days_in = 0
    for i in range(1, len(dates) - 1):
        signal = {s: ret[s][i] for s in UNIVERSE if ret[s][i] is not None}
        fwd = {s: ret[s][i + 1] for s in UNIVERSE}
        spy_prev = bench_ret[i]
        w = {}
        if spy_prev is not None and spy_prev >= CRASH_FILTER and len(signal) >= TOP_N:
            picks = sorted(signal.items(), key=lambda kv: kv[1])[:TOP_N]
            for sym, _ in picks:
                w[sym] = 1.0 / TOP_N
            days_in += 1
        traded = sum(abs(w.get(s, 0) - prev_w.get(s, 0)) for s in (set(w) | set(prev_w)))
        turnover_total += traded
        cost = traded * COST_PER_SIDE
        gross = sum(wt * (fwd.get(s) if fwd.get(s) is not None else 0.0) for s, wt in w.items())
        strat_rets.append((dates[i + 1], gross - cost))
        gross_rets.append((dates[i + 1], gross))
        prev_w = w

    sr = strat_rets
    br = []
    for i in range(1, len(dates) - 1):
        d1 = dates[i + 1]
        r = bench_ret[i + 1]
        br.append((d1, r if r is not None else 0.0))

    m_s = metrics(sr)
    m_g = metrics(gross_rets)
    m_b = metrics(br)
    print("\n=== Single-stock daily reversal vs SPY ===")
    print(f"Window: {sr[0][0]} -> {sr[-1][0]}  ({m_s['n']} trading days, {days_in} invested)")
    avg_to = turnover_total / max(1, len(sr))
    print(f"Avg daily turnover: {avg_to:.3f}  (annualized ~{avg_to*252:.0f}x)")
    hdr = f"{'':<16}{'CAGR':>8}{'Vol':>8}{'Sharpe':>8}{'Sortino':>9}{'maxDD':>9}{'$1->':>8}"
    print(hdr)
    for name, m in [("Reversal (net)", m_s), ("Reversal (gross, no cost, diagnostic only)", m_g), ("SPY B&H", m_b)]:
        print(f"{name:<16}{m['cagr']*100:>7.1f}%{m['vol']*100:>7.1f}%{m['sharpe']:>8.2f}"
              f"{m['sortino']:>9.2f}{m['maxdd']*100:>8.1f}%{m['final']:>7.2f}")

    by_year_s, by_year_b = {}, {}
    for d, r in sr:
        by_year_s.setdefault(d.year, []).append(r)
    for d, r in br:
        by_year_b.setdefault(d.year, []).append(r)
    print("\nPer-year returns (reversal | SPY same window):")
    for y in sorted(by_year_s.keys()):
        acc_s, acc_b = 1.0, 1.0
        for r in by_year_s[y]:
            acc_s *= (1 + r)
        for r in by_year_b.get(y, []):
            acc_b *= (1 + r)
        print(f"  {y}: reversal {acc_s-1:7.2%}   spy {acc_b-1:7.2%}")


if __name__ == "__main__":
    main()
