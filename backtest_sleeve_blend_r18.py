"""Experiment #18 (R18) — Fixed-weight blend: R10/V2 vol-target rotation sleeve + SPY B&H.

Rules (locked before running; see Evervault
research/finance/backtests/results/r18-sleeve-blend-voltarget-spy.md for full spec).

Sleeve A = R10/V2 exact spec (11 SPDR sectors, top-3 abs-momentum vs BIL, SPY-vol-target
@15%, monthly rebal, 5bps/side). Sleeve B = SPY B&H, same monthly grid. Blended at fixed
weights w in {0, 25, 50, 75, 100}%, monthly rebalance back to target weight, with a
blend-level rebalancing cost (SPY-leg-only, 5bps/side) applied to the weight drift between
sleeves each month. Sleeve A's own internal trading costs are already embedded in its
monthly returns.

Pure stdlib, reads the existing cached data/cache/closes.csv (same cache as R1/R3/R5/R10/
R11/R16) -- no new fetch, no installs.

Run: cd ~/Documents/trading && python3 backtest_sleeve_blend_r18.py
"""
import csv
import os
import statistics
from datetime import date as Date

SECTORS = ["XLK", "XLF", "XLV", "XLE", "XLI", "XLP", "XLY", "XLU", "XLB", "XLRE", "XLC"]
ALL = SECTORS + ["SPY", "BIL"]
COST_PER_SIDE = 0.0005
TOP_N = 3
LOOKBACK_M = 12
VOL_LOOKBACK_D = 20
VOL_TARGET = 0.15  # R10/V2
CACHE = os.path.join(os.path.dirname(__file__) or ".", "data", "cache", "closes.csv")

BLEND_WEIGHTS = [0.0, 0.25, 0.50, 0.75, 1.00]


def load_closes():
    if not os.path.exists(CACHE):
        raise SystemExit(f"Cache missing at {CACHE} — expected R1/R3/R5/R10 cache to already "
                          "exist; not pulling new data for this experiment.")
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


def daily_series(dates, data, sym):
    return [data[d].get(sym) for d in dates]


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


def realized_vol_daily(vals, window):
    rets = pct_change(vals)
    n = len(vals)
    out = [None] * n
    for i in range(n):
        if i + 1 < window + 1:
            continue
        chunk = [r for r in rets[i + 1 - window:i + 1] if r is not None]
        if len(chunk) < window:
            continue
        out[i] = statistics.stdev(chunk) * (252 ** 0.5)
    return out


def base_weights(sig_t, bil_t, top_n):
    top = sorted(sig_t.items(), key=lambda kv: -kv[1])[:top_n]
    w = {}
    for sym, val in top:
        tgt = sym if (bil_t is not None and val > bil_t) else "BIL"
        w[tgt] = w.get(tgt, 0) + 1 / top_n
    return w


def blend_scale(w, scale):
    out = {s: wt * scale for s, wt in w.items()}
    out["BIL"] = out.get("BIL", 0) + (1 - scale)
    return out


