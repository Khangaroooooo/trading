"""Experiment R26 — Monthly single-stock momentum + SPY blend (higher-return universe).

Locked spec (written before running; mirrors the adopted R20/R8 methodology exactly,
only the universe changes from 11 SPDR sectors to 40 mega-cap single stocks).

Hypothesis: the proven monthly top-N relative-momentum + per-slot abs-momentum(vs BIL)
+ SPY-blend machinery, applied to a HIGHER-RETURN single-stock universe, captures more
CAGR than the sector version while monthly cadence avoids the daily-turnover death that
killed R6/R12/R17 (those were reversal + daily; this is momentum + monthly).

Universe: 40 mega-caps from data/cache/closes_stocks40_daily.csv (dividend-adjusted,
adjustment="all", 2016-01-04+). Cash proxy BIL pulled from data/cache/closes.csv (same
adjustment, same window). SPY present in both.

Primary config (pre-declared): TOP_N=3, monthly, 5bps/side, abs-momentum filter vs BIL.
Grid over N in {2,3,5} and blend w in {0.50,0.75,1.00} reported as EXPLORATORY CONTEXT,
explicitly NOT used to select a winner.

Promotion bars (pre-declared, from the project charter), evaluated at 5bps/side:
  (a) beat SPY CAGR
  (b) Sharpe > 1
  (c) maxDD shallower than -20%
  (d) beat SPY 2022 calendar return (defensive check)
A backtest pass makes this a CANDIDATE only. Charter still requires >=3 months and
>=30 trades of PAPER forward-testing before any live adoption.

KNOWN LIMITATION (flagged up front, not discovered after): the 40-name universe is
TODAY's mega-caps backfilled to 2016 -> survivorship bias. These are the survivors/
winners; delisted or faded names are absent. This inflates single-stock backtest returns
in a way the sector-ETF version does NOT suffer. Any CAGR edge here must be read against
that bias. Reported, not hidden.

Pure stdlib, no installs, no new network fetch (both caches already exist).
Run: cd ~/Documents/trading && python3 backtest_single_stock_momentum_r26.py
"""
import csv
import os
import statistics
from datetime import date as Date

HERE = os.path.dirname(__file__) or "."
STOCK_CACHE = os.path.join(HERE, "data", "cache", "closes_stocks40_daily.csv")
BIL_CACHE = os.path.join(HERE, "data", "cache", "closes.csv")
COST_PER_SIDE = 0.0005
LOOKBACK_M = 12


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
        buckets[(d.year, d.month)] = d  # last date seen in each month
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


def run_sleeve(labels, universe, r1m, sig, bil_sig, top_n):
    """Top-N abs-momentum single-stock rotation book. Returns (date, net_ret) per month
    and the average two-way turnover."""
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
        cost = traded * COST_PER_SIDE
        gross = 0.0
        for s, wt in w.items():
            rv = r1m[s][i + 1] if s != "BIL" else bil_r1m[i + 1]
            gross += wt * (rv if rv is not None else 0.0)
        port_ret.append((t1, gross - cost))
        prev = w
    avg_turn = statistics.mean(turnovers) if turnovers else 0.0
    return port_ret, avg_turn


