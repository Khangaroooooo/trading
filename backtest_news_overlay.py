"""R4 Phase B — News-sentiment stand-aside overlay on R1 rotation (locked rules;
see Evervault research/finance/backtests/results/r4-news-sentiment-overlay-feasibility.md
for the full pre-declared spec).

Phase A (news_audit.py) cleared the pre-declared coverage gate for the SPDR
sector-ETF universe (9/11 symbols qualify: >=4 headlines/mo avg, <25% zero-coverage
months), so Phase B runs on sector ETFs. Mega-caps structurally could not clear the
gate (qualifying>=8 threshold on a 5-symbol universe) — noted in the results write-up,
not a tuning decision.

Base signal is UNCHANGED from R1: month-end 12m-momentum ranking, top-3 equal-weight,
absolute-momentum-vs-BIL filter, monthly rebalance, 5bps/side.

Overlay (locked, applied daily within each month's holding period): for each
currently-held sector position, count that day's headlines for that symbol
containing >=1 of the fixed negative-keyword lexicon. If the trailing 3-trading-day
sum of such headline hits reaches >=2, stand aside to BIL for the next 5 trading
days, then resume the period's normal rotation weight (or get re-triggered if bad
news continues). Stand-aside state resets fresh at every month-end rebalance.

Implementation note (mechanical, not tunable): the trigger is evaluated using
headlines up to and including trading day d, but the stand-aside only takes effect
starting day d+1 (today's weight is decided before today's news is folded into the
rolling window) — avoids intraday lookahead, since headline timestamps land at
arbitrary times during the day. This is the only interpretive decision needed to
make the locked spec mechanical; it does not touch the keyword list, the 3-day/
2-headline trigger, or the 5-day stand-aside length, all of which are exactly as
locked.

V0 (overlay disabled) reruns the identical R1 trades on a daily engine instead of
monthly — should reproduce R1/R3-V0/R5-V0 CAGR/Sharpe/maxDD closely (small
differences only from daily- vs monthly-compounding path), serving as a
reimplementation check exactly like R3/R5/R6's V0 rows did.

Pure stdlib, reuses R1's cached data/cache/closes.csv and R4 Phase A's cached
data/cache/news_r4.jsonl — no new fetch, no installs.

Run: cd ~/Documents/trading && python3 backtest_news_overlay.py
"""
import csv
import json
import os
import statistics
from collections import defaultdict
from datetime import date as Date, datetime

SECTORS = ["XLK", "XLF", "XLV", "XLE", "XLI", "XLP", "XLY", "XLU", "XLB", "XLRE", "XLC"]
ALL = SECTORS + ["SPY", "BIL"]
COST_PER_SIDE = 0.0005
TOP_N = 3
LOOKBACK_M = 12
ROLL_WINDOW_D = 3
TRIGGER_COUNT = 2
STANDASIDE_D = 5
KEYWORDS = ["downgrade", "misses", "miss estimates", "cuts guidance", "lawsuit",
            "recall", "investigation", "fraud", "bankruptcy", "plunge", "warns",
            "disappointing", "layoffs", "resigns", "probe"]

CLOSES_CACHE = os.path.join(os.path.dirname(__file__) or ".", "data", "cache", "closes.csv")
NEWS_CACHE = os.path.join(os.path.dirname(__file__) or ".", "data", "cache", "news_r4.jsonl")

VARIANTS = ["V0 Baseline (=R1, daily engine)", "V1 News stand-aside overlay"]


def load_closes():
    if not os.path.exists(CLOSES_CACHE):
        raise SystemExit(f"Cache missing at {CLOSES_CACHE} — expected R1 cache to already exist.")
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
    """{(sector_symbol, date): count of that day's keyword-matching headlines}."""
    if not os.path.exists(NEWS_CACHE):
        raise SystemExit(f"News cache missing at {NEWS_CACHE} — run news_audit.py (Phase A) first.")
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
            syms = [s for s in it.get("symbols", []) if s in SECTORS]
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
          f"a keyword AND tagged a sector ETF.")
    return hits


def daily_series(dates, data, sym):
    return [data[d].get(sym) for d in dates]


def pct_change(vals):
    out = [None]
    for i in range(1, len(vals)):
        a, b = vals[i - 1], vals[i]
        out.append((b / a - 1) if (a is not None and b is not None and a != 0) else None)
    return out


def resample_month_end(dates, data, symbols):
    buckets = {}
    for d in dates:
        buckets[(d.year, d.month)] = d
    labels = [buckets[k] for k in sorted(buckets.keys())]
    series = {sym: [data[d].get(sym) for d in labels] for sym in symbols}
    return labels, series


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


