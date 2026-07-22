"""Experiment #9 — Rotation cost-sensitivity stress test (locked spec, see Evervault
research/finance/backtests/results/r9-rotation-cost-sensitivity.md for full spec).

Restricts R3's variant grid to V0 (monthly baseline) and V5 (weekly rebalance) and
sweeps the cost-per-side assumption (0/5/10/20 bps) instead of holding it fixed.
Answers: how much of V0's edge and V5's maxDD failure is cost-driven vs signal-driven.

Pure stdlib (no pandas/requests) — reads the existing cached closes.csv directly;
this environment can't install packages for an unattended run.

Run: cd ~/Documents/trading && python3 backtest_rotation_cost_sensitivity.py
"""
import csv
import os
import statistics
from datetime import timedelta, date as Date

SECTORS = ["XLK", "XLF", "XLV", "XLE", "XLI", "XLP", "XLY", "XLU", "XLB", "XLRE", "XLC"]
CACHE = os.path.join(os.path.dirname(__file__) or ".", "data", "cache", "closes.csv")

VARIANTS = [
    dict(label="V0 Baseline (monthly)", top_n=3, lookback=12, skip_month=False, freq="M"),
    dict(label="V5 Weekly rebalance",   top_n=3, lookback=52, skip_month=False, freq="W"),
]

COST_LEVELS_BPS = [0, 5, 10, 20]


