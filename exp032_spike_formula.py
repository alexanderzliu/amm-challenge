#!/usr/bin/env python3
"""Experiment 032: Alternative Spike Formulas.

The current spike formula: spike = tr * 5/4 + wmul(tr,tr) * 15
This was tuned for the symmetric case and adopted for DirContrarian.
Maybe the optimal spike formula for DirContrarian is DIFFERENT.

The spike determines two things:
1. How much arb protection we get (larger spike = wider no-arb band)
2. How quickly we lose retail on the spiked side (larger spike = more retail loss)

With DirContrarian, the spiked side is OPPOSITE to the arb direction.
Only 50% of next-step arbs come from that direction. But ALL retail
on that side is lost.

New idea: what if the optimal spike is much STEEPER but NARROWER?
- Very aggressive for large trades (arbs) → maximum arb protection
- But decays very fast → doesn't persist for retail

Or: what if the spike should be based on a DIFFERENT signal?
- Not just tradeRatio but also something else?
"""

import subprocess

STRATEGIES = {}

# Baseline
STRATEGIES["DC_baseline"] = """// SPDX-License-Identifier: MIT
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

# A: Pure quadratic spike (no linear term) — steeper for large, gentler for small
STRATEGIES["DC_pureQuad"] = """// SPDX-License-Identifier: MIT
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
        uint256 spike = wmul(tr, tr) * 27; // Pure quadratic, calibrated to match total at tr=0.005
        uint256 fresh = baseFee + spike;
        uint256 dBid = bidFee * 8 / 9; uint256 dAsk = askFee * 8 / 9;
        if (dBid < baseFee) dBid = baseFee; if (dAsk < baseFee) dAsk = baseFee;
        if (trade.isBuy) { askFee = fresh > dAsk ? fresh : dAsk; bidFee = dBid; }
        else { bidFee = fresh > dBid ? fresh : dBid; askFee = dAsk; }
        bidFee = clampFee(bidFee); askFee = clampFee(askFee);
        slots[0] = bidFee; slots[1] = askFee; return (bidFee, askFee);
    }
    function getName() external pure override returns (string memory) { return "DPQ"; }
}
"""

# B: Pure linear spike (no quadratic)
STRATEGIES["DC_pureLin"] = """// SPDX-License-Identifier: MIT
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
        uint256 spike = tr * 2; // Pure linear, stronger coefficient
        uint256 fresh = baseFee + spike;
        uint256 dBid = bidFee * 8 / 9; uint256 dAsk = askFee * 8 / 9;
        if (dBid < baseFee) dBid = baseFee; if (dAsk < baseFee) dAsk = baseFee;
        if (trade.isBuy) { askFee = fresh > dAsk ? fresh : dAsk; bidFee = dBid; }
        else { bidFee = fresh > dBid ? fresh : dBid; askFee = dAsk; }
        bidFee = clampFee(bidFee); askFee = clampFee(askFee);
        slots[0] = bidFee; slots[1] = askFee; return (bidFee, askFee);
    }
    function getName() external pure override returns (string memory) { return "DPL"; }
}
"""

# C: Very fast decay (lose spike quickly) — fee only lasts 1-2 trades
STRATEGIES["DC_fastDecay"] = """// SPDX-License-Identifier: MIT
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
        // Very fast decay: 2/3 per trade
        uint256 dBid = bidFee * 2 / 3; uint256 dAsk = askFee * 2 / 3;
        if (dBid < baseFee) dBid = baseFee; if (dAsk < baseFee) dAsk = baseFee;
        if (trade.isBuy) { askFee = fresh > dAsk ? fresh : dAsk; bidFee = dBid; }
        else { bidFee = fresh > dBid ? fresh : dBid; askFee = dAsk; }
        bidFee = clampFee(bidFee); askFee = clampFee(askFee);
        slots[0] = bidFee; slots[1] = askFee; return (bidFee, askFee);
    }
    function getName() external pure override returns (string memory) { return "DFD"; }
}
"""

# D: STRONGER spike but faster decay — big initial protection, quick return to base
STRATEGIES["DC_bigFast"] = """// SPDX-License-Identifier: MIT
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
        uint256 spike = tr * 3 + wmul(tr, tr) * 30; // 2x stronger
        uint256 fresh = baseFee + spike;
        uint256 dBid = bidFee * 3 / 4; uint256 dAsk = askFee * 3 / 4; // faster decay
        if (dBid < baseFee) dBid = baseFee; if (dAsk < baseFee) dAsk = baseFee;
        if (trade.isBuy) { askFee = fresh > dAsk ? fresh : dAsk; bidFee = dBid; }
        else { bidFee = fresh > dBid ? fresh : dBid; askFee = dAsk; }
        bidFee = clampFee(bidFee); askFee = clampFee(askFee);
        slots[0] = bidFee; slots[1] = askFee; return (bidFee, askFee);
    }
    function getName() external pure override returns (string memory) { return "DBF"; }
}
"""

# E: Spike based on BOTH X and Y ratios (geometric mean)
STRATEGIES["DC_geoMean"] = """// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;
import {AMMStrategyBase} from "./AMMStrategyBase.sol";
import {IAMMStrategy, TradeInfo} from "./IAMMStrategy.sol";
contract Strategy is AMMStrategyBase {
    function afterInitialize(uint256, uint256) external override returns (uint256, uint256) {
        uint256 fee = 24 * BPS; slots[0] = fee; slots[1] = fee; return (fee, fee);
    }
    function afterSwap(TradeInfo calldata trade) external override returns (uint256, uint256) {
        uint256 bidFee = slots[0]; uint256 askFee = slots[1]; uint256 baseFee = 24 * BPS;
        uint256 trY = wdiv(trade.amountY, trade.reserveY);
        uint256 trX = wdiv(trade.amountX, trade.reserveX);
        uint256 tr = sqrt(wmul(trX, trY)); // geometric mean
        uint256 spike = tr * 5 / 4 + wmul(tr, tr) * 15;
        uint256 fresh = baseFee + spike;
        uint256 dBid = bidFee * 8 / 9; uint256 dAsk = askFee * 8 / 9;
        if (dBid < baseFee) dBid = baseFee; if (dAsk < baseFee) dAsk = baseFee;
        if (trade.isBuy) { askFee = fresh > dAsk ? fresh : dAsk; bidFee = dBid; }
        else { bidFee = fresh > dBid ? fresh : dBid; askFee = dAsk; }
        bidFee = clampFee(bidFee); askFee = clampFee(askFee);
        slots[0] = bidFee; slots[1] = askFee; return (bidFee, askFee);
    }
    function getName() external pure override returns (string memory) { return "DGM"; }
}
"""

# F: Spike as fraction of RESERVES (not trade ratio) — conceptually different
# Use the deviation of reserves from initial values
STRATEGIES["DC_reserveSpike"] = """// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;
import {AMMStrategyBase} from "./AMMStrategyBase.sol";
import {IAMMStrategy, TradeInfo} from "./IAMMStrategy.sol";
contract Strategy is AMMStrategyBase {
    function afterInitialize(uint256 ix, uint256 iy) external override returns (uint256, uint256) {
        uint256 fee = 24 * BPS;
        slots[0] = fee; slots[1] = fee;
        slots[2] = ix; slots[3] = iy; // Store initial reserves
        return (fee, fee);
    }
    function afterSwap(TradeInfo calldata trade) external override returns (uint256, uint256) {
        uint256 bidFee = slots[0]; uint256 askFee = slots[1]; uint256 baseFee = 24 * BPS;
        uint256 tr = wdiv(trade.amountY, trade.reserveY);
        // Standard spike
        uint256 spike = tr * 5 / 4 + wmul(tr, tr) * 15;
        // Add reserve deviation bonus: how far are we from initial?
        uint256 initY = slots[3];
        uint256 devY = absDiff(trade.reserveY, initY);
        uint256 devRatio = wdiv(devY, initY);
        // Scale spike by (1 + devRatio * 5)
        spike = spike + wmul(spike, devRatio * 5);
        uint256 fresh = baseFee + spike;
        uint256 dBid = bidFee * 8 / 9; uint256 dAsk = askFee * 8 / 9;
        if (dBid < baseFee) dBid = baseFee; if (dAsk < baseFee) dAsk = baseFee;
        if (trade.isBuy) { askFee = fresh > dAsk ? fresh : dAsk; bidFee = dBid; }
        else { bidFee = fresh > dBid ? fresh : dBid; askFee = dAsk; }
        bidFee = clampFee(bidFee); askFee = clampFee(askFee);
        slots[0] = bidFee; slots[1] = askFee; return (bidFee, askFee);
    }
    function getName() external pure override returns (string memory) { return "DRS"; }
}
"""

# G: SLOWER decay (more persistent spike) — 9/10 instead of 8/9
STRATEGIES["DC_slowDecay"] = """// SPDX-License-Identifier: MIT
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
        uint256 dBid = bidFee * 9 / 10; uint256 dAsk = askFee * 9 / 10;
        if (dBid < baseFee) dBid = baseFee; if (dAsk < baseFee) dAsk = baseFee;
        if (trade.isBuy) { askFee = fresh > dAsk ? fresh : dAsk; bidFee = dBid; }
        else { bidFee = fresh > dBid ? fresh : dBid; askFee = dAsk; }
        bidFee = clampFee(bidFee); askFee = clampFee(askFee);
        slots[0] = bidFee; slots[1] = askFee; return (bidFee, askFee);
    }
    function getName() external pure override returns (string memory) { return "DSD"; }
}
"""

# H: Spike with DIFFERENT decay for same vs opposite side
# Same side: fast decay (quickly return to base for retail)
# Opposite side: slow decay (persist for arb protection)
STRATEGIES["DC_asymDecay"] = """// SPDX-License-Identifier: MIT
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
        // Asymmetric decay: same side decays faster, opposite slower
        if (trade.isBuy) {
            // same = bid (fast decay 6/7), opp = ask (slow decay 9/10)
            uint256 dBid = bidFee * 6 / 7;
            uint256 dAsk = askFee * 9 / 10;
            if (dBid < baseFee) dBid = baseFee; if (dAsk < baseFee) dAsk = baseFee;
            askFee = fresh > dAsk ? fresh : dAsk;
            bidFee = dBid;
        } else {
            uint256 dBid = bidFee * 9 / 10;
            uint256 dAsk = askFee * 6 / 7;
            if (dBid < baseFee) dBid = baseFee; if (dAsk < baseFee) dAsk = baseFee;
            bidFee = fresh > dBid ? fresh : dBid;
            askFee = dAsk;
        }
        bidFee = clampFee(bidFee); askFee = clampFee(askFee);
        slots[0] = bidFee; slots[1] = askFee; return (bidFee, askFee);
    }
    function getName() external pure override returns (string memory) { return "DAD"; }
}
"""

# I: Track both CURRENT fee and PREVIOUS trade's spike — use max for persistence
STRATEGIES["DC_spikeMax"] = """// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;
import {AMMStrategyBase} from "./AMMStrategyBase.sol";
import {IAMMStrategy, TradeInfo} from "./IAMMStrategy.sol";
contract Strategy is AMMStrategyBase {
    // slots[0]=bid, slots[1]=ask, slots[2]=prevSpike
    function afterInitialize(uint256, uint256) external override returns (uint256, uint256) {
        uint256 fee = 24 * BPS; slots[0] = fee; slots[1] = fee; return (fee, fee);
    }
    function afterSwap(TradeInfo calldata trade) external override returns (uint256, uint256) {
        uint256 bidFee = slots[0]; uint256 askFee = slots[1]; uint256 baseFee = 24 * BPS;
        uint256 prevSpike = slots[2];
        uint256 tr = wdiv(trade.amountY, trade.reserveY);
        uint256 spike = tr * 5 / 4 + wmul(tr, tr) * 15;
        // Use max of current and decayed previous spike
        uint256 dPrev = prevSpike * 7 / 8;
        uint256 effectiveSpike = spike > dPrev ? spike : dPrev;
        uint256 fresh = baseFee + effectiveSpike;
        uint256 dBid = bidFee * 8 / 9; uint256 dAsk = askFee * 8 / 9;
        if (dBid < baseFee) dBid = baseFee; if (dAsk < baseFee) dAsk = baseFee;
        if (trade.isBuy) { askFee = fresh > dAsk ? fresh : dAsk; bidFee = dBid; }
        else { bidFee = fresh > dBid ? fresh : dBid; askFee = dAsk; }
        bidFee = clampFee(bidFee); askFee = clampFee(askFee);
        slots[0] = bidFee; slots[1] = askFee; slots[2] = effectiveSpike;
        return (bidFee, askFee);
    }
    function getName() external pure override returns (string memory) { return "DSM"; }
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


print("=== Experiment 032: Alternative Spike Formulas (100 sims) ===\n")
results = []
order = ["DC_baseline", "DC_pureQuad", "DC_pureLin", "DC_fastDecay",
         "DC_bigFast", "DC_geoMean", "DC_reserveSpike", "DC_slowDecay",
         "DC_asymDecay", "DC_spikeMax"]
for name in order:
    edge = run_strategy(name, STRATEGIES[name], n_sims=100)
    print(f"{name:25s} -> edge={edge}", flush=True)
    results.append((name, edge))

print("\n=== 500-sim validation ===")
promising = [(name, STRATEGIES[name]) for name, edge in results
             if edge and edge > 505 and name != "DC_baseline"]
for name, code in promising:
    edge = run_strategy(name, code, n_sims=500)
    print(f"{name:25s} -> edge={edge} (500 sims)", flush=True)

# Restore
with open("my_strategy.sol", "w") as f:
    f.write(STRATEGIES["DC_baseline"])
print("\nRestored DC baseline")
