"""Experiment R17 — Single-stock reversal cadence sweep: biweekly & monthly (locked rules,
see Evervault research/finance/backtests/results/r17-reversal-cadence-sweep.md).

R6 (daily, 15-name, N=3) found a real gross reversal signal destroyed by turnover cost.
R12/V1 (weekly, same universe) cut turnover in half and flipped net CAGR positive but still
missed SPY on every metric and lost more than SPY in 2022. This adds two more pre-declared
cadence points (biweekly, monthly) on the same universe/signal/costs to see whether the
degradation from daily->weekly->biweekly->monthly is monotonic or has a local sweet spot.

Reuses R12's cached 15-name data (data/cache/closes_stocks_daily.csv), no new fetch needed.

Run: cd ~/Documents/trading && python3 backtest_reversal_r17.py
"""
import csv
import os
import statistics
from datetime import date as Date

UNIVERSE_15 = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "JPM", "V",
               "JNJ", "PG", "HD", "XOM", "UNH", "KO", "DIS"]
BENCH = "SPY"
COST_PER_SIDE = 0.0015
TOP_N = 3
CRASH_FILTER = -0.03
CACHE_15 = os.path.join(os.path.dirname(__file__) or ".", "data", "cache", "closes_stocks_daily.csv")


def _read_cache(cache_path, all_syms):
    with open(cache_path, newline="") as f:
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


def metrics(returns_by_date, periods_per_year):
    rets = [r for _, r in returns_by_date]
    eq = []
    acc = 1.0
    for r in rets:
        acc *= (1 + r)
        eq.append(acc)
    n = len(rets)
    years = n / periods_per_year
    cagr = eq[-1] ** (1 / years) - 1 if years > 0 else float("nan")
    vol = statistics.stdev(rets) * (periods_per_year ** 0.5) if n > 1 else float("nan")
    mean = statistics.mean(rets)
    sharpe = (mean * periods_per_year) / vol if vol and vol > 0 else float("nan")
    neg = [r for r in rets if r < 0]
    downside = statistics.stdev(neg) * (periods_per_year ** 0.5) if len(neg) > 1 else float("nan")
    sortino = (mean * periods_per_year) / downside if downside else float("nan")
    running_max = -float("inf")
    maxdd = 0.0
    for e in eq:
        running_max = max(running_max, e)
        dd = e / running_max - 1
        maxdd = min(maxdd, dd)
    return dict(cagr=cagr, vol=vol, sharpe=sharpe, sortino=sortino, maxdd=maxdd, final=eq[-1], n=n)


def print_table(title, rows):
    print(f"\n=== {title} ===")
    hdr = f"{'':<20}{'CAGR':>8}{'Vol':>8}{'Sharpe':>8}{'Sortino':>9}{'maxDD':>9}{'$1->':>8}"
    print(hdr)
    for name, m in rows:
        print(f"{name:<20}{m['cagr']*100:>7.1f}%{m['vol']*100:>7.1f}%{m['sharpe']:>8.2f}"
              f"{m['sortino']:>9.2f}{m['maxdd']*100:>8.1f}%{m['final']:>7.2f}")


def per_year_table(strat_series, bench_series, label):
    by_year_s, by_year_b = {}, {}
    for d, r in strat_series:
        by_year_s.setdefault(d.year, []).append(r)
    for d, r in bench_series:
        by_year_b.setdefault(d.year, []).append(r)
    print(f"\nPer-year net returns ({label} | SPY same window):")
    for y in sorted(by_year_s.keys()):
        acc_s, acc_b = 1.0, 1.0
        for r in by_year_s[y]:
            acc_s *= (1 + r)
        for r in by_year_b.get(y, []):
            acc_b *= (1 + r)
        print(f"  {y}: {label} {acc_s-1:7.2%}   spy {acc_b-1:7.2%}")


