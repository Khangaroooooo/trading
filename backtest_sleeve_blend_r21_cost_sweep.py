"""Experiment R21 -- Cost-sensitivity re-sweep on R20's top-2/SPY blend.

Rules (locked before running; see Evervault
research/finance/backtests/results/r21-top2-blend-cost-sensitivity.md for full spec).

Sleeve A = R8/R20 exact spec (11 SPDR sectors, top-2 abs-momentum vs BIL, monthly
rebal, no vol-target overlay) with Sleeve A's *internal* per-side trading cost swept
across {0, 5, 10, 20} bps/side. Sleeve B = SPY B&H, same monthly grid. Blended at
fixed weights w in {0, 25, 50, 75, 100}% at each cost level, with a blend-level
rebalancing cost (SPY-leg-only, 5bps/side, held FIXED across the sweep) applied to
the weight drift between sleeves each month -- identical blend methodology to R18/R20
(backtest_sleeve_blend_r20.py). Only Sleeve A's internal cost varies; the blend
rebalancing cost is not part of this sweep.

Pure stdlib, reads the existing cached data/cache/closes.csv (same cache as
R1/R3/R5/R8/R10/R11/R16/R18/R20) -- no new fetch, no installs.

Run: cd ~/Documents/trading && python3 backtest_sleeve_blend_r21_cost_sweep.py
"""
import csv
import os
import statistics
from datetime import date as Date

SECTORS = ["XLK", "XLF", "XLV", "XLE", "XLI", "XLP", "XLY", "XLU", "XLB", "XLRE", "XLC"]
ALL = SECTORS + ["SPY", "BIL"]
TOP_N = 2
LOOKBACK_M = 12
CACHE = os.path.join(os.path.dirname(__file__) or ".", "data", "cache", "closes.csv")

BLEND_WEIGHTS = [0.0, 0.25, 0.50, 0.75, 1.00]
SLEEVE_A_COST_LEVELS = [0.0000, 0.0005, 0.0010, 0.0020]  # 0/5/10/20 bps/side
BLEND_REBAL_COST_PER_SIDE = 0.0005  # SPY-leg drift cost, held fixed (R18/R20 convention)


def load_closes():
    if not os.path.exists(CACHE):
        raise SystemExit(f"Cache missing at {CACHE} -- expected R1/R3/R5/R8/R10/R18/R20 "
                          "cache to already exist; not pulling new data for this experiment.")
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


def run_sleeve_a(labels, r1m, sig, cost_per_side):
    """R8/R20: top-2 abs-momentum rotation book, no vol-target overlay."""
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
        cost = traded * cost_per_side
        gross = 0.0
        for s, wt in w.items():
            rv = r1m[s][i + 1]
            gross += wt * (rv if rv is not None else 0.0)
        port_ret.append((t1, gross - cost))
        prev = w
    return port_ret


def run_blend(sleeve_a_ret, sleeve_b_ret, w):
    """Fixed-mix blend of two monthly return streams, rebalanced back to w each month,
    with a blend-level rebalancing cost on the drift (SPY-leg-only, fixed bps/side)."""
    assert [d for d, _ in sleeve_a_ret] == [d for d, _ in sleeve_b_ret]
    out = []
    for (t, ra), (_, rb) in zip(sleeve_a_ret, sleeve_b_ret):
        gross = w * ra + (1 - w) * rb
        wa_post = (w * (1 + ra)) / (w * (1 + ra) + (1 - w) * (1 + rb)) if (w > 0 or (1 - w) > 0) else w
        drift = abs(wa_post - w)
        rebal_cost = drift * 2 * BLEND_REBAL_COST_PER_SIDE
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


def main():
    dates, data = load_closes()

    labels, series = resample_month_end(dates, data, ALL)
    r1m = {s: pct_change(series[s]) for s in ALL}
    sig = {s: momentum_12m(series[s], LOOKBACK_M) for s in ALL}

    sleeve_b = None  # filled once labels are known from sleeve_a at any cost level

    m_b_ref = None
    all_results = {}  # cost_level -> [(w, m), ...]

    for cost in SLEEVE_A_COST_LEVELS:
        sleeve_a = run_sleeve_a(labels, r1m, sig, cost)
        if sleeve_b is None:
            sleeve_b = [(t1, r1m["SPY"][labels.index(t1)]) for t1, _ in sleeve_a]
            m_b_ref = metrics(sleeve_b)

        rows = []
        for w in BLEND_WEIGHTS:
            blend_ret = run_blend(sleeve_a, sleeve_b, w)
            m = metrics(blend_ret)
            rows.append((w, m))
        all_results[cost] = rows

        if abs(cost - 0.0005) < 1e-9:
            m_a5 = metrics(sleeve_a)
            print(f"Sanity check -- Sleeve A @5bps/side (R8/R20 reproduction): "
                  f"CAGR {m_a5['cagr']:.2%} maxDD {m_a5['maxdd']:.2%} "
                  f"(R8/R20 published: CAGR 16.69%, maxDD -17.11%)")

    print(f"\n[SPY same-window] CAGR {m_b_ref['cagr']:.2%}  Sharpe {m_b_ref['sharpe']:.2f}  "
          f"Sortino {m_b_ref['sortino']:.2f}  maxDD {m_b_ref['maxdd']:.2%}")

    for cost in SLEEVE_A_COST_LEVELS:
        bps = cost * 10000
        print(f"\n=== Sleeve A internal cost = {bps:.0f} bps/side ===")
        print(f"{'w(top2)':>7s} {'CAGR':>8s} {'Vol':>8s} {'Sharpe':>7s} {'Sortino':>8s} "
              f"{'maxDD':>8s} {'$1->':>8s}   n")
        for w, m in all_results[cost]:
            print(f"{w:6.0%} {m['cagr']:8.2%} {m['vol']:8.2%} {m['sharpe']:7.2f} "
                  f"{m['sortino']:8.2f} {m['maxdd']:8.2%} {m['final']:7.2f}x   n={m['n']}")

        print("Pre-declared bars vs SPY (Sharpe>=, Sortino>=, maxDD shallower, CAGR within 1.5pt):")
        for w, m in all_results[cost]:
            bar_sharpe = m["sharpe"] >= m_b_ref["sharpe"]
            bar_sortino = m["sortino"] >= m_b_ref["sortino"]
            bar_maxdd = m["maxdd"] > m_b_ref["maxdd"]
            bar_cagr = abs(m["cagr"] - m_b_ref["cagr"]) <= 0.015
            n_clear = sum([bar_sharpe, bar_sortino, bar_maxdd, bar_cagr])
            print(f"  w={w:.0%}: Sharpe={'Y' if bar_sharpe else 'n'} Sortino={'Y' if bar_sortino else 'n'} "
                  f"maxDD={'Y' if bar_maxdd else 'n'} CAGR-within-1.5pt={'Y' if bar_cagr else 'n'}  "
                  f"({n_clear}/4)  CAGRdelta={m['cagr']-m_b_ref['cagr']:+.2%}")

    print("\nCAGR edge over SPY, by weight, across cost levels (erosion table):")
    print(f"{'w':>5s}" + "".join(f"{c*10000:>10.0f}bps" for c in SLEEVE_A_COST_LEVELS))
    for w in BLEND_WEIGHTS:
        row = f"{w:4.0%} "
        for cost in SLEEVE_A_COST_LEVELS:
            m = dict(all_results[cost])[w]
            edge = m["cagr"] - m_b_ref["cagr"]
            row += f"{edge:+12.2%}"
        print(row)


if __name__ == "__main__":
    main()
