"""R14 Phase B — News-sentiment stand-aside overlay on a 15-name single-stock
buy-and-hold-ish base (locked rules; see Evervault
research/finance/backtests/results/r14-single-name-news-sentiment-overlay.md
for the full pre-declared spec).

Runs only if R14 Phase A (news_audit_r14.py) clears the corrected gate
(>=80% of the 15-name universe qualifies: >=4 headlines/mo avg, <25%
zero-coverage months).

Base: equal-weight (1/15) across all 15 names, recomputed at each month-end
rebalance (drift-correction only — no momentum/ranking signal, no name is
ever excluded from the base book).

Overlay (locked, identical mechanic + keyword lexicon to R4 Phase B): for
each currently-held name, count that day's headlines containing >=1 of the
fixed negative-keyword lexicon. If the trailing 3-trading-day sum of such
headline hits reaches >=2, stand aside that name's weight to CASH (0% daily
return, not BIL — avoids merging a second price series; locked as a mildly
pessimistic-for-the-overlay simplification) for the next 5 trading days,
then resume normal weight (or re-trigger if bad news continues). Stand-aside
state resets fresh at every month-end rebalance. Same lookahead-avoidance
convention as R4: trigger evaluated through day d, takes effect day d+1.

Costs: 10 bps/side (single-stock, per charter standing rule), applied to
both monthly drift-rebalance turnover and overlay-driven turnover.

Window: 2017-02 -> 2026-07-17 (matches R1/R4/R6 convention).

Pure stdlib, reuses cached data/cache/closes_stocks_daily.csv (R6/R12) and
R14 Phase A's cached data/cache/news_r14.jsonl — no new fetch, no installs.

Run: cd ~/Documents/trading && python3 backtest_news_overlay_r14.py
"""
import csv
import json
import os
import statistics
from collections import defaultdict
from datetime import date as Date, datetime

UNIVERSE = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "JPM", "V",
            "JNJ", "PG", "HD", "XOM", "UNH", "KO", "DIS"]
BENCH = "SPY"
ALL_SYMS = UNIVERSE + [BENCH]
COST_PER_SIDE = 0.0010   # 10 bps/side — single-stock, per charter standing rule
ROLL_WINDOW_D = 3
TRIGGER_COUNT = 2
STANDASIDE_D = 5
KEYWORDS = ["downgrade", "misses", "miss estimates", "cuts guidance", "lawsuit",
            "recall", "investigation", "fraud", "bankruptcy", "plunge", "warns",
            "disappointing", "layoffs", "resigns", "probe"]
WINDOW_START = Date(2017, 2, 1)

CLOSES_CACHE = os.path.join(os.path.dirname(__file__) or ".", "data", "cache", "closes_stocks_daily.csv")
NEWS_CACHE = os.path.join(os.path.dirname(__file__) or ".", "data", "cache", "news_r14.jsonl")

VARIANTS = ["V0 Baseline (equal-weight, no overlay)", "V1 News stand-aside overlay"]


def load_closes():
    if not os.path.exists(CLOSES_CACHE):
        raise SystemExit(f"Cache missing at {CLOSES_CACHE} — expected R6/R12 cache to already exist.")
    with open(CLOSES_CACHE, newline="") as f:
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


def load_news_hits():
    """{(symbol, date): count of that day's keyword-matching headlines}."""
    if not os.path.exists(NEWS_CACHE):
        raise SystemExit(f"News cache missing at {NEWS_CACHE} — run news_audit_r14.py (Phase A) first.")
    hits = defaultdict(int)
    total_headlines = 0
    matched_headlines = 0
    with open(NEWS_CACHE) as f:
        for line in f:
            it = json.loads(line)
            total_headlines += 1
            headline = (it.get("headline") or "").lower()
            if not any(kw in headline for kw in KEYWORDS):
                continue
            syms = [s for s in it.get("symbols", []) if s in UNIVERSE]
            if not syms:
                continue
            matched_headlines += 1
            try:
                d = datetime.strptime(it["created_at"], "%Y-%m-%dT%H:%M:%SZ").date()
            except ValueError:
                d = datetime.fromisoformat(it["created_at"].replace("Z", "+00:00")).date()
            for sym in syms:
                hits[(sym, d)] += 1
    print(f"News lexicon match: {matched_headlines}/{total_headlines} headlines matched "
          f"a keyword AND tagged a universe symbol.")
    return hits


def daily_series(dates, data, sym):
    return [data[d].get(sym) for d in dates]


def pct_change(vals):
    out = [None]
    for i in range(1, len(vals)):
        a, b = vals[i - 1], vals[i]
        out.append((b / a - 1) if (a is not None and b is not None and a != 0) else None)
    return out


def month_end_labels(dates):
    buckets = {}
    for d in dates:
        buckets[(d.year, d.month)] = d
    return [buckets[k] for k in sorted(buckets.keys())]


