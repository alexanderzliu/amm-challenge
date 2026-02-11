#!/usr/bin/env python3
"""Experiment 034: No-Memory and Fresh-Only Fee Strategies.

Key insight: the MAX operation (max(fresh, decayed)) makes the decayed
arb spike persist for retail. What if we DON'T persist?

Variants:
A) Pure fresh (no memory): fee = baseFee + spike(current_trade)
   After arb: fee = high. After retail: fee = low. No persistence.

B) Blended: fee = alpha * fresh + (1-alpha) * decayed
   Instead of max, use a weighted average

C) Conditional max: only persist if the NEW spike is also large
   If new spike < threshold, use fresh only (reset)

D) Direction-aware fresh: keep contrarian spike, but RESET on direction change
   If arb was buy, spike ask. If next trade is sell (same as arb), reset ask to fresh.

E) What if same-side fee is ALWAYS fresh (no memory)?
   Opposite side uses max(fresh, decayed) for persistence.
   Same side uses fresh only — after small retail, it's base+tiny.
"""

import subprocess

STRATEGIES = {}

# Baseline
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

# A: Pure fresh — no memory at all
STRATEGIES["DC_noMem"] = """// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;
import {AMMStrategyBase} from "./AMMStrategyBase.sol";
import {IAMMStrategy, TradeInfo} from "./IAMMStrategy.sol";
contract Strategy is AMMStrategyBase {
    function afterInitialize(uint256, uint256) external override returns (uint256, uint256) {
        uint256 fee = 24 * BPS; return (fee, fee);
    }
    function afterSwap(TradeInfo calldata trade) external override returns (uint256, uint256) {
        uint256 baseFee = 24 * BPS;
        uint256 tr = wdiv(trade.amountY, trade.reserveY);
        uint256 spike = tr * 5 / 4 + wmul(tr, tr) * 15;
        uint256 fresh = baseFee + spike;
        uint256 bidFee; uint256 askFee;
        if (trade.isBuy) { askFee = fresh; bidFee = baseFee; }
        else { bidFee = fresh; askFee = baseFee; }
        bidFee = clampFee(bidFee); askFee = clampFee(askFee);
        return (bidFee, askFee);
    }
    function getName() external pure override returns (string memory) { return "DCNM"; }
}
"""

# B: Blended — fresh and decayed averaged
STRATEGIES["DC_blend50"] = """// SPDX-License-Identifier: MIT
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
            askFee = (fresh + dAsk) / 2; // Blend 50/50
            bidFee = dBid;
        } else {
            bidFee = (fresh + dBid) / 2;
            askFee = dAsk;
        }
        bidFee = clampFee(bidFee); askFee = clampFee(askFee);
        slots[0] = bidFee; slots[1] = askFee; return (bidFee, askFee);
    }
    function getName() external pure override returns (string memory) { return "DCB5"; }
}
"""

# C: Opp uses max (persistent), same uses fresh only (no memory on same side)
STRATEGIES["DC_freshSame"] = """// SPDX-License-Identifier: MIT
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
            askFee = fresh > dAsk ? fresh : dAsk; // opp: max (persistent)
            bidFee = baseFee + spike; // same: fresh only (always from current trade)
            if (bidFee < baseFee) bidFee = baseFee;
        } else {
            bidFee = fresh > dBid ? fresh : dBid;
            askFee = baseFee + spike;
            if (askFee < baseFee) askFee = baseFee;
        }
        bidFee = clampFee(bidFee); askFee = clampFee(askFee);
        slots[0] = bidFee; slots[1] = askFee; return (bidFee, askFee);
    }
    function getName() external pure override returns (string memory) { return "DCFS"; }
}
"""

# D: ADDITIVE spike update (instead of max)
# fee_new = decayed + spike (not max(fresh, decayed))
# This means each trade ADDS to the accumulated fee
# After arb: fee goes very high
# After retail: fee gets a tiny addition to the decayed high value
# With fast enough decay, this could work
STRATEGIES["DC_additive"] = """// SPDX-License-Identifier: MIT
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
        uint256 dBid = bidFee * 7 / 8; uint256 dAsk = askFee * 7 / 8;
        if (dBid < baseFee) dBid = baseFee; if (dAsk < baseFee) dAsk = baseFee;
        // ADDITIVE: decayed + fresh spike (instead of max)
        if (trade.isBuy) {
            askFee = dAsk + spike; // add spike to decayed
            bidFee = dBid; // same side just decays
        } else {
            bidFee = dBid + spike;
            askFee = dAsk;
        }
        bidFee = clampFee(bidFee); askFee = clampFee(askFee);
        slots[0] = bidFee; slots[1] = askFee; return (bidFee, askFee);
    }
    function getName() external pure override returns (string memory) { return "DCA"; }
}
"""

# E: REPLACE always (fee = fresh, ignoring decayed, but keep opp persistent)
# Same side: always fresh from current trade (baseFee + tiny_spike for retail)
# Opp side: always fresh from current trade (baseFee + spike)
# No decay at all — each trade completely determines next fee
STRATEGIES["DC_replace"] = """// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;
import {AMMStrategyBase} from "./AMMStrategyBase.sol";
import {IAMMStrategy, TradeInfo} from "./IAMMStrategy.sol";
contract Strategy is AMMStrategyBase {
    function afterInitialize(uint256, uint256) external override returns (uint256, uint256) {
        uint256 fee = 24 * BPS; return (fee, fee);
    }
    function afterSwap(TradeInfo calldata trade) external override returns (uint256, uint256) {
        uint256 baseFee = 24 * BPS;
        uint256 tr = wdiv(trade.amountY, trade.reserveY);
        uint256 spike = tr * 5 / 4 + wmul(tr, tr) * 15;
        uint256 oppFee = baseFee + spike;
        uint256 sameFee = baseFee; // Same side always at base
        uint256 bidFee; uint256 askFee;
        if (trade.isBuy) { askFee = oppFee; bidFee = sameFee; }
        else { bidFee = oppFee; askFee = sameFee; }
        bidFee = clampFee(bidFee); askFee = clampFee(askFee);
        return (bidFee, askFee);
    }
    function getName() external pure override returns (string memory) { return "DCR"; }
}
"""

