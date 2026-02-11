#!/usr/bin/env python3
"""Experiment 036: Comprehensive Parameter Grid for DirContrarian.

Fine-grained 4D grid search around the current optimum.
Current best: base=24, lin=5/4, quad=15, decay=8/9

Also includes some outlier combos to check for distant optima.
"""

import subprocess
import sys

def run_strategy(code, n_sims=50):
    with open("my_strategy.sol", "w") as f:
        f.write(code)
    try:
        result = subprocess.run(
            ["amm-match", "run", "my_strategy.sol", "--simulations", str(n_sims)],
            capture_output=True, text=True, timeout=600
        )
        for line in result.stdout.strip().split("\n"):
            if "Edge:" in line:
                return float(line.split("Edge:")[-1].strip())
    except Exception as e:
        print(f"  ERROR: {e}", file=sys.stderr)
    return None

def make_dc(base, lin_n, lin_d, quad, dec_n, dec_d):
    return f"""// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;
import {{AMMStrategyBase}} from "./AMMStrategyBase.sol";
import {{IAMMStrategy, TradeInfo}} from "./IAMMStrategy.sol";
contract Strategy is AMMStrategyBase {{
    function afterInitialize(uint256, uint256) external override returns (uint256, uint256) {{
        uint256 fee = {base} * BPS; slots[0] = fee; slots[1] = fee; return (fee, fee);
    }}
    function afterSwap(TradeInfo calldata trade) external override returns (uint256, uint256) {{
        uint256 bidFee = slots[0]; uint256 askFee = slots[1]; uint256 baseFee = {base} * BPS;
        uint256 tr = wdiv(trade.amountY, trade.reserveY);
        uint256 spike = tr * {lin_n} / {lin_d} + wmul(tr, tr) * {quad};
        uint256 fresh = baseFee + spike;
        uint256 dBid = bidFee * {dec_n} / {dec_d}; uint256 dAsk = askFee * {dec_n} / {dec_d};
        if (dBid < baseFee) dBid = baseFee; if (dAsk < baseFee) dAsk = baseFee;
        if (trade.isBuy) {{ askFee = fresh > dAsk ? fresh : dAsk; bidFee = dBid; }}
        else {{ bidFee = fresh > dBid ? fresh : dBid; askFee = dAsk; }}
        bidFee = clampFee(bidFee); askFee = clampFee(askFee);
        slots[0] = bidFee; slots[1] = askFee; return (bidFee, askFee);
    }}
    function getName() external pure override returns (string memory) {{ return "DC"; }}
}}
"""

# Focused grid: vary each dimension more finely around optimum
# Current: base=24, lin=5/4=1.25, quad=15, decay=8/9=0.889

combos = []

# Phase 1: Fine-tune linear and quad with fixed base=24, decay=8/9
print("=== Phase 1: lin x quad grid (base=24, decay=8/9) ===")
for ln, ld in [(1, 1), (9, 8), (5, 4), (11, 8), (3, 2), (7, 4), (2, 1)]:
    for quad in [8, 10, 12, 15, 18, 20, 25]:
        label = f"b24_l{ln}d{ld}_q{quad}_d8_9"
        combos.append((label, 24, ln, ld, quad, 8, 9))

results = []
for i, (label, base, ln, ld, quad, dn, dd) in enumerate(combos):
    code = make_dc(base, ln, ld, quad, dn, dd)
    edge = run_strategy(code, n_sims=50)
    results.append((label, edge, base, ln, ld, quad, dn, dd))
    if (i+1) % 10 == 0:
        print(f"  Progress: {i+1}/{len(combos)}", flush=True)

results.sort(key=lambda x: x[1] if x[1] else 0, reverse=True)
print("\nTop 10 (lin x quad):")
for label, edge, *_ in results[:10]:
    print(f"  {label:35s} -> {edge:.1f}")

# Phase 2: Fine-tune decay with best lin/quad from Phase 1
best_params = results[0]
_, _, _, best_ln, best_ld, best_quad, _, _ = best_params
print(f"\nBest lin={best_ln}/{best_ld}, quad={best_quad}")

print(f"\n=== Phase 2: decay grid (base=24, lin={best_ln}/{best_ld}, quad={best_quad}) ===")
combos2 = []
for dn, dd in [(3, 4), (4, 5), (5, 6), (6, 7), (7, 8), (8, 9), (9, 10), (10, 11),
               (11, 12), (13, 14), (14, 15), (17, 18), (19, 20)]:
    label = f"b24_l{best_ln}d{best_ld}_q{best_quad}_d{dn}_{dd}"
    combos2.append((label, 24, best_ln, best_ld, best_quad, dn, dd))

results2 = []
for label, base, ln, ld, quad, dn, dd in combos2:
    code = make_dc(base, ln, ld, quad, dn, dd)
    edge = run_strategy(code, n_sims=50)
    results2.append((label, edge, base, ln, ld, quad, dn, dd))

results2.sort(key=lambda x: x[1] if x[1] else 0, reverse=True)
print("Decay sweep:")
for label, edge, *_ in results2:
    print(f"  {label:40s} -> {edge:.1f}")

# Phase 3: Fine-tune base with best other params
best2 = results2[0]
_, _, _, _, _, _, best_dn, best_dd = best2
print(f"\nBest decay={best_dn}/{best_dd}")

print(f"\n=== Phase 3: base grid ===")
combos3 = []
for base in [20, 21, 22, 23, 24, 25, 26, 27, 28]:
    label = f"b{base}_l{best_ln}d{best_ld}_q{best_quad}_d{best_dn}_{best_dd}"
    combos3.append((label, base, best_ln, best_ld, best_quad, best_dn, best_dd))

results3 = []
for label, base, ln, ld, quad, dn, dd in combos3:
    code = make_dc(base, ln, ld, quad, dn, dd)
    edge = run_strategy(code, n_sims=50)
    results3.append((label, edge, base, ln, ld, quad, dn, dd))

results3.sort(key=lambda x: x[1] if x[1] else 0, reverse=True)
print("Base sweep:")
for label, edge, *_ in results3:
    print(f"  {label:40s} -> {edge:.1f}")

# Get the overall best combination
best3 = results3[0]
_, _, final_base, final_ln, final_ld, final_quad, final_dn, final_dd = best3

print(f"\n=== BEST PARAMS: base={final_base}, lin={final_ln}/{final_ld}, quad={final_quad}, decay={final_dn}/{final_dd} ===")

# Validate at 500 sims
print("\n=== 500-sim validation ===")
code = make_dc(final_base, final_ln, final_ld, final_quad, final_dn, final_dd)
ve = run_strategy(code, n_sims=500)
print(f"Best: edge={ve:.2f} (500 sims)")

# Compare to current best
code_cur = make_dc(24, 5, 4, 15, 8, 9)
ve_cur = run_strategy(code_cur, n_sims=500)
print(f"Current (24/5d4/15/8d9): edge={ve_cur:.2f} (500 sims)")

# Also validate a few other top combos from Phase 1
print("\n=== Additional 500-sim validations ===")
for label, edge, base, ln, ld, quad, dn, dd in results[:3]:
    code = make_dc(base, ln, ld, quad, dn, dd)
    ve = run_strategy(code, n_sims=500)
    print(f"{label:35s} -> {ve:.2f} (500 sims)")

# Restore
with open("my_strategy.sol", "w") as f:
    f.write(make_dc(24, 5, 4, 15, 8, 9))
print("\nRestored DC baseline")
