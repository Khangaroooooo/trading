"""
R13 - cost-breakeven turnover analysis (methodology note, not a backtest).

Pure arithmetic over already-published numbers from this program's own results
notes. No market data is fetched here. Every input is cited to its source file.
"""

# Dataset A: fixed turnover, varying cost. Source: results/r9-rotation-cost-sensitivity.md
# (turnover_annualized as a two-way multiple, cost in bps/side, CAGR in %)
dataset_a = [
    # (label, turnover_annualized, cost_bps, cagr_pct)
    ("R9/V0 0bps",  5.784, 0,  13.97),
    ("R9/V0 5bps",  5.784, 5,  13.64),
    ("R9/V0 10bps", 5.784, 10, 13.31),
    ("R9/V0 20bps", 5.784, 20, 12.67),
    ("R9/V5 0bps",  12.646, 0,  10.61),
    ("R9/V5 5bps",  12.646, 5,  9.91),
    ("R9/V5 10bps", 12.646, 10, 9.22),
    ("R9/V5 20bps", 12.646, 20, 7.84),
]

# Dataset B: fixed cost (15bps/side), varying turnover. Gross vs net CAGR at the
# same cost level. Sources: results/r6-single-stock-reversal.md,
# results/r12-weekly-reversal-wider-universe.md, results/r17-reversal-cadence-sweep.md
dataset_b = [
    # (label, turnover_annualized, cost_bps, gross_cagr_pct, net_cagr_pct)
    ("R17/V2 monthly",        17,  15, 18.8, 15.9),
    ("R17/V1 biweekly",       39,  15, 19.3, 12.5),
    ("R12/V1 weekly",         79,  15, 19.6, 6.3),
    ("R6 daily 15-name",      388, 15, 18.0, -34.1),
    ("R12/V2 daily 40-name",  435, 15, 14.0, -40.7),
]

print("=== Dataset A: fixed turnover, varying cost (delta from 0bps baseline) ===")
points = []
for variant_turnover in (5.784, 12.646):
    rows = [r for r in dataset_a if r[1] == variant_turnover]
    baseline = [r for r in rows if r[2] == 0][0]
    for label, turnover, cost, cagr in rows:
        if cost == 0:
            continue
        actual_drag = baseline[3] - cagr
        predicted_drag = turnover * (cost / 100)
        multiplier = actual_drag / predicted_drag
        points.append((label, turnover, cost, actual_drag, predicted_drag, multiplier))
        print(f"{label:16s} turnover={turnover:8.3f}x cost={cost:2d}bps "
              f"actual_drag={actual_drag:5.2f}pt predicted={predicted_drag:5.2f}pt "
              f"multiplier={multiplier:5.2f}")

print("\n=== Dataset B: fixed cost (15bps/side), varying turnover (gross vs net) ===")
for label, turnover, cost, gross, net in dataset_b:
    actual_drag = gross - net
    predicted_drag = turnover * (cost / 100)
    multiplier = actual_drag / predicted_drag
    points.append((label, turnover, cost, actual_drag, predicted_drag, multiplier))
    print(f"{label:20s} turnover={turnover:6.1f}x cost={cost:2d}bps "
          f"actual_drag={actual_drag:6.2f}pt predicted={predicted_drag:6.2f}pt "
          f"multiplier={multiplier:5.2f}")

print("\n=== Multiplier by turnover range ===")
low_mid = [p for p in points if p[1] <= 100]
high = [p for p in points if p[1] > 100]
lo_vals = [p[5] for p in low_mid]
hi_vals = [p[5] for p in high]
print(f"Turnover <=100x/yr: n={len(lo_vals)}, min={min(lo_vals):.2f}, max={max(lo_vals):.2f}, "
      f"mean={sum(lo_vals)/len(lo_vals):.3f}, spread(max/min)={max(lo_vals)/min(lo_vals):.2f}")
print(f"Turnover  >100x/yr: n={len(hi_vals)}, min={min(hi_vals):.2f}, max={max(hi_vals):.2f}, "
      f"mean={sum(hi_vals)/len(hi_vals):.3f}")

validated_multiplier = sum(lo_vals) / len(lo_vals)

print(f"\nValidated multiplier (turnover <=100x/yr, n={len(lo_vals)}): {validated_multiplier:.3f}")

print("\n=== R6/R12 388x-vs-154x cross-check ===")
r6_gross, r6_net, r6_cost = 18.0, -34.1, 15
r6_actual_drag = r6_gross - r6_net
for candidate_turnover in (154, 388):
    pred_linear = candidate_turnover * (r6_cost / 100)
    pred_corrected = pred_linear * validated_multiplier
    ratio_to_validated = r6_actual_drag / pred_corrected
    print(f"turnover={candidate_turnover}x: linear_pred={pred_linear:.1f}pt "
          f"corrected_pred={pred_corrected:.1f}pt actual={r6_actual_drag:.1f}pt "
          f"actual/corrected_pred={ratio_to_validated:.2f}")

print("\n=== Reference table: predicted annual CAGR drag (%) ===")
print("(validated multiplier applied; turnover range restricted to <=100x/yr — see caveats)")
cost_levels = [5, 10, 15, 20]
turnover_levels = [6, 12, 25, 40, 60, 80, 100]
header = "turnover\\cost | " + " | ".join(f"{c:>6d}bps" for c in cost_levels)
print(header)
for t in turnover_levels:
    row = [f"{t:>10d}x |"]
    for c in cost_levels:
        drag = t * (c / 100) * validated_multiplier
        row.append(f"{drag:>8.2f}%")
    print(" ".join(row))

print("\n=== Inverted: max sustainable annualized turnover for a given required edge ===")
print("(turnover_max = required_edge / (cost_per_side% x validated_multiplier); valid only while turnover_max <= 100x)")
required_edges = [2, 5, 10, 20]
header2 = "required_edge\\cost | " + " | ".join(f"{c:>6d}bps" for c in cost_levels)
print(header2)
for e in required_edges:
    row = [f"{e:>15d}% |"]
    for c in cost_levels:
        t_max = e / ((c / 100) * validated_multiplier)
        flag = "" if t_max <= 100 else " (>100x, outside validated range)"
        row.append(f"{t_max:>8.1f}x{flag}")
    print(" ".join(row))
