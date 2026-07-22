"""Experiment #11 (R11) — Confirmed 200dma gate (2-month persistence) on R1 rotation.

Rules (locked before running; see Evervault
research/finance/backtests/results/r11-regime-gate-confirmation.md for full spec).

Base signal is UNCHANGED from R1: 11 SPDR sectors, month-end 12m-total-return
ranking, top-3 equal-weight, absolute-momentum filter vs BIL. One pre-declared
overlay variant on top of that exact signal, plus a baseline sanity check:
  V0 Baseline          — no overlay (should reproduce R1/R3/R5-V0 numbers).
  V1 Confirmed 200dma  — same raw 200dma gate as R5/V1, but the effective
                         regime state only flips when the raw signal has
                         agreed for 2 consecutive month-ends; else it holds
                         the prior effective state (whipsaw-reduction rule).

Pure stdlib, reads the existing cached data/cache/closes.csv (same cache as
R1/R3/R5) — no new fetch, no installs.

Run: cd ~/Documents/trading && python3 backtest_regime_confirmation.py
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
SMA_LOOKBACK_D = 200
CONFIRM_MONTHS = 2
CACHE = os.path.join(os.path.dirname(__file__) or ".", "data", "cache", "closes.csv")

VARIANTS = ["V0 Baseline (=R1)", "V1 Confirmed 200dma gate"]


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


def base_weights(sig_t, bil_t, top_n):
    """R1's exact top-N + absolute-momentum-vs-BIL logic for one rebalance date."""
    top = sorted(sig_t.items(), key=lambda kv: -kv[1])[:top_n]
    w = {}
    for sym, val in top:
        tgt = sym if (bil_t is not None and val > bil_t) else "BIL"
        w[tgt] = w.get(tgt, 0) + 1 / top_n
    return w


def confirmed_gate_series(labels, day_index, spy_gate_raw_daily):
    """Month-end confirmed gate: flips only when raw agrees for CONFIRM_MONTHS
    consecutive month-end observations; else holds prior effective state."""
    raw_at_label = []
    for t in labels:
        di = day_index.get(t)
        raw_at_label.append(None if di is None else spy_gate_raw_daily[di])

    effective = [None] * len(labels)
    state = None
    run_val = None
    run_len = 0
    for i, raw in enumerate(raw_at_label):
        if raw is None:
            effective[i] = state
            continue
        if raw == run_val:
            run_len += 1
        else:
            run_val = raw
            run_len = 1
        if state is None:
            state = raw  # first valid observation seeds state directly
        elif run_len >= CONFIRM_MONTHS:
            state = run_val
        effective[i] = state
    return effective


def run_variant(variant, labels, day_index, r1m, sig, confirmed_gate):
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

        if variant == "V0 Baseline (=R1)":
            w = w_base
        elif variant == "V1 Confirmed 200dma gate":
            state = confirmed_gate[i]
            gated_off = state is False
            w = {"BIL": 1.0} if gated_off else w_base
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
    spy_gate_raw = [None if (p is None or s is None) else (p >= s)
                    for p, s in zip(spy_daily, spy_sma200)]  # True = risk-on
    day_index = {d: i for i, d in enumerate(dates)}

    labels, series = resample_month_end(dates, data, ALL)
    r1m = {s: pct_change(series[s]) for s in ALL}
    sig = {s: momentum_12m(series[s], LOOKBACK_M) for s in ALL}

    confirmed_gate = confirmed_gate_series(labels, day_index, spy_gate_raw)

    # Count how many months the confirmed gate actually flips vs raw gate,
    # for the whipsaw-reduction check.
    raw_at_label = [spy_gate_raw[day_index[t]] if day_index.get(t) is not None else None
                     for t in labels]
    raw_flips = sum(1 for i in range(1, len(raw_at_label))
                     if raw_at_label[i] is not None and raw_at_label[i - 1] is not None
                     and raw_at_label[i] != raw_at_label[i - 1])
    confirmed_flips = sum(1 for i in range(1, len(confirmed_gate))
                           if confirmed_gate[i] is not None and confirmed_gate[i - 1] is not None
                           and confirmed_gate[i] != confirmed_gate[i - 1])

    rows = []
    for v in VARIANTS:
        port_ret = run_variant(v, labels, day_index, r1m, sig, confirmed_gate)
        spy_ret = [(t1, r1m["SPY"][labels.index(t1)], 0.0) for t1, _, _ in port_ret]
        m_rot = metrics(port_ret)
        m_spy = metrics(spy_ret)
        yr_rot = year_returns(port_ret)
        yr_spy = year_returns(spy_ret)
        rows.append((v, m_rot, m_spy, yr_rot, yr_spy))

    print(f"\n{'Variant':26s} {'CAGR':>8s} {'Vol':>8s} {'Sharpe':>7s} {'Sortino':>8s} "
          f"{'maxDD':>8s} {'$1->':>8s} {'AvgTurn':>8s}   [SPY same-window CAGR / maxDD]  window")
    for label, m_rot, m_spy, _, _ in rows:
        print(f"{label:26s} {m_rot['cagr']:8.2%} {m_rot['vol']:8.2%} {m_rot['sharpe']:7.2f} "
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
        print(f"  {label:26s} 2022 rot {y22r_s:>8s} vs SPY {y22s_s:>8s}  beats_2022={beats_2022:>3s}   "
              f"maxDD rot {m_rot['maxdd']:7.2%} vs SPY {m_spy['maxdd']:7.2%}  beats_maxDD={beats_dd}   "
              f"vs V0 Sortino delta={m_rot['sortino'] - rows[0][1]['sortino']:+.2f}")

    print(f"\nRaw 200dma monthly flip count: {raw_flips}  |  Confirmed ({CONFIRM_MONTHS}mo) gate flip count: {confirmed_flips}")
    print("(R5/V1 raw-gate reference, 5bps/side, same window: CAGR 9.24%, Sortino 1.11, "
          "maxDD -16.20%, avg turnover 69.3%/mo)")

    print("\nPer-year returns (variant | SPY same window):")
    for label, m_rot, m_spy, yr_rot, yr_spy in rows:
        print(f"  {label}:")
        for y in sorted(yr_rot.keys()):
            print(f"    {y}: rot {yr_rot[y]:7.2%}   spy {yr_spy[y]:7.2%}")


if __name__ == "__main__":
    main()
