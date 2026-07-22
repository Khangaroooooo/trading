"""Experiment R12 — Weekly single-stock reversal & wider-universe reversal (locked rules,
see Evervault research/finance/backtests/results/r12-weekly-reversal-wider-universe.md).

R6 found a real gross single-stock reversal signal (daily, 15-name universe, bottom N=3,
1-day hold) destroyed by ~154%/day turnover at 15bps/side. This tests two independent,
pre-declared levers to cut turnover:
  V1 — slow to weekly rebalance (same 15-name universe)
  V2 — widen universe to 40 liquid large-caps (same daily frequency, still N=3)

Rules locked before running, nothing tuned after. Pure stdlib (urllib), caches to
data/cache/closes_stocks_daily.csv (15-name, reused from R6) and
data/cache/closes_stocks40_daily.csv (40-name, new fetch for V2).

Run: cd ~/Documents/trading && python3 backtest_reversal_r12.py
"""
import csv
import json
import os
import statistics
import urllib.request
import urllib.parse
from datetime import date as Date

UNIVERSE_15 = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "JPM", "V",
               "JNJ", "PG", "HD", "XOM", "UNH", "KO", "DIS"]
UNIVERSE_40 = UNIVERSE_15 + ["TSLA", "AVGO", "ORCL", "COST", "PEP", "ABBV", "MRK", "PFE",
                             "CVX", "WMT", "BAC", "MA", "ADBE", "CRM", "NFLX", "INTC",
                             "CSCO", "VZ", "T", "CMCSA", "TXN", "QCOM", "IBM", "GE", "CAT"]
BENCH = "SPY"
START = "2016-01-01"
COST_PER_SIDE = 0.0015
TOP_N = 3
CRASH_FILTER = -0.03
CACHE_15 = os.path.join(os.path.dirname(__file__) or ".", "data", "cache", "closes_stocks_daily.csv")
CACHE_40 = os.path.join(os.path.dirname(__file__) or ".", "data", "cache", "closes_stocks40_daily.csv")
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


