#!/usr/bin/env python3
"""Experiment 031: Understanding the optimal retail fee.

Key insight from routing math: revenue = share × fee per order.
At our reserves (x=100, y=10000), routing share per retail order:
  share ≈ 0.5 + 5000*(γ_us - γ_van) / Y_order    (rough approximation)

Revenue = share × fee is maximized around 36 bps for a single order.

But DirContrarian sacrifices half of retail directions (spiked side gets 0%).
What if we use a SYMMETRIC approach at the revenue-optimal fee?

Test: Symmetric spike at fee near 33-38 bps to maximize per-order revenue,
combined with different spike/decay params optimized for higher base.

Also test: very low-base DirContrarian variants (18-22 bps) to see if
capturing MORE retail at lower fee beats capturing LESS at higher fee.

And: New idea — what if the "winning strategy" uses NO spike at all,
just a well-chosen CONSTANT fee? Re-test constants more systematically.
"""

import subprocess

STRATEGIES = {}

# --- Constant fee scan (no spikes) ---
for f in [28, 30, 32, 33, 34, 35, 36, 38, 40, 50, 60, 75]:
    STRATEGIES[f"Const_{f}"] = f"""// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;
import {{AMMStrategyBase}} from "./AMMStrategyBase.sol";
import {{IAMMStrategy, TradeInfo}} from "./IAMMStrategy.sol";
contract Strategy is AMMStrategyBase {{
    function afterInitialize(uint256, uint256) external override returns (uint256, uint256) {{
        uint256 fee = {f} * BPS; return (fee, fee);
    }}
    function afterSwap(TradeInfo calldata) external override returns (uint256, uint256) {{
        uint256 fee = {f} * BPS; return (fee, fee);
    }}
    function getName() external pure override returns (string memory) {{ return "C{f}"; }}
}}
"""

# --- Symmetric spike at various bases with tuned params ---
# At higher base, maybe weaker spikes work better (less total spike)
for base, lnum, lden, quad, dn, dd in [
    (30, 5, 4, 15, 8, 9),   # Standard spike params
    (30, 3, 4, 10, 8, 9),   # Weaker spikes
    (30, 1, 1, 8, 8, 9),    # Much weaker
    (33, 3, 4, 10, 8, 9),   # Base 33 weak spike
    (33, 5, 4, 15, 8, 9),   # Base 33 standard spike
    (36, 1, 2, 5, 8, 9),    # Base 36 very weak spike
]:
    label = f"Sym{base}_l{lnum}d{lden}_q{quad}"
    STRATEGIES[label] = f"""// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;
import {{AMMStrategyBase}} from "./AMMStrategyBase.sol";
import {{IAMMStrategy, TradeInfo}} from "./IAMMStrategy.sol";
contract Strategy is AMMStrategyBase {{
    function afterInitialize(uint256, uint256) external override returns (uint256, uint256) {{
        uint256 fee = {base} * BPS; slots[0] = fee; return (fee, fee);
    }}
    function afterSwap(TradeInfo calldata trade) external override returns (uint256, uint256) {{
        uint256 curFee = slots[0]; uint256 baseFee = {base} * BPS;
        uint256 tr = wdiv(trade.amountY, trade.reserveY);
        uint256 spike = tr * {lnum} / {lden} + wmul(tr, tr) * {quad};
        uint256 fresh = baseFee + spike;
        uint256 decayed = curFee * {dn} / {dd};
        if (decayed < baseFee) decayed = baseFee;
        uint256 fee = fresh > decayed ? fresh : decayed;
        fee = clampFee(fee);
        slots[0] = fee; return (fee, fee);
    }}
    function getName() external pure override returns (string memory) {{ return "S"; }}
}}
"""

# --- DirContrarian at low bases (maximize routing share) ---
for base in [16, 18, 20, 22]:
    STRATEGIES[f"DC_{base}_low"] = f"""// SPDX-License-Identifier: MIT
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
        uint256 spike = tr * 5 / 4 + wmul(tr, tr) * 15;
        uint256 fresh = baseFee + spike;
        uint256 dBid = bidFee * 8 / 9; uint256 dAsk = askFee * 8 / 9;
        if (dBid < baseFee) dBid = baseFee; if (dAsk < baseFee) dAsk = baseFee;
        if (trade.isBuy) {{ askFee = fresh > dAsk ? fresh : dAsk; bidFee = dBid; }}
        else {{ bidFee = fresh > dBid ? fresh : dBid; askFee = dAsk; }}
        bidFee = clampFee(bidFee); askFee = clampFee(askFee);
        slots[0] = bidFee; slots[1] = askFee; return (bidFee, askFee);
    }}
    function getName() external pure override returns (string memory) {{ return "DC{base}"; }}
}}
"""

