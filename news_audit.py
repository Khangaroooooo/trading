"""R4 Phase A — Alpaca/Benzinga news coverage audit (READ-ONLY, no orders).

Rules locked in Evervault `research/finance/backtests/results/r4-news-sentiment-overlay-feasibility.md`
BEFORE this script was run. Measures headline coverage density and latency for
11 SPDR sector ETFs vs 5 liquid mega-caps, to decide (mechanically, via the
pre-declared gate) whether Phase B (locked keyword-overlay backtest) runs.

Run: cd /Users/kkhangaroo/Documents/trading && python3 news_audit.py
"""
import os
import json
import time
import urllib.request
import urllib.parse
from datetime import datetime, timezone
from collections import defaultdict

SECTORS = ["XLK", "XLF", "XLV", "XLE", "XLI", "XLP", "XLY", "XLU", "XLB", "XLRE", "XLC"]
MEGACAPS = ["AAPL", "MSFT", "AMZN", "GOOGL", "NVDA"]
ALL_SYMBOLS = SECTORS + MEGACAPS
START = "2016-01-01T00:00:00Z"
CACHE_DIR = os.path.join(os.path.dirname(__file__) or ".", "data", "cache")
CACHE = os.path.join(CACHE_DIR, "news_r4.jsonl")
URL = "https://data.alpaca.markets/v1beta1/news"


def load_env(path):
    env = {}
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k] = v.strip().strip('"')
    return env


def fetch_all_news():
    if os.path.exists(CACHE):
        items = []
        with open(CACHE) as f:
            for line in f:
                items.append(json.loads(line))
        return items

    env = load_env(os.path.join(os.path.dirname(__file__) or ".", ".env"))
    headers = {
        "APCA-API-KEY-ID": env["ALPACA_PAPER_KEY"],
        "APCA-API-SECRET-KEY": env["ALPACA_PAPER_SECRET"],
    }
    end = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    params = {
        "symbols": ",".join(ALL_SYMBOLS),
        "start": START,
        "end": end,
        "limit": 50,
        "include_content": "false",
        "sort": "asc",
    }
    items = []
    page = 0
    t0 = time.time()
    while True:
        qs = urllib.parse.urlencode(params)
        req = urllib.request.Request(f"{URL}?{qs}", headers=headers)
        with urllib.request.urlopen(req, timeout=30) as resp:
            js = json.loads(resp.read().decode())
        batch = js.get("news") or []
        items.extend(batch)
        page += 1
        if page % 20 == 0:
            print(f"  ...page {page}, {len(items)} headlines so far, "
                  f"{time.time()-t0:.0f}s elapsed")
        token = js.get("next_page_token")
        if not token:
            break
        params["page_token"] = token

    os.makedirs(CACHE_DIR, exist_ok=True)
    with open(CACHE, "w") as f:
        for it in items:
            f.write(json.dumps(it) + "\n")
    print(f"Fetched {len(items)} headlines in {page} pages, {time.time()-t0:.0f}s. Cached to {CACHE}")
    return items


def month_key(dt):
    return (dt.year, dt.month)


def audit(items, universe_name, symbols):
    print(f"\n=== {universe_name} ({len(symbols)} symbols) ===")
    per_symbol_dates = defaultdict(list)
    for it in items:
        try:
            dt = datetime.strptime(it["created_at"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        except ValueError:
            dt = datetime.fromisoformat(it["created_at"].replace("Z", "+00:00"))
        for sym in it.get("symbols", []):
            if sym in symbols:
                per_symbol_dates[sym].append(dt)

    start_dt = datetime.strptime(START, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    end_dt = datetime.now(timezone.utc)
    total_months = (end_dt.year - start_dt.year) * 12 + (end_dt.month - start_dt.month) + 1

    rows = []
    for sym in symbols:
        dates = sorted(per_symbol_dates.get(sym, []))
        total = len(dates)
        months_with = len({month_key(d) for d in dates})
        pct_zero_months = 1 - (months_with / total_months) if total_months else float("nan")
        avg_per_month = total / total_months if total_months else 0.0

        # median headlines/day on days with >=1 headline
        per_day = defaultdict(int)
        for d in dates:
            per_day[d.date()] += 1
        counts = sorted(per_day.values())
        median_per_day = counts[len(counts) // 2] if counts else 0

        pre, intraday, after = 0, 0, 0
        for d in dates:
            # created_at is UTC; ET is UTC-4/UTC-5 depending on DST — use UTC-4 (EDT)
            # as a coarse approximation for this audit-only latency proxy.
            et_hour = (d.hour - 4) % 24
            et_min = et_hour * 60 + d.minute
            if et_min < 9 * 60 + 30:
                pre += 1
            elif et_min <= 16 * 60:
                intraday += 1
            else:
                after += 1

        rows.append({
            "symbol": sym, "total": total, "avg_per_month": avg_per_month,
            "pct_zero_months": pct_zero_months, "median_per_day": median_per_day,
            "pre": pre, "intraday": intraday, "after": after,
        })

    print(f"{'sym':6s} {'total':>7s} {'avg/mo':>8s} {'%zero-mo':>9s} {'med/day':>8s} "
          f"{'pre%':>6s} {'intr%':>6s} {'aft%':>6s}")
    for row in rows:
        t = row["total"] or 1
        print(f"{row['symbol']:6s} {row['total']:7d} {row['avg_per_month']:8.2f} "
              f"{row['pct_zero_months']:8.1%} {row['median_per_day']:8d} "
              f"{row['pre']/t:6.1%} {row['intraday']/t:6.1%} {row['after']/t:6.1%}")

    return rows, total_months


def main():
    print("Fetching Alpaca/Benzinga news for R4 Phase A audit...")
    items = fetch_all_news()

    sector_rows, total_months = audit(items, "SPDR sector ETFs", SECTORS)
    mega_rows, _ = audit(items, "Mega-caps", MEGACAPS)

    # Pre-declared gate: >=4 headlines/month avg AND <25% zero-coverage months,
    # for at least 8 of the symbols in that universe.
    def gate_pass(rows):
        qualifying = sum(1 for r in rows if r["avg_per_month"] >= 4 and r["pct_zero_months"] < 0.25)
        return qualifying, qualifying >= 8

    sec_qual, sec_pass = gate_pass(sector_rows)
    mega_qual, mega_pass = gate_pass(mega_rows)

    print(f"\n=== Gate check (>=4 headlines/mo avg, <25% zero-coverage months, >=8/universe) ===")
    print(f"Sector ETFs: {sec_qual}/11 symbols qualify -> {'PASS' if sec_pass else 'FAIL'}")
    print(f"Mega-caps:   {mega_qual}/5 symbols qualify -> {'PASS' if mega_pass else 'FAIL'}")
    print(f"\nGate result: {'PHASE B RUNS' if (sec_pass or mega_pass) else 'PHASE B SKIPPED — feasibility-only result'}")


if __name__ == "__main__":
    main()
