"""Experiment #5 (R5) — Regime filter overlay on the R1 dual-momentum rotation.

Rules (locked before running; see Evervault
research/finance/backtests/results/r5-regime-filter-on-rotation.md for full spec).

Base signal is UNCHANGED from R1: 11 SPDR sectors, month-end 12m-total-return
ranking, top-3 equal-weight, absolute-momentum filter vs BIL. Four pre-declared
overlay variants on top of that exact signal:
  V0 Baseline        — no overlay (should reproduce R1/R3-V0 numbers).
  V1 200dma gate      — SPY close < trailing 200-trading-day SMA => 100% BIL
                        that month; else normal R1 weights.
  V2 Vol-target scale — scale R1 weights by min(1, 12%/trailing-20d-SPY-vol),
                        remainder to BIL. No leverage (cap at 1.0).
  V3 Combined         — V1 gate first, then V2 scaling if not gated.

Pure stdlib, reads the existing cached data/cache/closes.csv (same cache as
R1/R3) — no new fetch, no installs.

Run: cd ~/Documents/trading && python3 backtest_regime_filter.py
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
VOL_TARGET = 0.12
SMA_LOOKBACK_D = 200
CACHE = os.path.join(os.path.dirname(__file__) or ".", "data", "cache", "closes.csv")

VARIANTS = ["V0 Baseline (=R1)", "V1 200dma gate", "V2 Vol-target scale", "V3 Combined"]


def load_closes():
    if not os.path.exists(CACHE):
        raise SystemExit(f"Cache missing at {CACHE} — expected R1/R3 cache to already exist; "
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


def sma_daily(vals, window):
    """Trailing simple moving average, one value per day (None until warmed up)."""
    n = len(vals)
    out = [None] * n
    for i in range(n):
        if i + 1 < window:
            continue
        chunk = vals[i + 1 - window:i + 1]
        if any(v is None for v in chunk):
            continue
        out[i] = sum(chunk) / window
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
    """R1's exact top-N + absolute-momentum-vs-BIL logic for one rebalance date."""
    top = sorted(sig_t.items(), key=lambda kv: -kv[1])[:top_n]
    w = {}
    for sym, val in top:
        tgt = sym if (bil_t is not None and val > bil_t) else "BIL"
        w[tgt] = w.get(tgt, 0) + 1 / top_n
    return w


def blend(w, scale):
    """Scale rotation weights by `scale`, remainder parked in BIL."""
    out = {s: wt * scale for s, wt in w.items()}
    out["BIL"] = out.get("BIL", 0) + (1 - scale)
    return out


def run_variant(variant, labels, day_index, r1m, sig, spy_gate, spy_scale):
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
        if variant == "V0 Baseline (=R1)":
            w = w_base
        elif variant == "V1 200dma gate":
            gated_off = spy_gate[di] is False
            w = {"BIL": 1.0} if gated_off else w_base
        elif variant == "V2 Vol-target scale":
            s = spy_scale[di]
            w = w_base if s is None else blend(w_base, s)
        elif variant == "V3 Combined":
            gated_off = spy_gate[di] is False
            if gated_off:
                w = {"BIL": 1.0}
            else:
                s = spy_scale[di]
                w = w_base if s is None else blend(w_base, s)
        else:
            raise ValueError(variant)

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
    dates = [d for d, _, _ in returns_by_date]
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
                final=eq[-1], n=n, dates=dates, eq=eq, avg_turnover=statistics.mean(turns))


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

    spy_daily = daily_series(dates, data, "SPY")
    spy_sma200 = sma_daily(spy_daily, SMA_LOOKBACK_D)
    spy_gate = [None if (p is None or s is None) else (p >= s)
                for p, s in zip(spy_daily, spy_sma200)]  # True = risk-on
    spy_vol20 = realized_vol_daily(spy_daily, VOL_LOOKBACK_D)
    spy_scale = [None if v is None or v == 0 else min(1.0, VOL_TARGET / v) for v in spy_vol20]
    day_index = {d: i for i, d in enumerate(dates)}

    labels, series = resample_month_end(dates, data, ALL)
    r1m = {s: pct_change(series[s]) for s in ALL}
    sig = {s: momentum_12m(series[s], LOOKBACK_M) for s in ALL}

    rows = []
    for v in VARIANTS:
        port_ret = run_variant(v, labels, day_index, r1m, sig, spy_gate, spy_scale)
        spy_ret = [(t1, r1m["SPY"][labels.index(t1)], 0.0) for t1, _, _ in port_ret]
        m_rot = metrics(port_ret)
        m_spy = metrics(spy_ret)
        yr_rot = year_returns(port_ret)
        yr_spy = year_returns(spy_ret)
        rows.append((v, m_rot, m_spy, yr_rot, yr_spy))

    print(f"\n{'Variant':22s} {'CAGR':>8s} {'Vol':>8s} {'Sharpe':>7s} {'Sortino':>8s} "
          f"{'maxDD':>8s} {'$1->':>8s} {'AvgTurn':>8s}   [SPY same-window CAGR / maxDD]  window")
    for label, m_rot, m_spy, _, _ in rows:
        print(f"{label:22s} {m_rot['cagr']:8.2%} {m_rot['vol']:8.2%} {m_rot['sharpe']:7.2f} "
              f"{m_rot['sortino']:8.2f} {m_rot['maxdd']:8.2%} {m_rot['final']:7.2f}x "
              f"{m_rot['avg_turnover']:8.2%}   [{m_spy['cagr']:.2%} / {m_spy['maxdd']:.2%}]  "
              f"n={m_rot['n']}  {m_rot['dates'][0]}->{m_rot['dates'][-1]}")

    print("\n2022 return (variant vs SPY, same window) and maxDD-beats-SPY check:")
    for label, m_rot, m_spy, yr_rot, yr_spy in rows:
        y22r, y22s = yr_rot.get(2022), yr_spy.get(2022)
        beats_2022 = "n/a" if y22r is None else ("YES" if y22r > y22s else "no")
        beats_dd = "YES" if m_rot["maxdd"] > m_spy["maxdd"] else "no"
        y22r_s = f"{y22r:.2%}" if y22r is not None else "n/a"
        y22s_s = f"{y22s:.2%}" if y22s is not None else "n/a"
        print(f"  {label:22s} 2022 rot {y22r_s:>8s} vs SPY {y22s_s:>8s}  beats_2022={beats_2022:>3s}   "
              f"maxDD rot {m_rot['maxdd']:7.2%} vs SPY {m_spy['maxdd']:7.2%}  beats_maxDD={beats_dd}   "
              f"vs V0 Sortino delta={m_rot['sortino'] - rows[0][1]['sortino']:+.2f}")

    print("\nPer-year returns (variant | SPY same window):")
    for label, m_rot, m_spy, yr_rot, yr_spy in rows:
        print(f"  {label}:")
        for y in sorted(yr_rot.keys()):
            print(f"    {y}: rot {yr_rot[y]:7.2%}   spy {yr_spy[y]:7.2%}")


if __name__ == "__main__":
    main()
