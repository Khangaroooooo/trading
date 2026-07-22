"""R14 Phase A — single-name news coverage audit (READ-ONLY, no orders).

Rules locked in Evervault `research/finance/backtests/results/r14-single-name-news-sentiment-overlay.md`
BEFORE this script was run. Same fetch/audit logic as R4's news_audit.py, applied
to R6's 15-name mega/large-cap universe, with a gate scaled to universe size
(>=80% of symbols qualify, vs R4's fixed >=8-symbol count).

Run: cd /Users/kkhangaroo/Documents/trading && python3 news_audit_r14.py
"""
import os
import json
import time
import urllib.request
import urllib.parse
from datetime import datetime, timezone
from collections import defaultdict

UNIVERSE = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "JPM", "V",
            "JNJ", "PG", "HD", "XOM", "UNH", "KO", "DIS"]
START = "2016-01-01T00:00:00Z"
CACHE_DIR = os.path.join(os.path.dirname(__file__) or ".", "data", "cache")
CACHE = os.path.join(CACHE_DIR, "news_r14.jsonl")
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
        "symbols": ",".join(UNIVERSE),
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
                  f"{time.time()-t0:.0f}s elapsed", flush=True)
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


def audit(items, symbols):
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

        per_day = defaultdict(int)
        for d in dates:
            per_day[d.date()] += 1
        counts = sorted(per_day.values())
        median_per_day = counts[len(counts) // 2] if counts else 0

        rows.append({
            "symbol": sym, "total": total, "avg_per_month": avg_per_month,
            "pct_zero_months": pct_zero_months, "median_per_day": median_per_day,
        })

    print(f"{'sym':6s} {'total':>7s} {'avg/mo':>8s} {'%zero-mo':>9s} {'med/day':>8s}")
    for row in rows:
        print(f"{row['symbol']:6s} {row['total']:7d} {row['avg_per_month']:8.2f} "
              f"{row['pct_zero_months']:8.1%} {row['median_per_day']:8d}")

    return rows, total_months


def main():
    print("Fetching Alpaca/Benzinga news for R14 Phase A audit (15-name universe)...")
    items = fetch_all_news()

    rows, total_months = audit(items, UNIVERSE)

    def gate_pass(rows, universe_size, pct_threshold=0.80):
        qualifying = sum(1 for r in rows if r["avg_per_month"] >= 4 and r["pct_zero_months"] < 0.25)
        needed = universe_size * pct_threshold
        return qualifying, qualifying >= needed

    qual, passed = gate_pass(rows, len(UNIVERSE))

    print(f"\n=== Gate check (>=4 headlines/mo avg, <25% zero-coverage months, >=80% of {len(UNIVERSE)}-symbol universe = >={len(UNIVERSE)*0.8:.1f}) ===")
    print(f"15-name universe: {qual}/{len(UNIVERSE)} symbols qualify -> {'PASS' if passed else 'FAIL'}")
    print(f"\nGate result: {'PHASE B RUNS' if passed else 'PHASE B SKIPPED — feasibility-only result'}")


if __name__ == "__main__":
    main()
