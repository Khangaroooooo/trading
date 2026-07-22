"""Experiment R27 — Top-5 single-stock momentum, locked standalone confirmation.

Locked spec (written before running; see Evervault
research/finance/backtests/results/r27-single-stock-momentum-top5-confirmation.md
for the full pre-declared rationale).

R26's exploratory grid (NOT a pre-declared decision config) showed top-5, w=100%
clearing all 4 promotion bars while the pre-declared primary (top-3) failed 2/4.
Per this program's precedent (R3 exploratory lead -> R8 standalone confirmation),
a sweep-surfaced lead needs its own freshly-locked, standalone run before being
taken seriously. This script is that confirmation for top-5.

PRIMARY CONFIG (pre-declared, decides the verdict): top-5, standalone sleeve,
w=100%, 5bps/side, monthly, abs-momentum filter vs BIL, same window as R26.

Promotion bars (identical to R26/R8):
  (a) beat SPY CAGR
  (b) Sharpe > 1
  (c) maxDD shallower than -20%
  (d) beat SPY 2022 calendar return

SECONDARY, PRE-DECLARED SWEEP (reported in full, does not override the primary
verdict): cost sensitivity on the same top-5 w=100% config at 0/5/10/20 bps/side.

CARRIED-FORWARD CAVEAT (unchanged from R26): 40-name universe is today's mega-caps
backfilled to 2016 -> survivorship bias. This run cannot resolve that; a pass here
still cannot be adopted live without a survivorship-corrected universe.

Pure stdlib, no installs, no new network fetch (reuses R26's caches).
Run: cd ~/Documents/trading && python3 backtest_single_stock_momentum_r27.py
"""
import csv
import os
import statistics
from datetime import date as Date

HERE = os.path.dirname(__file__) or "."
STOCK_CACHE = os.path.join(HERE, "data", "cache", "closes_stocks40_daily.csv")
BIL_CACHE = os.path.join(HERE, "data", "cache", "closes.csv")
LOOKBACK_M = 12
TOP_N = 5


def load_cache(path):
    with open(path, newline="") as f:
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
    return sorted(data.keys()), data, cols


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


def run_sleeve(labels, universe, r1m, bil_r1m, sig, bil_sig, top_n, cost_per_side):
    prev = {}
    port_ret = []
    turnovers = []
    for i in range(LOOKBACK_M, len(labels) - 1):
        t1 = labels[i + 1]
        sig_t = {s: sig[s][i] for s in universe if sig[s][i] is not None}
        if len(sig_t) < top_n:
            continue
        bil = bil_sig[i]
        w = base_weights(sig_t, bil, top_n)
        traded = sum(abs(w.get(s, 0) - prev.get(s, 0)) for s in (set(w) | set(prev)))
        turnovers.append(traded)
        cost = traded * cost_per_side
        gross = 0.0
        for s, wt in w.items():
            rv = r1m[s][i + 1] if s != "BIL" else bil_r1m[i + 1]
            gross += wt * (rv if rv is not None else 0.0)
        port_ret.append((t1, gross - cost))
        prev = w
    avg_turn = statistics.mean(turnovers) if turnovers else 0.0
    return port_ret, avg_turn