# --- NEW: DirContrarian but both-sides-spike with asymmetric magnitudes ---
# Same side gets a VERY small spike (just 1-2 bps above base for revenue),
# opposite gets full spike (for arb protection).
# The same-side spike RAISES the fee on retail that would normally see base.
# At 24 + 2 = 26 bps on same side:
# Revenue per order = share(26) × 26 ≈ 55% × 26 = 14.3 (vs 57.5% × 24 = 13.8)
STRATEGIES["DC_asym_s2"] = """// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;
import {AMMStrategyBase} from "./AMMStrategyBase.sol";
import {IAMMStrategy, TradeInfo} from "./IAMMStrategy.sol";
contract Strategy is AMMStrategyBase {
    function afterInitialize(uint256, uint256) external override returns (uint256, uint256) {
        uint256 fee = 24 * BPS; slots[0] = fee; slots[1] = fee; return (fee, fee);
    }
    function afterSwap(TradeInfo calldata trade) external override returns (uint256, uint256) {
        uint256 bidFee = slots[0]; uint256 askFee = slots[1]; uint256 baseFee = 24 * BPS;
        uint256 tr = wdiv(trade.amountY, trade.reserveY);
        uint256 oppSpike = tr * 5 / 4 + wmul(tr, tr) * 15;
        uint256 sameSpike = 2 * BPS; // constant 2 bps bump on same side
        uint256 freshOpp = baseFee + oppSpike;
        uint256 freshSame = baseFee + sameSpike;
        uint256 dBid = bidFee * 8 / 9; uint256 dAsk = askFee * 8 / 9;
        if (dBid < baseFee) dBid = baseFee; if (dAsk < baseFee) dAsk = baseFee;
        if (trade.isBuy) {
            askFee = freshOpp > dAsk ? freshOpp : dAsk;
            bidFee = freshSame > dBid ? freshSame : dBid;
        } else {
            bidFee = freshOpp > dBid ? freshOpp : dBid;
            askFee = freshSame > dAsk ? freshSame : dAsk;
        }
        bidFee = clampFee(bidFee); askFee = clampFee(askFee);
        slots[0] = bidFee; slots[1] = askFee; return (bidFee, askFee);
    }
    function getName() external pure override returns (string memory) { return "DCA2"; }
}
"""

# Same but 4 bps same-side bump
STRATEGIES["DC_asym_s4"] = """// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;
import {AMMStrategyBase} from "./AMMStrategyBase.sol";
import {IAMMStrategy, TradeInfo} from "./IAMMStrategy.sol";
contract Strategy is AMMStrategyBase {
    function afterInitialize(uint256, uint256) external override returns (uint256, uint256) {
        uint256 fee = 24 * BPS; slots[0] = fee; slots[1] = fee; return (fee, fee);
    }
    function afterSwap(TradeInfo calldata trade) external override returns (uint256, uint256) {
        uint256 bidFee = slots[0]; uint256 askFee = slots[1]; uint256 baseFee = 24 * BPS;
        uint256 tr = wdiv(trade.amountY, trade.reserveY);
        uint256 oppSpike = tr * 5 / 4 + wmul(tr, tr) * 15;
        uint256 sameSpike = 4 * BPS;
        uint256 freshOpp = baseFee + oppSpike;
        uint256 freshSame = baseFee + sameSpike;
        uint256 dBid = bidFee * 8 / 9; uint256 dAsk = askFee * 8 / 9;
        if (dBid < baseFee) dBid = baseFee; if (dAsk < baseFee) dAsk = baseFee;
        if (trade.isBuy) {
            askFee = freshOpp > dAsk ? freshOpp : dAsk;
            bidFee = freshSame > dBid ? freshSame : dBid;
        } else {
            bidFee = freshOpp > dBid ? freshOpp : dBid;
            askFee = freshSame > dAsk ? freshSame : dAsk;
        }
        bidFee = clampFee(bidFee); askFee = clampFee(askFee);
        slots[0] = bidFee; slots[1] = askFee; return (bidFee, askFee);
    }
    function getName() external pure override returns (string memory) { return "DCA4"; }
}
"""