def run_blend(sleeve_a_ret, sleeve_b_ret, w):
    assert [d for d, _ in sleeve_a_ret] == [d for d, _ in sleeve_b_ret]
    out = []
    for (t, ra), (_, rb) in zip(sleeve_a_ret, sleeve_b_ret):
        gross = w * ra + (1 - w) * rb
        wa_post = (w * (1 + ra)) / (w * (1 + ra) + (1 - w) * (1 + rb))
        drift = abs(wa_post - w)
        rebal_cost = drift * 2 * COST_PER_SIDE
        out.append((t, gross - rebal_cost))
    return out


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
    global bil_r1m
    sdates, sdata, scols = load_cache(STOCK_CACHE)
    bdates, bdata, bcols = load_cache(BIL_CACHE)

    universe = [c for c in scols if c != "SPY"]

    # Align on the stock cache's month-end labels; pull BIL from the sector cache by date.
    labels, series = resample_month_end(sdates, sdata, scols)
    # BIL month-end series on the SAME labels:
    bil_series = []
    for d in labels:
        # nearest available BIL close on/just before this label date
        v = bdata.get(d, {}).get("BIL")
        if v is None:
            # fall back to the last available bdate <= d
            prior = [bd for bd in bdates if bd <= d]
            v = bdata[prior[-1]]["BIL"] if prior else None
        bil_series.append(v)

    r1m = {s: pct_change(series[s]) for s in scols}
    bil_r1m = pct_change(bil_series)
    sig = {s: momentum_12m(series[s], LOOKBACK_M) for s in scols}
    bil_sig = momentum_12m(bil_series, LOOKBACK_M)

    # SPY sleeve aligned to whatever the primary sleeve produces
    def spy_sleeve(ref_ret):
        return [(t1, r1m["SPY"][labels.index(t1)]) for t1, _ in ref_ret]

    print("=" * 78)
    print("R26 — Monthly single-stock momentum (40 mega-caps) + SPY blend")
    print("=" * 78)

    # SPY benchmark (built off primary top-3 dates)
    primary_sleeve, primary_turn = run_sleeve(labels, universe, r1m, sig, bil_sig, 3)
    spy = spy_sleeve(primary_sleeve)
    m_spy = metrics(spy)
    yr_spy = year_returns(spy)
    print(f"\n[SPY B&H same window]  CAGR {m_spy['cagr']:.2%}  Sharpe {m_spy['sharpe']:.2f}  "
          f"Sortino {m_spy['sortino']:.2f}  maxDD {m_spy['maxdd']:.2%}  "
          f"2022 {yr_spy.get(2022, float('nan')):.2%}  n={m_spy['n']}")
    print(f"Window: {m_spy['dates'][0]} -> {m_spy['dates'][-1]}")

    print(f"\n{'config':>22s} {'CAGR':>8s} {'Vol':>7s} {'Sharpe':>7s} {'Sortino':>8s} "
          f"{'maxDD':>8s} {'2022':>8s} {'$1->':>7s} {'turn/mo':>8s}")

    grid = []
    for n in (2, 3, 5):
        sleeve, turn = run_sleeve(labels, universe, r1m, sig, bil_sig, n)
        spy_n = spy_sleeve(sleeve)
        for w in (1.00, 0.75, 0.50):
            if w == 1.00:
                ret = sleeve
            else:
                ret = run_blend(sleeve, spy_n, w)
            m = metrics(ret)
            yr = year_returns(ret)
            tag = f"top{n} w={w:.0%}"
            grid.append((n, w, m, yr, turn))
            print(f"{tag:>22s} {m['cagr']:8.2%} {m['vol']:7.2%} {m['sharpe']:7.2f} "
                  f"{m['sortino']:8.2f} {m['maxdd']:8.2%} {yr.get(2022, float('nan')):8.2%} "
                  f"{m['final']:6.2f}x {turn:8.1%}")

    # ---- Pre-declared promotion bars, PRIMARY config only (top-3, standalone sleeve, 5bps) ----
    prim = next(g for g in grid if g[0] == 3 and abs(g[1] - 1.00) < 1e-9)
    _, _, mp, yrp, _ = prim
    print("\n" + "-" * 78)
    print("PROMOTION BARS — primary config = top-3, w=100% (standalone sleeve), 5bps/side")
    print("-" * 78)
    a = mp["cagr"] > m_spy["cagr"]
    b = mp["sharpe"] > 1.0
    c = mp["maxdd"] > -0.20
    d = yrp.get(2022, -1) > yr_spy.get(2022, -1)
    print(f"  (a) beat SPY CAGR:        {'PASS' if a else 'FAIL'}  ({mp['cagr']:.2%} vs {m_spy['cagr']:.2%})")
    print(f"  (b) Sharpe > 1:           {'PASS' if b else 'FAIL'}  ({mp['sharpe']:.2f})")
    print(f"  (c) maxDD shallower -20%: {'PASS' if c else 'FAIL'}  ({mp['maxdd']:.2%})")
    print(f"  (d) beat SPY 2022:        {'PASS' if d else 'FAIL'}  ({yrp.get(2022, float('nan')):.2%} vs {yr_spy.get(2022, float('nan')):.2%})")
    print(f"\n  => {sum([a,b,c,d])}/4 bars cleared. "
          f"{'CANDIDATE (still needs paper forward-test).' if sum([a,b,c,d])==4 else 'Does not clear all bars.'}")

    # Also show the blended w=75% primary (matches the adopted live config's blend weight)
    prim75 = next(g for g in grid if g[0] == 3 and abs(g[1] - 0.75) < 1e-9)
    _, _, m75, yr75, _ = prim75
    print(f"\n  [context] top-3 blended w=75% (live blend weight): CAGR {m75['cagr']:.2%} "
          f"Sharpe {m75['sharpe']:.2f} maxDD {m75['maxdd']:.2%} 2022 {yr75.get(2022, float('nan')):.2%}")

    print("\nSURVIVORSHIP-BIAS CAVEAT: universe = today's 40 mega-caps backfilled to 2016. "
          "Any single-stock CAGR edge is inflated by this bias; the sector-ETF R20 result is not.")


if __name__ == "__main__":
    bil_r1m = []
    main()
