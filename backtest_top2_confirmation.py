"""Experiment R8 — Top-2 sector rotation, standalone confirmation + cost sensitivity
(see Evervault research/finance/backtests/results/r8-top2-concentration-followup.md
for full locked spec — written and committed before this script was run).

R3's sweep found top-2-of-11-sectors beat both the R1/R3 top-3 baseline and SPY on
raw CAGR, but as one variant in a 6-way sweep answering a different question. This
is a standalone confirmation run of that exact config (12m lookback, monthly rebal,
abs-momentum vs BIL, top-2 equal-weight) across four pre-declared cost levels
(0/5/10/20 bps/side) to see how cost-sensitive the edge is given concentration
roughly doubles per-rebalance turnover variance vs top-3.

Pure stdlib (no pandas/requests) — reads the existing cached closes.csv directly.

Run: cd ~/Documents/trading && python3 backtest_top2_confirmation.py
"""
import csv
import os
import statistics
from datetime import date as Date

SECTORS = ["XLK", "XLF", "XLV", "XLE", "XLI", "XLP", "XLY", "XLU", "XLB", "XLRE", "XLC"]
TOP_N = 2
LOOKBACK = 12
COST_LEVELS_BPS = [0, 5, 10, 20]
CACHE = os.path.join(os.path.dirname(__file__) or ".", "data", "cache", "closes.csv")


def load_closes():
    if not os.path.exists(CACHE):
        raise SystemExit(f"Cache missing at {CACHE} — expected R1/R3/R5 cache to already exist; "
                          "not pulling new data for this experiment.")
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


def resample_month_end(dates, data, symbols):
    buckets = {}
    for d in dates:
        buckets[(d.year, d.month)] = d
    labels = [buckets[k] for k in sorted(buckets.keys())]
    series = {sym: [data[d].get(sym) for d in labels] for sym in symbols}
    return labels, series


def pct_change(vals):
    out = [None]
    for i in range(1, len(vals)):
        a, b = vals[i - 1], vals[i]
        out.append((b / a - 1) if (a is not None and b is not None and a != 0) else None)
    return out


def momentum(vals, lookback):
    n = len(vals)
    out = [None] * n
    for i in range(n):
        j, k = i, i - lookback
        if k < 0:
            continue
        a, b = vals[k], vals[j]
        if a is not None and b is not None and a != 0:
            out[i] = b / a - 1
    return out


def run(labels, r1, sig, cost_per_side):
    start_i = LOOKBACK
    prev = {}
    port_ret = []
    turnovers = []
    for i in range(start_i, len(labels) - 1):
        t1 = labels[i + 1]
        sig_t = {s: sig[s][i] for s in SECTORS if sig[s][i] is not None}
        if len(sig_t) < TOP_N:
            continue
        top = sorted(sig_t.items(), key=lambda kv: -kv[1])[:TOP_N]
        bil = sig["BIL"][i]
        w = {}
        for sym, val in top:
            tgt = sym if (bil is not None and val > bil) else "BIL"
            w[tgt] = w.get(tgt, 0) + 1 / TOP_N
        traded = sum(abs(w.get(s, 0) - prev.get(s, 0)) for s in (set(w) | set(prev)))
        turnovers.append(traded)
        cost = traded * cost_per_side
        gross = 0.0
        for s, wt in w.items():
            rv = r1[s][i + 1]
            gross += wt * (rv if rv is not None else 0.0)
        port_ret.append((t1, gross - cost))
        prev = w
    return port_ret, turnovers


def metrics(returns_by_date, periods_per_year):
    rets = [r for _, r in returns_by_date]
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
    sharpe = mean / statistics.stdev(rets) * (periods_per_year ** 0.5)
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
                final=eq[-1], n=n, dates=[d for d, _ in returns_by_date], eq=eq)


def year_return(returns_by_date, year):
    rs = [r for d, r in returns_by_date if d.year == year]
    if not rs:
        return None
    acc = 1.0
    for r in rs:
        acc *= (1 + r)
    return acc - 1


def main():
    dates, data = load_closes()
    all_syms = SECTORS + ["SPY", "BIL"]
    labels, series = resample_month_end(dates, data, all_syms)
    r1 = {s: pct_change(series[s]) for s in all_syms}
    sig = {s: momentum(series[s], LOOKBACK) for s in all_syms}

    print(f"\n{'Cost/side':>10s} {'CAGR':>8s} {'Vol':>8s} {'Sharpe':>7s} {'Sortino':>8s} "
          f"{'maxDD':>8s} {'$1->':>8s} {'AvgTurn/mo':>11s}   n / window")

    results = []
    spy_ret_ref = None
    m_spy_ref = None
    for bps in COST_LEVELS_BPS:
        cost_per_side = bps / 10000.0
        port_ret, turnovers = run(labels, r1, sig, cost_per_side)
        spy_ret = [(t1, r1["SPY"][labels.index(t1)]) for t1, _ in port_ret]
        m = metrics(port_ret, 12)
        m_spy = metrics(spy_ret, 12)
        avg_turn = statistics.mean(turnovers)
        results.append((bps, m, m_spy, port_ret, spy_ret, avg_turn))
        if spy_ret_ref is None:
            spy_ret_ref, m_spy_ref = spy_ret, m_spy
        print(f"{bps:>9d}bp {m['cagr']:8.2%} {m['vol']:8.2%} {m['sharpe']:7.2f} "
              f"{m['sortino']:8.2f} {m['maxdd']:8.2%} {m['final']:7.2f}x {avg_turn:10.1%}   "
              f"n={m['n']}  {m['dates'][0]}->{m['dates'][-1]}")

    print(f"\n{'SPY B&H (same window)':>10s} {m_spy_ref['cagr']:8.2%} {m_spy_ref['vol']:8.2%} "
          f"{m_spy_ref['sharpe']:7.2f} {m_spy_ref['sortino']:8.2f} {m_spy_ref['maxdd']:8.2%} "
          f"{m_spy_ref['final']:7.2f}x")

    print("\nDecision-criteria checks (primary = 5bps/side):")
    for bps, m, m_spy, port_ret, spy_ret, avg_turn in results:
        if bps != 5:
            continue
        y22r = year_return(port_ret, 2022)
        y22s = year_return(spy_ret, 2022)
        beats_cagr = m["cagr"] > m_spy["cagr"]
        beats_2022 = (y22r is not None and y22s is not None and y22r > y22s)
        beats_dd = m["maxdd"] > m_spy["maxdd"]
        print(f"  beats SPY CAGR: {beats_cagr}  ({m['cagr']:.2%} vs {m_spy['cagr']:.2%})")
        print(f"  beats SPY 2022 return: {beats_2022}  ({y22r:.2%} vs {y22s:.2%})")
        print(f"  beats SPY maxDD: {beats_dd}  ({m['maxdd']:.2%} vs {m_spy['maxdd']:.2%})")

    print("\nCost sensitivity of the CAGR edge over SPY (top2 CAGR minus SPY CAGR, same window each level):")
    for bps, m, m_spy, port_ret, spy_ret, avg_turn in results:
        edge = m["cagr"] - m_spy["cagr"]
        print(f"  {bps:>3d}bps/side: edge = {edge:+.2%}  (top2 {m['cagr']:.2%} vs SPY {m_spy['cagr']:.2%})")


if __name__ == "__main__":
    main()
