#!/usr/bin/env python3
"""Experiment 028: Retail Fee Optimization.

Key observation: Winner earns 36 bps avg on retail while capturing 77K retail (vs our 24 bps on 63K).
Winner's retail revenue: ~77K * 36 bps = much higher than ours: ~63K * 24 bps.
This suggests either:
  A) Higher base fee with DirContrarian (needs spike rebalancing)
  B) Size-dependent fee behavior (low for arb detection, higher for retail)
  C) Completely different mechanism that achieves ~36 bps avg with good routing

Test: various base fees with DirContrarian, constant fees, and new mechanisms."""

import subprocess

STRATEGIES = {}

# --- BASELINES ---
STRATEGIES["DC_base24"] = """// SPDX-License-Identifier: MIT
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
    function getName() external pure override returns (string memory) { return "DC24"; }
}
"""

# Constant fee = winner's avg
STRATEGIES["Const36"] = """// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;
import {AMMStrategyBase} from "./AMMStrategyBase.sol";
import {IAMMStrategy, TradeInfo} from "./IAMMStrategy.sol";
contract Strategy is AMMStrategyBase {
    function afterInitialize(uint256, uint256) external override returns (uint256, uint256) {
        uint256 fee = 36 * BPS; return (fee, fee);
    }
    function afterSwap(TradeInfo calldata) external override returns (uint256, uint256) {
        uint256 fee = 36 * BPS; return (fee, fee);
    }
    function getName() external pure override returns (string memory) { return "C36"; }
}
"""

# --- DirContrarian with higher bases + REBALANCED spikes ---
# At higher base, the spike adds on top. Reduce spike to keep total spike similar.
# Currently: base=24, spike = tr*5/4 + tr^2*15. At tr=0.01: spike ≈ 0.0125 + 0.0015 = 0.014 WAD ≈ 140 bps
# Total at tr=0.01: 24 + 140 = 164 bps
# With base=36, to keep same total: spike = tr*5/4 + tr^2*15 - 12*BPS? No, that's wrong.
# Actually, the spike formula should stay the same — it's responding to trade size, not base.
# The base just shifts where retail sees the fee during calm periods.

# Simple higher base
STRATEGIES["DC_base30"] = """// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;
import {AMMStrategyBase} from "./AMMStrategyBase.sol";
import {IAMMStrategy, TradeInfo} from "./IAMMStrategy.sol";
contract Strategy is AMMStrategyBase {
    function afterInitialize(uint256, uint256) external override returns (uint256, uint256) {
        uint256 fee = 30 * BPS; slots[0] = fee; slots[1] = fee; return (fee, fee);
    }
    function afterSwap(TradeInfo calldata trade) external override returns (uint256, uint256) {
        uint256 bidFee = slots[0]; uint256 askFee = slots[1]; uint256 baseFee = 30 * BPS;
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
    function getName() external pure override returns (string memory) { return "DC30"; }
}
"""

STRATEGIES["DC_base36"] = """// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;
import {AMMStrategyBase} from "./AMMStrategyBase.sol";
import {IAMMStrategy, TradeInfo} from "./IAMMStrategy.sol";
contract Strategy is AMMStrategyBase {
    function afterInitialize(uint256, uint256) external override returns (uint256, uint256) {
        uint256 fee = 36 * BPS; slots[0] = fee; slots[1] = fee; return (fee, fee);
    }
    function afterSwap(TradeInfo calldata trade) external override returns (uint256, uint256) {
        uint256 bidFee = slots[0]; uint256 askFee = slots[1]; uint256 baseFee = 36 * BPS;
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
    function getName() external pure override returns (string memory) { return "DC36"; }
}
"""

