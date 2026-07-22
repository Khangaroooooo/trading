"""Experiment #3 — Rotation robustness sweep (locked variant grid, see Evervault
research/finance/backtests/results/r3-rotation-robustness-sweep.md for full spec).

One-factor-at-a-time perturbations off the R1 baseline: top-N, lookback window,
skip-last-month momentum, weekly vs monthly rebalance. All variants declared
before running; none tuned after seeing results.

Pure stdlib (no pandas/requests) — reads the existing cached closes.csv directly;
this environment can't install packages for an unattended run.

Run: cd ~/Documents/trading && python3 backtest_rotation_sweep.py
"""
import csv
import os
import statistics
from datetime import timedelta, date as Date

SECTORS = ["XLK", "XLF", "XLV", "XLE", "XLI", "XLP", "XLY", "XLU", "XLB", "XLRE", "XLC"]
COST_PER_SIDE = 0.0005
CACHE = os.path.join(os.path.dirname(__file__) or ".", "data", "cache", "closes.csv")

VARIANTS = [
    dict(label="V0 Baseline (=R1 replica)", top_n=3, lookback=12, skip_month=False, freq="M"),
    dict(label="V1 Top-2",                  top_n=2, lookback=12, skip_month=False, freq="M"),
    dict(label="V2 Top-4",                  top_n=4, lookback=12, skip_month=False, freq="M"),
    dict(label="V3 6m lookback",            top_n=3, lookback=6,  skip_month=False, freq="M"),
    dict(label="V4 Skip-last-month (12-1)", top_n=3, lookback=12, skip_month=True,  freq="M"),
    dict(label="V5 Weekly rebalance",       top_n=3, lookback=52, skip_month=False, freq="W"),
]


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


def run_variant(labels, r1, sig, all_syms, top_n, lookback, skip_month):
    start_i = lookback + (1 if skip_month else 0)
    prev = {}
    port_ret = []
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
        cost = traded * COST_PER_SIDE
        gross = 0.0
        for s, wt in w.items():
            rv = r1[s][i + 1]
            gross += wt * (rv if rv is not None else 0.0)
        port_ret.append((t1, gross - cost))
        prev = w
    return port_ret


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


def year_returns(returns_by_date):
    by_year = {}
    for d, r in returns_by_date:
        by_year.setdefault(d.year, []).append(r)
    out = {}
    for y, rs in by_year.items():
        acc = 1.0
        for r in rs:
            acc *= (1 + r)
        out[y] = acc - 1
    return out


def main():
    dates, data = load_closes()
    all_syms = SECTORS + ["SPY", "BIL"]

    cache = {}

    def get_freq_data(freq):
        if freq not in cache:
            if freq == "M":
                labels, series = resample_month_end(dates, data, all_syms)
            else:
                labels, series = resample_weekly(dates, data, all_syms)
            r1 = {s: pct_change(series[s]) for s in all_syms}
            cache[freq] = (labels, series, r1)
        return cache[freq]

    rows = []
    for v in VARIANTS:
        ppy = 12 if v["freq"] == "M" else 52
        labels, series, r1 = get_freq_data(v["freq"])
        sig = {s: momentum(series[s], v["lookback"], v["skip_month"]) for s in all_syms}
        port_ret = run_variant(labels, r1, sig, all_syms, v["top_n"], v["lookback"], v["skip_month"])
        spy_ret = [(t1, r1["SPY"][labels.index(t1)]) for t1, _ in port_ret]

        m_rot = metrics(port_ret, ppy)
        m_spy = metrics(spy_ret, ppy)
        yr_rot = year_returns(port_ret)
        yr_spy = year_returns(spy_ret)
        rows.append((v["label"], m_rot, m_spy, yr_rot.get(2022), yr_spy.get(2022), yr_rot, yr_spy))

    print(f"\n{'Variant':30s} {'CAGR':>8s} {'Vol':>8s} {'Sharpe':>7s} {'Sortino':>8s} "
          f"{'maxDD':>8s} {'$1->':>8s}   [SPY same-window CAGR / maxDD]  window")
    for label, m_rot, m_spy, y22r, y22s, yr_rot, yr_spy in rows:
        print(f"{label:30s} {m_rot['cagr']:8.2%} {m_rot['vol']:8.2%} {m_rot['sharpe']:7.2f} "
              f"{m_rot['sortino']:8.2f} {m_rot['maxdd']:8.2%} {m_rot['final']:7.2f}x   "
              f"[{m_spy['cagr']:.2%} / {m_spy['maxdd']:.2%}]  n={m_rot['n']}  "
              f"{m_rot['dates'][0]}->{m_rot['dates'][-1]}")

    print("\n2022 return (rotation vs SPY, same window) and maxDD-beats-SPY check:")
    for label, m_rot, m_spy, y22r, y22s, yr_rot, yr_spy in rows:
        beats_2022 = "n/a" if y22r is None else ("YES" if y22r > y22s else "no")
        beats_dd = "YES" if m_rot["maxdd"] > m_spy["maxdd"] else "no"
        y22r_s = f"{y22r:.2%}" if y22r is not None else "n/a"
        y22s_s = f"{y22s:.2%}" if y22s is not None else "n/a"
        print(f"  {label:30s} 2022 rot {y22r_s:>8s} vs SPY {y22s_s:>8s}  beats_2022={beats_2022:>3s}   "
              f"maxDD rot {m_rot['maxdd']:7.2%} vs SPY {m_spy['maxdd']:7.2%}  beats_maxDD={beats_dd}")

    print("\nPer-year returns (rotation | SPY same window) per variant:")
    for label, m_rot, m_spy, y22r, y22s, yr_rot, yr_spy in rows:
        print(f"  {label}:")
        for y in sorted(yr_rot.keys()):
            print(f"    {y}: rot {yr_rot[y]:7.2%}   spy {yr_spy[y]:7.2%}")


if __name__ == "__main__":
    main()
