#!/usr/bin/env python3
"""Experiment 029: K-preservation and fee optimization.

Key insight: routing advantage comes from k-preservation (reserves), not fee level.
At 24 bps vs vanilla 30 bps, the fee routing advantage is only 0.015%.
So our 57% retail share must come from having higher k (better reserves) than vanilla.

The arb loss per trade = reserves * (sqrt(k/(γp)) - x) for one direction.
Higher base fee → wider no-arb band → less frequent arb → better k preservation.
But higher fee → slightly less retail routing (small effect from fee level).

Hypothesis: there's an optimal base fee > 24 that maximizes k-preservation benefit
while maintaining DirContrarian spike protection.

Also test: symmetric vs contrarian at various bases to isolate the k-preservation effect.
"""

import subprocess

STRATEGIES = {}

# DirContrarian at various bases
for base in [20, 22, 24, 26, 28, 30, 32, 34, 36, 40]:
    STRATEGIES[f"DC_{base}"] = f"""// SPDX-License-Identifier: MIT
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

# Symmetric spike at various bases (to isolate contrarian effect)
for base in [24, 30, 36]:
    STRATEGIES[f"Sym_{base}"] = f"""// SPDX-License-Identifier: MIT
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
        uint256 spike = tr * 5 / 4 + wmul(tr, tr) * 15;
        uint256 fresh = baseFee + spike;
        uint256 decayed = curFee * 8 / 9;
        if (decayed < baseFee) decayed = baseFee;
        uint256 fee = fresh > decayed ? fresh : decayed;
        fee = clampFee(fee);
        slots[0] = fee; return (fee, fee);
    }}
    function getName() external pure override returns (string memory) {{ return "Sym{base}"; }}
}}
"""

# DirContrarian with same-side at 30 (match vanilla) but opposite spike starts at 24
# Idea: same-side fee matches vanilla exactly, so routing depends purely on k
STRATEGIES["DC_match30"] = """// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;
import {AMMStrategyBase} from "./AMMStrategyBase.sol";
import {IAMMStrategy, TradeInfo} from "./IAMMStrategy.sol";
contract Strategy is AMMStrategyBase {
    function afterInitialize(uint256, uint256) external override returns (uint256, uint256) {
        uint256 fee = 30 * BPS; slots[0] = fee; slots[1] = fee; return (fee, fee);
    }
    function afterSwap(TradeInfo calldata trade) external override returns (uint256, uint256) {
        uint256 bidFee = slots[0]; uint256 askFee = slots[1];
        uint256 spikeBase = 24 * BPS; // spike formula uses 24 as base
        uint256 sameFee = 30 * BPS; // same side always at 30 (match vanilla)
        uint256 tr = wdiv(trade.amountY, trade.reserveY);
        uint256 spike = tr * 5 / 4 + wmul(tr, tr) * 15;
        uint256 fresh = spikeBase + spike;
        uint256 dBid = bidFee * 8 / 9; uint256 dAsk = askFee * 8 / 9;
        if (dBid < spikeBase) dBid = spikeBase; if (dAsk < spikeBase) dAsk = spikeBase;
        if (trade.isBuy) {
            askFee = fresh > dAsk ? fresh : dAsk; // opposite: spike
            bidFee = sameFee; // same: always 30
        } else {
            bidFee = fresh > dBid ? fresh : dBid;
            askFee = sameFee;
        }
        bidFee = clampFee(bidFee); askFee = clampFee(askFee);
        slots[0] = bidFee; slots[1] = askFee; return (bidFee, askFee);
    }
    function getName() external pure override returns (string memory) { return "DCM30"; }
}
"""

# DirContrarian where same-side is always exactly base (no decay memory)
# Tests whether the decay memory on same side matters
STRATEGIES["DC_noMemSame"] = """// SPDX-License-Identifier: MIT
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
        if (trade.isBuy) {
            askFee = fresh > dAsk ? fresh : dAsk;
            bidFee = baseFee; // Always reset same side to base (no memory)
        } else {
            bidFee = fresh > dBid ? fresh : dBid;
            askFee = baseFee;
        }
        bidFee = clampFee(bidFee); askFee = clampFee(askFee);
        slots[0] = bidFee; slots[1] = askFee; return (bidFee, askFee);
    }
    function getName() external pure override returns (string memory) { return "DCNM"; }
}
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


print("=== Experiment 029: K-Preservation & Base Fee Scan (100 sims) ===\n")
results = []

# Phase 1: DirContrarian base scan
print("--- DC base scan ---")
dc_order = [f"DC_{b}" for b in [20, 22, 24, 26, 28, 30, 32, 34, 36, 40]]
for name in dc_order:
    edge = run_strategy(name, STRATEGIES[name], n_sims=100)
    print(f"{name:25s} -> edge={edge}", flush=True)
    results.append((name, edge))

# Phase 2: Symmetric baselines
print("\n--- Symmetric baselines ---")
sym_order = [f"Sym_{b}" for b in [24, 30, 36]]
for name in sym_order:
    edge = run_strategy(name, STRATEGIES[name], n_sims=100)
    print(f"{name:25s} -> edge={edge}", flush=True)
    results.append((name, edge))

# Phase 3: Special variants
print("\n--- Special variants ---")
for name in ["DC_match30", "DC_noMemSame"]:
    edge = run_strategy(name, STRATEGIES[name], n_sims=100)
    print(f"{name:25s} -> edge={edge}", flush=True)
    results.append((name, edge))

# 500-sim validate any promising results
print("\n=== 500-sim validation ===")
promising = [(name, STRATEGIES[name]) for name, edge in results
             if edge and edge > 504 and name != "DC_24"]
for name, code in promising:
    edge = run_strategy(name, code, n_sims=500)
    print(f"{name:25s} -> edge={edge} (500 sims)", flush=True)

# Restore
with open("my_strategy.sol", "w") as f:
    f.write(STRATEGIES["DC_24"])
print("\nRestored DC_24")