# DC base 36 with REDUCED spike (since base already provides more arb protection)
STRATEGIES["DC_b36_weakspk"] = """// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;
import {AMMStrategyBase} from "./AMMStrategyBase.sol";
import {IAMMStrategy, TradeInfo} from "./IAMMStrategy.sol";
contract Strategy is AMMStrategyBase {
    function afterInitialize(uint256, uint256) external override returns (uint256, uint256) {
        uint256 fee = 36 * BPS; slots[0] = fee; slots[1] = fee; return (fee, fee);
    }
    function afterSwap(TradeInfo calldata trade) external override returns (uint256, uint256) {
        uint256 bidFee = slots[0]; uint256 askFee = slots[1]; uint256 baseFee = 36 * BPS;
        uint256 tr = wdiv(trade.amountY, trade.reserveY);
        uint256 spike = tr * 3 / 4 + wmul(tr, tr) * 10;
        uint256 fresh = baseFee + spike;
        uint256 dBid = bidFee * 8 / 9; uint256 dAsk = askFee * 8 / 9;
        if (dBid < baseFee) dBid = baseFee; if (dAsk < baseFee) dAsk = baseFee;
        if (trade.isBuy) { askFee = fresh > dAsk ? fresh : dAsk; bidFee = dBid; }
        else { bidFee = fresh > dBid ? fresh : dBid; askFee = dAsk; }
        bidFee = clampFee(bidFee); askFee = clampFee(askFee);
        slots[0] = bidFee; slots[1] = askFee; return (bidFee, askFee);
    }
    function getName() external pure override returns (string memory) { return "DC36w"; }
}
"""

# --- SIZE-DEPENDENT FEE: different behavior for small vs large trades ---
# After large trade (arb): standard contrarian spike
# After small trade (retail): rapid decay to moderate level (36 bps)
# This way arb sees spikes, but fee quickly drops to 36 for following retail
STRATEGIES["DC_sizeDecay36"] = """// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;
import {AMMStrategyBase} from "./AMMStrategyBase.sol";
import {IAMMStrategy, TradeInfo} from "./IAMMStrategy.sol";
contract Strategy is AMMStrategyBase {
    function afterInitialize(uint256, uint256) external override returns (uint256, uint256) {
        uint256 fee = 24 * BPS; slots[0] = fee; slots[1] = fee; return (fee, fee);
    }
    function afterSwap(TradeInfo calldata trade) external override returns (uint256, uint256) {
        uint256 bidFee = slots[0]; uint256 askFee = slots[1];
        uint256 baseFee = 24 * BPS;
        uint256 retailTarget = 36 * BPS;
        uint256 tr = wdiv(trade.amountY, trade.reserveY);
        bool isLarge = tr > 3e15; // ~0.3% of reserves = likely arb
        if (isLarge) {
            // Standard DirContrarian spike
            uint256 spike = tr * 5 / 4 + wmul(tr, tr) * 15;
            uint256 fresh = baseFee + spike;
            uint256 dBid = bidFee * 8 / 9; uint256 dAsk = askFee * 8 / 9;
            if (dBid < baseFee) dBid = baseFee; if (dAsk < baseFee) dAsk = baseFee;
            if (trade.isBuy) { askFee = fresh > dAsk ? fresh : dAsk; bidFee = dBid; }
            else { bidFee = fresh > dBid ? fresh : dBid; askFee = dAsk; }
        } else {
            // Small trade (retail): rapid decay toward retailTarget on spiked side
            // Same-side: set to retailTarget
            // Opposite-side: fast decay (halve toward retailTarget)
            uint256 dBid = (bidFee + retailTarget) / 2;
            uint256 dAsk = (askFee + retailTarget) / 2;
            if (dBid < retailTarget) dBid = retailTarget;
            if (dAsk < retailTarget) dAsk = retailTarget;
            bidFee = dBid; askFee = dAsk;
        }
        bidFee = clampFee(bidFee); askFee = clampFee(askFee);
        slots[0] = bidFee; slots[1] = askFee; return (bidFee, askFee);
    }
    function getName() external pure override returns (string memory) { return "DCSD36"; }
}
"""