def run_variant(overlay_enabled, dates, day_index, daily_ret, labels, news_hits):
    port_ret = []
    prev_w = {}
    n_triggers = 0
    standaside_days_total = 0
    w_base = {s: 1 / len(UNIVERSE) for s in UNIVERSE}

    start_li = next(i for i, d in enumerate(labels) if d >= WINDOW_START)

    for i in range(start_li, len(labels) - 1):
        t, t1 = labels[i], labels[i + 1]
        standaside_remaining = {s: 0 for s in UNIVERSE}
        roll_hits = {s: [] for s in UNIVERSE}

        start_di, end_di = day_index[t], day_index[t1]
        for di in range(start_di + 1, end_di + 1):
            d = dates[di]

            # Step 1: decide today's weight from state carried in from before today.
            w_today = {}
            freed = 0.0
            for s, wt in w_base.items():
                if standaside_remaining.get(s, 0) > 0:
                    freed += wt
                    standaside_days_total += 1
                else:
                    w_today[s] = wt
            # freed capital sits in cash (0% return) — not tracked as a symbol,
            # simply omitted from w_today so it earns 0 for the day.

            # Step 2: today consumes one day of any active stand-aside.
            for s in standaside_remaining:
                if standaside_remaining[s] > 0:
                    standaside_remaining[s] -= 1

            # Step 3: fold in today's news, check for a (re-)trigger for tomorrow+.
            if overlay_enabled:
                for s in UNIVERSE:
                    hit = news_hits.get((s, d), 0)
                    roll_hits[s].append(hit)
                    if len(roll_hits[s]) > ROLL_WINDOW_D:
                        roll_hits[s].pop(0)
                    if standaside_remaining[s] == 0 and sum(roll_hits[s]) >= TRIGGER_COUNT:
                        standaside_remaining[s] = STANDASIDE_D
                        n_triggers += 1

            traded = sum(abs(w_today.get(s, 0) - prev_w.get(s, 0))
                         for s in (set(w_today) | set(prev_w)))
            cost = traded * COST_PER_SIDE
            gross = 0.0
            for s, wt in w_today.items():
                rv = daily_ret[s][di]
                gross += wt * (rv if rv is not None else 0.0)
            port_ret.append((d, gross - cost, traded))
            prev_w = w_today

    return port_ret, n_triggers, standaside_days_total


def metrics(returns_by_date, periods_per_year=252):
    rets = [r for _, r, _ in returns_by_date]
    dates = [d for d, _, _ in returns_by_date]
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
    sharpe = (mean * periods_per_year) / vol if vol > 0 else float("nan")
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
                final=eq[-1], n=n, dates=dates, avg_turnover=statistics.mean(turns))


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
    print("Loading cached closes (R6/R12) + R14 Phase A news cache (no new fetch)...")
    dates, data = load_closes()
    news_hits = load_news_hits()
    day_index = {d: i for i, d in enumerate(dates)}
    daily_ret = {s: pct_change(daily_series(dates, data, s)) for s in ALL_SYMS}
    labels = month_end_labels(dates)

    rows = []
    for overlay, label in [(False, VARIANTS[0]), (True, VARIANTS[1])]:
        port_ret, n_triggers, standaside_days = run_variant(
            overlay, dates, day_index, daily_ret, labels, news_hits)
        spy_ret = [(d, daily_ret["SPY"][day_index[d]] or 0.0, 0.0) for d, _, _ in port_ret]
        m = metrics(port_ret)
        m_spy = metrics(spy_ret)
        yr = year_returns(port_ret)
        yr_spy = year_returns(spy_ret)
        rows.append((label, m, m_spy, yr, yr_spy, n_triggers, standaside_days))

    print(f"\n{'Variant':40s} {'CAGR':>8s} {'Vol':>8s} {'Sharpe':>7s} {'Sortino':>8s} "
          f"{'maxDD':>8s} {'$1->':>8s} {'AvgTurn':>8s}  triggers  stand-aside-days")
    for label, m, m_spy, _, _, n_triggers, sa_days in rows:
        print(f"{label:40s} {m['cagr']:8.2%} {m['vol']:8.2%} {m['sharpe']:7.2f} "
              f"{m['sortino']:8.2f} {m['maxdd']:8.2%} {m['final']:7.2f}x "
              f"{m['avg_turnover']:8.3%}  {n_triggers:8d}  {sa_days:16d}")

    print(f"\n{'SPY (same window as each variant)':40s}")
    for label, m, m_spy, _, _, _, _ in rows:
        print(f"  vs {label:37s} CAGR {m_spy['cagr']:7.2%}  Sharpe {m_spy['sharpe']:5.2f}  "
              f"Sortino {m_spy['sortino']:5.2f}  maxDD {m_spy['maxdd']:7.2%}  "
              f"final {m_spy['final']:.2f}x   n={m_spy['n']}  {m_spy['dates'][0]}->{m_spy['dates'][-1]}")

    print("\n2022 return (variant vs SPY, same window) and maxDD-beats-SPY check:")
    for label, m, m_spy, yr, yr_spy, _, _ in rows:
        y22r, y22s = yr.get(2022), yr_spy.get(2022)
        beats_2022 = "n/a" if y22r is None else ("YES" if y22r > y22s else "no")
        beats_dd = "YES" if m["maxdd"] > m_spy["maxdd"] else "no"
        y22r_s = f"{y22r:.2%}" if y22r is not None else "n/a"
        y22s_s = f"{y22s:.2%}" if y22s is not None else "n/a"
        print(f"  {label:40s} 2022 {y22r_s:>8s} vs SPY {y22s_s:>8s}  beats_2022={beats_2022:>3s}   "
              f"maxDD beats_SPY={beats_dd}")

    print("\nPer-year returns (variant | SPY same window):")
    for label, m, m_spy, yr, yr_spy, _, _ in rows:
        print(f"  {label}:")
        for y in sorted(yr.keys()):
            print(f"    {y}: {yr[y]:7.2%}   spy {yr_spy[y]:7.2%}")


if __name__ == "__main__":
    main()