def load_closes():
    if not os.path.exists(CACHE):
        raise SystemExit(f"Cache missing at {CACHE} — expected R1/R2 cache to already exist; "
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


def friday_of_week(d):
    return d + timedelta(days=4 - d.weekday())


def resample_weekly(dates, data, symbols):
    buckets = {}
    for d in dates:
        buckets[friday_of_week(d)] = d
    labels = [buckets[k] for k in sorted(buckets.keys())]
    series = {sym: [data[d].get(sym) for d in labels] for sym in symbols}
    return labels, series


def pct_change(vals):
    out = [None]
    for i in range(1, len(vals)):
        a, b = vals[i - 1], vals[i]
        out.append((b / a - 1) if (a is not None and b is not None and a != 0) else None)
    return out


def momentum(vals, lookback, skip_month):
    n = len(vals)
    out = [None] * n
    for i in range(n):
        if skip_month:
            j, k = i - 1, i - lookback - 1
        else:
            j, k = i, i - lookback
        if j < 0 or k < 0:
            continue
        a, b = vals[k], vals[j]
        if a is not None and b is not None and a != 0:
            out[i] = b / a - 1
    return out


def run_variant_impl(labels, r1, sig, top_n, lookback, skip_month, cost_per_side):
    start_i = lookback + (1 if skip_month else 0)
    prev = {}
    port_ret = []
    turnovers = []
    for i in range(start_i, len(labels) - 1):
        t1 = labels[i + 1]
        sig_t = {s: sig[s][i] for s in SECTORS if sig[s][i] is not None}
        if len(sig_t) < top_n:
            continue
        top = sorted(sig_t.items(), key=lambda kv: -kv[1])[:top_n]
        bil = sig["BIL"][i]
        w = {}
        for sym, val in top:
            tgt = sym if (bil is not None and val > bil) else "BIL"
            w[tgt] = w.get(tgt, 0) + 1 / top_n
        traded = sum(abs(w.get(s, 0) - prev.get(s, 0)) for s in (set(w) | set(prev)))
        cost = traded * cost_per_side
        turnovers.append(traded)
        gross = 0.0
        for s, wt in w.items():
            rv = r1[s][i + 1]
            gross += wt * (rv if rv is not None else 0.0)
        port_ret.append((t1, gross - cost))
        prev = w
    return port_ret, turnovers


def metrics(returns_by_date, periods_per_year):
    dates = [d for d, _ in returns_by_date]
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
                final=eq[-1], n=n, dates=dates, eq=eq)


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

    freq_cache = {}

    def get_freq_data(freq):
        if freq not in freq_cache:
            if freq == "M":
                labels, series = resample_month_end(dates, data, all_syms)
            else:
                labels, series = resample_weekly(dates, data, all_syms)
            r1 = {s: pct_change(series[s]) for s in all_syms}
            freq_cache[freq] = (labels, series, r1)
        return freq_cache[freq]

    print(f"{'Variant':22s} {'Cost/side':>10s} {'CAGR':>8s} {'Vol':>8s} {'Sharpe':>7s} "
          f"{'Sortino':>8s} {'maxDD':>8s} {'$1->':>7s} {'AvgTO':>7s}  n   window")

    results = {}
    for v in VARIANTS:
        ppy = 12 if v["freq"] == "M" else 52
        labels, series, r1 = get_freq_data(v["freq"])
        sig = {s: momentum(series[s], v["lookback"], v["skip_month"]) for s in all_syms}

        variant_rows = []
        for bps in COST_LEVELS_BPS:
            cost_per_side = bps / 10000.0
            port_ret, turnovers = run_variant_impl(
                labels, r1, sig, v["top_n"], v["lookback"], v["skip_month"], cost_per_side)
            spy_ret = [(t1, r1["SPY"][labels.index(t1)]) for t1, _ in port_ret]

            m_rot = metrics(port_ret, ppy)
            m_spy = metrics(spy_ret, ppy)
            y22_rot = year_return(port_ret, 2022)
            y22_spy = year_return(spy_ret, 2022)
            avg_to = statistics.mean(turnovers) if turnovers else 0.0

            print(f"{v['label']:22s} {bps:>8d}bps {m_rot['cagr']:8.2%} {m_rot['vol']:8.2%} "
                  f"{m_rot['sharpe']:7.2f} {m_rot['sortino']:8.2f} {m_rot['maxdd']:8.2%} "
                  f"{m_rot['final']:6.2f}x {avg_to:6.1%}  {m_rot['n']:d}  "
                  f"{m_rot['dates'][0]}->{m_rot['dates'][-1]}")

            variant_rows.append(dict(
                bps=bps, m_rot=m_rot, m_spy=m_spy, y22_rot=y22_rot, y22_spy=y22_spy,
                avg_to=avg_to))
        results[v["label"]] = variant_rows
        print()

    print("\nDefensive-profile check per cost level (2022 return, maxDD vs SPY same window):")
    for v in VARIANTS:
        print(f"  {v['label']}:")
        for row in results[v["label"]]:
            beats_2022 = "n/a"
            if row["y22_rot"] is not None and row["y22_spy"] is not None:
                beats_2022 = "YES" if row["y22_rot"] > row["y22_spy"] else "no"
            beats_dd = "YES" if row["m_rot"]["maxdd"] > row["m_spy"]["maxdd"] else "no"
            y22r = f"{row['y22_rot']:.2%}" if row["y22_rot"] is not None else "n/a"
            y22s = f"{row['y22_spy']:.2%}" if row["y22_spy"] is not None else "n/a"
            print(f"    {row['bps']:3d}bps: 2022 rot {y22r:>8s} vs SPY {y22s:>8s}  "
                  f"beats_2022={beats_2022:>3s}   maxDD rot {row['m_rot']['maxdd']:7.2%} "
                  f"vs SPY {row['m_spy']['maxdd']:7.2%}  beats_maxDD={beats_dd}")

    print("\nCAGR gap to SPY across cost levels (rot CAGR - SPY CAGR):")
    for v in VARIANTS:
        print(f"  {v['label']}:")
        for row in results[v["label"]]:
            gap = row["m_rot"]["cagr"] - row["m_spy"]["cagr"]
            print(f"    {row['bps']:3d}bps: gap = {gap:+.2%}  (rot {row['m_rot']['cagr']:.2%} "
                  f"vs SPY {row['m_spy']['cagr']:.2%})")


if __name__ == "__main__":
    main()