def fetch_closes(universe, cache_path):
    all_syms = universe + [BENCH]
    if os.path.exists(cache_path):
        with open(cache_path, newline="") as f:
            reader = csv.reader(f)
            header = next(reader)
            if set(all_syms).issubset(set(header[1:])):
                return _read_cache(cache_path, all_syms)
    env = load_env(ENV_PATH)
    key, sec = env["ALPACA_PAPER_KEY"], env["ALPACA_PAPER_SECRET"]
    headers = {"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": sec}
    all_data = {}
    for sym in all_syms:
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
    os.makedirs(os.path.dirname(cache_path), exist_ok=True)
    with open(cache_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow([""] + all_syms)
        for d in dates:
            row = [d.isoformat()] + [all_data[d].get(s, "") for s in all_syms]
            w.writerow(row)
    return dates, all_data


def _read_cache(cache_path, all_syms):
    with open(cache_path, newline="") as f:
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


def metrics(returns_by_date, periods_per_year):
    rets = [r for _, r in returns_by_date]
    eq = []
    acc = 1.0
    for r in rets:
        acc *= (1 + r)
        eq.append(acc)
    n = len(rets)
    years = n / periods_per_year
    cagr = eq[-1] ** (1 / years) - 1 if years > 0 else float("nan")
    vol = statistics.stdev(rets) * (periods_per_year ** 0.5) if n > 1 else float("nan")
    mean = statistics.mean(rets)
    sharpe = (mean * periods_per_year) / vol if vol and vol > 0 else float("nan")
    neg = [r for r in rets if r < 0]
    downside = statistics.stdev(neg) * (periods_per_year ** 0.5) if len(neg) > 1 else float("nan")
    sortino = (mean * periods_per_year) / downside if downside else float("nan")
    running_max = -float("inf")
    maxdd = 0.0
    for e in eq:
        running_max = max(running_max, e)
        dd = e / running_max - 1
        maxdd = min(maxdd, dd)
    return dict(cagr=cagr, vol=vol, sharpe=sharpe, sortino=sortino, maxdd=maxdd, final=eq[-1], n=n)


def print_table(title, rows):
    print(f"\n=== {title} ===")
    hdr = f"{'':<20}{'CAGR':>8}{'Vol':>8}{'Sharpe':>8}{'Sortino':>9}{'maxDD':>9}{'$1->':>8}"
    print(hdr)
    for name, m in rows:
        print(f"{name:<20}{m['cagr']*100:>7.1f}%{m['vol']*100:>7.1f}%{m['sharpe']:>8.2f}"
              f"{m['sortino']:>9.2f}{m['maxdd']*100:>8.1f}%{m['final']:>7.2f}")


def per_year_table(strat_series, bench_series, label):
    by_year_s, by_year_b = {}, {}
    for d, r in strat_series:
        by_year_s.setdefault(d.year, []).append(r)
    for d, r in bench_series:
        by_year_b.setdefault(d.year, []).append(r)
    print(f"\nPer-year net returns ({label} | SPY same window):")
    for y in sorted(by_year_s.keys()):
        acc_s, acc_b = 1.0, 1.0
        for r in by_year_s[y]:
            acc_s *= (1 + r)
        for r in by_year_b.get(y, []):
            acc_b *= (1 + r)
        print(f"  {y}: {label} {acc_s-1:7.2%}   spy {acc_b-1:7.2%}")


def run_daily(dates, data, universe, top_n):
    """Daily reversal, N=top_n from universe, 1-day hold. Returns net/gross series + turnover."""
    ret = {s: pct_change_series(dates, data, s) for s in universe + [BENCH]}
    bench_ret = ret[BENCH]
    net_series, gross_series, bench_series = [], [], []
    prev_w = {}
    turnover_total = 0.0
    days_in = 0
    for i in range(1, len(dates) - 1):
        signal = {s: ret[s][i] for s in universe if ret[s][i] is not None}
        fwd = {s: ret[s][i + 1] for s in universe}
        spy_prev = bench_ret[i]
        w = {}
        if spy_prev is not None and spy_prev >= CRASH_FILTER and len(signal) >= top_n:
            picks = sorted(signal.items(), key=lambda kv: kv[1])[:top_n]
            for sym, _ in picks:
                w[sym] = 1.0 / top_n
            days_in += 1
        traded = sum(abs(w.get(s, 0) - prev_w.get(s, 0)) for s in (set(w) | set(prev_w)))
        turnover_total += traded
        cost = traded * COST_PER_SIDE
        gross = sum(wt * (fwd.get(s) if fwd.get(s) is not None else 0.0) for s, wt in w.items())
        net_series.append((dates[i + 1], gross - cost))
        gross_series.append((dates[i + 1], gross))
        prev_w = w
    for i in range(1, len(dates) - 1):
        d1 = dates[i + 1]
        r = bench_ret[i + 1]
        bench_series.append((d1, r if r is not None else 0.0))
    return net_series, gross_series, bench_series, turnover_total, days_in


def build_weekly_index(dates):
    """Map each date to its ISO (year, week) and return sorted list of week-end date indices."""
    week_of = [d.isocalendar()[:2] for d in dates]
    week_end_idx = []
    for i in range(len(dates)):
        if i == len(dates) - 1 or week_of[i] != week_of[i + 1]:
            week_end_idx.append(i)
    return week_end_idx


def run_weekly(dates, data, universe, top_n):
    """Weekly reversal: signal = prior week-end-to-week-end return, hold following week."""
    all_syms = universe + [BENCH]
    week_end_idx = build_weekly_index(dates)
    closes = {s: [data[dates[i]].get(s) for i in range(len(dates))] for s in all_syms}

    week_ret = {s: [] for s in all_syms}
    for s in all_syms:
        prev_close = None
        for idx in week_end_idx:
            c = closes[s][idx]
            if prev_close is not None and c is not None and prev_close != 0:
                week_ret[s].append(c / prev_close - 1)
            else:
                week_ret[s].append(None)
            if c is not None:
                prev_close = c

    net_series, gross_series, bench_series = [], [], []
    prev_w = {}
    turnover_total = 0.0
    weeks_in = 0
    n_weeks = len(week_end_idx)
    for wi in range(1, n_weeks - 1):
        signal = {s: week_ret[s][wi] for s in universe if week_ret[s][wi] is not None}
        fwd = {s: week_ret[s][wi + 1] for s in universe}
        spy_prev = week_ret[BENCH][wi]
        w = {}
        if spy_prev is not None and spy_prev >= CRASH_FILTER and len(signal) >= top_n:
            picks = sorted(signal.items(), key=lambda kv: kv[1])[:top_n]
            for sym, _ in picks:
                w[sym] = 1.0 / top_n
            weeks_in += 1
        traded = sum(abs(w.get(s, 0) - prev_w.get(s, 0)) for s in (set(w) | set(prev_w)))
        turnover_total += traded
        cost = traded * COST_PER_SIDE
        gross = sum(wt * (fwd.get(s) if fwd.get(s) is not None else 0.0) for s, wt in w.items())
        end_date = dates[week_end_idx[wi + 1]]
        net_series.append((end_date, gross - cost))
        gross_series.append((end_date, gross))
        spy_fwd = week_ret[BENCH][wi + 1]
        bench_series.append((end_date, spy_fwd if spy_fwd is not None else 0.0))
        prev_w = w
    return net_series, gross_series, bench_series, turnover_total, weeks_in, n_weeks


def main():
    print("=== R12 V1: weekly rebalance, 15-name universe ===")
    print("Fetching daily closes (15-name, reused from R6)...")
    dates15, data15 = fetch_closes(UNIVERSE_15, CACHE_15)
    print(f"  {len(dates15)} trading days: {dates15[0]} -> {dates15[-1]}")

    net_w, gross_w, bench_w, turnover_w, weeks_in, n_weeks = run_weekly(dates15, data15, UNIVERSE_15, TOP_N)
    m_net_w = metrics(net_w, periods_per_year=52)
    m_gross_w = metrics(gross_w, periods_per_year=52)
    m_bench_w = metrics(bench_w, periods_per_year=52)
    avg_to_w = turnover_w / max(1, len(net_w))
    print(f"Window: {net_w[0][0]} -> {net_w[-1][0]}  ({m_net_w['n']} weeks, {weeks_in} invested of {n_weeks})")
    print(f"Avg weekly turnover: {avg_to_w:.3f}  (annualized ~{avg_to_w*52:.0f}x)")
    print_table("V1: Weekly reversal (15-name) vs SPY", [
        ("Reversal (net)", m_net_w),
        ("Reversal (gross)", m_gross_w),
        ("SPY B&H (weekly)", m_bench_w),
    ])
    per_year_table(net_w, bench_w, "V1 weekly")

    print("\n\n=== R12 V2: daily rebalance, 40-name universe ===")
    print("Fetching daily closes (40-name, new fetch for the 25 added symbols)...")
    dates40, data40 = fetch_closes(UNIVERSE_40, CACHE_40)
    print(f"  {len(dates40)} trading days: {dates40[0]} -> {dates40[-1]}")

    net_d, gross_d, bench_d, turnover_d, days_in = run_daily(dates40, data40, UNIVERSE_40, TOP_N)
    m_net_d = metrics(net_d, periods_per_year=252)
    m_gross_d = metrics(gross_d, periods_per_year=252)
    m_bench_d = metrics(bench_d, periods_per_year=252)
    avg_to_d = turnover_d / max(1, len(net_d))
    print(f"Window: {net_d[0][0]} -> {net_d[-1][0]}  ({m_net_d['n']} trading days, {days_in} invested)")
    print(f"Avg daily turnover: {avg_to_d:.3f}  (annualized ~{avg_to_d*252:.0f}x)")
    print_table("V2: Daily reversal (40-name) vs SPY", [
        ("Reversal (net)", m_net_d),
        ("Reversal (gross)", m_gross_d),
        ("SPY B&H (daily)", m_bench_d),
    ])
    per_year_table(net_d, bench_d, "V2 daily-40")


if __name__ == "__main__":
    main()