def metrics(returns_by_date, ppy=12):
    rets = [r for _, r in returns_by_date]
    dates = [d for d, _ in returns_by_date]
    eq = []
    acc = 1.0
    for r in rets:
        acc *= (1 + r)
        eq.append(acc)
    n = len(rets)
    years = n / ppy
    cagr = eq[-1] ** (1 / years) - 1
    sd = statistics.stdev(rets)
    vol = sd * (ppy ** 0.5)
    mean = statistics.mean(rets)
    sharpe = mean / sd * (ppy ** 0.5)
    neg = [r for r in rets if r < 0]
    downside = statistics.stdev(neg) * (ppy ** 0.5) if len(neg) > 1 else float("nan")
    sortino = (mean * ppy) / downside if downside else float("nan")
    rmax = -float("inf")
    maxdd = 0.0
    for e in eq:
        rmax = max(rmax, e)
        maxdd = min(maxdd, e / rmax - 1)
    return dict(cagr=cagr, vol=vol, sharpe=sharpe, sortino=sortino, maxdd=maxdd,
                final=eq[-1], n=n, dates=dates)


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
    sdates, sdata, scols = load_cache(STOCK_CACHE)
    bdates, bdata, bcols = load_cache(BIL_CACHE)

    universe = [c for c in scols if c != "SPY"]

    labels, series = resample_month_end(sdates, sdata, scols)
    bil_series = []
    for d in labels:
        v = bdata.get(d, {}).get("BIL")
        if v is None:
            prior = [bd for bd in bdates if bd <= d]
            v = bdata[prior[-1]]["BIL"] if prior else None
        bil_series.append(v)

    r1m = {s: pct_change(series[s]) for s in scols}
    bil_r1m = pct_change(bil_series)
    sig = {s: momentum_12m(series[s], LOOKBACK_M) for s in scols}
    bil_sig = momentum_12m(bil_series, LOOKBACK_M)

    print("=" * 78)
    print("R27 — Top-5 single-stock momentum, locked standalone confirmation")
    print("=" * 78)

    # PRIMARY: top-5, w=100%, 5bps/side
    primary_ret, primary_turn = run_sleeve(labels, universe, r1m, bil_r1m, sig, bil_sig,
                                            TOP_N, 0.0005)
    spy_ret = [(t1, r1m["SPY"][labels.index(t1)]) for t1, _ in primary_ret]
    m_spy = metrics(spy_ret)
    yr_spy = year_returns(spy_ret)
    m_p = metrics(primary_ret)
    yr_p = year_returns(primary_ret)

    print(f"\n[SPY B&H same window]  CAGR {m_spy['cagr']:.2%}  Sharpe {m_spy['sharpe']:.2f}  "
          f"Sortino {m_spy['sortino']:.2f}  maxDD {m_spy['maxdd']:.2%}  "
          f"2022 {yr_spy.get(2022, float('nan')):.2%}  n={m_spy['n']}")
    print(f"Window: {m_spy['dates'][0]} -> {m_spy['dates'][-1]}")

    print(f"\n[PRIMARY top-5 w=100% @5bps/side]  CAGR {m_p['cagr']:.2%}  Vol {m_p['vol']:.2%}  "
          f"Sharpe {m_p['sharpe']:.2f}  Sortino {m_p['sortino']:.2f}  maxDD {m_p['maxdd']:.2%}  "
          f"2022 {yr_p.get(2022, float('nan')):.2%}  $1-> {m_p['final']:.2f}x  "
          f"turn/mo {primary_turn:.1%}")

    a = m_p["cagr"] > m_spy["cagr"]
    b = m_p["sharpe"] > 1.0
    c = m_p["maxdd"] > -0.20
    d = yr_p.get(2022, -1) > yr_spy.get(2022, -1)
    print("\n" + "-" * 78)
    print("PROMOTION BARS — primary config = top-5, w=100% (standalone sleeve), 5bps/side")
    print("-" * 78)
    print(f"  (a) beat SPY CAGR:        {'PASS' if a else 'FAIL'}  ({m_p['cagr']:.2%} vs {m_spy['cagr']:.2%})")
    print(f"  (b) Sharpe > 1:           {'PASS' if b else 'FAIL'}  ({m_p['sharpe']:.2f})")
    print(f"  (c) maxDD shallower -20%: {'PASS' if c else 'FAIL'}  ({m_p['maxdd']:.2%})")
    print(f"  (d) beat SPY 2022:        {'PASS' if d else 'FAIL'}  ({yr_p.get(2022, float('nan')):.2%} vs {yr_spy.get(2022, float('nan')):.2%})")
    print(f"\n  => {sum([a,b,c,d])}/4 bars cleared. "
          f"{'CONFIRMED CANDIDATE (still not adoptable live -- survivorship bias unresolved).' if sum([a,b,c,d])==4 else 'Does not confirm R26 lead.'}")

    # SECONDARY, pre-declared: cost sensitivity sweep at 0/5/10/20 bps/side
    print("\n" + "=" * 78)
    print("SECONDARY (pre-declared, does not override primary verdict): cost sweep")
    print("=" * 78)
    print(f"\n{'cost/side':>10s} {'CAGR':>8s} {'Vol':>7s} {'Sharpe':>7s} {'Sortino':>8s} "
          f"{'maxDD':>8s} {'2022':>8s} {'$1->':>7s} {'turn/mo':>8s} {'4-bar':>6s}")
    for bps in (0, 5, 10, 20):
        ret, turn = run_sleeve(labels, universe, r1m, bil_r1m, sig, bil_sig, TOP_N, bps / 10000)
        m = metrics(ret)
        yr = year_returns(ret)
        aa = m["cagr"] > m_spy["cagr"]
        bb = m["sharpe"] > 1.0
        cc = m["maxdd"] > -0.20
        dd = yr.get(2022, -1) > yr_spy.get(2022, -1)
        print(f"{bps:>9d}b {m['cagr']:8.2%} {m['vol']:7.2%} {m['sharpe']:7.2f} "
              f"{m['sortino']:8.2f} {m['maxdd']:8.2%} {yr.get(2022, float('nan')):8.2%} "
              f"{m['final']:6.2f}x {turn:8.1%} {sum([aa,bb,cc,dd])}/4")

    print("\nSURVIVORSHIP-BIAS CAVEAT (carried forward from R26, unresolved): universe = "
          "today's 40 mega-caps backfilled to 2016. Any pass here confirms the config is "
          "stable/non-fluke, NOT that it is adoptable live.")


if __name__ == "__main__":
    main()
