"""Experiment R25 -- Pre-2016 data feasibility check (second independent bear market).

Rules locked before running; see Evervault
research/finance/backtests/results/r25-pre2016-data-feasibility.md for full spec.

Phase A: can Alpaca supply real daily bars back to the 2008-2009 financial crisis for
SPY, BIL, and the 9 "classic" SPDR sector ETFs (XLRE/XLC excluded up front -- they
postdate the window by construction)? Pass/fail gate is locked in the spec note.

Phase B (only if Phase A passes): re-run R1's exact rotation methodology on the
recovered window as a first look at a second, independent bear-market observation.

Pure stdlib (no pandas/requests in this unattended environment) -- urllib.request,
same pattern as R6/R12/R17/R24. Fresh fetch -- the existing closes.csv cache starts
2016-01-04 and cannot answer this question.

Run: cd ~/Documents/trading && python3 backtest_pre2016_feasibility_r25.py
"""
import csv
import json
import os
import statistics
import urllib.request
import urllib.parse
from datetime import date as Date, timedelta

SECTORS_9 = ["XLK", "XLF", "XLV", "XLE", "XLI", "XLP", "XLY", "XLU", "XLB"]
ALL_SYMS = SECTORS_9 + ["SPY", "BIL"]
REQ_START = "2006-01-01"
REQ_END = "2010-12-31"
BIL_KNOWN_INCEPTION = Date(2007, 5, 30)   # public fact, locked before fetch
GATE_MAX_START = Date(2007, 6, 1)
GATE_MAX_MISSING_PCT = 0.10
WINDOW_START = Date(2007, 1, 1)
WINDOW_END = Date(2010, 12, 31)

COST_PER_SIDE = 0.0005
TOP_N = 3
LOOKBACK_M = 12

CACHE = os.path.join(os.path.dirname(__file__) or ".", "data", "cache", "closes_pre2016_r25.csv")
ENV_PATH = os.path.join(os.path.dirname(__file__) or ".", ".env")


def load_env(path):
    env = {}
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k] = v.strip().strip('"')
    return env


def fetch_json(url, headers):
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def fetch_symbol(sym, headers, feed):
    params = {
        "symbols": sym, "timeframe": "1Day", "start": REQ_START, "end": REQ_END,
        "adjustment": "all", "feed": feed, "limit": 10000,
    }
    rows = []
    page = None
    used_feed = feed
    while True:
        if page:
            params["page_token"] = page
        url = "https://data.alpaca.markets/v2/stocks/bars?" + urllib.parse.urlencode(params)
        try:
            j = fetch_json(url, headers)
        except urllib.error.HTTPError as e:
            if e.code == 403 and used_feed == "sip":
                print(f"  {sym}: SIP 403'd, falling back to IEX feed")
                used_feed = "iex"
                params["feed"] = "iex"
                page = None
                continue
            raise
        bars = j.get("bars", {}).get(sym, [])
        rows.extend(bars)
        page = j.get("next_page_token")
        if not page:
            break
    return rows, used_feed