# Same idea but decay to 30 (match vanilla exactly)
STRATEGIES["DC_sizeDecay30"] = """// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;
import {AMMStrategyBase} from "./AMMStrategyBase.sol";
import {IAMMStrategy, TradeInfo} from "./IAMMStrategy.sol";
contract Strategy is AMMStrategyBase {
    function afterInitialize(uint256, uint256) external override returns (uint256, uint256) {
        uint256 fee = 24 * BPS; slots[0] = fee; slots[1] = fee; return (fee, fee);
    }
    function afterSwap(TradeInfo calldata trade) external override returns (uint256, uint256) {
        uint256 bidFee = slots[0]; uint256 askFee = slots[1];
        uint256 baseFee = 24 * BPS;
        uint256 retailTarget = 30 * BPS;
        uint256 tr = wdiv(trade.amountY, trade.reserveY);
        bool isLarge = tr > 3e15;
        if (isLarge) {
            uint256 spike = tr * 5 / 4 + wmul(tr, tr) * 15;
            uint256 fresh = baseFee + spike;
            uint256 dBid = bidFee * 8 / 9; uint256 dAsk = askFee * 8 / 9;
            if (dBid < baseFee) dBid = baseFee; if (dAsk < baseFee) dAsk = baseFee;
            if (trade.isBuy) { askFee = fresh > dAsk ? fresh : dAsk; bidFee = dBid; }
            else { bidFee = fresh > dBid ? fresh : dBid; askFee = dAsk; }
        } else {
            uint256 dBid = (bidFee + retailTarget) / 2;
            uint256 dAsk = (askFee + retailTarget) / 2;
            if (dBid < retailTarget) dBid = retailTarget;
            if (dAsk < retailTarget) dAsk = retailTarget;
            bidFee = dBid; askFee = dAsk;
        }
        bidFee = clampFee(bidFee); askFee = clampFee(askFee);
        slots[0] = bidFee; slots[1] = askFee; return (bidFee, askFee);
    }
    function getName() external pure override returns (string memory) { return "DCSD30"; }
}
"""

# --- SAME-SIDE FLOOR: DirContrarian but same side never goes below 36 bps ---
# Retail on same side pays 36 bps instead of 24 → more revenue per trade
STRATEGIES["DC_sameFloor36"] = """// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;
import {AMMStrategyBase} from "./AMMStrategyBase.sol";
import {IAMMStrategy, TradeInfo} from "./IAMMStrategy.sol";
contract Strategy is AMMStrategyBase {
    function afterInitialize(uint256, uint256) external override returns (uint256, uint256) {
        uint256 fee = 36 * BPS; slots[0] = fee; slots[1] = fee; return (fee, fee);
    }
    function afterSwap(TradeInfo calldata trade) external override returns (uint256, uint256) {
        uint256 bidFee = slots[0]; uint256 askFee = slots[1];
        uint256 baseFee = 24 * BPS;
        uint256 sameFloor = 36 * BPS;
        uint256 tr = wdiv(trade.amountY, trade.reserveY);
        uint256 spike = tr * 5 / 4 + wmul(tr, tr) * 15;
        uint256 fresh = baseFee + spike;
        uint256 dBid = bidFee * 8 / 9; uint256 dAsk = askFee * 8 / 9;
        if (dBid < baseFee) dBid = baseFee; if (dAsk < baseFee) dAsk = baseFee;
        if (trade.isBuy) {
            askFee = fresh > dAsk ? fresh : dAsk;
            bidFee = dBid < sameFloor ? sameFloor : dBid; // Same side floor = 36
        } else {
            bidFee = fresh > dBid ? fresh : dBid;
            askFee = dAsk < sameFloor ? sameFloor : dAsk; // Same side floor = 36
        }
        bidFee = clampFee(bidFee); askFee = clampFee(askFee);
        slots[0] = bidFee; slots[1] = askFee; return (bidFee, askFee);
    }
    function getName() external pure override returns (string memory) { return "DCSF36"; }
}
"""

