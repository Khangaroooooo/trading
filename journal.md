# Experiment journal

Rules: every experiment gets logged — including the losers (PBO discipline). Metrics per the scoreboard in Evervault `research/finance/findings/evaluation-metrics-and-sample-size.md`.

---

## #23 — Formally test w=95%/100% (top-2 sleeve + SPY) under R22's corrected CAGR bar (2026-07-20)

**Why:** R22 fixed R20's symmetric "CAGR within 1.5pt" guardrail (wrong-signed for a sleeve whose CAGR already beats SPY's) with a corrected, direction-aware bar (CAGR≥SPY, delta≤3.0pt), then ran a finer 60–90% grid under it — but stopped short of 100% and only *inferred*, from R20's already-published numbers, that w=100% would also clear the corrected bar. This experiment closes that inference gap: a small, pre-declared 2-point grid (95%, 100%) formally run and scored, plus w=75% as a sanity anchor. Script: `backtest_sleeve_blend_r23.py` (pure stdlib, reuses R8/R18/R20/R22's cached `closes.csv`, no new fetch).

**Results (net of 5bps/side, 2017-02→2026-07, n=114mo):**

| w(top2) | CAGR | Sharpe | Sortino | maxDD | $1→ | 2022 return | Bars cleared |
|---|---|---|---|---|---|---|---|
| 75% (sanity anchor) | 16.37% | 1.09 | 1.53 | −17.72% | $4.22 | +9.45% | 4/4 |
| 95% | 16.63% | 1.08 | 1.55 | −17.23% | $4.31 | +17.94% | 4/4 |
| 100% | 16.69% | 1.07 | 1.55 | −17.11% | $4.33 | +20.14% | 4/4 |

[SPY same window] CAGR 15.01%, Sharpe 0.97, Sortino 1.44, maxDD −23.93%.

Sanity checks passed exactly: w=75% and w=100% both reproduce R20/R22's published numbers to the decimal.

**Honest read: CONFIRMS INFERENCE, no new best.** Both w=95% and w=100% clear all four corrected bars — CAGR deltas (+1.62pt, +1.68pt) sit well inside the 3.0pt ceiling. R22's unrun inference about w=100% is now an exact-match, directly-run result. Neither weight dominates w=75% under R22's strict rule: Sharpe declines slightly past 75% (1.09→1.08→1.07), which alone blocks dominance even as Sortino/maxDD keep improving monotonically. Practically nothing changes about the program's standing recommendation (w=75% stays the default); this run's value is closing an open evidentiary gap in the R20/R22 thread, not producing a new lead.