def fetch_all():
    if os.path.exists(CACHE):
        print(f"Using cached fetch at {CACHE}")
        return _read_cache()
    env = load_env(ENV_PATH)
    headers = {"APCA-API-KEY-ID": env["ALPACA_PAPER_KEY"],
               "APCA-API-SECRET-KEY": env["ALPACA_PAPER_SECRET"]}
    all_data = {}
    feed_used = {}
    for sym in ALL_SYMS:
        rows, used_feed = fetch_symbol(sym, headers, "sip")
        feed_used[sym] = used_feed
        for b in rows:
            d = Date.fromisoformat(b["t"][:10])
            all_data.setdefault(d, {})[sym] = b["c"]
        print(f"  fetched {sym}: {len(rows)} bars via {used_feed} feed")
    dates = sorted(all_data.keys())
    os.makedirs(os.path.dirname(CACHE), exist_ok=True)
    with open(CACHE, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow([""] + ALL_SYMS)
        for d in dates:
            row = [d.isoformat()] + [all_data[d].get(s, "") for s in ALL_SYMS]
            w.writerow(row)
    return dates, all_data, feed_used


def _read_cache():
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
    return dates, data, {}


def business_days_between(d0, d1):
    # rough NYSE trading-day count proxy: weekdays only, no holiday calendar
    n = 0
    d = d0
    while d <= d1:
        if d.weekday() < 5:
            n += 1
        d += timedelta(days=1)
    return n


def phase_a_audit(dates, data):
    print("\n=== Phase A: data feasibility audit ===")
    print(f"Requested range: {REQ_START} .. {REQ_END}")
    results = {}
    expected_days = business_days_between(WINDOW_START, WINDOW_END)
    for sym in ALL_SYMS:
        sym_dates = [d for d in dates if sym in data[d]]
        if not sym_dates:
            results[sym] = {"first": None, "last": None, "n_in_window": 0,
                             "missing_pct": 1.0}
            print(f"  {sym:6s}  NO DATA RETURNED")
            continue
        first, last = sym_dates[0], sym_dates[-1]
        in_window = [d for d in sym_dates if WINDOW_START <= d <= WINDOW_END]
        missing_pct = 1 - (len(in_window) / expected_days) if expected_days else 1.0
        results[sym] = {"first": first, "last": last, "n_in_window": len(in_window),
                         "missing_pct": missing_pct}
        print(f"  {sym:6s}  first={first}  last_in_req_range={last}  "
              f"n_in_2007-2010_window={len(in_window)}  missing_pct~{missing_pct:.1%}")

    # Gate: SPY + 9 sectors must start on/before GATE_MAX_START with <10% missing.
    # BIL is exempted from the start-date check (known 2007-05-30 inception, handled
    # via the pre-declared synthetic-cash fallback), but still checked for coverage
    # from its own inception onward.
    gate_syms = SECTORS_9 + ["SPY"]
    fails = []
    for sym in gate_syms:
        r = results[sym]
        if r["first"] is None or r["first"] > GATE_MAX_START:
            fails.append(f"{sym}: first available date {r['first']} is after gate "
                         f"cutoff {GATE_MAX_START}")
        elif r["missing_pct"] > GATE_MAX_MISSING_PCT:
            fails.append(f"{sym}: missing_pct {r['missing_pct']:.1%} exceeds "
                         f"{GATE_MAX_MISSING_PCT:.0%} gate")

    bil = results["BIL"]
    bil_note = ""
    if bil["first"] is None:
        fails.append("BIL: no data at all (even the synthetic-cash fallback needs a "
                      "real BIL series post-inception)")
    elif bil["first"] > BIL_KNOWN_INCEPTION + timedelta(days=30):
        bil_note = (f"BIL first available {bil['first']} is later than known inception "
                    f"{BIL_KNOWN_INCEPTION} by >30d -- larger gap than anticipated, "
                    "synthetic-cash fallback covers it per locked rule regardless.")

    passed = len(fails) == 0
    print(f"\nGate result: {'PASS' if passed else 'FAIL'}")
    if fails:
        for f in fails:
            print(f"  FAIL reason: {f}")
    if bil_note:
        print(f"  Note: {bil_note}")
    return passed, results


def resample_month_end(dates, data, symbols):
    by_month = {}
    for d in dates:
        key = (d.year, d.month)
        by_month[key] = d  # last date seen per month = month-end (dates sorted)
    months = sorted(by_month.keys())
    out = {}
    for key in months:
        d = by_month[key]
        out[key] = {s: data[d].get(s) for s in symbols if s in data[d]}
    return months, out


def phase_b_backtest(dates, data):
    print("\n=== Phase B: R1 methodology on 9-sector universe, 2007-2010 window ===")
    universe = SECTORS_9 + ["SPY", "BIL"]
    months, monthly_px = resample_month_end(dates, data, universe)

    # monthly total-return series per symbol (dividend-adjusted closes already, per fetch)
    r1 = {}
    for i in range(1, len(months)):
        prev_m, cur_m = months[i - 1], months[i]
        r1[cur_m] = {}
        for s in universe:
            p0 = monthly_px[prev_m].get(s)
            p1 = monthly_px[cur_m].get(s)
            if p0 and p1:
                r1[cur_m][s] = p1 / p0 - 1

    def bil_return(m):
        if "BIL" in r1.get(m, {}):
            return r1[m]["BIL"]
        return 0.0  # pre-declared synthetic-cash fallback for BIL's pre-inception gap

    def r12_signal(m_idx, sym):
        # 12m total return ending at months[m_idx], using monthly_px directly
        if m_idx < LOOKBACK_M:
            return None
        m0, m1 = months[m_idx - LOOKBACK_M], months[m_idx]
        p0 = monthly_px[m0].get(sym)
        p1 = monthly_px[m1].get(sym)
        if sym == "BIL" and (p0 is None or p1 is None):
            return 0.0  # synthetic cash proxy pre-inception
        if p0 is None or p1 is None:
            return None
        return p1 / p0 - 1

    port_ret = []
    cost_drag = []
    weights_log = []
    prev_w = {}
    for i in range(LOOKBACK_M, len(months) - 1):
        m, m_next = months[i], months[i + 1]
        if not (WINDOW_START <= Date(m_next[0], m_next[1], 1) <= WINDOW_END or True):
            continue
        sigs = {}
        for s in SECTORS_9:
            v = r12_signal(i, s)
            if v is not None:
                sigs[s] = v
        if len(sigs) < TOP_N:
            continue
        bil_sig = r12_signal(i, "BIL")
        top = sorted(sigs.items(), key=lambda kv: kv[1], reverse=True)[:TOP_N]
        w = {}
        for sym, val in top:
            tgt = sym if (bil_sig is None or val > bil_sig) else "BIL"
            w[tgt] = w.get(tgt, 0) + 1 / TOP_N
        traded = sum(abs(w.get(k, 0) - prev_w.get(k, 0)) for k in set(w) | set(prev_w))
        cost = traded * COST_PER_SIDE
        gross = 0.0
        for sym, wt in w.items():
            ret = r1.get(m_next, {}).get(sym) if sym != "BIL" else bil_return(m_next)
            if ret is not None:
                gross += wt * ret
        port_ret.append((m_next, gross - cost))
        cost_drag.append(cost)
        weights_log.append((m_next, dict(w)))
        prev_w = w

    # restrict to the target window for reporting
    port_ret_win = [(m, v) for m, v in port_ret if WINDOW_START.year <= m[0] <= WINDOW_END.year]

    def metrics(series, label):
        vals = [v for _, v in series]
        if not vals:
            print(f"{label}: no data in window")
            return None
        eq = []
        acc = 1.0
        for v in vals:
            acc *= (1 + v)
            eq.append(acc)
        years = len(vals) / 12
        cagr = eq[-1] ** (1 / years) - 1 if years > 0 else float("nan")
        vol = statistics.pstdev(vals) * (12 ** 0.5) if len(vals) > 1 else float("nan")
        mean = statistics.mean(vals)
        sharpe = (mean / statistics.pstdev(vals)) * (12 ** 0.5) if len(vals) > 1 and statistics.pstdev(vals) else float("nan")
        downside_vals = [v for v in vals if v < 0]
        downside = statistics.pstdev(downside_vals) * (12 ** 0.5) if len(downside_vals) > 1 else float("nan")
        sortino = (mean * 12) / downside if downside else float("nan")
        peak = eq[0]
        maxdd = 0.0
        for e in eq:
            peak = max(peak, e)
            maxdd = min(maxdd, e / peak - 1)
        print(f"{label:22s} CAGR {cagr:7.2%}  vol {vol:7.2%}  Sharpe {sharpe:5.2f}  "
              f"Sortino {sortino:5.2f}  maxDD {maxdd:8.2%}  final ${eq[-1]:,.2f}/$1  n={len(vals)}mo")
        return {"cagr": cagr, "vol": vol, "sharpe": sharpe, "sortino": sortino,
                "maxdd": maxdd, "final": eq[-1], "n": len(vals)}

    print(f"\nWindow traded: {port_ret_win[0][0] if port_ret_win else 'N/A'} -> "
          f"{port_ret_win[-1][0] if port_ret_win else 'N/A'} "
          f"({len(port_ret_win)} months, avg cost drag "
          f"{statistics.mean(cost_drag) if cost_drag else 0:.3%}/mo)")
    rot_m = metrics(port_ret_win, "Rotation (9-sector, net)")

    spy_series = [(m, r1.get(m, {}).get("SPY")) for m, _ in port_ret_win]
    spy_series = [(m, v) for m, v in spy_series if v is not None]
    spy_m = metrics(spy_series, "SPY buy-and-hold")

    print("\nPer-year returns:")
    years_seen = sorted(set(m[0] for m, _ in port_ret_win))
    port_dict = dict(port_ret_win)
    spy_dict = dict(spy_series)
    for y in years_seen:
        p_months = [v for m, v in port_ret_win if m[0] == y]
        s_months = [v for m, v in spy_series if m[0] == y]
        if not p_months or not s_months:
            continue
        p = 1.0
        for v in p_months:
            p *= (1 + v)
        p -= 1
        s = 1.0
        for v in s_months:
            s *= (1 + v)
        s -= 1
        flag = "  <-- rotation wins" if p > s else ""
        print(f"  {y}: rotation {p:7.2%}   SPY {s:7.2%}{flag}")

    return rot_m, spy_m


def main():
    result = fetch_all()
    if len(result) == 3:
        dates, data, _ = result
    else:
        dates, data = result
    passed, audit = phase_a_audit(dates, data)
    if not passed:
        print("\nPhase A FAILED -- stopping per locked rule. No Phase B run.")
        return
    phase_b_backtest(dates, data)


if __name__ == "__main__":
    main()