# --- DC with PROPORTIONAL same-side spike (fraction of trade-size) ---
for frac_num, frac_den in [(1, 8), (1, 4), (1, 2)]:
    label = f"DC_prop{frac_num}_{frac_den}"
    STRATEGIES[label] = f"""// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;
import {{AMMStrategyBase}} from "./AMMStrategyBase.sol";
import {{IAMMStrategy, TradeInfo}} from "./IAMMStrategy.sol";
contract Strategy is AMMStrategyBase {{
    function afterInitialize(uint256, uint256) external override returns (uint256, uint256) {{
        uint256 fee = 24 * BPS; slots[0] = fee; slots[1] = fee; return (fee, fee);
    }}
    function afterSwap(TradeInfo calldata trade) external override returns (uint256, uint256) {{
        uint256 bidFee = slots[0]; uint256 askFee = slots[1]; uint256 baseFee = 24 * BPS;
        uint256 tr = wdiv(trade.amountY, trade.reserveY);
        uint256 oppSpike = tr * 5 / 4 + wmul(tr, tr) * 15;
        uint256 freshOpp = baseFee + oppSpike;
        uint256 freshSame = baseFee + oppSpike * {frac_num} / {frac_den};
        uint256 dBid = bidFee * 8 / 9; uint256 dAsk = askFee * 8 / 9;
        if (dBid < baseFee) dBid = baseFee; if (dAsk < baseFee) dAsk = baseFee;
        if (trade.isBuy) {{
            askFee = freshOpp > dAsk ? freshOpp : dAsk;
            bidFee = freshSame > dBid ? freshSame : dBid;
        }} else {{
            bidFee = freshOpp > dBid ? freshOpp : dBid;
            askFee = freshSame > dAsk ? freshSame : dAsk;
        }}
        bidFee = clampFee(bidFee); askFee = clampFee(askFee);
        slots[0] = bidFee; slots[1] = askFee; return (bidFee, askFee);
    }}
    function getName() external pure override returns (string memory) {{ return "DCP"; }}
}}
"""


def run_strategy(name, code, n_sims=100):
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
        print(f"  ERROR: {e}")
    return None


print("=== Experiment 031: Optimal Retail Fee Study (100 sims) ===\n")

# Phase 1: Constant fee landscape
print("--- Constant fee landscape ---")
results_const = []
for f in [28, 30, 32, 33, 34, 35, 36, 38, 40, 50, 60, 75]:
    name = f"Const_{f}"
    edge = run_strategy(name, STRATEGIES[name], n_sims=100)
    print(f"{name:25s} -> edge={edge}", flush=True)
    results_const.append((name, edge))

# Phase 2: Symmetric with tuned spikes at various bases
print("\n--- Symmetric spike variants ---")
results_sym = []
sym_keys = [k for k in STRATEGIES.keys() if k.startswith("Sym")]
for name in sym_keys:
    edge = run_strategy(name, STRATEGIES[name], n_sims=100)
    print(f"{name:25s} -> edge={edge}", flush=True)
    results_sym.append((name, edge))

# Phase 3: DC at low bases
print("\n--- DC at low bases ---")
results_dc = []
dc_keys = [f"DC_{b}_low" for b in [16, 18, 20, 22]]
for name in dc_keys:
    edge = run_strategy(name, STRATEGIES[name], n_sims=100)
    print(f"{name:25s} -> edge={edge}", flush=True)
    results_dc.append((name, edge))

# Phase 4: Asymmetric same-side bump
print("\n--- Asymmetric same-side bump ---")
results_asym = []
for name in ["DC_asym_s2", "DC_asym_s4", "DC_prop1_8", "DC_prop1_4", "DC_prop1_2"]:
    edge = run_strategy(name, STRATEGIES[name], n_sims=100)
    print(f"{name:25s} -> edge={edge}", flush=True)
    results_asym.append((name, edge))

# Validate promising
print("\n=== 500-sim validation ===")
all_results = results_const + results_sym + results_dc + results_asym
promising = [(name, STRATEGIES[name]) for name, edge in all_results
             if edge and edge > 504]
for name, code in promising:
    edge = run_strategy(name, code, n_sims=500)
    print(f"{name:25s} -> edge={edge} (500 sims)", flush=True)

# Restore DC baseline
baseline = """// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;
import {AMMStrategyBase} from "./AMMStrategyBase.sol";
import {IAMMStrategy, TradeInfo} from "./IAMMStrategy.sol";
contract Strategy is AMMStrategyBase {
    function afterInitialize(uint256, uint256) external override returns (uint256, uint256) {
        uint256 fee = 24 * BPS; slots[0] = fee; slots[1] = fee; return (fee, fee);
    }
    function afterSwap(TradeInfo calldata trade) external override returns (uint256, uint256) {
        uint256 bidFee = slots[0]; uint256 askFee = slots[1]; uint256 baseFee = 24 * BPS;
        uint256 tr = wdiv(trade.amountY, trade.reserveY);
        uint256 spike = tr * 5 / 4 + wmul(tr, tr) * 15;
        uint256 fresh = baseFee + spike;
        uint256 dBid = bidFee * 8 / 9; uint256 dAsk = askFee * 8 / 9;
        if (dBid < baseFee) dBid = baseFee; if (dAsk < baseFee) dAsk = baseFee;
        if (trade.isBuy) { askFee = fresh > dAsk ? fresh : dAsk; bidFee = dBid; }
        else { bidFee = fresh > dBid ? fresh : dBid; askFee = dAsk; }
        bidFee = clampFee(bidFee); askFee = clampFee(askFee);
        slots[0] = bidFee; slots[1] = askFee; return (bidFee, askFee);
    }
    function getName() external pure override returns (string memory) { return "DC"; }
}
"""
with open("my_strategy.sol", "w") as f:
    f.write(baseline)
print("\nRestored DC baseline")