def run_sleeve_a(labels, day_index, r1m, sig, spy_vol20):
    """R10/V2: SPY vol-target @15% on the top-3 abs-momentum rotation book."""
    start_i = LOOKBACK_M
    prev = {}
    port_ret = []
    for i in range(start_i, len(labels) - 1):
        t, t1 = labels[i], labels[i + 1]
        sig_t = {s: sig[s][i] for s in SECTORS if sig[s][i] is not None}
        if len(sig_t) < TOP_N:
            continue
        bil = sig["BIL"][i]
        w_base = base_weights(sig_t, bil, TOP_N)

        di = day_index[t]
        v = spy_vol20[di]
        if v is None or v == 0:
            w = w_base
        else:
            s = min(1.0, VOL_TARGET / v)
            w = blend_scale(w_base, s)

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
    day_index = {d: i for i, d in enumerate(dates)}

    spy_daily = daily_series(dates, data, "SPY")
    spy_vol20 = realized_vol_daily(spy_daily, VOL_LOOKBACK_D)

    labels, series = resample_month_end(dates, data, ALL)
    r1m = {s: pct_change(series[s]) for s in ALL}
    sig = {s: momentum_12m(series[s], LOOKBACK_M) for s in ALL}

    sleeve_a = run_sleeve_a(labels, day_index, r1m, sig, spy_vol20)
    sleeve_b = [(t1, r1m["SPY"][labels.index(t1)]) for t1, _ in sleeve_a]

    m_a = metrics(sleeve_a)
    m_b = metrics(sleeve_b)
    print(f"\nSanity check — Sleeve A (R10/V2 reproduction): CAGR {m_a['cagr']:.2%} "
          f"Sortino {m_a['sortino']:.2f} maxDD {m_a['maxdd']:.2%}  "
          f"(R10/V2 published: CAGR 12.06%, Sortino 1.47, maxDD -14.27%)")
    print(f"Sanity check — Sleeve B (SPY B&H): CAGR {m_b['cagr']:.2%} "
          f"Sortino {m_b['sortino']:.2f} maxDD {m_b['maxdd']:.2%}")

    rows = []
    for w in BLEND_WEIGHTS:
        blend_ret = run_blend(sleeve_a, sleeve_b, w)
        m = metrics(blend_ret)
        yr = year_returns(blend_ret)
        rows.append((w, m, yr))

    yr_spy = year_returns(sleeve_b)

    print(f"\n{'w(rot)':>7s} {'CAGR':>8s} {'Vol':>8s} {'Sharpe':>7s} {'Sortino':>8s} "
          f"{'maxDD':>8s} {'$1->':>8s}   n / window")
    for w, m, yr in rows:
        print(f"{w:6.0%} {m['cagr']:8.2%} {m['vol']:8.2%} {m['sharpe']:7.2f} "
              f"{m['sortino']:8.2f} {m['maxdd']:8.2%} {m['final']:7.2f}x   "
              f"n={m['n']}  {m['dates'][0]}->{m['dates'][-1]}")

    print(f"\n[SPY same-window] CAGR {m_b['cagr']:.2%}  Sharpe {m_b['sharpe']:.2f}  "
          f"Sortino {m_b['sortino']:.2f}  maxDD {m_b['maxdd']:.2%}")

    print("\nPre-declared bars vs SPY (Sharpe>=, Sortino>=, maxDD shallower, CAGR within 1.5pt):")
    for w, m, yr in rows:
        bar_sharpe = m["sharpe"] >= m_b["sharpe"]
        bar_sortino = m["sortino"] >= m_b["sortino"]
        bar_maxdd = m["maxdd"] > m_b["maxdd"]
        bar_cagr = abs(m["cagr"] - m_b["cagr"]) <= 0.015
        n_clear = sum([bar_sharpe, bar_sortino, bar_maxdd, bar_cagr])
        print(f"  w={w:.0%}: Sharpe={'Y' if bar_sharpe else 'n'} Sortino={'Y' if bar_sortino else 'n'} "
              f"maxDD={'Y' if bar_maxdd else 'n'} CAGR-within-1.5pt={'Y' if bar_cagr else 'n'}  "
              f"({n_clear}/4)  CAGRdelta={m['cagr']-m_b['cagr']:+.2%}")

    print("\n2022 return (blend vs SPY, same window):")
    for w, m, yr in rows:
        y22, y22s = yr.get(2022), yr_spy.get(2022)
        y22_s = f"{y22:.2%}" if y22 is not None else "n/a"
        y22s_s = f"{y22s:.2%}" if y22s is not None else "n/a"
        beats = "n/a" if y22 is None else ("YES" if y22 > y22s else "no")
        print(f"  w={w:.0%}: blend {y22_s:>8s} vs SPY {y22s_s:>8s}  beats_2022={beats}")

    print("\nPer-year returns (blend | SPY same window):")
    for w, m, yr in rows:
        print(f"  w={w:.0%}:")
        for y in sorted(yr.keys()):
            print(f"    {y}: blend {yr[y]:7.2%}   spy {yr_spy[y]:7.2%}")


if __name__ == "__main__":
    main()