# F: SYMMETRIC but with much faster spike rise and VERY slow decay
# The idea: symmetric means BOTH sides spike after arb, so arb protection
# on both sides. But the spike is moderate (not huge) and decays very slowly.
# Over time, average fee stays around 36 bps (matching winner).
STRATEGIES["Sym_moderate"] = """// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;
import {AMMStrategyBase} from "./AMMStrategyBase.sol";
import {IAMMStrategy, TradeInfo} from "./IAMMStrategy.sol";
contract Strategy is AMMStrategyBase {
    function afterInitialize(uint256, uint256) external override returns (uint256, uint256) {
        uint256 fee = 36 * BPS; slots[0] = fee; return (fee, fee);
    }
    function afterSwap(TradeInfo calldata trade) external override returns (uint256, uint256) {
        uint256 curFee = slots[0]; uint256 baseFee = 36 * BPS;
        uint256 tr = wdiv(trade.amountY, trade.reserveY);
        // Moderate spike, meant to keep fee around 36-50 bps
        uint256 spike = tr * 1 / 2 + wmul(tr, tr) * 5;
        uint256 fresh = baseFee + spike;
        uint256 decayed = curFee * 19 / 20; // Very slow decay
        if (decayed < baseFee) decayed = baseFee;
        uint256 fee = fresh > decayed ? fresh : decayed;
        fee = clampFee(fee);
        slots[0] = fee; return (fee, fee);
    }
    function getName() external pure override returns (string memory) { return "SM"; }
}
"""

# G: What about WEIGHTED by trade direction count? Track how many consecutive
# trades in same direction, use it to modulate spike
STRATEGIES["DC_dirCount"] = """// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;
import {AMMStrategyBase} from "./AMMStrategyBase.sol";
import {IAMMStrategy, TradeInfo} from "./IAMMStrategy.sol";
contract Strategy is AMMStrategyBase {
    // slots[0]=bid, slots[1]=ask, slots[2]=buyCount, slots[3]=sellCount
    function afterInitialize(uint256, uint256) external override returns (uint256, uint256) {
        uint256 fee = 24 * BPS; slots[0] = fee; slots[1] = fee; return (fee, fee);
    }
    function afterSwap(TradeInfo calldata trade) external override returns (uint256, uint256) {
        uint256 bidFee = slots[0]; uint256 askFee = slots[1]; uint256 baseFee = 24 * BPS;
        uint256 buys = slots[2]; uint256 sells = slots[3];
        uint256 tr = wdiv(trade.amountY, trade.reserveY);
        if (trade.isBuy) { buys = buys + 1; sells = sells > 0 ? sells - 1 : 0; }
        else { sells = sells + 1; buys = buys > 0 ? buys - 1 : 0; }
        // More consecutive buys → stronger ask spike
        uint256 spike = tr * 5 / 4 + wmul(tr, tr) * 15;
        uint256 fresh = baseFee + spike;
        uint256 dBid = bidFee * 8 / 9; uint256 dAsk = askFee * 8 / 9;
        if (dBid < baseFee) dBid = baseFee; if (dAsk < baseFee) dAsk = baseFee;
        if (trade.isBuy) {
            // More buy pressure → spike ask more
            uint256 mult = buys > 5 ? 5 : buys;
            uint256 adjFresh = baseFee + spike * (10 + mult) / 10;
            askFee = adjFresh > dAsk ? adjFresh : dAsk;
            bidFee = dBid;
        } else {
            uint256 mult = sells > 5 ? 5 : sells;
            uint256 adjFresh = baseFee + spike * (10 + mult) / 10;
            bidFee = adjFresh > dBid ? adjFresh : dBid;
            askFee = dAsk;
        }
        bidFee = clampFee(bidFee); askFee = clampFee(askFee);
        slots[0] = bidFee; slots[1] = askFee; slots[2] = buys; slots[3] = sells;
        return (bidFee, askFee);
    }
    function getName() external pure override returns (string memory) { return "DCDC"; }
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


print("=== Experiment 034: No-Memory & Alternative Update Rules (100 sims) ===\n")
results = []
order = ["DC_base", "DC_noMem", "DC_blend50", "DC_freshSame",
         "DC_additive", "DC_replace", "Sym_moderate", "DC_dirCount"]
for name in order:
    edge = run_strategy(name, STRATEGIES[name], n_sims=100)
    print(f"{name:25s} -> edge={edge}", flush=True)
    results.append((name, edge))

print("\n=== 500-sim validation ===")
promising = [(name, STRATEGIES[name]) for name, edge in results
             if edge and edge > 505 and name != "DC_base"]
for name, code in promising:
    edge = run_strategy(name, code, n_sims=500)
    print(f"{name:25s} -> edge={edge} (500 sims)", flush=True)

# Restore
with open("my_strategy.sol", "w") as f:
    f.write(STRATEGIES["DC_base"])
print("\nRestored DC baseline")
