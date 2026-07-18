# Experiment journal

Rules: every experiment gets logged — including the losers (PBO discipline). Metrics per the scoreboard in Evervault `research/finance/findings/evaluation-metrics-and-sample-size.md`.

---

## #1 — Dual-momentum sector rotation (2026-07-18)

**Setup:** fixed Antonacci-style rules, zero fitted parameters (locked before running). 11 SPDR sector ETFs; month-end 12m-total-return ranking; top 3 equal-weight; absolute-momentum filter vs BIL; 5bps/side cost on turnover. Data: Alpaca SIP daily bars 2016-01→2026-07, dividend-adjusted (`adjustment=all`). Window: 2017-02→2026-07 (114 months). Script: `backtest_rotation.py`.

**Results (net of costs):**

| | CAGR | Vol | Sharpe | Sortino | maxDD | $1 grows to |
|---|---|---|---|---|---|---|
| Rotation | 13.64% | 13.93% | 0.99 | 1.34 | −18.06% | $3.37 |
| SPY B&H | 15.01% | 15.69% | 0.97 | 1.44 | −23.93% | $3.78 |

**Honest read:** does **NOT** beat SPY on raw return over this window (a strongly bullish decade — exactly the regime research says rotation lags). It earns its keep on defense: **2022 bear +5.1% vs SPY −18.2%**, maxDD 6pts shallower, Sharpe a hair higher. 2026 YTD it leads (+20.8% vs +9.6%). Matches the literature's profile almost perfectly → confidence the harness is measuring correctly.

**Caveats:** execution assumed at signal close (slightly optimistic vs next-open); single 9.5-yr window dominated by one regime; monthly rebalance = only ~114 observations. No parameter tuning was done (nothing to overfit, but also nothing optimized).

**Role going forward:** defensive baseline, not the alpha engine. Candidates #2 (PEAD) and #3 (sentiment overlay) are where upside vs SPY has to come from; rotation is the "never get wrecked" sleeve.

**Current signal (2026-07-31 rebalance):** XLK / XLE / XLI, ⅓ each. *(Recorded for tracking only — not advice; nothing is being traded live.)*