def build_biweekly_index(dates):
    """Bucket dates into consecutive non-overlapping 2-ISO-week blocks; return last trading
    day index of each block."""
    week_of = [d.isocalendar()[:2] for d in dates]
    block_end_idx = []
    block_id = None
    for i in range(len(dates)):
        y, w = week_of[i]
        this_block = (y, (w - 1) // 2)
        if block_id is None:
            block_id = this_block
        elif this_block != block_id:
            block_end_idx.append(i - 1)
            block_id = this_block
    block_end_idx.append(len(dates) - 1)
    return block_end_idx


def build_monthly_index(dates):
    """Return last trading day index of each calendar month."""
    month_of = [(d.year, d.month) for d in dates]
    month_end_idx = []
    for i in range(len(dates)):
        if i == len(dates) - 1 or month_of[i] != month_of[i + 1]:
            month_end_idx.append(i)
    return month_end_idx


def run_periodic(dates, data, universe, top_n, period_end_idx, periods_per_year, label):
    """Generic periodic reversal: signal = prior-period close-to-close return, hold following
    period. period_end_idx = sorted list of trading-day indices marking each period's end."""
    all_syms = universe + [BENCH]
    closes = {s: [data[dates[i]].get(s) for i in range(len(dates))] for s in all_syms}

    period_ret = {s: [] for s in all_syms}
    for s in all_syms:
        prev_close = None
        for idx in period_end_idx:
            c = closes[s][idx]
            if prev_close is not None and c is not None and prev_close != 0:
                period_ret[s].append(c / prev_close - 1)
            else:
                period_ret[s].append(None)
            if c is not None:
                prev_close = c

    net_series, gross_series, bench_series = [], [], []
    prev_w = {}
    turnover_total = 0.0
    periods_in = 0
    n_periods = len(period_end_idx)
    for pi in range(1, n_periods - 1):
        signal = {s: period_ret[s][pi] for s in universe if period_ret[s][pi] is not None}
        fwd = {s: period_ret[s][pi + 1] for s in universe}
        spy_prev = period_ret[BENCH][pi]
        w = {}
        if spy_prev is not None and spy_prev >= CRASH_FILTER and len(signal) >= top_n:
            picks = sorted(signal.items(), key=lambda kv: kv[1])[:top_n]
            for sym, _ in picks:
                w[sym] = 1.0 / top_n
            periods_in += 1
        traded = sum(abs(w.get(s, 0) - prev_w.get(s, 0)) for s in (set(w) | set(prev_w)))
        turnover_total += traded
        cost = traded * COST_PER_SIDE
        gross = sum(wt * (fwd.get(s) if fwd.get(s) is not None else 0.0) for s, wt in w.items())
        end_date = dates[period_end_idx[pi + 1]]
        net_series.append((end_date, gross - cost))
        gross_series.append((end_date, gross))
        spy_fwd = period_ret[BENCH][pi + 1]
        bench_series.append((end_date, spy_fwd if spy_fwd is not None else 0.0))
        prev_w = w

    m_net = metrics(net_series, periods_per_year)
    m_gross = metrics(gross_series, periods_per_year)
    m_bench = metrics(bench_series, periods_per_year)
    avg_to = turnover_total / max(1, len(net_series))
    print(f"Window: {net_series[0][0]} -> {net_series[-1][0]}  "
          f"({m_net['n']} periods, {periods_in} invested of {n_periods})")
    print(f"Avg turnover/period: {avg_to:.3f}  (annualized ~{avg_to*periods_per_year:.0f}x)")
    print_table(f"{label}: Reversal vs SPY", [
        ("Reversal (net)", m_net),
        ("Reversal (gross)", m_gross),
        ("SPY B&H", m_bench),
    ])
    per_year_table(net_series, bench_series, label)
    return m_net, m_gross, m_bench, avg_to


def main():
    print("Loading cached 15-name daily closes (reused from R6/R12)...")
    all_syms = UNIVERSE_15 + [BENCH]
    dates, data = _read_cache(CACHE_15, all_syms)
    print(f"  {len(dates)} trading days: {dates[0]} -> {dates[-1]}")

    print("\n\n=== R17 V1: biweekly rebalance, 15-name universe ===")
    biweekly_idx = build_biweekly_index(dates)
    run_periodic(dates, data, UNIVERSE_15, TOP_N, biweekly_idx, periods_per_year=26, label="V1 biweekly")

    print("\n\n=== R17 V2: monthly rebalance, 15-name universe ===")
    monthly_idx = build_monthly_index(dates)
    run_periodic(dates, data, UNIVERSE_15, TOP_N, monthly_idx, periods_per_year=12, label="V2 monthly")


if __name__ == "__main__":
    main()