def run_variant(overlay_enabled, dates, day_index, daily_ret, labels, sig, news_hits):
    port_ret = []
    prev_w = {}
    n_triggers = 0
    standaside_days_total = 0

    for i in range(LOOKBACK_M, len(labels) - 1):
        t, t1 = labels[i], labels[i + 1]
        sig_t = {s: sig[s][i] for s in SECTORS if sig[s][i] is not None}
        if len(sig_t) < TOP_N:
            continue
        bil = sig["BIL"][i]
        w_base = base_weights(sig_t, bil, TOP_N)
        held_sectors = [s for s in w_base if s != "BIL"]
        standaside_remaining = {s: 0 for s in held_sectors}
        roll_hits = {s: [] for s in held_sectors}

        start_di, end_di = day_index[t], day_index[t1]
        for di in range(start_di + 1, end_di + 1):
            d = dates[di]

            # Step 1: decide today's weight from state carried in from before today.
            w_today = {}
            freed = 0.0
            for s, wt in w_base.items():
                if s == "BIL":
                    continue
                if standaside_remaining.get(s, 0) > 0:
                    freed += wt
                    standaside_days_total += 1
                else:
                    w_today[s] = wt
            w_today["BIL"] = w_base.get("BIL", 0) + freed

            # Step 2: today consumes one day of any active stand-aside.
            for s in standaside_remaining:
                if standaside_remaining[s] > 0:
                    standaside_remaining[s] -= 1

            # Step 3: fold in today's news, check for a (re-)trigger for tomorrow+.
            if overlay_enabled:
                for s in held_sectors:
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
    print("Loading cached closes + R4 Phase A news cache (no new fetch)...")
    dates, data = load_closes()
    news_hits = load_news_hits()
    day_index = {d: i for i, d in enumerate(dates)}
    daily_ret = {s: pct_change(daily_series(dates, data, s)) for s in ALL}

    labels, series = resample_month_end(dates, data, ALL)
    sig = {s: momentum_12m(series[s], LOOKBACK_M) for s in ALL}

    rows = []
    for overlay, label in [(False, VARIANTS[0]), (True, VARIANTS[1])]:
        port_ret, n_triggers, standaside_days = run_variant(
            overlay, dates, day_index, daily_ret, labels, sig, news_hits)
        spy_ret = [(d, daily_ret["SPY"][day_index[d]] or 0.0, 0.0) for d, _, _ in port_ret]
        m = metrics(port_ret)
        m_spy = metrics(spy_ret)
        yr = year_returns(port_ret)
        yr_spy = year_returns(spy_ret)
        rows.append((label, m, m_spy, yr, yr_spy, n_triggers, standaside_days))

    print(f"\n{'Variant':32s} {'CAGR':>8s} {'Vol':>8s} {'Sharpe':>7s} {'Sortino':>8s} "
          f"{'maxDD':>8s} {'$1->':>8s} {'AvgTurn':>8s}  triggers  stand-aside-days")
    for label, m, m_spy, _, _, n_triggers, sa_days in rows:
        print(f"{label:32s} {m['cagr']:8.2%} {m['vol']:8.2%} {m['sharpe']:7.2f} "
              f"{m['sortino']:8.2f} {m['maxdd']:8.2%} {m['final']:7.2f}x "
              f"{m['avg_turnover']:8.3%}  {n_triggers:8d}  {sa_days:16d}")

    print(f"\n{'SPY (same window as each variant)':32s}")
    for label, m, m_spy, _, _, _, _ in rows:
        print(f"  vs {label:29s} CAGR {m_spy['cagr']:7.2%}  Sharpe {m_spy['sharpe']:5.2f}  "
              f"Sortino {m_spy['sortino']:5.2f}  maxDD {m_spy['maxdd']:7.2%}  "
              f"final {m_spy['final']:.2f}x   n={m_spy['n']}  {m_spy['dates'][0]}->{m_spy['dates'][-1]}")

    print("\n2022 return (variant vs SPY, same window) and maxDD-beats-SPY check:")
    for label, m, m_spy, yr, yr_spy, _, _ in rows:
        y22r, y22s = yr.get(2022), yr_spy.get(2022)
        beats_2022 = "n/a" if y22r is None else ("YES" if y22r > y22s else "no")
        beats_dd = "YES" if m["maxdd"] > m_spy["maxdd"] else "no"
        y22r_s = f"{y22r:.2%}" if y22r is not None else "n/a"
        y22s_s = f"{y22s:.2%}" if y22s is not None else "n/a"
        print(f"  {label:32s} 2022 {y22r_s:>8s} vs SPY {y22s_s:>8s}  beats_2022={beats_2022:>3s}   "
              f"maxDD beats_SPY={beats_dd}")

    print("\nPer-year returns (variant | SPY same window):")
    for label, m, m_spy, yr, yr_spy, _, _ in rows:
        print(f"  {label}:")
        for y in sorted(yr.keys()):
            print(f"    {y}: {yr[y]:7.2%}   spy {yr_spy[y]:7.2%}")


if __name__ == "__main__":
    main()
