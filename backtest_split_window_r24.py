"""Experiment R24 -- Out-of-sample / split-window robustness check on the R20/R22
top-2-SPY blend.

Rules (locked before running; see Evervault
research/finance/backtests/results/r24-split-window-robustness.md for full spec).

Sleeve A = R8/R20 exact spec (11 SPDR sectors, top-2 abs-momentum vs BIL, monthly
rebal, 5bps/side, no vol-target overlay). Sleeve B = SPY B&H, same monthly grid.
Blended at fixed weights w in {25,50,75}% (R20/R22's adopted region), monthly
rebalance back to target weight, blend-level rebalancing cost (SPY-leg-only,
5bps/side) on weight drift, identical methodology to R18/R20/R21/R22.

The only new thing here: the 114-month Sleeve-A return series is cut at its exact
midpoint (index 57) into two non-overlapping 57-month halves (H1 = 2017-02..2021-10,
H2 = 2021-11..2026-07), and every metric/bar is recomputed against a SPY comparator
over the SAME half-window (not the full-window SPY baseline).

Pure stdlib, reads the existing cached data/cache/closes.csv (same cache as
R1/R3/R5/R8/R10/R16/R18/R20/R22) -- no new fetch, no installs.

Run: cd ~/Documents/trading && python3 backtest_split_window_r24.py
"""
import csv
import os
import statistics
from datetime import date as Date

SECTORS = ["XLK", "XLF", "XLV", "XLE", "XLI", "XLP", "XLY", "XLU", "XLB", "XLRE", "XLC"]
ALL = SECTORS + ["SPY", "BIL"]
COST_PER_SIDE = 0.0005
TOP_N = 2
LOOKBACK_M = 12
CACHE = os.path.join(os.path.dirname(__file__) or ".", "data", "cache", "closes.csv")

BLEND_WEIGHTS = [0.25, 0.50, 0.75]


def load_closes():
    if not os.path.exists(CACHE):
        raise SystemExit(f"Cache missing at {CACHE} — expected R1/R3/R5/R8/R10/R18 cache to "
                          "already exist; not pulling new data for this experiment.")
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


def momentum_12m(vals, lookback):
    n = len(vals)
    out = [None] * n
    for i in range(n):
        j = i - lookback
        if j < 0:
            continue
        a, b = vals[j], vals[i]
        if a is not None and b is not None and a != 0:
            out[i] = b / a - 1
    return out


def base_weights(sig_t, bil_t, top_n):
    top = sorted(sig_t.items(), key=lambda kv: -kv[1])[:top_n]
    w = {}
    for sym, val in top:
        tgt = sym if (bil_t is not None and val > bil_t) else "BIL"
        w[tgt] = w.get(tgt, 0) + 1 / top_n
    return w


def run_sleeve_a(labels, r1m, sig):
    """R8: top-2 abs-momentum rotation book, no vol-target overlay."""
    start_i = LOOKBACK_M
    prev = {}
    port_ret = []
    for i in range(start_i, len(labels) - 1):
        t1 = labels[i + 1]
        sig_t = {s: sig[s][i] for s in SECTORS if sig[s][i] is not None}
        if len(sig_t) < TOP_N:
            continue
        bil = sig["BIL"][i]
        w = base_weights(sig_t, bil, TOP_N)

        traded = sum(abs(w.get(s, 0) - prev.get(s, 0)) for s in (set(w) | set(prev)))
        cost = traded * COST_PER_SIDE
        gross = 0.0
        for s, wt in w.items():
            rv = r1m[s][i + 1]
            gross += wt * (rv if rv is not None else 0.0)
        port_ret.append((t1, gross - cost))
        prev = w
    return port_ret


def run_blend(sleeve_a_ret, sleeve_b_ret, w):
    """Fixed-mix blend of two monthly return streams, rebalanced back to w each month,
    with a blend-level rebalancing cost on the drift (SPY-leg-only, 5bps/side)."""
    assert [d for d, _ in sleeve_a_ret] == [d for d, _ in sleeve_b_ret]
    out = []
    for (t, ra), (_, rb) in zip(sleeve_a_ret, sleeve_b_ret):
        gross = w * ra + (1 - w) * rb
        wa_post = (w * (1 + ra)) / (w * (1 + ra) + (1 - w) * (1 + rb)) if (w > 0 or (1 - w) > 0) else w
        drift = abs(wa_post - w)
        rebal_cost = drift * 2 * COST_PER_SIDE
        out.append((t, gross - rebal_cost))
    return out


def metrics(returns_by_date, periods_per_year=12):
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
                final=eq[-1], n=n, dates=dates)


