# trading

A pre-registered backtesting log. 27 experiments (R1–R27) on US equities, paper account only,
every one of them declaring its success criteria before it runs and getting written up either
way — including the losers.

## Why it's structured this way

Backtesting rewards you for lying to yourself. Run enough variants and something clears any
bar you set afterward. The discipline here is meant to make that harder:

- **Criteria are locked before the run.** Bars (Sharpe / Sortino / maxDD / CAGR band vs SPY)
  are written into the experiment spec first, not chosen once results are in.
- **Negative results are published.** `journal.md` logs every experiment with an explicit
  "honest read" line, and several of them say the lead didn't survive.
- **Reruns must reproduce prior numbers to the decimal** before a new result counts.

The clearest example is **R24**. Experiments R1–R22 all shared one ~9.5-year window containing
exactly one bear market (2022) — flagged as a caveat repeatedly, never actually tested. R24 cut
the return series at a pre-declared midpoint and re-scored each half. In the bull half the
strategy failed 3–4 of its 4 bars outright; the entire full-window edge lived in the half
containing 2022. That reclassified the result from "an edge" to "a bear-market hedge, N=1" —
which is what it had been the whole time.

## Layout

- `journal.md` — the experiment log. Start here.
- `backtest_*.py` — one script per experiment, suffixed with its R-number. Pure stdlib where
  possible; later runs reuse the cached `closes.csv` rather than re-fetching.
- `smoke_test.py` — read-only connectivity check (account + SPY quote).
- `news_audit*.py`, `turnover_cost_breakeven.py` — supporting analyses.
- `mcp_alpaca.sh` — Alpaca MCP wrapper.

## Rules of the road

- **Paper only.** US stocks only.
- Risk limits are hard-coded outside the LLM, not left to model judgment.
- Any future live-order path requires explicit human approval per order.
- `.env` holds Alpaca **paper** keys, is gitignored, and never gets committed or pasted into
  a chat.

Results are net of costs (5bps/side unless stated). Full specs and locked criteria live in the
knowledge base at `~/Evervault/research/finance/`.
