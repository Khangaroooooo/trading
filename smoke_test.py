"""Smoke test: read paper keys from .env, hit the Alpaca paper API, print account status.

Read-only — checks the account endpoint and one quote. No orders placed.
Run: python3 smoke_test.py
"""
import json
import os
import urllib.request

def load_env(path=".env"):
    env = {}
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k] = v.strip().strip('"')
    return env

def get(url, headers):
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req) as r:
        return json.load(r)

def main():
    env = load_env(os.path.join(os.path.dirname(__file__) or ".", ".env"))
    key, secret = env.get("ALPACA_PAPER_KEY"), env.get("ALPACA_PAPER_SECRET")
    if not key or not secret:
        raise SystemExit("Keys missing — paste them into .env first.")
    headers = {"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret}

    acct = get(f"{env['ALPACA_PAPER_URL']}/v2/account", headers)
    print(f"account status : {acct['status']}")
    print(f"paper equity   : ${float(acct['equity']):,.2f}")
    print(f"buying power   : ${float(acct['buying_power']):,.2f}")

    quote = get(
        "https://data.alpaca.markets/v2/stocks/SPY/snapshot?feed=iex", headers
    )
    price = quote["latestTrade"]["p"]
    print(f"SPY last (IEX) : ${price}")
    print("\nSmoke test passed — paper account + market data both reachable.")

if __name__ == "__main__":
    main()
