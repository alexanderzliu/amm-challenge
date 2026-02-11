#!/usr/bin/env python3
"""Experiment 033: Inferred Volatility and Reserve-Based Fee.

Analysis of our strategy shows:
- Arb vol: 25.5K (half of vanilla's 50.2K) — good arb protection
- Retail share: 42.7% (below 50%!) — spiked side loses too much retail
- Edge is highly correlated with arb volume (r=0.9)

New approaches:
1. Use the PRICE CHANGE implied by reserves to set fee dynamically
   After arb: new_spot = reserveY / reserveX. Compare to previous.
   This tells us the recent sigma. Set fee proportional to implied vol.

2. Track cumulative squared returns (realized variance) to adapt fee.

3. "Smart" DirContrarian: on calm steps (no arb, small trades), set fee
   very low (15-20 bps) to capture MORE retail. On volatile steps
   (arb detected), spike as usual. This trades arb protection during
   calm for more retail capture.

4. Test the hypothesis: the winner might use a SIMPLER mechanism —
   just symmetric spike with well-chosen params we haven't tested.
   Grid search symmetric more thoroughly.
"""

import subprocess

STRATEGIES = {}

# Baseline DirContrarian
STRATEGIES["DC_base"] = """// SPDX-License-Identifier: MIT
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

# A: Implied vol from reserves — track spot price and compute realized vol
# Use vol EMA to scale spike intensity
STRATEGIES["DC_volScale"] = """// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;
import {AMMStrategyBase} from "./AMMStrategyBase.sol";
import {IAMMStrategy, TradeInfo} from "./IAMMStrategy.sol";
contract Strategy is AMMStrategyBase {
    // slots: 0=bid, 1=ask, 2=prevSpot, 3=volEMA
    function afterInitialize(uint256 ix, uint256 iy) external override returns (uint256, uint256) {
        uint256 fee = 24 * BPS;
        slots[0] = fee; slots[1] = fee;
        slots[2] = wdiv(iy, ix);
        slots[3] = 1e15; // initial vol estimate
        return (fee, fee);
    }
    function afterSwap(TradeInfo calldata trade) external override returns (uint256, uint256) {
        uint256 bidFee = slots[0]; uint256 askFee = slots[1];
        uint256 prevSpot = slots[2]; uint256 volEMA = slots[3];
        uint256 baseFee = 24 * BPS;
        uint256 tr = wdiv(trade.amountY, trade.reserveY);
        // Update spot and vol
        uint256 spot = wdiv(trade.reserveY, trade.reserveX);
        uint256 ret = 0;
        if (prevSpot > 0) {
            ret = absDiff(spot, prevSpot);
            ret = wdiv(ret, prevSpot);
        }
        // Vol EMA: 15/16 * old + 1/16 * |return|
        volEMA = volEMA * 15 / 16 + ret / 16;
        // Scale base by vol (higher vol → higher base for protection)
        // Nominal vol = 1e15 (~0.1%), scale linearly
        uint256 scaledBase = wmul(baseFee, wdiv(volEMA, 1e15));
        if (scaledBase < 20 * BPS) scaledBase = 20 * BPS;
        if (scaledBase > 40 * BPS) scaledBase = 40 * BPS;
        uint256 spike = tr * 5 / 4 + wmul(tr, tr) * 15;
        uint256 fresh = scaledBase + spike;
        uint256 dBid = bidFee * 8 / 9; uint256 dAsk = askFee * 8 / 9;
        if (dBid < scaledBase) dBid = scaledBase; if (dAsk < scaledBase) dAsk = scaledBase;
        if (trade.isBuy) { askFee = fresh > dAsk ? fresh : dAsk; bidFee = dBid; }
        else { bidFee = fresh > dBid ? fresh : dBid; askFee = dAsk; }
        bidFee = clampFee(bidFee); askFee = clampFee(askFee);
        slots[0] = bidFee; slots[1] = askFee; slots[2] = spot; slots[3] = volEMA;
        return (bidFee, askFee);
    }
    function getName() external pure override returns (string memory) { return "DCV"; }
}
"""

# B: Ultra-low base during calm, standard spike on arb
# Idea: most steps have no arb. Set base=15 to capture 70%+ of retail.
# On arb steps, spike protects. Sacrifice some arb protection for more retail.
STRATEGIES["DC_ultraLow"] = """// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;
import {AMMStrategyBase} from "./AMMStrategyBase.sol";
import {IAMMStrategy, TradeInfo} from "./IAMMStrategy.sol";
contract Strategy is AMMStrategyBase {
    function afterInitialize(uint256, uint256) external override returns (uint256, uint256) {
        uint256 fee = 15 * BPS; slots[0] = fee; slots[1] = fee; return (fee, fee);
    }
    function afterSwap(TradeInfo calldata trade) external override returns (uint256, uint256) {
        uint256 bidFee = slots[0]; uint256 askFee = slots[1]; uint256 baseFee = 15 * BPS;
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
    function getName() external pure override returns (string memory) { return "DUL"; }
}
"""

# C: Symmetric spike grid — maybe we missed the optimal symmetric params
# Since symmetric gives ~482, there might be 40+ point room for improvement
# that would bring symmetric above 520
for base, lnum, lden, quad, dn, dd in [
    # Aggressive spike, medium base
    (24, 7, 8, 27, 6, 7),  # Original best symmetric
    (24, 3, 2, 20, 8, 9),  # Stronger linear
    (24, 2, 1, 25, 8, 9),  # Even stronger linear
    (24, 1, 1, 30, 8, 9),  # Strong quad
    (24, 5, 4, 15, 8, 9),  # DC spike params but symmetric
    # Very slow decay to maintain protection
    (24, 5, 4, 15, 14, 15),
    (24, 5, 4, 15, 19, 20),
    (24, 7, 8, 27, 14, 15),
]:
    label = f"Sym_b{base}_l{lnum}d{lden}_q{quad}_d{dn}_{dd}"
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

# D: HALF-CONTRARIAN: spike opposite fully, but also spike same side at HALF intensity
# This provides both-sides arb protection while keeping same-side fee moderate
STRATEGIES["DC_half"] = """// SPDX-License-Identifier: MIT
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
        uint256 sameSpike = oppSpike / 2; // Half intensity
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
    function getName() external pure override returns (string memory) { return "DCH"; }
}
"""

# E: FAST SAME-SIDE DECAY, SLOW OPP DECAY — different decay rates per side
# Same side: 6/7 (fast return to base for retail capture)
# Opposite side: 14/15 (slow, persistent arb protection)
STRATEGIES["DC_splitDecay"] = """// SPDX-License-Identifier: MIT
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
        if (trade.isBuy) {
            uint256 dAsk = askFee * 14 / 15; // slow opp decay
            uint256 dBid = bidFee * 6 / 7;   // fast same decay
            if (dAsk < baseFee) dAsk = baseFee;
            if (dBid < baseFee) dBid = baseFee;
            askFee = fresh > dAsk ? fresh : dAsk;
            bidFee = dBid;
        } else {
            uint256 dBid = bidFee * 14 / 15;
            uint256 dAsk = askFee * 6 / 7;
            if (dBid < baseFee) dBid = baseFee;
            if (dAsk < baseFee) dAsk = baseFee;
            bidFee = fresh > dBid ? fresh : dBid;
            askFee = dAsk;
        }
        bidFee = clampFee(bidFee); askFee = clampFee(askFee);
        slots[0] = bidFee; slots[1] = askFee; return (bidFee, askFee);
    }
    function getName() external pure override returns (string memory) { return "DCSD"; }
}
"""

# F: CONTRARIAN with WEAKER spike but BOTH-SIDES protection
# The idea: instead of 100% opp spike + 0% same,
# use 70% opp + 30% same. Net result: both sides have SOME protection,
# but opp side has more. Retail on same side pays a moderate fee.
STRATEGIES["DC_70_30"] = """// SPDX-License-Identifier: MIT
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
        uint256 fullSpike = tr * 5 / 4 + wmul(tr, tr) * 15;
        uint256 oppFresh = baseFee + fullSpike * 7 / 10;
        uint256 sameFresh = baseFee + fullSpike * 3 / 10;
        uint256 dBid = bidFee * 8 / 9; uint256 dAsk = askFee * 8 / 9;
        if (dBid < baseFee) dBid = baseFee; if (dAsk < baseFee) dAsk = baseFee;
        if (trade.isBuy) {
            askFee = oppFresh > dAsk ? oppFresh : dAsk;
            bidFee = sameFresh > dBid ? sameFresh : dBid;
        } else {
            bidFee = oppFresh > dBid ? oppFresh : dBid;
            askFee = sameFresh > dAsk ? sameFresh : dAsk;
        }
        bidFee = clampFee(bidFee); askFee = clampFee(askFee);
        slots[0] = bidFee; slots[1] = askFee; return (bidFee, askFee);
    }
    function getName() external pure override returns (string memory) { return "DC73"; }
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