# --- MATCH VANILLA: same side fee = 30 bps (match vanilla exactly → 50/50 routing) ---
STRATEGIES["DC_sameFloor30"] = """// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;
import {AMMStrategyBase} from "./AMMStrategyBase.sol";
import {IAMMStrategy, TradeInfo} from "./IAMMStrategy.sol";
contract Strategy is AMMStrategyBase {
    function afterInitialize(uint256, uint256) external override returns (uint256, uint256) {
        uint256 fee = 30 * BPS; slots[0] = fee; slots[1] = fee; return (fee, fee);
    }
    function afterSwap(TradeInfo calldata trade) external override returns (uint256, uint256) {
        uint256 bidFee = slots[0]; uint256 askFee = slots[1];
        uint256 baseFee = 24 * BPS;
        uint256 sameFloor = 30 * BPS;
        uint256 tr = wdiv(trade.amountY, trade.reserveY);
        uint256 spike = tr * 5 / 4 + wmul(tr, tr) * 15;
        uint256 fresh = baseFee + spike;
        uint256 dBid = bidFee * 8 / 9; uint256 dAsk = askFee * 8 / 9;
        if (dBid < baseFee) dBid = baseFee; if (dAsk < baseFee) dAsk = baseFee;
        if (trade.isBuy) {
            askFee = fresh > dAsk ? fresh : dAsk;
            bidFee = dBid < sameFloor ? sameFloor : dBid;
        } else {
            bidFee = fresh > dBid ? fresh : dBid;
            askFee = dAsk < sameFloor ? sameFloor : dAsk;
        }
        bidFee = clampFee(bidFee); askFee = clampFee(askFee);
        slots[0] = bidFee; slots[1] = askFee; return (bidFee, askFee);
    }
    function getName() external pure override returns (string memory) { return "DCSF30"; }
}
"""

# --- NEW PARADIGM: Step-aware fee switching ---
# Track timestamp. After first trade of new step (likely arb): spike high.
# After subsequent trades in same step (retail): set moderate fee.
STRATEGIES["DC_stepAware"] = """// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;
import {AMMStrategyBase} from "./AMMStrategyBase.sol";
import {IAMMStrategy, TradeInfo} from "./IAMMStrategy.sol";
contract Strategy is AMMStrategyBase {
    // slots[0]=bid, slots[1]=ask, slots[2]=lastTs, slots[3]=tradeCount
    function afterInitialize(uint256, uint256) external override returns (uint256, uint256) {
        uint256 fee = 24 * BPS; slots[0] = fee; slots[1] = fee; return (fee, fee);
    }
    function afterSwap(TradeInfo calldata trade) external override returns (uint256, uint256) {
        uint256 bidFee = slots[0]; uint256 askFee = slots[1];
        uint256 lastTs = slots[2]; uint256 cnt = slots[3];
        uint256 baseFee = 24 * BPS;
        uint256 tr = wdiv(trade.amountY, trade.reserveY);
        bool newStep = trade.timestamp != lastTs;
        if (newStep) { cnt = 1; } else { cnt = cnt + 1; }
        if (cnt <= 1) {
            // First trade of step (usually arb) — standard DirContrarian
            uint256 spike = tr * 5 / 4 + wmul(tr, tr) * 15;
            uint256 fresh = baseFee + spike;
            uint256 dBid = bidFee * 8 / 9; uint256 dAsk = askFee * 8 / 9;
            if (dBid < baseFee) dBid = baseFee; if (dAsk < baseFee) dAsk = baseFee;
            if (trade.isBuy) { askFee = fresh > dAsk ? fresh : dAsk; bidFee = dBid; }
            else { bidFee = fresh > dBid ? fresh : dBid; askFee = dAsk; }
        } else {
            // Subsequent trades (retail) — set both to moderate level
            uint256 modFee = 30 * BPS;
            // Decay spiked side fast, raise low side
            if (bidFee > modFee) bidFee = (bidFee + modFee) / 2;
            else bidFee = modFee;
            if (askFee > modFee) askFee = (askFee + modFee) / 2;
            else askFee = modFee;
        }
        bidFee = clampFee(bidFee); askFee = clampFee(askFee);
        slots[0] = bidFee; slots[1] = askFee;
        slots[2] = trade.timestamp; slots[3] = cnt;
        return (bidFee, askFee);
    }
    function getName() external pure override returns (string memory) { return "DCSA"; }
}
"""