**Caveats:** same single ~9.5yr/one-2022-bear window as R20/R22 (n=114). At w=100% the "blend-level rebalancing cost" is structurally ~0 (no SPY leg to rebalance against), so w=100% here is effectively R8 standalone. Only 5bps/side tested (R21's cost sweep not re-run at these weights). Full spec, locked criteria, and results: Evervault `research/finance/backtests/results/r23-top2-blend-w95-100-corrected-bar.md`.

---

## #24 — Split-window robustness check on the R20/R22 top-2-SPY blend (2026-07-20)

**Why:** R1 through R22 all share the same single ~9.5yr window (2017-02→2026-07) with exactly one bear-market observation (2022) — flagged as a caveat repeatedly but never actually tested. R24 cuts the R20/R22 blend's 114-month return series at its exact midpoint (index 57, fixed before running, no alternative splits tried) into H1 (2017-02→2021-10, no bear-market event) and H2 (2021-11→2026-07, contains all of 2022), and re-runs the same pre-declared bars (Sharpe/Sortino/maxDD ≥ SPY, CAGR within 3.0pt corrected band) against a SPY comparator over each half-window separately, for R20's adopted weights (25/50/75%). No new tuning, no new sleeve mechanics — pure re-slicing of the existing window. Script: `backtest_split_window_r24.py` (pure stdlib, reuses R8/R18/R20/R22's cached `closes.csv`, no new fetch).

**Results (n=57/half):**

| Half | w=25% bars | w=50% bars | w=75% bars | CAGR Δ vs SPY (same half) |
|---|---|---|---|---|
| H1 (2017-02→2021-10, no bear) | 2/4 | 1/4 | 1/4 | −0.74 / −1.53 / −2.37pt |
| H2 (2021-11→2026-07, has 2022) | 4/4 | 3/4 | 3/4 | +1.73 / +3.40 / +5.02pt |
| Full window (R20/R22 reference) | 4/4 | 4/4 | 4/4 | +0.52 / +0.97 / +1.36pt |

**Honest read: the full-window dominance is almost entirely a 2022/H2 artifact, not a consistent-across-regimes property.** In H1 (pure bull, no crash), Sleeve A alone trails SPY outright (14.66% vs 17.92% CAGR) and every blend weight fails 3–4 of the 4 bars — only maxDD survives at every weight. In H2, 100% of the full-window edge shows up: w=25% clears all 4 bars cleanly; w=50%/75% clear 3/4, missing only because they win *too much* CAGR (+3.40pt/+5.02pt, over the 3.0pt cap) — the same guardrail-asymmetry pattern R22 flagged at w=100% on the full window. Not a full rejection: w=25% still clears every bar in the hard half using the intended crisis-defense mechanism, and H1 isn't a collapse (Sharpe within ~0.06 of SPY at w=25%). The honest characterization going forward: **this is a bear-market hedge, not an all-weather edge** — consistent with R1's original "defensive baseline" framing, now measured directly instead of assumed.

**Caveats:** n=57/half is thin (noisy Sortino especially); H2 is still a single event (2022) re-isolated into its own half, not a second independent bear-market observation — R24 answers "does the full-window number depend on averaging in the bear market" (yes) but not "does the strategy work in a *different* bear market" (still unresolved, N=1). One locked split point, not a sweep over cut dates. Full spec, locked criteria, and results: Evervault `research/finance/backtests/results/r24-split-window-robustness.md`.

---

## #22 — Finer blend-weight grid around R20's w=75% (top-2 sleeve + SPY) (2026-07-20)

**Why:** R20's coarse 5-point grid (0/25/50/75/100%) found w=75% the single best point — highest Sharpe/Sortino, shallowest maxDD among qualifiers — with w=100% only "failing" the CAGR guardrail because Sleeve A's CAGR is *above* SPY's by more than the original symmetric 1.5pt bar (a guardrail-design artifact, not a real defect, per R20's own write-up). R20's curve is monotonic/dominance-driven (unlike R18/R19's tradeoff curve), so a finer grid here has a real chance of finding a genuinely better point rather than just re-confirming sampling noise, per the R16 lesson. Locked spec: 7-point grid w∈{60,65,70,75,80,85,90}%, identical Sleeve A (R8 top-2)/blend methodology to R18/R20, but with a corrected, direction-aware CAGR bar (CAGR≥SPY and delta≤3.0pt, pre-declared before running) instead of the original symmetric one. Dominance-vs-w=75% check also pre-declared (must clear all 4 bars AND beat w=75% on ≥2 of Sharpe/Sortino/maxDD without losing on the third). Script: `backtest_sleeve_blend_r22.py` (pure stdlib, reuses R8/R18/R20's cached `closes.csv`, no new fetch).

**Results (net of costs, 2017-02→2026-07, n=114mo):**

| w(top2) | CAGR | Sharpe | Sortino | maxDD | 2022 return | Bars (corrected) |
|---|---|---|---|---|---|---|
| 60% | 16.15% | 1.09 | 1.50 | −18.08% | +3.41% | 4/4 |
| 65% | 16.23% | 1.09 | 1.51 | −17.96% | +5.39% | 4/4 |
| 70% | 16.30% | 1.09 | 1.51 | −17.84% | +7.41% | 4/4 |
| 75% | 16.37% | 1.09 | 1.53 | −17.72% | +9.45% | 4/4 (=R20 exactly) |
| 80% | 16.44% | 1.09 | 1.54 | −17.60% | +11.53% | 4/4 |
| 85% | 16.51% | 1.09 | 1.52 | −17.47% | +13.63% | 4/4 |
| 90% | 16.57% | 1.08 | 1.54 | −17.35% | +15.77% | 4/4 |

SPY same window: CAGR 15.01%, Sharpe 0.97, Sortino 1.44, maxDD −23.93%, 2022 −18.17%.

**Honest read: CONFIRMS w=75% region, no new best.** All seven weights clear the corrected 4-bar test — R20's coarse-grid dominance holds smoothly across the whole 60–90% band, no gaps or cliffs. But per the pre-declared strict dominance rule, **nothing beats w=75%**: Sharpe never rises above 1.09 (it's flat 60–80%, ticks down to 1.08 at 90%), which alone blocks every candidate regardless of CAGR/maxDD moving favorably with w. CAGR and maxDD both improve monotonically as w rises (CAGR +0.07pt, maxDD +0.12pt per 5pt of w) but the moves are small relative to n=114 and one bear-market observation; Sortino wobbles in a tight 1.50–1.54 band with no clean peak. Practical takeaway: the whole 60–90% range is close to statistically indistinguishable on a risk-adjusted basis — w=75% (R20's original pick) remains a perfectly good default, and this closes the weight-fine-tuning thread rather than opening a new lead. Flagged as inference, not re-run here: R20's own published w=100% numbers, rescored against this experiment's corrected bar, would also clear all 4 (CAGR delta +1.68pt ≤ 3.0pt) — confirming that R20's "w=100% fails" was purely an artifact of the original guardrail's symmetric design.

**Caveats:** same single ~9.5yr/one-2022-bear window as the R1/R8/R18/R20 family — Sortino/maxDD separation from SPY is still driven almost entirely by that one event. Blend-rebalance cost model (SPY-leg-only, 5bps/side on drift) is a modeled assumption, identical to R18/R20/R21, not observed execution. Only 5bps/side tested for Sleeve A's own cost at this finer resolution — R21 already showed the wider family's dominance compresses but doesn't flip up to 20bps/side; not re-verified here. Full spec, locked criteria, and results: Evervault `research/finance/backtests/results/r22-top2-blend-fine-grid-around-75.md`.

---

## #21 — Cost-sensitivity re-sweep on R20's top-2/SPY blend (2026-07-20)

**Why:** R20 found w=25/50/75% of R8's top-2 sleeve blended with SPY beat SPY on Sharpe, Sortino, maxDD, *and* CAGR simultaneously (dominance, not a tradeoff) — but only tested Sleeve A's internal trading cost at the primary 5bps/side level. R20's own write-up flagged the gap: R8's standalone cost sweep already showed its CAGR edge over SPY thinning under stress, so does R20's dominance survive the same stress? Locked spec: identical R18/R20 blend methodology (5-point weight grid, SPY-leg blend-rebalancing cost held fixed at 5bps/side) with Sleeve A's own internal cost swept across 0/5/10/20bps/side, all four levels × all five weights reported. Same four pre-declared bars as R20 (Sharpe≥SPY, Sortino≥SPY, maxDD shallower, CAGR within 1.5pt). Script: `backtest_sleeve_blend_r21_cost_sweep.py` (pure stdlib, reuses R1/R3/R5/R8/R10/R18/R20 cached `closes.csv`, no new fetch).

**Results (net of costs, 2017-02→2026-07, n=114mo) — bars cleared out of 4:**

| Sleeve A cost/side | w=25% | w=50% | w=75% | w=100% |
|---|---|---|---|---|
| 0 bps (gross) | 4/4 | 4/4 | 3/4 (CAGR +1.62pt) | 3/4 (CAGR +2.03pt) |
| 5 bps (primary, = R20) | 4/4 | 4/4 | 4/4 | 3/4 (CAGR +1.68pt) |
| 10 bps (stress) | 4/4 | 4/4 | 4/4 | 4/4 |
| 20 bps (stress) | 4/4 | 4/4 | 4/4 | 4/4 |

CAGR edge over SPY erosion table (matches R8's format): w=75% goes +1.62%→+1.36%→+1.09%→+0.57% across 0/5/10/20bps; w=100% (=R8 standalone) reproduces R8's own numbers exactly, +2.03%→+1.68%→+1.33%→+0.63%. Sanity check passed: 5bps row reproduces R20 to the decimal.

**Honest read: ROBUST.** All three of R20's adopted weights (25/50/75%) clear all four bars at every cost level including the 20bps/side stress scenario — the dominance result isn't an artifact of the optimistic 5bps assumption, since Sharpe/Sortino/maxDD are driven mostly by 2022 defense (barely touched by trading-cost assumptions), and the CAGR guardrail never breaks for these three even as the edge visibly thins (w=75%'s edge nearly halves, +1.36pt→+0.57pt). Worth flagging: w=100% flips 3/4→4/4 as costs *rise* — the opposite direction from every other robustness check in this program. This isn't concentration getting safer under stress; it's the same guardrail asymmetry R20 already flagged (the 1.5pt bar was built to catch a defensive sleeve giving up too much upside, and here it's instead catching a high-CAGR sleeve's edge being too large at low cost — rising costs compress that edge back toward the bar, passing it for the wrong reason). The w=25/50/75% ROBUST verdict doesn't depend on this artifact.

**Caveats:** same single ~9.5yr/one-2022-bear window as the R1/R8/R18/R20 family — the Sharpe/Sortino/maxDD robustness shown here largely restates "2022 defense survives cost stress," never in serious doubt since 2022 defense is signal-timing, not cost-sensitive; the CAGR erosion (the genuinely uncertain part) does erode steadily and w=75%'s edge is down to +0.57pt at 20bps, thin enough that live slippage could plausibly erase it even though it never flips negative here. Blend-rebalancing cost (SPY leg) held fixed at 5bps/side throughout — a joint sweep of both cost parameters together is out of scope, not run here. 20bps/side is a deliberately pessimistic stress scenario for SPDR sector ETFs. Full spec, locked criteria, and results: Evervault `research/finance/backtests/results/r21-top2-blend-cost-sensitivity.md`.

---

## #20 — Fixed-weight blend: R8 top-2 concentration sleeve + SPY B&H (2026-07-20)

**Why:** R18 blended R10/V2 (vol-target-scaled rotation) with SPY and found w=25–50% beats SPY on Sharpe/Sortino/maxDD within a CAGR guardrail. R8's top-2 concentration sleeve is a different candidate — it already beats SPY outright on raw CAGR (16.69% vs 15.01%) with no vol-target overlay. Open question: does blending this higher-CAGR, un-scaled sleeve with SPY find an even better risk-adjusted point than blending the vol-target sleeve did? Locked spec, identical methodology to R18: 5-point weight grid (w=0/25/50/75/100% top-2 rotation, rest SPY), monthly fixed-mix rebalance with the same blend-level rebalancing cost model (SPY-leg-only, 5bps/side on weight drift) on top of Sleeve A's own already-net R8 returns. Same pre-declared ADOPT bar as R18: Sharpe≥SPY AND Sortino≥SPY AND maxDD shallower AND CAGR within 1.5pt, simultaneously. Script: `backtest_sleeve_blend_r20.py` (pure stdlib, reuses R1/R3/R5/R8/R10/R18 cached `closes.csv`, no new fetch).

**Results (net of costs, 2017-02→2026-07, n=114mo):**

| w(top2) | CAGR | Vol | Sharpe | Sortino | maxDD | $1→ | 2022 return | Bars cleared |
|---|---|---|---|---|---|---|---|---|
| 0% (pure SPY) | 15.01% | 15.69% | 0.97 | 1.44 | −23.93% | $3.78 | −18.17% | 3/4 |
| 25% | 15.53% | 15.06% | 1.04 | 1.49 | −18.93% | $3.94 | −9.67% | **4/4** |
| 50% | 15.99% | 14.83% | 1.08 | 1.48 | −18.32% | $4.09 | −0.47% | **4/4** |
| 75% | 16.37% | 15.02% | 1.09 | 1.53 | −17.72% | $4.22 | +9.45% | **4/4** |
| 100% (pure R8) | 16.69% | 15.61% | 1.07 | 1.55 | −17.11% | $4.33 | +20.14% | 3/4 (CAGR +1.68pt, over guardrail) |

Sanity checks passed exactly: w=0% reproduces SPY B&H; w=100% reproduces R8's published standalone numbers (CAGR 16.69%, maxDD −17.11%) to the decimal.

**Honest read: ADOPTED w=25/50/75%, a stronger result than R18.** All three qualifying weights beat SPY on Sharpe, Sortino, maxDD, *and* CAGR simultaneously — strict dominance, not a tradeoff — because Sleeve A (R8) already beats SPY on raw CAGR outright, so blending doesn't have to sacrifice upside for defense. w=75% is the best single point (highest Sharpe/Sortino, shallowest qualifying maxDD, biggest CAGR edge still inside the guardrail). Directly beats R18 at comparable weights: w=25% here gives CAGR 15.53% (+0.52pt vs SPY) against R18's 14.36% (−0.65pt vs SPY), with Sortino/maxDD essentially tied. Worth flagging: w=100% "fails" the CAGR guardrail only because its CAGR is 1.68pt *above* SPY's — the symmetric 1.5pt bar was designed (in R18) to catch a defensive sleeve giving up too much upside, not this direction; taken literally it's 3/4, but a reader could reasonably treat "CAGR too high" as a non-issue.

**Caveats:** same single ~9.5yr/one-2022-bear window as the rest of the R1 family. R8's own cost sweep showed its CAGR edge over SPY thinning under cost stress (+2.03pt gross → +0.63pt at 20bps/side) — this run only tested the primary 5bps/side level, so the dominance shown would likely compress (not necessarily vanish) at higher costs; a cost-sensitivity re-sweep on the blend itself is a natural next step, not run here. Blend-rebalancing cost model (SPY-leg-only, 5bps/side on drift) is modeled, not observed execution — identical assumption to R18. Full spec, locked criteria, and results: Evervault `research/finance/backtests/results/r20-top2-spy-blend.md`.

---

## #18 — Fixed-weight blend: R10/V2 vol-target rotation sleeve + SPY B&H (2026-07-20)

**Why:** Every prior experiment (R1–R17) evaluated a strategy as 100% of capital in isolation vs. SPY. The one adopted candidate, R10/V2 (SPY-vol-target-scaled rotation @15%), wins on Sortino/maxDD but trails SPY on raw CAGR (12.06% vs 15.01%). New axis, not a re-parameterization: does blending the defensive sleeve with plain SPY at a fixed weight recover CAGR while keeping meaningful downside protection? Locked spec: 5-point weight grid (w=0/25/50/75/100% rotation, rest SPY), monthly fixed-mix rebalance with a blend-level rebalancing cost (SPY-leg-only, 5bps/side on weight drift) on top of Sleeve A's own already-net R10/V2 returns. Pre-declared ADOPT bar: Sharpe≥SPY AND Sortino≥SPY AND maxDD shallower AND CAGR within 1.5pt, simultaneously. Script: `backtest_sleeve_blend_r18.py` (pure stdlib, reuses R1/R3/R5/R10 cached `closes.csv`, no new fetch).

**Results (net of costs, 2017-02→2026-07, n=114mo):**

| w(rotation) | CAGR | Vol | Sharpe | Sortino | maxDD | $1→ | 2022 return | Bars cleared |
|---|---|---|---|---|---|---|---|---|
| 0% (pure SPY) | 15.01% | 15.69% | 0.97 | 1.44 | −23.93% | $3.78 | −18.17% | 3/4 |
| 25% | 14.36% | 14.23% | 1.02 | 1.47 | −19.04% | $3.58 | −12.91% | **4/4** |
| 50% | 13.65% | 13.05% | 1.05 | 1.50 | −16.90% | $3.37 | −7.43% | **4/4** |
| 75% | 12.88% | 12.24% | 1.06 | 1.51 | −15.59% | $3.16 | −1.75% | 3/4 |
| 100% (pure R10/V2) | 12.06% | 11.86% | 1.02 | 1.47 | −14.27% | $2.95 | +4.14% | 3/4 |

Sanity checks passed exactly: w=0% reproduces SPY B&H; w=100% reproduces R10/V2's published numbers to the decimal (validates the reimplementation).

**Honest read: ADOPT w=25% (w=50% a viable alternative).** First result in the program to beat SPY on Sharpe *and* Sortino *and* maxDD simultaneously while staying inside the CAGR guardrail — no single 100%-allocation sleeve managed that (R10/V2 alone gives up 2.95pt CAGR, missing the 1.5pt bar). It's arithmetic on two already-known return streams, not new alpha: R10/V2 is a good risk-reducer that's too conservative held alone, and 25–50% of it layered onto SPY captures most of the defensive benefit (2022: −12.91% to −7.43% vs SPY's −18.17%) for only 0.65–1.36pt of CAGR. w=25% gives up the least CAGR of the two that clear all four bars; w=50% trades more CAGR for meaningfully better maxDD/2022 defense — a real choice by risk tolerance, not strict dominance. Changes the program's standing recommendation: a 25–50% rotation / SPY blend beats either pure-SPY or pure-R10/V2 on risk-adjusted terms.

**Caveats:** single ~9.5yr window with one bear event (2022) driving nearly all the maxDD/Sortino separation — the monotonic weight curve is a mechanical property of blending two return series over one regime, not independent cross-regime evidence. Blend-rebalancing cost model is a reasonable assumption, not observed execution. Doesn't reduce reliance on R10/V2's own signal-risk caveats — those still apply in full to the rotation leg. Full spec, locked criteria, and results: Evervault `research/finance/backtests/results/r18-sleeve-blend-voltarget-spy.md`.

---

## #14 — Single-name news-sentiment overlay feasibility, corrected gate (2026-07-20)

**Why:** R4 found sector-ETF headlines almost never keyword-relevant (129/90,119 matched, overlay fired 4x/9.5yrs — non-event) but its own Phase A audit showed the 5 mega-caps it sampled had dense, keyword-relevant coverage; they just couldn't clear R4's fixed "≥8 qualifying symbols" gate, sized for an 11-symbol sector universe. Re-ran the same two-phase gated test on R6's 15-name mega-cap universe with a gate corrected to scale with universe size (≥80% of symbols qualify, locked before fetching). Scripts: `news_audit_r14.py` (Phase A fetch/audit), `backtest_news_overlay_r14.py` (Phase B, reuses R6/R12's cached closes + fresh news cache).

**Phase A (corrected gate, ≥4 headlines/mo avg AND <25% zero-coverage months AND ≥80%/≥12-of-15 symbols):** 120,982 headlines fetched. 14/15 symbols qualify (only META fails, on bursty-not-absent coverage: 86.66/mo avg but 52.8% zero-coverage months) → **PASS, Phase B runs.**

**Phase B results (net of 10bps/side, 2017-03→2026-07-17, n=2358d):**

| Variant | CAGR | Vol | Sharpe | Sortino | maxDD | $1→ | Avg turnover | Triggers | Stand-aside days |
|---|---|---|---|---|---|---|---|---|---|
| V0 Baseline (equal-weight, no overlay) | 21.04% | 18.94% | 1.10 | 1.35 | −32.17% | $5.97 | 0.042% | 0 | 0 |
| V1 News stand-aside overlay | 14.07% | 16.86% | 0.87 | 1.01 | −31.32% | $3.43 | 4.820% | 1,109 | 4,748 |
| SPY B&H | 14.78% | — | 0.85 | 1.03 | −33.79% | $3.63 | — | — | — |

Lexicon match rate 4,141/120,982 (3.42%) — an order of magnitude denser than R4's 0.14%. Unlike R4, the overlay actually fires (1,109 triggers).

**Honest read: REJECTED — overlay is actively harmful, not a non-event.** Phase A's corrected gate worked as intended, confirming single names (unlike sector ETFs) have real keyword-relevant news density. But once the overlay actually fires, it hurts on every axis: CAGR falls 21.04%→14.07% (−6.97pts, the biggest single-lever hit of any filter tested in this program), Sharpe/Sortino both drop *below SPY's own* (0.87/1.01 vs SPY's 0.85/1.03), and 2022 — the one year an overlay like this should help — gets *worse*, not better (−22.82% vs V0's −18.88%, both vs SPY's −18.17%). Standing aside after a 3-day bad-headline cluster reads as selling into weakness and buying back after the move, not genuine defense. Closes the news-overlay thread from both ends: R4 = too sparse to fire on ETFs, R14 = wrong-signed when it does fire on single names.

**Caveats:** single ~9.5yr/one-2022-bear window (n=2358d, same regime-count caveat as every experiment in this program). Stand-aside destination is cash at 0% (not BIL) — a conservative bias *against* the overlay, but nowhere near large enough to close a −6.97pt CAGR gap. Lexicon unchanged from R4/R6; a severity-weighted or ML-classified signal is a different, heavier experiment, not a parameter tweak. Full spec, locked criteria, and results: Evervault `research/finance/backtests/results/r14-single-name-news-sentiment-overlay.md`.

---

## #17 — Single-stock reversal cadence sweep: biweekly & monthly (2026-07-20)

**Why:** R6 (daily, 15-name, N=3) found a real gross reversal signal (18.0% CAGR, Sharpe 0.80) destroyed by ~388x/yr-annualized turnover at 15bps/side (net CAGR −34.1%). R12/V1 (weekly, same universe) cut turnover to ~79x/yr and flipped net CAGR positive (6.3%) but still missed every ADOPT bar and lost more than SPY in 2022. This adds two more pre-declared cadence points — biweekly and monthly — on the identical universe/signal/cost spec, to test whether the turnover-vs-edge tradeoff is monotonic (no sweet spot) or has a local optimum. Script: `backtest_reversal_r17.py` (pure stdlib, reuses R6/R12's cached 15-name closes, no new fetch).

**Results (net of 15bps/side costs, 2016-01→2026-07-17):**

V1 Biweekly, n=274 periods (246 invested):

| | CAGR | Vol | Sharpe | Sortino | maxDD | $1→ |
|---|---|---|---|---|---|---|
| Reversal (net) | 12.5% | 20.5% | 0.68 | 0.93 | −35.9% | $3.48 |
| Reversal (gross) | 19.3% | 20.5% | 0.97 | 1.27 | −32.8% | $6.40 |
| SPY B&H | 15.4% | 17.5% | 0.91 | 1.00 | −30.8% | $4.51 |

V2 Monthly, n=125 periods (107 invested):

| | CAGR | Vol | Sharpe | Sortino | maxDD | $1→ |
|---|---|---|---|---|---|---|
| Reversal (net) | 15.9% | 18.1% | 0.91 | 1.27 | −36.2% | $4.64 |
| Reversal (gross) | 18.8% | 18.1% | 1.05 | 1.41 | −34.4% | $6.00 |
| SPY B&H | 15.6% | 15.1% | 1.04 | 1.49 | −23.9% | $4.52 |

**Honest read: both REJECTED, but the cadence question is now answered.** Turnover falls monotonically across daily→weekly→biweekly→monthly (~388x→79x→39x→17x/yr) and net CAGR/Sharpe rise monotonically in step (−34.1%/−1.59 → 6.3%/0.39 → 12.5%/0.68 → 15.9%/0.91) — a clean cost-drag curve, not a hump, so there's no hidden sweet spot between R6 and R2. Monthly (V2) is the closest miss yet: first variant in this family to beat SPY on raw net CAGR (15.9% vs 15.6%), but Sharpe still misses (0.91 vs 1.04) and 2022 is actually its worst point of all (−31.1% vs SPY −18.2%) — every cadence tested loses more than SPY in 2022, so slowing the clock fixes the turnover-cost problem but never fixes the signal's pro-cyclical (amplifier, not diversifier) character. Closes the single-stock reversal cadence thread — R6/R12/R17 now form a consistent three-strike rejection.

**Caveats:** same single ~10.5yr/one-2022-bear window (N=1 regime) as R2/R6/R12 — the 2022 disqualifier rests on one observation. Biweekly (2-ISO-week) and monthly (calendar-month) bucketing aren't uniform-length blocks, so turnover multiples aren't perfectly comparable across variants. −3% crash filter threshold carried over unchanged from R6/R12, not re-derived per period scale. Full spec, locked criteria, and results: Evervault `research/finance/backtests/results/r17-reversal-cadence-sweep.md`.

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

---

## #2 (price-only) — Short-term weekly mean reversion (2026-07-18)

**Why this and not PEAD:** the intended #2 (PEAD event swings) is blocked on a missing earnings calendar (no Finnhub key yet). Ran a tractable price-only reversal candidate in the meantime. Rules locked before running, nothing tuned. Script: `backtest_reversal.py`.

**Setup:** 11 SPDR sectors + QQQ; weekly (Fri close); rank by prior-week return; hold bottom 3 ("oversold") equal-weight next week; skip weeks where SPY prior-week < −5% (crash filter); **10 bps/side** cost (turnover is brutal). Data: Alpaca SIP daily, dividend-adjusted, 2016-01→2026-07. Window: 548 weeks (538 invested).

**Results (net of costs):**

| | CAGR | Vol | Sharpe | Sortino | maxDD | $1 grows to |
|---|---|---|---|---|---|---|
| Reversal | 3.9% | 18.4% | 0.30 | 0.42 | −29.2% | $1.50 |
| SPY B&H | 15.7% | 16.8% | 0.95 | 1.19 | −31.6% | $4.65 |

**Honest read: REJECTED.** Loses decisively on every axis — a quarter of SPY's Sharpe, higher vol, similar drawdown, ~4× worse terminal wealth. Avg weekly turnover 1.45 (~76×/yr) means costs alone are a heavy drag, but even gross it isn't compelling. Sector-ETF short-term reversal is not an edge here (consistent with the literature: reversal lives more at the single-stock/overnight level and gets arbitraged at the liquid-ETF level). Good clean negative — no reason to iterate on it.

**Takeaway for the program:** rotation (#1) remains the defensive baseline; reversal is off the list. Real upside vs SPY still has to come from **PEAD** (needs the Finnhub earnings key — Khang's 5-min action) and the **news-sentiment overlay** (Alpaca `get_news` is available; heavier build). Those are the next two experiments.

---

## #3 — Rotation robustness sweep (2026-07-19)

**Why:** stress-test whether R1's defensive profile (loses to SPY on raw CAGR, wins on 2022/maxDD) is robust to nearby config choices or a single-config fluke. Six variants locked before running, one-factor-at-a-time off the R1 baseline: top-2, top-4, 6m lookback, skip-last-month (12-1) momentum, weekly rebalance. Script: `backtest_rotation_sweep.py` (pure-stdlib rewrite — no pandas install available in the unattended run; V0 reproduces R1's numbers exactly, validating the reimplementation).

**Results (net of costs, 5bps/side):**

| Variant | CAGR | Sharpe | maxDD | $1→ | Beats SPY 2022 | Beats SPY maxDD |
|---|---|---|---|---|---|---|
| V0 Baseline (=R1) | 13.64% | 0.99 | −18.06% | $3.37 | YES | YES |
| V1 Top-2 | 16.69% | 1.07 | −17.11% | $4.33 | YES | YES |
| V2 Top-4 | 12.33% | 0.96 | −16.44% | $3.02 | YES | YES |
| V3 6m lookback | 6.70% | 0.54 | −16.20% | $1.91 | YES | YES |
| V4 Skip-last-month | 14.19% | 1.00 | −15.55% | $3.49 | YES | YES |
| V5 Weekly rebalance | 9.91% | 0.66 | −32.97% | $2.47 | YES (barely) | **NO** |

**Honest read: ROBUST, with one clean exception.** 5/6 variants pass both pre-declared defensive tests (2022 return beats SPY, maxDD shallower than SPY) — the defensive profile is a property of monthly-rebalance dual-momentum, not an R1-specific fluke. **V5 (weekly rebalance) is the one real failure**: maxDD is worse than SPY's over the same window, and Sortino craters to 0.72 — don't rebalance this signal weekly, it whipsaws a slow-moving momentum signal. **V3 (6m lookback) keeps the defensive shape but is a much worse strategy overall** (CAGR 6.70%, Sharpe 0.54) — shortening the lookback is a bad idea even though it technically passes the defense test. **V1 (top-2) is the standout** — beats SPY's raw CAGR (16.69% vs 15.01%) while keeping the best defense of the grid — but it's one of six pre-declared variants, not a validated standalone strategy; flagging as a lead for a fresh, separately-locked follow-up, not adopting it as the new baseline (that would be exactly the parameter-fishing this program exists to avoid).

**Caveats:** same single-decade/one-2022-bear window as R1 (n≈114 monthly obs, n=1 bear-market event); V3's window starts 6mo earlier due to shorter lookback warm-up; V5's turnover-driven cost sensitivity wasn't separately stress-tested; execution-at-signal-close convention carried over from R1.

**Role going forward:** R1's rotation baseline is now validated as a *class*, not a lucky config. Weekly rebalance ruled out. Top-2 concentration is the most promising open thread — candidate for a dedicated next experiment.

---

## #5 — Regime filter overlay on R1 rotation (2026-07-19)

**Why:** R1/R3 established rotation as a defensive sleeve that lags SPY on raw CAGR but wins on 2022/maxDD. Regime-detection literature (Barroso/Santa-Clara, Moreira/Muir, Faber) says 200dma trend gates and vol-target scaling are drawdown reducers, not return enhancers — tested whether stacking either on R1's exact signal helps. Four variants locked before running: V0 baseline, V1 200dma gate (SPY below 200d SMA → 100% BIL), V2 vol-target scale (scale weights by min(1, 12%/trailing-20d-SPY-vol), capped at 1.0, no leverage), V3 combined. Script: `backtest_regime_filter.py` (pure stdlib, reuses R1/R3's cached closes.csv). V0 exactly reproduced R1/R3's numbers, validating the reimplementation.

**Results (net of costs, 5bps/side, 2017-02→2026-07, n=114mo):**

| Variant | CAGR | Sharpe | Sortino | maxDD | $1→ | Avg turnover/mo |
|---|---|---|---|---|---|---|
| V0 Baseline (=R1) | 13.64% | 0.99 | 1.34 | −18.06% | $3.37 | 48.3% |
| V1 200dma gate | 9.24% | 0.85 | 1.11 | −16.20% | $2.31 | 69.3% |
| V2 Vol-target scale | 11.02% | 1.03 | 1.44 | −13.10% | $2.70 | 61.3% |
| V3 Combined | 8.62% | 0.90 | 1.14 | −13.25% | $2.19 | 72.2% |

**Honest read: REJECT V1 and V3; V2 is a marginal near-miss, not a win.** V1 and V3 both whipsaw around the 200dma — CAGR falls 4.4–5.0pts and Sortino *worsens* despite maxDD improving, turnover jumps ~50%. V2 is the interesting case: it's the only variant improving maxDD, Sortino, *and* Sharpe simultaneously (matching the literature's actual claim), but CAGR falls 2.62pts — a hair past the pre-declared "~2pt" guardrail, so calling it a miss rather than rounding it into a pass. Flagged as a lead for a dedicated follow-up (higher vol target, or scale off the rotation book's own vol instead of SPY's), not adopted. Cross-cutting finding: all three overlays *increase* turnover — R1's own per-sector absolute-momentum-vs-BIL filter was already doing most of the defensive work; a second, coarser whole-book regime signal mostly added whipsaw cost, not incremental defense.

**Caveats:** same single ~9.5yr/one-2022-bear window as R1/R3; 200dma computed on trading days; 12% vol target is literature-informed, not calibrated to this universe; no leverage tested (capped at 1.0 given paper-account context). Full spec, criteria, and results: Evervault `research/finance/backtests/results/r5-regime-filter-on-rotation.md`.

---

## #6 — Single-stock daily reversal check (2026-07-19)

**Why:** R2 rejected short-term reversal on sector ETFs; literature says the effect lives at the single-stock level. Rules locked before running (15 liquid mega-caps, daily rebalance, prior-day-return signal, bottom-3 long, −3% SPY crash filter, 15bps/side, single config — no sweep). Script: `backtest_single_stock_reversal.py` (pure stdlib, fresh Alpaca SIP daily pull, dividend-adjusted, 2016-01→2026-07).

**Results (2016-01-06→2026-07-17, n=2647 trading days, 2615 invested):**

| | CAGR | Vol | Sharpe | Sortino | maxDD | $1→ |
|---|---|---|---|---|---|---|
| Reversal, net of costs (locked) | −34.1% | 24.4% | −1.59 | −2.16 | −98.9% | $0.01 |
| Reversal, gross (diagnostic) | 18.0% | 24.4% | 0.80 | 1.06 | −41.7% | $5.68 |
| SPY B&H | 15.0% | 17.6% | 0.88 | 1.07 | −33.8% | $4.34 |

Avg daily turnover 1.539 (max possible 2.0) — annualized ≈388×.

**Honest read: REJECTED decisively, but cleanly explained.** The signal is real gross of costs (18.0% CAGR, Sharpe 0.80 — beats SPY, consistent with the reversal literature). But bottom-3-of-15 picked fresh every day has almost no day-to-day persistence, so turnover is nearly total (1.539/2.0) — at 15bps/side that's ~23bps/day of drag, compounding to a −99% wipeout over the window. Every single calendar year is negative net of costs, regardless of SPY's direction that year. This isn't "reversal doesn't exist" — R2 already showed no edge even gross at the ETF level; R6 shows the mechanism explicitly: the edge exists but daily/narrow-universe reversal requires trading nearly the whole book every day, and no realistic cost survives that. A cost sweep wouldn't change the conclusion (even 5bps/side implies ~−87% over the window) — the honest next thread, if any, is a wider universe or slower (weekly) single-stock frequency, not a cost sweep on this exact config.

**Caveats:** 15-mega-cap universe only, doesn't generalize to small/mid-caps; execution-at-signal-close convention (optimistic); single ~10.5yr window. Full spec, criteria, and results: Evervault `research/finance/backtests/results/r6-single-stock-reversal.md`.

---

## #4 — News-sentiment overlay feasibility, sector ETFs (2026-07-20)

**Why:** rules locked in advance across two gated phases — Phase A audits Alpaca/Benzinga news coverage for 11 SPDR sector ETFs + 5 mega-caps; Phase B (a keyword-lexicon stand-aside overlay on R1's rotation) only runs if a pre-declared coverage gate clears. Scripts: `news_audit.py` (Phase A), `backtest_news_overlay.py` (Phase B, daily engine reusing R1's cached prices).

**Phase A:** fetched 90,119 headlines (2016-01→now). Sector ETFs: 9/11 symbols clear ≥4 headlines/mo avg and <25% zero-coverage months → **gate PASSES**. Mega-caps individually blew past the per-symbol bar (146–246 headlines/mo) but the gate's "≥8 qualifying symbols" threshold structurally can't be met by a 5-symbol universe — a drafting bug in the locked spec, noted rather than silently fixed; doesn't affect the sector-ETF result.

**Phase B (net of costs, 5bps/side, daily engine, 2017-02→2026-07, n=2377 days):**

| Variant | CAGR | Sharpe | Sortino | maxDD | $1→ | Triggers | Stand-aside days |
|---|---|---|---|---|---|---|---|
| V0 Baseline (=R1, daily engine) | 13.71% | 0.80 | 0.98 | −31.49% | $3.36 | 0 | 0 |
| V1 News stand-aside overlay | 13.58% | 0.80 | 0.97 | −31.49% | $3.32 | 4 | 15 |
| SPY B&H | 15.13% | 0.87 | 1.05 | −33.79% | $3.78 | — | — |

**Honest read: REJECT as a non-event, not as a negative signal.** Only 129 of 90,119 headlines (0.14%) both matched the negative-keyword lexicon and tagged a sector ETF, so the overlay fired just 4 times in 9.5 years (15 stand-aside days out of 2,377). Every metric moves by noise (CAGR −13bps, Sharpe unchanged). This means the coverage-density gate (raw headline volume) was the wrong proxy for "will the overlay ever fire" — sector-ETF headlines are mostly generic wrapper coverage, not single-name-style adverse-event language, so a keyword lexicon built for corporate events rarely matches. n=4 is too small to say the mechanism doesn't work, only that it wasn't meaningfully tested here. V0 also serves as a reimplementation check: daily-engine CAGR 13.71% vs R1's original monthly-engine 13.64% (close); maxDD is much deeper on the daily engine (−31.49% vs R1's −18.06%) purely from measurement frequency (daily catches intramonth troughs monthly sampling hides) — SPY shows the same effect, so the relative comparison still holds.

**Takeaway for the program:** sector-ETF keyword-overlay news is off the list — not because sentiment is disproven, but because the signal essentially never fires at the ETF level. If sentiment overlays are worth another look, the next thread is single-name stocks (dense, keyword-relevant Benzinga coverage per Phase A's mega-cap numbers) with a correctly-sized gate, and probably the LLM-materiality-scoring design over a keyword lexicon. Full spec, gate definition, and results: Evervault `research/finance/backtests/results/r4-news-sentiment-overlay-feasibility.md`.

---

## #8 — Top-2 sector rotation concentration, standalone confirmation + cost sensitivity (2026-07-20)

**Why:** R3's sweep found top-2-of-11-sectors beat both the R1 baseline and SPY on raw CAGR while keeping the best defensive profile in the grid — but as one of six pre-declared variants answering a different question (robustness), not a standalone hypothesis test. Charter flagged it for a dedicated, freshly-locked confirmation run. Since the cached price history (2016-01→2026-07) is already the full pull with no room to extend the window, this run used the other lever the charter offered: a pre-declared cost-sensitivity sweep, since concentrating to 2 names raises idiosyncratic single-sector risk. Script: `backtest_top2_confirmation.py` (pure stdlib, reuses R1/R3/R5's cached `closes.csv`).

**Results (2017-02-28→2026-07-17, n=114 monthly obs):**

| Cost/side | CAGR | Vol | Sharpe | Sortino | maxDD | $1→ | Avg turnover/mo |
|---|---|---|---|---|---|---|---|
| 0 bps (gross) | 17.05% | 15.61% | 1.09 | 1.58 | −17.07% | $4.46 | 50.9% |
| 5 bps (primary) | 16.69% | 15.61% | 1.07 | 1.55 | −17.11% | $4.33 | 50.9% |
| 10 bps | 16.34% | 15.61% | 1.05 | 1.52 | −17.16% | $4.21 | 50.9% |
| 20 bps | 15.64% | 15.61% | 1.01 | 1.45 | −17.84% | $3.98 | 50.9% |
| SPY B&H | 15.01% | 15.69% | 0.97 | 1.44 | −23.93% | $3.78 | — |

**Honest read: CONFIRMED, not fragile — but the edge is thinning.** At the primary 5bps/side, exactly reproduces R3/V1's numbers (16.69% CAGR, −17.11% maxDD — validates the standalone reimplementation) and passes all three pre-declared tests: beats SPY on CAGR (16.69% vs 15.01%), 2022 return (20.14% vs −18.17%), and maxDD (−17.11% vs −23.93%). The cost sweep shows turnover is flat (~51%/mo) regardless of cost assumption — concentration's real cost here is idiosyncratic single-sector risk, not extra turnover — but the CAGR edge over SPY does erode steadily under cost stress, from +2.03pt gross to +0.63pt at a (unrealistically high) 20bps/side. Never flips negative in this sample, so this isn't R2/R6's "cost kills it" failure mode, but a +0.63pt edge at the stressed end is thin enough that live slippage could plausibly erase it.

**Caveats:** identical single ~9.5yr/one-2022-bear window as R1/R3/R5 (n=114, n=1 bear event) — a replication of the same period, not independent out-of-sample evidence. Concentrating to 2 names raises idiosyncratic single-sector risk even though turnover doesn't change. 20bps/side is a deliberate stress scenario, not a realistic SPDR spread. Full spec and results: Evervault `research/finance/backtests/results/r8-top2-concentration-followup.md`.

---

## #10 — Vol-target scaling follow-up on R1/R5 (2026-07-20)

**Why:** R5/V2 (scale R1's rotation weights by min(1, 12%/trailing-20d-SPY-vol), unlevered) improved maxDD, Sortino, and Sharpe simultaneously vs the unscaled baseline but missed R5's pre-declared CAGR guardrail (≤2pt loss) by 0.62pt — flagged as a near-miss lead, not adopted. Two untested levers, locked in advance: (a) raise the vol target from 12% to 15%, (b) scale off the rotation book's own realized vol instead of SPY's. Five pre-declared variants (V0 baseline, V1 SPY@12%=reproduction check, V2 SPY@15%, V3 own-vol@12%, V4 own-vol@15%). Script: `backtest_vol_target_followup.py` (pure stdlib, reuses R1/R3/R5's cached `closes.csv`).

**Results (2017-02-28→2026-07-17, n=114 monthly obs):**

| Variant | CAGR | Sharpe | Sortino | maxDD | $1→ | Avg turnover/mo |
|---|---|---|---|---|---|---|
| V0 Baseline (=R1) | 13.64% | 0.99 | 1.34 | −18.06% | $3.37 | 48.3% |
| V1 SPY vol-target @12% (=R5/V2) | 11.02% | 1.03 | 1.44 | −13.10% | $2.70 | 61.3% |
| V2 SPY vol-target @15% | 12.06% | 1.02 | 1.47 | −14.27% | $2.95 | 57.5% |
| V3 Own-vol target @12% | 10.68% | 1.00 | 1.40 | −12.04% | $2.62 | 66.5% |
| V4 Own-vol target @15% | 11.80% | 0.98 | 1.34 | −14.84% | $2.88 | 62.5% |
| SPY B&H | 15.01% | — | — | −23.93% | $3.78 | — |

**Honest read: ADOPT V2; lever (a) works, lever (b) doesn't.** V1 exactly reproduces R5/V2 (validates the reimplementation). V2 (SPY vol-target raised to 15%) is the first vol-scaling variant across R5+R10 to clear all three pre-declared bars at once: maxDD improves (−14.27% vs V0's −18.06%), Sortino improves to 1.47 (best in the whole family), and CAGR falls only 1.58pt (13.64%→12.06%) — inside the 2pt guardrail with room to spare. Simply using a less aggressive (higher) vol target recovered enough CAGR while still improving risk-adjusted return. V3/V4 (own-portfolio vol instead of SPY vol) both underperform their SPY-based counterparts at matching targets — the rotation book's own trailing-20d vol, concentrated in 3 sectors, is noisier than SPY's and triggers more/worse de-risking, not better. V4 technically clears the CAGR guardrail but ties (doesn't improve) Sortino vs V0, so it fails the pre-declared bar on a technicality; not worth chasing further since the underlying mechanism (own-vol adds noise) is now shown twice. V2's 12.06% CAGR still trails SPY B&H (15.01%) — this is a defensive/risk-adjusted candidate (best Sortino/Sharpe of the R1–R10 family), same role as R1/R3, not a CAGR-beater.

**Caveats:** same single ~9.5yr/one-2022-bear window as R1/R3/R5/R8 (n=114). "Own-portfolio vol" is defined from the *unscaled* base-weight daily series (locked to avoid circularity), not a recursive/scaled definition. 15% is one discrete step above R5's 12%, not a swept optimum. Full spec, locked criteria, and results: Evervault `research/finance/backtests/results/r10-vol-target-scaling-followup.md`.

---

## #15 — Stack R10/V2 vol-target scaling on R8's top-2 concentration (2026-07-20)

**Why:** R8 confirmed top-2-of-11-sector concentration beats both the R1/R3 top-3 baseline and SPY on raw CAGR (16.69% vs 15.01% at 5bps/side). R10 separately adopted SPY-vol-target-@15% scaling (capped 1.0x, unlevered) on the *top-3* R1 book, clearing all three of its guardrails. Neither had been tested combined — worth checking whether vol-target's defensive benefit transfers cleanly to the more concentrated, higher-idiosyncratic-risk top-2 base. Two pre-declared variants locked before running: V0 baseline (top-2, no overlay — reproduction check), V1 (top-2 base weights scaled by R10/V2's exact overlay mechanic, min(1, 15%/trailing-20d SPY vol), capped 1.0). Script: `backtest_top2_voltarget_stack.py` (pure stdlib, reuses R1/R3/R5/R8/R10's cached `closes.csv`).

**Results (net of costs, 5bps/side, 2017-02→2026-07, n=114mo):**

| Variant | CAGR | Vol | Sharpe | Sortino | maxDD | $1→ | Avg turnover/mo |
|---|---|---|---|---|---|---|---|
| V0 Baseline (=R8 @5bps) | 16.69% | 15.61% | 1.07 | 1.55 | −17.11% | $4.33 | 50.88% |
| V1 Top-2 + SPY vol-target @15% | 14.28% | 13.11% | 1.09 | 1.65 | −15.16% | $3.55 | 59.86% |
| SPY B&H | 15.01% | — | — | — | −23.93% | $3.78 | — |

**Honest read: REJECT the stack.** V0 exactly reproduces R8 (validates the reimplementation). The vol-target overlay's risk-reduction mechanism transfers directionally to the top-2 base — maxDD improves (−15.16% vs −17.11%), Sortino improves (1.65 vs 1.55), Sharpe ticks up (1.09 vs 1.07), same qualitative effect R10 found on top-3. But the CAGR cost is bigger here (2.41pt lost vs R10/V2's 1.58pt on top-3), breaching the pre-declared 2pt guardrail and — more importantly — flipping the combined strategy from beating SPY on CAGR (top-2 alone: +1.68pt) to trailing it (14.28% vs 15.01%, −0.73pt). Turnover also rose more than in either parent experiment (59.86%/mo, vs R8's 50.88% and R10/V2's 57.5%): the same SPY-vol-driven scale factor forces bigger weight swings on a more concentrated, higher-swing base. Top-2's edge over SPY was already thin (R8's cost sweep showed it eroding to +0.63pt under cost stress) — vol-target's CAGR tax, a reasonable trade on the diversified top-3 book, is large enough to fully erase that thinner edge on the concentrated one. Neither R8 nor R10 is invalidated individually; it's specifically the combination that fails.

**Caveats:** identical single ~9.5yr/one-2022-bear window as R1/R3/R5/R8/R10 (n=114, n=1 bear event) — a replication of the same period, not independent out-of-sample evidence. Scale factor driven by SPY vol only (R10 already showed own-portfolio vol is noisier, not re-tested here). Single cost level (5bps/side), no fresh cost sweep this iteration. Full spec, locked criteria, and results: Evervault `research/finance/backtests/results/r15-top2-voltarget-stack.md`.

---

## #9 — Rotation cost-sensitivity stress test (2026-07-20)

**Why:** R3's own caveats flagged that no cost-sensitivity sweep had been run on the rotation baseline, and specifically that V5's (weekly rebalance) maxDD failure could be a cost-drag artifact rather than a signal problem — left as an open question. This run sweeps cost/side (0/5/10/20bps) on two of R3's variants: V0 (monthly baseline, = R1) and V5 (weekly rebalance, R3's one clean failure). V1–V4 out of scope by design (R8 already covers V1/top-2's cost sensitivity; V2/V3/V4 showed no cost-related anomaly in R3). Script: `backtest_rotation_cost_sensitivity.py` (pure stdlib, reuses R1/R3/R5/R8/R10's cached `closes.csv`).

**Results:**

V0 Baseline (monthly), n=114, 2017-02-28→2026-07-17:

| Cost/side | CAGR | maxDD | Beats SPY 2022 | Beats SPY maxDD |
|---|---|---|---|---|
| 0 bps | 13.97% | −17.97% | YES | YES |
| 5 bps | 13.64% | −18.06% | YES | YES |
| 10 bps | 13.31% | −18.15% | YES | YES |
| 20 bps | 12.67% | −18.33% | YES | YES |
| SPY B&H | 15.01% | −23.93% | — | — |

V5 Weekly rebalance, n=497, 2017-01-13→2026-07-17:

| Cost/side | CAGR | maxDD | Beats SPY 2022 | Beats SPY maxDD |
|---|---|---|---|---|
| 0 bps (gross) | 10.61% | **−32.78%** | YES | **NO** |
| 5 bps | 9.91% | −32.97% | YES | NO |
| 10 bps | 9.22% | −33.16% | YES | NO |
| 20 bps | 7.84% | −33.53% | NO (flips) | NO |
| SPY B&H | 14.93% | −31.65% | — | — |

**Honest read: V0 is cost-robust; V5's failure is signal-driven, not cost-driven.** Reimplementation check passed (5bps numbers match R3 exactly for both variants). V0's defensive edge (beats SPY on 2022 return and maxDD) holds at every cost level up to a 20bps stress test — the CAGR gap to SPY widens only 0.98pt from 5bps to 20bps, well inside the pre-declared 2pt threshold. V5 is the more important finding: at **0bps — zero cost, pure gross returns** — its maxDD is already worse than SPY's (−32.78% vs −31.65%). The whipsaw R3 found is baked in before a single basis point of cost is applied, so "don't rebalance dual-momentum weekly" is a signal/cadence-mismatch story, not a cost-drag story. Costs do compound the damage — V5's CAGR gap to SPY roughly doubles from −4.32pt gross to −7.09pt at 20bps (turnover is ~2.7x more frequent annualized than V0's), and at the 20bps stress level even the 2022-beats-SPY claim narrows to a wash — but removing costs entirely would not have saved V5.

**Caveats:** identical single ~9.5yr/one-2022-bear window as R1/R3/R5/R8/R10 (n=114 monthly / n=497 weekly, n=1 bear event) — re-cut by cost assumption, not new out-of-sample evidence. V5's weekly observations are highly autocorrelated (overlapping ~12m signal), so effective sample size is well below 497. 20bps/side is a deliberate stress scenario, not a realistic SPDR spread. Full spec, locked criteria, and results: Evervault `research/finance/backtests/results/r9-rotation-cost-sensitivity.md`.

---

## #16 — Vol-target sweep 13-18% around R10/V2's adopted 15% (2026-07-20)

**Why:** R10 tested only two discrete SPY-vol-target levels (12%, 15%) and adopted 15% (the only variant clearing all 3 guardrails) — flagged as "one discrete step, not a swept optimum." This run maps the local curve with a symmetric 6-point pre-declared grid (13/14/15/16/17/18%), SPY-vol lever only (R10's own-vol lever already rejected, not retested). Script: `backtest_vol_target_sweep.py` (pure stdlib, reuses R1/R3/R5/R10's cached `closes.csv`).

**Results (net of costs, 5bps/side, 2017-02→2026-07, n=114mo):**

| Variant | CAGR | Sharpe | Sortino | maxDD | $1→ | Avg turnover/mo |
|---|---|---|---|---|---|---|
| V0 Baseline (=R1) | 13.64% | 0.99 | 1.34 | −18.06% | $3.37 | 48.25% |
| V13 @13% | 11.49% | 1.03 | 1.47 | −13.49% | $2.81 | 59.93% |
| V14 @14% | 11.85% | 1.03 | 1.48 | −13.88% | $2.90 | 58.46% |
| V15 @15% (=R10/V2) | 12.06% | 1.02 | 1.47 | −14.27% | $2.95 | 57.52% |
| V16 @16% | 12.22% | 1.02 | 1.44 | −14.66% | $2.99 | 57.01% |
| V17 @17% | 12.31% | 1.01 | 1.41 | −15.05% | $3.01 | 56.40% |
| V18 @18% | 12.38% | 0.99 | 1.38 | −15.44% | $3.03 | 55.74% |

**Honest read: keep 15%, no change — the sweep confirms it rather than beats it.** V15 exactly reproduces R10/V2 (validates the reimplementation). Every metric moves smoothly and monotonically across the grid (CAGR up, maxDD deeper as target rises; Sortino humps at 14% then declines above 15%) — no cliff or magic number near 15%. V14 technically clears the pre-declared "replace" bar (Sortino 1.48 > V15's 1.47, CAGR only −0.21pt) but V13 *ties* V15's Sortino exactly while losing more CAGR, showing the "14% peak" is noise-level (n=114, one bear event) rather than a real optimum — reporting it as a new best would be overfitting to this one window despite technically passing a pre-declared test. Verdict: R10's 15% stays adopted; the value here is ruling out a sharp exploitable optimum being left nearby (13–18% all land in a tight CAGR 11.49–12.38% / Sortino 1.38–1.48 band).

**Caveats:** same single ~9.5yr/one-2022-bear window as R1/R5/R10 (n=114) — maps in-sample sensitivity, not out-of-sample robustness. The pre-declared replace-bar margin (Sortino↑, ΔCAGR ≥ −0.5pt) was tight enough to be satisfied by noise — a design lesson for future refinement sweeps. SPY-vol source only; own-vol not retested. Full spec, locked criteria, and results: Evervault `research/finance/backtests/results/r16-vol-target-sweep-13-18.md`.

---

## #12 — Weekly single-stock reversal & wider-universe reversal (2026-07-20)

**Why:** R6 found a real gross single-stock reversal signal (15-name mega-cap universe, daily rebalance, bottom N=3, 1-day hold: 18.0% CAGR gross, Sharpe 0.80 > SPY) destroyed by ~154%/yr-annualized turnover at 15bps/side (net CAGR −34.1%). Two independent, pre-declared levers tested to cut turnover, both locked before running: V1 slows to weekly rebalance (same 15-name universe); V2 widens the universe to 40 liquid large-caps (same daily frequency, still N=3). Script: `backtest_reversal_r12.py` (pure stdlib, reuses R6's 15-name cache + new 40-name fetch).

**Results (net of 15bps/side costs, 2016-01→2026-07-17):**

V1 Weekly, 15-name, n=548wk (517 invested):

| | CAGR | Vol | Sharpe | Sortino | maxDD | $1→ |
|---|---|---|---|---|---|---|
| Reversal (net) | 6.3% | 21.6% | 0.39 | 0.53 | −46.1% | $1.90 |
| Reversal (gross) | 19.6% | 21.6% | 0.94 | 1.26 | −39.4% | $6.59 |
| SPY B&H | 15.7% | 16.8% | 0.95 | 1.19 | −31.6% | $4.65 |

V2 Daily, 40-name, n=2647d (2615 invested):

| | CAGR | Vol | Sharpe | Sortino | maxDD | $1→ |
|---|---|---|---|---|---|---|
| Reversal (net) | −40.7% | 29.1% | −1.64 | −2.27 | −99.6% | $0.00 |
| Reversal (gross) | 14.0% | 29.2% | 0.60 | 0.81 | −56.6% | $3.98 |
| SPY B&H | 15.0% | 17.6% | 0.88 | 1.07 | −33.8% | $4.34 |

**Honest read: both REJECTED.** V1 (weekly) is the first version of this mechanic that doesn't implode — turnover halves (~79x/yr vs R6's ~154x/yr) and net CAGR turns positive (6.3%) with a gross signal still competitive with SPY (19.6% gross, Sharpe 0.94) — but it misses SPY on every net metric and, tellingly, loses *more* than SPY in 2022 (−41.7% vs −18.2%), the opposite of a diversifier. LEAD, not adopted. V2 (widen universe) is a clean negative: the "more candidates → stickier picks → less churn" premise doesn't hold — turnover went *up* 2.8x (154x→435x/yr) and gross Sharpe dropped (0.80→0.60), because a bigger pool fills the bottom-3 slots with more one-off noisy movers rather than persistent reversal candidates. Terminal wealth $0.00 per $1; every year 2016–2026 negative for the strategy.

**Caveats:** same single ~10.5yr/one-2022-bear window (N=1 regime) as R2/R6. V1's −3% weekly crash filter is a same-threshold carryover from R6's daily version, not re-derived for weekly scale. V2's 40-name universe is large/mega-cap only — "widen" here means widen among mega-caps, not a true breadth test. Full spec, locked criteria, and results: Evervault `research/finance/backtests/results/r12-weekly-reversal-wider-universe.md`.

---

## #11 — Regime-gate whipsaw diagnosis: 2-month confirmation rule on R5's 200dma gate (2026-07-20)

**Why:** R5/V1's raw 200dma gate on the R1 rotation sleeve was rejected — maxDD improved but Sortino fell and CAGR dropped 4.4pts, with turnover jumping 48%→69%/mo from whipsaw. Before discarding trend-gating entirely, tested the standard practitioner fix: a confirmation rule requiring the regime signal to persist for 2 consecutive month-ends before the effective gate state switches. Single pre-declared variant, locked before running. Script: `backtest_regime_confirmation.py` (pure stdlib, reuses R1/R3/R5's cached `closes.csv`).

**Results (net of 5bps/side, 2017-02→2026-07, n=114mo):**

| Variant | CAGR | Sharpe | Sortino | maxDD | $1→ | Avg turnover/mo |
|---|---|---|---|---|---|---|
| V0 Baseline (=R1) | 13.64% | 0.99 | 1.34 | −18.06% | $3.37 | 48.25% |
| V1 Confirmed 200dma gate (2mo) | 11.78% | 0.96 | 1.24 | −18.17% | $2.88 | 50.58% |
| R5/V1 raw gate (reference) | 9.24% | 0.85 | 1.11 | −16.20% | $2.31 | 69.3% |

Raw 200dma signal flips 20x across 114 months; confirmed gate flips only 8x.

**Honest read: REJECTED as a regime filter.** The confirmation rule works exactly as designed on the whipsaw side — turnover drops from R5/V1's 69.3%/mo to 50.58%/mo (close to baseline), and CAGR/Sortino drag roughly halve relative to the raw gate. But it doesn't just cut whipsaw cost, it cuts the entire point of the gate: maxDD is unchanged from baseline (−18.17% vs V0's −18.06%) and actually *worse* than the raw gate's −16.20%. Requiring 2 months of confirmation makes the gate too slow to protect against the drawdown event itself. Per-year detail shows the confirmed gate notably underperforms V0 in 2020 (0.51% vs 11.16% — the fast COVID crash/recovery, where a 2-month lag misses both the exit and reentry) and in 2025 (6.96% vs 16.09%, a normal year paying reaction-lag cost with no crash to defend against); it does look better in 2022/2023 (7.83%/16.81% vs V0's 5.11%/11.59%), so the net effect isn't uniformly bad, it's a wash-to-negative on full-sample risk metrics. Closes off "smooth the 200dma gate" as a lever — trend-gate whipsaw here isn't fixable with a simple persistence rule; it trades whipsaw cost for reaction lag, and the lag lands on exactly the drawdown protection the gate exists to provide.

**Caveats:** same single ~9.5yr/one-2022-bear window as R1/R3/R5 (n=114). N=2 confirmation months is the standard practitioner default, not tuned to this dataset, but also the only value tested (a sweep would need its own locked spec). Full spec, locked criteria, and results: Evervault `research/finance/backtests/results/r11-regime-gate-confirmation.md`.

---

## #13 — Cost-breakeven turnover analysis (methodology note, not a backtest) (2026-07-20)

**Why:** R2, R6, R12, and R17 all died to the same turnover-cost mechanism, re-derived from scratch each time — and R12/R17 left an unresolved inconsistency where R6's annualized turnover was described as both "~154x/yr" and "≈388×". No new market data or trading signal here — pure arithmetic over numbers already published in R6/R9/R12/R17's results notes, cross-validated two ways: R9 holds turnover fixed and sweeps cost (0/5/10/20bps); R6/R12/R17 hold cost fixed (15bps/side) and sweep turnover (17x–435x/yr). Script: `turnover_cost_breakeven.py` (pure stdlib, hardcoded/cited inputs, no fetch).

**Model:** `annual CAGR drag (%) ≈ turnover_annualized(two-way multiple) × cost_per_side(%) × multiplier`.

**Results:** multiplier = actual drag ÷ naive-linear-predicted drag, computed at 11 independent points. For turnover ≤100x/yr (n=9, spanning both sweep axes and both strategy families): multiplier clusters 1.10–1.16 (spread 1.06) → **validated constant, 1.125**. Above 100x/yr (n=2: R6 at 388x, R12/V2 at 435x): multiplier drops to 0.84–0.90 — the linear model overpredicts, consistent with CAGR's −100% floor saturating the effect once cost drag approaches the size of gross returns.

**154x-vs-388x resolved:** applying the validated 1.125x multiplier, 388x implies a multiplier of 0.80 (same direction/magnitude as the other >100x point, 0.84); 154x implies 2.00 (wildly outside the validated band). **(inference)** 388x is very likely the correct figure for R6; 154x was likely a mislabel from annualizing with ~100 trading days instead of ~252 (1.539/day × 100 ≈ 154 vs × 252 ≈ 388).

**Reference table (validated range, ≤100x/yr turnover):** e.g. at 15bps/side, 40x/yr turnover costs ~6.75% CAGR/yr; at 80x/yr it's ~13.5%/yr. Inverted: to survive 79x/yr turnover (R12/V1's weekly reversal) at 15bps/side needs >8.9% gross annual edge just to hold a 1pt net edge — consistent with why every reversal cadence in the R6→R12→R17 family struggled.

**Honest read: closes R13, no strategy verdict changes.** A genuinely useful reference tool — the tight 1.06 multiplier spread across two structurally different strategies and two different sweep axes is real cross-validation, not a fitted curve. Caveats: calibrated to this program's single ~9–10yr window (2016–2026), so the 1.125x figure is horizon-specific even if the mechanism (cost drag compounds over time) is general; only 2 strategy families represented (both momentum/trend-adjacent); n=9/n=2 is thin even though tight; the 154x/388x resolution is inference from the drag pattern, not a re-run of either script's raw turnover series. Full spec, locked criteria, multiplier table, and reference tables: Evervault `research/finance/backtests/results/r13-cost-breakeven-turnover-analysis.md`.

---

## #19 — Finer blend-weight grid around R18's adopted region (2026-07-20)

**Why:** R18 blended R10/V2 (vol-target rotation sleeve @15%) with SPY B&H on a coarse 5-point grid (0/25/50/75/100%) and found w=25%/50% both clear all 4 pre-declared bars. R18 flagged the grid as coarse and named a finer sweep around the adopted region as the natural follow-up. Pre-declared grid w ∈ {10,20,30,40,60}% fills the gaps (25/50/75/100% not re-run — reused from R18's published numbers). Script: `backtest_sleeve_blend_r19.py` (pure stdlib, reuses R1/R3/R5/R10/R18's cached `closes.csv`, no new fetch).

**Results (net of costs, 2017-02→2026-07, n=114mo):**

| w(rotation) | CAGR | Sharpe | Sortino | maxDD | $1→ | 2022 return | Bars cleared |
|---|---|---|---|---|---|---|---|
| 10% | 14.76% | 0.99 | 1.45 | −22.00% | $3.70 | −16.09% | 4/4 |
| 20% | 14.50% | 1.01 | 1.47 | −20.04% | $3.62 | −13.98% | 4/4 |
| 30% | 14.22% | 1.03 | 1.47 | −18.04% | $3.54 | −11.83% | 4/4 |
| 40% | 13.94% | 1.04 | 1.48 | −17.43% | $3.46 | −9.65% | 4/4 |
| 60% | 13.35% | 1.06 | 1.51 | −16.37% | $3.29 | −5.18% | 3/4 (CAGR misses 1.5pt bar) |

[SPY same window] CAGR 15.01%, Sharpe 0.97, Sortino 1.44, maxDD −23.93%.

Sanity checks passed exactly: Sleeve A reproduces R10/V2, Sleeve B reproduces R18's SPY numbers, to the decimal. All 5 new points slot cleanly into R18's monotonic curve — no cliff, no bug.

**Honest read: LEAD, standing recommendation formally unchanged.** Pre-declared dominance test: does any new-grid weight beat BOTH R18's w=25% and w=50% on Sharpe/Sortino/maxDD while clearing its own CAGR bar? **No weight dominates both.** But w=40% strictly dominates w=25% alone (better Sharpe, Sortino, maxDD, still clears CAGR bar) — meaning w=25% is provably not Pareto-optimal, R18's coarse grid just didn't have a point between 25–50% to show it. w=40% does not dominate w=50% (worse on all three risk metrics there). Per the locked rule (dominate *both* named weights to supersede), this is a LEAD not an adoption change: w=50% remains the strongest all-around point in the family; w=40% is a better-reasoned choice than w=25% specifically if forced to pick a lower-allocation point.

**Caveats:** identical to R18 — same single ~9.5yr/one-2022-bear window (n=114); arithmetic interpolation on two already-published return streams, not new signal; R24's split-window finding (edge is a bear-market-hedge property, not all-weather) applies unchanged. Full spec, locked criteria, and results: Evervault `research/finance/backtests/results/r19-voltarget-blend-fine-grid.md`.

---

## #25 — Pre-2016 data feasibility check: can we reach a second independent bear market? (2026-07-20)

**Why:** R24's split-window test showed the program's full-window "dominance" result is a bear-market-hedge property built entirely on the 2022 event — H1/H2 just re-isolate the same crash, so "does this edge hold in a *different* crash" was still N=1 and unanswered. Before leaving that as a permanent caveat, checked whether Alpaca's data API can actually reach back to the 2008–2009 financial crisis for a genuinely independent second observation. Locked as an explicit data-audit-only iteration (same precedent as R4's Phase A) — Phase B (an actual R1-methodology backtest on a 9-sector universe over 2007–2010) was only to run if the feasibility gate passed. Script: `backtest_pre2016_feasibility_r25.py` (pure stdlib, fresh fetch, not the existing 2016+ cache).

**Phase A result: FAIL.** Requested `start=2006-01-01` for SPY, BIL, and the 9 pre-2016 SPDR sectors (XLRE/XLC excluded up front — they didn't exist yet) on both `feed=sip` and `feed=iex`. Every symbol returned 0 bars — a clean `200 {"bars":{},"next_page_token":null}`, not a 403/entitlement error. Root-cause diagnostic against the same endpoint: requesting `start` at 2006, 2010, 2013, 2015-01, and even 2015-12 all return the *same* first bar — **2016-01-04** — exactly matching the existing `data/cache/closes.csv`'s own start date from R1. This is a hard floor on this account's market-data endpoint, not a symbol-specific listing-date issue.

**Honest read: FAIL, closes the thread with a decisive negative.** Phase B correctly never ran. The 2008–2009 crisis is not reachable through this program's current data access regardless of feed or requested window. R24's "N=1, unanswered" caveat now has a concrete reason rather than an open action item — a second independent bear-market observation would need a different data vendor (outside this unattended, no-install toolchain) or a real future bear market to accumulate as new data.

**Caveats:** only establishes the floor for Alpaca's `/v2/stocks/bars` endpoint on this specific account/plan — says nothing about other market-data products or vendors, which are out of scope for this iteration. Full spec, locked criteria, and diagnostic table: Evervault `research/finance/backtests/results/r25-pre2016-data-feasibility.md`.

---

## #26 — First live paper deployment of the adopted strategy (2026-07-20)

**What:** Deployed the program's standing recommendation — **R20 top-2 sector-rotation sleeve + SPY blend at w=75%** — into the Alpaca paper account at Khang's request, market open ~14:39 ET.

**Signal computed live (trailing 12-mo total return, current price ÷ dividend-adjusted close on 2025-07-18):** XLE +39.7%, XLK +36.4%, XLV +23.3%, XLI +19.3%, XLB +13.0%, XLRE +11.7%, XLU +10.2%, XLF +8.5%, XLP +7.5%, XLC +5.8%, XLY +4.1%; BIL +3.8%. **Top-2 = XLE, XLK**, both far above BIL → no cash substitution. Target blend = 37.5% XLE / 37.5% XLK / 25% SPY.

**Sizing decision (Khang):** liquidate the $40.7k pre-existing BTC/ETH (not part of this program; had protective GTC stop-limit sells attached — canceled first) and deploy the full ~$100.4k portfolio, no margin.

**Fills (all market, day, filled at quote, slippage <0.02%):**
- XLE 646 @ $58.23 = $37,613 (37.5%)
- XLK 212 @ $176.88 = $37,490 (37.4%)
- SPY 33 @ $743.69 = $24,539 (24.4%)
- Cash ~$750. Portfolio ≈ $100,394.

**Rebalance discipline:** strategy is monthly, month-end. Next rebalance due ~2026-07-31: recompute top-2 by 12-mo momentum, re-blend to 37.5/37.5/25, trade the deltas. Client_order_ids: `kd-rot-{xle,xlk,spy}-20260720`.

**Caveat carried in:** per R24, the edge is a bear-market-hedge property (N=1, 2022) not an all-weather CAGR-beater; this is a live forward test of a single-window backtest, not independent validation.

## #26b — Risk overlay added to live deployment (2026-07-20)

**Context:** Khang asked to "improve the portfolio 1–3%/day, risk 1–2%." Pushed back honestly — 1–3%/day compounds to ×12–1640/yr, ~30x better than Medallion, not achievable; the program's own R6/R12/R17 already showed daily rebalancing gets destroyed by turnover. The "risk 1–2%" half IS sound (per-position risk sizing). Khang chose: add 1–2% risk stops.

**Implemented:** GTC stop-market sells on all three positions, uniform ~5% below entry (positions are 37/37/25% weighted, so 5% keeps each within 1–2% account risk):
- XLE 646 @ stop 55.30 → risk $1,893 (1.89%)
- XLK 212 @ stop 168.00 → risk $1,882 (1.87%)
- SPY 33 @ stop 706.40 → risk $1,231 (1.23%)
- Total portfolio heat if all trigger ≈ 5.0% (under the 7% charter cap). Client_order_ids `kd-rot-{xle,xlk,spy}-stop-20260720`.

**Caveat (important, not in the R20 backtest):** R20/R8 were tested with NO intra-month stops — pure monthly rebalance. Adding stops is a risk overlay layered on top; it can stop out mid-drawdown then miss a recovery before month-end, which would change realized returns vs the backtest. Worth a future backtest (stop-augmented rotation) before treating it as validated. At month-end rebalance, these stops must be canceled/replaced alongside the position changes.

---

## #27 — R26: single-stock momentum on a higher-return universe (2026-07-20)

**Why:** Khang asked to push returns higher, held to the charter promotion bar. Took the exact adopted R20 machinery (monthly top-N 12-mo momentum, abs-filter vs BIL, SPY blend) and swapped 11 sector ETFs → 40 mega-cap single stocks. Primary config pre-declared top-3 w=100%.

**Result: 2/4 bars — REJECTED as specified.** top-3 w=100%: CAGR 32.65% (PASS vs SPY 15.01%), Sharpe 0.95 (FAIL <1), maxDD −26.78% (FAIL, deeper than −20% AND deeper than SPY), 2022 +0.42% (PASS). The huge CAGR is bought with 36% vol — leverage-like risk, not a free lunch.

**Lead flagged, NOT adopted (would be parameter-fishing):** top-5 clears all 4 bars (Sharpe 1.26, maxDD −20.50%, 2022 +1.28%, CAGR 37%); more names → more diversification → monotonically better risk metrics. Worth a freshly-locked R27 confirmation.

**Dominant caveat:** universe = today's 40 mega-caps backfilled to 2016 → survivorship bias inflates ALL single-stock configs; the sector R20 result does not suffer this. So R26's CAGR edge over R20 is partly an artifact. A real follow-up needs a point-in-time universe (hard given Alpaca's 2016 data floor, R25).

**Verdict: no change to live strategy.** R20 sector top-2 + SPY w=75% stays deployed. Full note: Evervault `research/finance/backtests/results/r26-single-stock-momentum.md`. Script `backtest_single_stock_momentum_r26.py`.

---

## #28 — R27: top-5 single-stock momentum, locked standalone confirmation (2026-07-20)

**Why:** R26's exploratory grid (not a pre-declared decision config) showed top-5 w=100% appearing to clear all 4 promotion bars, while the pre-declared primary (top-3) was rejected. Per this program's own precedent (R3's exploratory lead → R8's standalone confirmation), a sweep-surfaced lead gets a freshly-locked, standalone run before being taken seriously — this is that run for top-5.

**Result: 3/4 bars — REJECTED, and it corrects a reporting error in R26.** Primary (top-5, w=100%, 5bps/side): CAGR 37.03% (PASS), Sharpe 1.26 (PASS), maxDD **−20.50% (FAIL** — R26 had listed this as a pass, but −20.50% is deeper than the −20% bar, not shallower), 2022 +1.28% (PASS). The underlying number matches R26's exactly; only the bar-scoring was wrong there.

**Cost sweep (0/5/10/20bps/side, pre-declared):** maxDD ranges −20.36% to −20.89% — fails the −20% bar at every cost level including zero-cost gross returns. Not a fluke of the cost assumption; the miss is small (~0.5pt) but structural.

**Verdict: no change to live strategy.** R20 sector top-2 + SPY w=75% stays deployed. Closes the R26/R27 single-stock-momentum thread — neither the pre-declared primary nor its best exploratory alternative clears all 4 bars once correctly graded. Full note: Evervault `research/finance/backtests/results/r27-single-stock-momentum-top5-confirmation.md`. Script `backtest_single_stock_momentum_r27.py`.
