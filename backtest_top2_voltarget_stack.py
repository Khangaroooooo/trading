"""Experiment R15 — Stack R10/V2 vol-target scaling on R8's top-2 concentration
(see Evervault research/finance/backtests/results/r15-top2-voltarget-stack.md
for full locked spec — written and committed before this script was run).

R8 confirmed top-2-of-11-sector concentration beats top-3 (R1/R3) and SPY on raw
CAGR. R10 separately adopted SPY-vol-target-@15% scaling (capped 1.0x, unlevered)
on the top-3 book. Neither has been tested combined. Two pre-declared variants:
  V0 Baseline           — top-2 base signal, no overlay (reproduces R8 @5bps).
  V1 Top-2 + vol-target — R8's base weights scaled by R10/V2's exact overlay
                          mechanic (min(1, 15%/trailing-20d SPY vol), capped 1.0).

Pure stdlib, reads the existing cached data/cache/closes.csv (same cache as
R1/R3/R5/R8/R10) — no new fetch, no installs.

Run: cd ~/Documents/trading && python3 backtest_top2_voltarget_stack.py
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
VOL_LOOKBACK_D = 20
VOL_TARGET = 0.15
CACHE = os.path.join(os.path.dirname(__file__) or ".", "data", "cache", "closes.csv")

VARIANTS = [
    ("V0 Baseline (=R8 @5bps)", False),
    ("V1 Top-2 + SPY vol-target @15%", True),
]


def load_closes():
    if not os.path.exists(CACHE):
        raise SystemExit(f"Cache missing at {CACHE} — expected R1/R3/R5/R8/R10 cache to already "
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
    """Trailing annualized realized vol of daily returns, one value per day."""
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
    """R8's exact top-2 + absolute-momentum-vs-BIL logic for one rebalance date."""
    top = sorted(sig_t.items(), key=lambda kv: -kv[1])[:top_n]
    w = {}
    for sym, val in top:
        tgt = sym if (bil_t is not None and val > bil_t) else "BIL"
        w[tgt] = w.get(tgt, 0) + 1 / top_n
    return w


def blend(w, scale):
    """Scale rotation weights by `scale`, remainder parked in BIL (R10 mechanic)."""
    out = {s: wt * scale for s, wt in w.items()}
    out["BIL"] = out.get("BIL", 0) + (1 - scale)
    return out


def run_variant(use_overlay, labels, day_index, r1m, sig, spy_vol20):
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

        if not use_overlay:
            w = w_base
        else:
            di = day_index[t]
            v = spy_vol20[di]
            if v is None or v == 0:
                w = w_base
            else:
                s = min(1.0, VOL_TARGET / v)
                w = blend(w_base, s)

        traded = sum(abs(w.get(s, 0) - prev.get(s, 0)) for s in (set(w) | set(prev)))
        cost = traded * COST_PER_SIDE
        gross = 0.0
        for s, wt in w.items():
            rv = r1m[s][i + 1]
            gross += wt * (rv if rv is not None else 0.0)
        port_ret.append((t1, gross - cost, traded))
        prev = w
    return port_ret


def metrics(returns_by_date, periods_per_year=12):
    rets = [r for _, r, _ in returns_by_date]
    turns = [tr for _, _, tr in returns_by_date]
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
                final=eq[-1], n=n, dates=[d for d, _, _ in returns_by_date], eq=eq,
                avg_turnover=statistics.mean(turns))


def year_returns(returns_by_date):
    by_year = {}
    for d, r, _ in returns_by_date:
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

    rows = []
    for label, use_overlay in VARIANTS:
        port_ret = run_variant(use_overlay, labels, day_index, r1m, sig, spy_vol20)
        spy_ret = [(t1, r1m["SPY"][labels.index(t1)], 0.0) for t1, _, _ in port_ret]
        m_rot = metrics(port_ret)
        m_spy = metrics(spy_ret)
        yr_rot = year_returns(port_ret)
        yr_spy = year_returns(spy_ret)
        rows.append((label, m_rot, m_spy, yr_rot, yr_spy))

    print(f"\n{'Variant':32s} {'CAGR':>8s} {'Vol':>8s} {'Sharpe':>7s} {'Sortino':>8s} "
          f"{'maxDD':>8s} {'$1->':>8s} {'AvgTurn':>8s}   [SPY same-window CAGR / maxDD]  window")
    for label, m_rot, m_spy, _, _ in rows:
        print(f"{label:32s} {m_rot['cagr']:8.2%} {m_rot['vol']:8.2%} {m_rot['sharpe']:7.2f} "
              f"{m_rot['sortino']:8.2f} {m_rot['maxdd']:8.2%} {m_rot['final']:7.2f}x "
              f"{m_rot['avg_turnover']:8.2%}   [{m_spy['cagr']:.2%} / {m_spy['maxdd']:.2%}]  "
              f"n={m_rot['n']}  {m_rot['dates'][0]}->{m_rot['dates'][-1]}")

    print("\n2022 return (variant vs SPY, same window), maxDD-beats-SPY, and vs-V0 deltas:")
    v0_cagr = rows[0][1]["cagr"]
    v0_sortino = rows[0][1]["sortino"]
    v0_maxdd = rows[0][1]["maxdd"]
    for label, m_rot, m_spy, yr_rot, yr_spy in rows:
        y22r, y22s = yr_rot.get(2022), yr_spy.get(2022)
        beats_2022 = "n/a" if y22r is None else ("YES" if y22r > y22s else "no")
        beats_dd = "YES" if m_rot["maxdd"] > m_spy["maxdd"] else "no"
        y22r_s = f"{y22r:.2%}" if y22r is not None else "n/a"
        y22s_s = f"{y22s:.2%}" if y22s is not None else "n/a"
        print(f"  {label:32s} 2022 rot {y22r_s:>8s} vs SPY {y22s_s:>8s}  beats_2022={beats_2022:>3s}   "
              f"maxDD rot {m_rot['maxdd']:7.2%} vs SPY {m_spy['maxdd']:7.2%}  beats_maxDD={beats_dd}   "
              f"vs V0: CAGR{m_rot['cagr'] - v0_cagr:+.2%} Sortino{m_rot['sortino'] - v0_sortino:+.2f} "
              f"maxDD{m_rot['maxdd'] - v0_maxdd:+.2%}")

    print("\nPer-year returns (variant | SPY same window):")
    for label, m_rot, m_spy, yr_rot, yr_spy in rows:
        print(f"  {label}:")
        for y in sorted(yr_rot.keys()):
            print(f"    {y}: rot {yr_rot[y]:7.2%}   spy {yr_spy[y]:7.2%}")


if __name__ == "__main__":
    main()