def bars(m, m_spy):
    bar_sharpe = m["sharpe"] >= m_spy["sharpe"]
    bar_sortino = m["sortino"] >= m_spy["sortino"]
    bar_maxdd = m["maxdd"] > m_spy["maxdd"]
    cagr_delta = m["cagr"] - m_spy["cagr"]
    bar_cagr = (cagr_delta >= 0) and (cagr_delta <= 0.03)
    n_clear = sum([bar_sharpe, bar_sortino, bar_maxdd, bar_cagr])
    return dict(sharpe=bar_sharpe, sortino=bar_sortino, maxdd=bar_maxdd, cagr=bar_cagr,
                n_clear=n_clear, cagr_delta=cagr_delta)


def print_half(name, sleeve_a_half, sleeve_b_half):
    m_a = metrics(sleeve_a_half)
    m_b = metrics(sleeve_b_half)
    print(f"\n=== {name}: {m_a['dates'][0]} -> {m_a['dates'][-1]}  (n={m_a['n']}) ===")
    print(f"Sleeve A alone: CAGR {m_a['cagr']:.2%} Sharpe {m_a['sharpe']:.2f} "
          f"Sortino {m_a['sortino']:.2f} maxDD {m_a['maxdd']:.2%} ${m_a['final']:.2f}->")
    print(f"SPY (same half): CAGR {m_b['cagr']:.2%} Sharpe {m_b['sharpe']:.2f} "
          f"Sortino {m_b['sortino']:.2f} maxDD {m_b['maxdd']:.2%} ${m_b['final']:.2f}->")

    print(f"\n{'w(top2)':>7s} {'CAGR':>8s} {'Vol':>8s} {'Sharpe':>7s} {'Sortino':>8s} "
          f"{'maxDD':>8s} {'$1->':>8s}   bars(4)  CAGRdelta")
    results = []
    for w in BLEND_WEIGHTS:
        blend_ret = run_blend(sleeve_a_half, sleeve_b_half, w)
        m = metrics(blend_ret)
        b = bars(m, m_b)
        results.append((w, m, b))
        tag = f"S={'Y' if b['sharpe'] else 'n'} So={'Y' if b['sortino'] else 'n'} " \
              f"D={'Y' if b['maxdd'] else 'n'} C={'Y' if b['cagr'] else 'n'} ({b['n_clear']}/4)"
        print(f"{w:6.0%} {m['cagr']:8.2%} {m['vol']:8.2%} {m['sharpe']:7.2f} "
              f"{m['sortino']:8.2f} {m['maxdd']:8.2%} {m['final']:7.2f}x   {tag}  "
              f"{b['cagr_delta']:+.2%}")
    return m_a, m_b, results


def main():
    dates, data = load_closes()

    labels, series = resample_month_end(dates, data, ALL)
    r1m = {s: pct_change(series[s]) for s in ALL}
    sig = {s: momentum_12m(series[s], LOOKBACK_M) for s in ALL}

    sleeve_a = run_sleeve_a(labels, r1m, sig)
    sleeve_b = [(t1, r1m["SPY"][labels.index(t1)]) for t1, _ in sleeve_a]

    m_a_full = metrics(sleeve_a)
    m_b_full = metrics(sleeve_b)
    print(f"Sanity check -- Sleeve A full window (R8/R20 reproduction): CAGR {m_a_full['cagr']:.2%} "
          f"maxDD {m_a_full['maxdd']:.2%}  n={m_a_full['n']}  "
          f"(R8 published: CAGR 16.69%, maxDD -17.11% at 5bps/side)")
    print(f"Sanity check -- SPY full window: CAGR {m_b_full['cagr']:.2%} "
          f"Sortino {m_b_full['sortino']:.2f} maxDD {m_b_full['maxdd']:.2%}  n={m_b_full['n']}")

    n = len(sleeve_a)
    mid = n // 2
    assert mid == 57 and n == 114, f"unexpected sample size n={n} mid={mid} -- spec assumed 114/57"

    h1_a, h1_b = sleeve_a[:mid], sleeve_b[:mid]
    h2_a, h2_b = sleeve_a[mid:], sleeve_b[mid:]

    print_half("H1 (first half, no bear-market event)", h1_a, h1_b)
    print_half("H2 (second half, contains 2022 bear market)", h2_a, h2_b)

    print("\n--- Full-window reference bars (for comparison, from R20/R22) ---")
    for w in BLEND_WEIGHTS:
        blend_ret = run_blend(sleeve_a, sleeve_b, w)
        m = metrics(blend_ret)
        b = bars(m, m_b_full)
        print(f"  w={w:.0%}: CAGR {m['cagr']:.2%} Sharpe {m['sharpe']:.2f} Sortino {m['sortino']:.2f} "
              f"maxDD {m['maxdd']:.2%}  bars {b['n_clear']}/4  CAGRdelta {b['cagr_delta']:+.2%}")


if __name__ == "__main__":
    main()
