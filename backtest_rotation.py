"""Experiment #1 — Dual-momentum sector rotation (fixed rules, no fitted parameters).

Rules (locked before running; Antonacci-style):
  - Universe: 11 SPDR sector ETFs. BIL = cash proxy, SPY = benchmark.
  - At each month-end close: rank sectors by 12-month total return (dividend-adjusted).
  - Hold top 3 equal-weight next month; any of the 3 whose 12m return <= BIL's 12m
    return is replaced by BIL (absolute momentum filter).
  - Costs: 5 bps per unit of weight traded (spread+slippage haircut, per side).
Convention: signal measured at month-end close, position assumed entered at that same
close (standard; slightly optimistic vs next-open execution — noted in journal).

Run: uv run --with pandas,requests backtest_rotation.py
"""
import os
import requests
import pandas as pd

SECTORS = ["XLK", "XLF", "XLV", "XLE", "XLI", "XLP", "XLY", "XLU", "XLB", "XLRE", "XLC"]
ALL = SECTORS + ["SPY", "BIL"]
START = "2016-01-01"
COST_PER_SIDE = 0.0005
TOP_N = 3
LOOKBACK_M = 12
CACHE = os.path.join(os.path.dirname(__file__) or ".", "data", "cache", "closes.csv")


def load_env(path):
    env = {}
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k] = v.strip().strip('"')
    return env


def fetch_closes():
    if os.path.exists(CACHE):
        return pd.read_csv(CACHE, index_col=0, parse_dates=True)
    env = load_env(os.path.join(os.path.dirname(__file__) or ".", ".env"))
    headers = {
        "APCA-API-KEY-ID": env["ALPACA_PAPER_KEY"],
        "APCA-API-SECRET-KEY": env["ALPACA_PAPER_SECRET"],
    }
    end = (pd.Timestamp.now("UTC") - pd.Timedelta(minutes=20)).strftime("%Y-%m-%dT%H:%M:%SZ")
    rows = {}
    params = {
        "symbols": ",".join(ALL), "timeframe": "1Day", "start": START, "end": end,
        "adjustment": "all", "feed": "sip", "limit": 10000,
    }
    url = "https://data.alpaca.markets/v2/stocks/bars"
    while True:
        r = requests.get(url, headers=headers, params=params, timeout=30)
        if r.status_code == 403 and params["feed"] == "sip":
            print("SIP historical not available on this plan — falling back to IEX feed.")
            params["feed"] = "iex"
            continue
        r.raise_for_status()
        js = r.json()
        for sym, bars in (js.get("bars") or {}).items():
            for b in bars:
                rows.setdefault(pd.Timestamp(b["t"][:10]), {})[sym] = b["c"]
        token = js.get("next_page_token")
        if not token:
            break
        params["page_token"] = token
    px = pd.DataFrame.from_dict(rows, orient="index").sort_index()
    os.makedirs(os.path.dirname(CACHE), exist_ok=True)
    px.to_csv(CACHE)
    return px


def metrics(monthly, label):
    eq = (1 + monthly).cumprod()
    years = len(monthly) / 12
    cagr = eq.iloc[-1] ** (1 / years) - 1
    vol = monthly.std() * (12 ** 0.5)
    sharpe = monthly.mean() / monthly.std() * (12 ** 0.5)
    downside = monthly[monthly < 0].std() * (12 ** 0.5)
    sortino = (monthly.mean() * 12) / downside if downside else float("nan")
    maxdd = (eq / eq.cummax() - 1).min()
    print(f"{label:22s} CAGR {cagr:6.2%}  vol {vol:6.2%}  Sharpe {sharpe:5.2f}  "
          f"Sortino {sortino:5.2f}  maxDD {maxdd:7.2%}  final ${eq.iloc[-1]:,.2f}/$1")
    return eq


def main():
    px = fetch_closes()
    m = px.resample("ME").last()                      # month-end closes
    r1 = m.pct_change()                               # realized monthly returns
    r12 = m / m.shift(LOOKBACK_M) - 1                 # 12m signal

    weights, prev = [], pd.Series(dtype=float)
    port_ret, cost_drag = [], []
    dates = m.index
    for i in range(LOOKBACK_M, len(dates) - 1):
        t, t1 = dates[i], dates[i + 1]
        sig = r12.loc[t, SECTORS].dropna()
        if len(sig) < TOP_N:
            continue
        top = sig.nlargest(TOP_N)
        bil = r12.loc[t, "BIL"]
        w = {}
        for sym, val in top.items():
            tgt = sym if val > bil else "BIL"
            w[tgt] = w.get(tgt, 0) + 1 / TOP_N
        w = pd.Series(w)
        traded = w.subtract(prev, fill_value=0).abs().sum()
        cost = traded * COST_PER_SIDE
        gross = (w * r1.loc[t1, w.index]).sum()
        port_ret.append((t1, gross - cost))
        cost_drag.append(cost)
        weights.append((t1, dict(w)))
        prev = w

    pr = pd.Series(dict(port_ret)).sort_index()
    spy = r1["SPY"].reindex(pr.index)

    print(f"\nDual-momentum sector rotation — {pr.index[0]:%Y-%m} → {pr.index[-1]:%Y-%m} "
          f"({len(pr)} months, costs {COST_PER_SIDE*1e4:.0f}bps/side, "
          f"avg cost drag {pd.Series(cost_drag).mean():.3%}/mo)\n")
    eq_p = metrics(pr, "Rotation (net)")
    eq_s = metrics(spy, "SPY buy-and-hold")

    print("\nPer-year returns:")
    for y in sorted(set(pr.index.year)):
        p = (1 + pr[pr.index.year == y]).prod() - 1
        s = (1 + spy[spy.index.year == y]).prod() - 1
        flag = "  <-- rotation wins" if p > s else ""
        print(f"  {y}: rotation {p:7.2%}   SPY {s:7.2%}{flag}")

    print("\nCurrent holdings (as of last rebalance):", weights[-1][0].strftime("%Y-%m-%d"),
          weights[-1][1])


if __name__ == "__main__":
    main()