# --- CONTRARIAN + BOTH SIDES MODERATE SPIKE ---
# After trade: spike opposite high, but ALSO bump same side to 36 bps
STRATEGIES["DC_bothBump"] = """// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;
import {AMMStrategyBase} from "./AMMStrategyBase.sol";
import {IAMMStrategy, TradeInfo} from "./IAMMStrategy.sol";
contract Strategy is AMMStrategyBase {
    function afterInitialize(uint256, uint256) external override returns (uint256, uint256) {
        uint256 fee = 36 * BPS; slots[0] = fee; slots[1] = fee; return (fee, fee);
    }
    function afterSwap(TradeInfo calldata trade) external override returns (uint256, uint256) {
        uint256 bidFee = slots[0]; uint256 askFee = slots[1];
        uint256 baseFee = 24 * BPS;
        uint256 sameBump = 36 * BPS;
        uint256 tr = wdiv(trade.amountY, trade.reserveY);
        uint256 spike = tr * 5 / 4 + wmul(tr, tr) * 15;
        uint256 fresh = baseFee + spike;
        uint256 dBid = bidFee * 8 / 9; uint256 dAsk = askFee * 8 / 9;
        if (dBid < baseFee) dBid = baseFee; if (dAsk < baseFee) dAsk = baseFee;
        if (trade.isBuy) {
            askFee = fresh > dAsk ? fresh : dAsk;
            bidFee = dBid < sameBump ? sameBump : dBid; // bump same side
        } else {
            bidFee = fresh > dBid ? fresh : dBid;
            askFee = dAsk < sameBump ? sameBump : dAsk;
        }
        bidFee = clampFee(bidFee); askFee = clampFee(askFee);
        slots[0] = bidFee; slots[1] = askFee; return (bidFee, askFee);
    }
    function getName() external pure override returns (string memory) { return "DCBB"; }
}
"""

# --- SYMMETRIC SPIKE AT BASE 36 ---
# What if the winner uses symmetric spike (both sides) at base 36?
# Higher base provides both-sides protection, spike adds on top
STRATEGIES["Sym_base36"] = """// SPDX-License-Identifier: MIT
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
        uint256 spike = tr * 5 / 4 + wmul(tr, tr) * 15;
        uint256 fresh = baseFee + spike;
        uint256 decayed = curFee * 8 / 9;
        if (decayed < baseFee) decayed = baseFee;
        uint256 fee = fresh > decayed ? fresh : decayed;
        fee = clampFee(fee);
        slots[0] = fee; return (fee, fee);
    }
    function getName() external pure override returns (string memory) { return "S36"; }
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


print("=== Experiment 028: Retail Fee Optimization (100 sims) ===\n")
results = []
order = ["DC_base24", "Const36", "DC_base30", "DC_base36", "DC_b36_weakspk",
         "DC_sizeDecay36", "DC_sizeDecay30", "DC_sameFloor36", "DC_sameFloor30",
         "DC_stepAware", "DC_bothBump", "Sym_base36"]
for name in order:
    code = STRATEGIES[name]
    edge = run_strategy(name, code, n_sims=100)
    print(f"{name:25s} -> edge={edge}", flush=True)
    results.append((name, edge))

print("\n=== 500-sim validation ===")
promising = [(name, STRATEGIES[name]) for name, edge in results
             if edge and edge > 500 and name != "DC_base24"]
for name, code in promising:
    edge = run_strategy(name, code, n_sims=500)
    print(f"{name:25s} -> edge={edge} (500 sims)", flush=True)

# Restore baseline
with open("my_strategy.sol", "w") as f:
    f.write(STRATEGIES["DC_base24"])
print("\nRestored DC_base24")