print("=== Experiment 033: Inferred Vol & Grid Search (100 sims) ===\n")
results = []

# DirContrarian variants
print("--- DC variants ---")
dc_names = ["DC_base", "DC_volScale", "DC_ultraLow", "DC_half", "DC_splitDecay", "DC_70_30"]
for name in dc_names:
    edge = run_strategy(name, STRATEGIES[name], n_sims=100)
    print(f"{name:40s} -> edge={edge}", flush=True)
    results.append((name, edge))

# Symmetric grid
print("\n--- Symmetric grid ---")
sym_names = [k for k in STRATEGIES.keys() if k.startswith("Sym_")]
for name in sym_names:
    edge = run_strategy(name, STRATEGIES[name], n_sims=100)
    print(f"{name:40s} -> edge={edge}", flush=True)
    results.append((name, edge))

# Validate
print("\n=== 500-sim validation ===")
promising = [(name, STRATEGIES[name]) for name, edge in results
             if edge and edge > 505 and name != "DC_base"]
for name, code in promising:
    edge = run_strategy(name, code, n_sims=500)
    print(f"{name:40s} -> edge={edge} (500 sims)", flush=True)

# Restore
with open("my_strategy.sol", "w") as f:
    f.write(STRATEGIES["DC_base"])
print("\nRestored DC baseline")
