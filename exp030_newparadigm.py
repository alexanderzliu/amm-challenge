#!/usr/bin/env python3
"""Experiment 030: New Paradigm Search.

All spike/decay DirContrarian enhancements exhausted at ~497.
Need a fundamentally different mechanism to reach 525+.

Key insights:
- Fee after step N is what arb sees at step N+1
- Within a step: arb → afterSwap → (more arbs on other AMMs) → retail
- Retail routing depends on sqrt(k * gamma)
- k-preservation from spikes gives us routing advantage
- We capture ~57% retail due to k advantage (fee advantage is only ~0.01%)

New ideas to test:
1. Oscillating fee: alternate high/low each trade (arb pays high, retail pays low)
2. Counter-based: track total trades, use modular arithmetic
3. Predictive: use trade size to predict arb/retail, set fee accordingly
4. Accumulator: accumulate a "threat level" from large trades, drain on small trades
5. Dual-regime: explicitly track arb vs non-arb phases
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

# A: OSCILLATING FEE — after each trade, toggle between high and low
# On "high" phase: standard spike (arb protection)
# On "low" phase: base fee (retail capture)
# Since arb is typically the first trade of step, it should see "high" phase more often
STRATEGIES["Oscillator"] = """// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;
import {AMMStrategyBase} from "./AMMStrategyBase.sol";
import {IAMMStrategy, TradeInfo} from "./IAMMStrategy.sol";
contract Strategy is AMMStrategyBase {
    // slots[0]=bid, slots[1]=ask, slots[2]=phase (0=high,1=low)
    function afterInitialize(uint256, uint256) external override returns (uint256, uint256) {
        uint256 fee = 24 * BPS; slots[0] = fee; slots[1] = fee; slots[2] = 0; return (fee, fee);
    }
    function afterSwap(TradeInfo calldata trade) external override returns (uint256, uint256) {
        uint256 bidFee = slots[0]; uint256 askFee = slots[1];
        uint256 phase = slots[2]; uint256 baseFee = 24 * BPS;
        uint256 tr = wdiv(trade.amountY, trade.reserveY);
        // Always compute contrarian spike
        uint256 spike = tr * 5 / 4 + wmul(tr, tr) * 15;
        uint256 fresh = baseFee + spike;
        uint256 dBid = bidFee * 8 / 9; uint256 dAsk = askFee * 8 / 9;
        if (dBid < baseFee) dBid = baseFee; if (dAsk < baseFee) dAsk = baseFee;
        if (phase == 0) {
            // High phase: standard DirContrarian
            if (trade.isBuy) { askFee = fresh > dAsk ? fresh : dAsk; bidFee = dBid; }
            else { bidFee = fresh > dBid ? fresh : dBid; askFee = dAsk; }
        } else {
            // Low phase: just decay, no spike
            bidFee = dBid; askFee = dAsk;
        }
        bidFee = clampFee(bidFee); askFee = clampFee(askFee);
        slots[0] = bidFee; slots[1] = askFee;
        slots[2] = 1 - phase; // toggle
        return (bidFee, askFee);
    }
    function getName() external pure override returns (string memory) { return "OSC"; }
}
"""

# B: TRADE SIZE PREDICTIVE — the CURRENT trade tells us about the NEXT trade.
# If current trade is large (arb), next trade is likely retail → set LOW fee
# If current trade is small (retail), another retail might come, or arb next step → keep contrarian
# This reverses the usual logic: spike after small trades (anticipating arb), decay after large (anticipating retail)
STRATEGIES["DC_inversePred"] = """// SPDX-License-Identifier: MIT
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
        bool isLarge = tr > 3e15;  // arb threshold
        if (isLarge) {
            // Large trade (arb just happened) → next trade is probably retail
            // Set BOTH fees low for retail capture
            bidFee = baseFee; askFee = baseFee;
        } else {
            // Small trade (retail) → next might be arb (next step) OR more retail
            // Keep contrarian spike for arb protection
            uint256 spike = tr * 5 / 4 + wmul(tr, tr) * 15;
            uint256 fresh = baseFee + spike;
            uint256 dBid = bidFee * 8 / 9; uint256 dAsk = askFee * 8 / 9;
            if (dBid < baseFee) dBid = baseFee; if (dAsk < baseFee) dAsk = baseFee;
            if (trade.isBuy) { askFee = fresh > dAsk ? fresh : dAsk; bidFee = dBid; }
            else { bidFee = fresh > dBid ? fresh : dBid; askFee = dAsk; }
        }
        bidFee = clampFee(bidFee); askFee = clampFee(askFee);
        slots[0] = bidFee; slots[1] = askFee; return (bidFee, askFee);
    }
    function getName() external pure override returns (string memory) { return "DCIP"; }
}
"""

# C: ACCUMULATOR — maintains a "threat level" that increases with large trades
# and decreases with small trades. Fee = base + threat_level_component.
# This way, arb periods have high fees, calm periods have low fees.
STRATEGIES["Accumulator"] = """// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;
import {AMMStrategyBase} from "./AMMStrategyBase.sol";
import {IAMMStrategy, TradeInfo} from "./IAMMStrategy.sol";
contract Strategy is AMMStrategyBase {
    // slots[0]=bid, slots[1]=ask, slots[2]=threat
    function afterInitialize(uint256, uint256) external override returns (uint256, uint256) {
        uint256 fee = 24 * BPS; slots[0] = fee; slots[1] = fee; slots[2] = 0; return (fee, fee);
    }
    function afterSwap(TradeInfo calldata trade) external override returns (uint256, uint256) {
        uint256 bidFee = slots[0]; uint256 askFee = slots[1];
        uint256 threat = slots[2]; uint256 baseFee = 24 * BPS;
        uint256 tr = wdiv(trade.amountY, trade.reserveY);
        // Update threat: increases with trade size, decays naturally
        uint256 trContrib = tr * 5 / 4 + wmul(tr, tr) * 15;
        threat = threat * 7 / 8 + trContrib; // EMA-like accumulation
        // DirContrarian with threat-scaled spike
        uint256 fresh = baseFee + threat;
        uint256 dBid = bidFee * 8 / 9; uint256 dAsk = askFee * 8 / 9;
        if (dBid < baseFee) dBid = baseFee; if (dAsk < baseFee) dAsk = baseFee;
        if (trade.isBuy) { askFee = fresh > dAsk ? fresh : dAsk; bidFee = dBid; }
        else { bidFee = fresh > dBid ? fresh : dBid; askFee = dAsk; }
        bidFee = clampFee(bidFee); askFee = clampFee(askFee);
        slots[0] = bidFee; slots[1] = askFee; slots[2] = threat;
        return (bidFee, askFee);
    }
    function getName() external pure override returns (string memory) { return "ACC"; }
}
"""

# D: DOUBLE CONTRARIAN — After buy, spike ask AND ALSO set bid to a slightly
# higher value (28-30 bps) to earn more from same-side retail.
# Different from sameFloor: we ADD a small bump proportional to trade size on same side.
STRATEGIES["DC_dualSpike"] = """// SPDX-License-Identifier: MIT
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
        uint256 freshOpp = baseFee + spike;
        // Small same-side bump: just 1/10 of the spike
        uint256 freshSame = baseFee + spike / 10;
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
    function getName() external pure override returns (string memory) { return "DCDS"; }
}
"""

# E: DELAYED CONTRARIAN — After trade, don't spike immediately. Store the spike
# in a buffer. On the NEXT trade, apply the buffered spike to the opposite side.
# This delays the spike by one trade, so if arb→retail, the retail sees pre-spike fee.
STRATEGIES["DC_delayed"] = """// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;
import {AMMStrategyBase} from "./AMMStrategyBase.sol";
import {IAMMStrategy, TradeInfo} from "./IAMMStrategy.sol";
contract Strategy is AMMStrategyBase {
    // slots[0]=bid, slots[1]=ask, slots[2]=pendingSpike, slots[3]=pendingDir (1=bid, 2=ask)
    function afterInitialize(uint256, uint256) external override returns (uint256, uint256) {
        uint256 fee = 24 * BPS; slots[0] = fee; slots[1] = fee; return (fee, fee);
    }
    function afterSwap(TradeInfo calldata trade) external override returns (uint256, uint256) {
        uint256 bidFee = slots[0]; uint256 askFee = slots[1];
        uint256 pendSpike = slots[2]; uint256 pendDir = slots[3];
        uint256 baseFee = 24 * BPS;
        uint256 tr = wdiv(trade.amountY, trade.reserveY);
        // Apply pending spike from PREVIOUS trade
        uint256 dBid = bidFee * 8 / 9; uint256 dAsk = askFee * 8 / 9;
        if (dBid < baseFee) dBid = baseFee; if (dAsk < baseFee) dAsk = baseFee;
        if (pendDir == 2) { // pending spike on ask
            askFee = pendSpike > dAsk ? pendSpike : dAsk;
            bidFee = dBid;
        } else if (pendDir == 1) { // pending spike on bid
            bidFee = pendSpike > dBid ? pendSpike : dBid;
            askFee = dAsk;
        } else {
            bidFee = dBid; askFee = dAsk;
        }
        // Compute new spike for NEXT trade
        uint256 spike = tr * 5 / 4 + wmul(tr, tr) * 15;
        uint256 fresh = baseFee + spike;
        if (trade.isBuy) { pendSpike = fresh; pendDir = 2; } // spike ask next
        else { pendSpike = fresh; pendDir = 1; } // spike bid next
        bidFee = clampFee(bidFee); askFee = clampFee(askFee);
        slots[0] = bidFee; slots[1] = askFee;
        slots[2] = pendSpike; slots[3] = pendDir;
        return (bidFee, askFee);
    }
    function getName() external pure override returns (string memory) { return "DCD"; }
}
"""

# F: WEIGHTED by trade direction AND size
# If the trade was large (arb), spike stronger in opposite direction
# If the trade was small (retail), keep a weaker contrarian effect
STRATEGIES["DC_weightedSize"] = """// SPDX-License-Identifier: MIT
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
        // Standard spike
        uint256 spike = tr * 5 / 4 + wmul(tr, tr) * 15;
        uint256 freshOpp = baseFee + spike;
        // For same side: if large trade, decay aggressively. If small, gentle.
        uint256 dBid; uint256 dAsk;
        if (tr > 3e15) {
            // Large (arb): same side decays faster
            dBid = bidFee * 7 / 9;
            dAsk = askFee * 7 / 9;
        } else {
            // Small (retail): same side decays slower (retains more)
            dBid = bidFee * 17 / 18;
            dAsk = askFee * 17 / 18;
        }
        if (dBid < baseFee) dBid = baseFee; if (dAsk < baseFee) dAsk = baseFee;
        if (trade.isBuy) { askFee = freshOpp > dAsk ? freshOpp : dAsk; bidFee = dBid; }
        else { bidFee = freshOpp > dBid ? freshOpp : dBid; askFee = dAsk; }
        bidFee = clampFee(bidFee); askFee = clampFee(askFee);
        slots[0] = bidFee; slots[1] = askFee; return (bidFee, askFee);
    }
    function getName() external pure override returns (string memory) { return "DCWS"; }
}
"""

# G: OPPOSITE SAME-SIDE SPIKE — After trade, instead of decaying same side,
# actually spike SAME side by a TINY amount (1-2 bps). This gives extra revenue
# from same-side retail while maintaining contrarian protection on opposite.
# Very different from the hybrid (exp 025) which used same formula for both sides.
STRATEGIES["DC_sameMicro"] = """// SPDX-License-Identifier: MIT
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
        uint256 freshOpp = baseFee + spike;
        // Micro-spike: same side gets a tiny boost (2 bps floor above base)
        uint256 sameMin = 26 * BPS;
        uint256 dBid = bidFee * 8 / 9; uint256 dAsk = askFee * 8 / 9;
        if (dBid < baseFee) dBid = baseFee; if (dAsk < baseFee) dAsk = baseFee;
        if (trade.isBuy) {
            askFee = freshOpp > dAsk ? freshOpp : dAsk;
            bidFee = dBid < sameMin ? sameMin : dBid;
        } else {
            bidFee = freshOpp > dBid ? freshOpp : dBid;
            askFee = dAsk < sameMin ? sameMin : dAsk;
        }
        bidFee = clampFee(bidFee); askFee = clampFee(askFee);
        slots[0] = bidFee; slots[1] = askFee; return (bidFee, askFee);
    }
    function getName() external pure override returns (string memory) { return "DCSM"; }
}
"""

# H: INVERSE CONTRARIAN — What if we spike the SAME direction and set opposite low?
# Already tested as "same-direction spike" (302 edge), but let's confirm it's bad.
# Actually, what about: same=spike, opposite=base, but with DIFFERENT spike params?
# Skip — already confirmed catastrophic in exp 025.

# I: REVERSE TIMING — Set fee HIGH as default. After arb (large trade), LOWER it.
# So arb sees high fee (good), retail sees lowered fee after arb (good for capture).
# The catch: between steps (no trades), fee stays high.
STRATEGIES["DC_highDefault"] = """// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;
import {AMMStrategyBase} from "./AMMStrategyBase.sol";
import {IAMMStrategy, TradeInfo} from "./IAMMStrategy.sol";
contract Strategy is AMMStrategyBase {
    function afterInitialize(uint256, uint256) external override returns (uint256, uint256) {
        uint256 fee = 80 * BPS; slots[0] = fee; slots[1] = fee; return (fee, fee);
    }
    function afterSwap(TradeInfo calldata trade) external override returns (uint256, uint256) {
        uint256 bidFee = slots[0]; uint256 askFee = slots[1];
        uint256 highFee = 80 * BPS; uint256 lowFee = 24 * BPS;
        uint256 tr = wdiv(trade.amountY, trade.reserveY);
        bool isLarge = tr > 3e15;
        if (isLarge) {
            // After arb: drop fee for retail capture (contrarian direction)
            if (trade.isBuy) { askFee = lowFee; bidFee = lowFee; }
            else { bidFee = lowFee; askFee = lowFee; }
        } else {
            // After retail: gradually raise back to high
            uint256 rBid = bidFee + (highFee - bidFee) / 4;
            uint256 rAsk = askFee + (highFee - askFee) / 4;
            bidFee = rBid; askFee = rAsk;
        }
        bidFee = clampFee(bidFee); askFee = clampFee(askFee);
        slots[0] = bidFee; slots[1] = askFee; return (bidFee, askFee);
    }
    function getName() external pure override returns (string memory) { return "HD"; }
}
"""

# J: FAST RISE to high after small trades (so arb sees high fee),
# with instant drop after large trade (so retail sees low fee).
# This is "reverse decay" — fee increases over time between arbs.
STRATEGIES["DC_reverseDecay"] = """// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;
import {AMMStrategyBase} from "./AMMStrategyBase.sol";
import {IAMMStrategy, TradeInfo} from "./IAMMStrategy.sol";
contract Strategy is AMMStrategyBase {
    function afterInitialize(uint256, uint256) external override returns (uint256, uint256) {
        uint256 fee = 80 * BPS; slots[0] = fee; slots[1] = fee; return (fee, fee);
    }
    function afterSwap(TradeInfo calldata trade) external override returns (uint256, uint256) {
        uint256 bidFee = slots[0]; uint256 askFee = slots[1];
        uint256 highFee = 80 * BPS; uint256 lowFee = 24 * BPS;
        uint256 tr = wdiv(trade.amountY, trade.reserveY);
        bool isLarge = tr > 3e15;
        if (isLarge) {
            // After arb: contrarian drop — opposite low, same high
            if (trade.isBuy) { askFee = lowFee; bidFee = highFee; }
            else { bidFee = lowFee; askFee = highFee; }
        } else {
            // After retail: INCREASE both fees toward high
            bidFee = bidFee + (highFee - bidFee) / 3;
            askFee = askFee + (highFee - askFee) / 3;
        }
        bidFee = clampFee(bidFee); askFee = clampFee(askFee);
        slots[0] = bidFee; slots[1] = askFee; return (bidFee, askFee);
    }
    function getName() external pure override returns (string memory) { return "RD"; }
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


print("=== Experiment 030: New Paradigm Search (100 sims) ===\n")
results = []
order = ["DC_baseline", "Oscillator", "DC_inversePred", "Accumulator",
         "DC_dualSpike", "DC_delayed", "DC_weightedSize", "DC_sameMicro",
         "DC_highDefault", "DC_reverseDecay"]
for name in order:
    code = STRATEGIES[name]
    edge = run_strategy(name, code, n_sims=100)
    print(f"{name:25s} -> edge={edge}", flush=True)
    results.append((name, edge))

print("\n=== 500-sim validation ===")
promising = [(name, STRATEGIES[name]) for name, edge in results
             if edge and edge > 504 and name != "DC_baseline"]
for name, code in promising:
    edge = run_strategy(name, code, n_sims=500)
    print(f"{name:25s} -> edge={edge} (500 sims)", flush=True)

# Restore
with open("my_strategy.sol", "w") as f:
    f.write(STRATEGIES["DC_baseline"])
print("\nRestored DC_baseline")
