#!/usr/bin/env python3
"""Experiment 037: Two-State Fee System + Novel Mechanisms.

Approach 1: Two-state system (calm/volatile)
- Calm: fee = 24 bps both sides (maximize retail capture)
- Volatile: contrarian spike (arb protection)
- Transition: calm→volatile on large trade, volatile→calm after N small trades

Approach 2: Inverse contrarian — instead of spiking opposite, what if we
DISCOUNT same side? Set same_fee = baseFee - discount after trade.
This way retail pays LESS than vanilla (24-X < 30) on same side.

Approach 3: Asymmetric base — different base for bid vs ask.
If we know one direction gets more arb, we can pre-position.

Approach 4: RADICAL — What if fee depends on reserves instead of trade size?
After arb, reserves shift. We can detect this shift and respond.
fee = base + scale * |reserveY/reserveX - 100| / 100

Approach 5: Use timestamp (step number) to decay. Between steps,
fee decays. Within step, fee doesn't decay (persistence for retail).
We can use slots to store the last-trade timestamp and only decay
when timestamp changes.
"""

import subprocess

STRATEGIES = {}

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

# Approach 5: TIMESTAMP-AWARE DECAY
# Key insight: decay should happen per STEP, not per TRADE.
# Within a step, arb trades first, then retail.
# After arb → spike (per trade). After retail in SAME step → no decay.
# Only decay when timestamp advances.
#
# This means:
# - Step N: arb fires → spike. Retail fires → sees spiked fee (no decay between them)
# - Step N+1: timestamp changed → decay ONCE. If no arb, retail sees decayed fee.
#
# Currently we decay per-trade, so after arb (trade 1) and then retail (trade 2 in same step),
# the retail sees: max(fresh_from_retail, decayed_spike_from_arb)
# With timestamp decay: retail sees spike from arb WITHOUT decay (same step)
#
# Wait — this means the OPPOSITE side stays spiked for retail. That's WORSE.
# Actually in DirContrarian: arb is buy → spike ask. Retail buy → sees spiked ask.
# Without decay, ask stays at arb spike level. Retail sell → sees bid which was decayed.
# With timestamp decay: bid doesn't decay within step either. But bid was already decayed
# by the arb trade (arb was buy → bidFee = dBid).
# Hmm, let me think more carefully...
#
# Step sequence:
# 1. arb buy → afterSwap: askFee = spike (high), bidFee = decay(old_bid)
# 2. retail buy → afterSwap: askFee = max(small_spike, decayed_high_ask), bidFee = decay(low_bid)
#    With timestamp decay: askFee = max(small_spike, high_ask [no decay]), bidFee = low_bid [no decay]
# 3. retail sell → afterSwap: bidFee = max(small_spike, decayed_low_bid), askFee = decay(high_ask)
#    With timestamp decay: bidFee = max(small_spike, low_bid), askFee = high_ask [still no decay]
#
# So timestamp decay means:
# - Opposite side stays spiked through the step (worse for opposite-side retail)
# - Same side stays low through the step (good for same-side retail)
# Net effect unclear. But the key difference is: decay only happens on step boundaries.

STRATEGIES["DC_timestampDecay"] = """// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;
import {AMMStrategyBase} from "./AMMStrategyBase.sol";
import {IAMMStrategy, TradeInfo} from "./IAMMStrategy.sol";
contract Strategy is AMMStrategyBase {
    // slots: 0=bid, 1=ask, 2=lastTimestamp
    function afterInitialize(uint256, uint256) external override returns (uint256, uint256) {
        uint256 fee = 24 * BPS; slots[0] = fee; slots[1] = fee; slots[2] = 0; return (fee, fee);
    }
    function afterSwap(TradeInfo calldata trade) external override returns (uint256, uint256) {
        uint256 bidFee = slots[0]; uint256 askFee = slots[1]; uint256 baseFee = 24 * BPS;
        uint256 lastTs = slots[2];
        uint256 tr = wdiv(trade.amountY, trade.reserveY);
        uint256 spike = tr * 5 / 4 + wmul(tr, tr) * 15;
        uint256 fresh = baseFee + spike;

        // Only decay when timestamp changes (new step)
        uint256 dBid = bidFee; uint256 dAsk = askFee;
        if (trade.timestamp > lastTs) {
            dBid = bidFee * 8 / 9; dAsk = askFee * 8 / 9;
            if (dBid < baseFee) dBid = baseFee; if (dAsk < baseFee) dAsk = baseFee;
        }

        if (trade.isBuy) { askFee = fresh > dAsk ? fresh : dAsk; bidFee = dBid; }
        else { bidFee = fresh > dBid ? fresh : dBid; askFee = dAsk; }
        bidFee = clampFee(bidFee); askFee = clampFee(askFee);
        slots[0] = bidFee; slots[1] = askFee; slots[2] = trade.timestamp;
        return (bidFee, askFee);
    }
    function getName() external pure override returns (string memory) { return "DCTD"; }
}
"""

# Variant: Decay per step, but ONLY same-side decays on first trade of step
# After arb (first trade of step): opposite spikes, same decays
# After retail (later in step): NO change to opposite, same gets tiny fresh spike
# Basically: within-step trades don't re-spike the opposite side
STRATEGIES["DC_noRespike"] = """// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;
import {AMMStrategyBase} from "./AMMStrategyBase.sol";
import {IAMMStrategy, TradeInfo} from "./IAMMStrategy.sol";
contract Strategy is AMMStrategyBase {
    // slots: 0=bid, 1=ask, 2=lastTimestamp, 3=tradeCountInStep
    function afterInitialize(uint256, uint256) external override returns (uint256, uint256) {
        uint256 fee = 24 * BPS; slots[0] = fee; slots[1] = fee; return (fee, fee);
    }
    function afterSwap(TradeInfo calldata trade) external override returns (uint256, uint256) {
        uint256 bidFee = slots[0]; uint256 askFee = slots[1]; uint256 baseFee = 24 * BPS;
        uint256 lastTs = slots[2]; uint256 tradeCount = slots[3];
        uint256 tr = wdiv(trade.amountY, trade.reserveY);
        uint256 spike = tr * 5 / 4 + wmul(tr, tr) * 15;
        uint256 fresh = baseFee + spike;

        if (trade.timestamp > lastTs) {
            // New step: decay and apply contrarian as normal
            tradeCount = 1;
            uint256 dBid = bidFee * 8 / 9; uint256 dAsk = askFee * 8 / 9;
            if (dBid < baseFee) dBid = baseFee; if (dAsk < baseFee) dAsk = baseFee;
            if (trade.isBuy) { askFee = fresh > dAsk ? fresh : dAsk; bidFee = dBid; }
            else { bidFee = fresh > dBid ? fresh : dBid; askFee = dAsk; }
        } else {
            // Same step: later trade. Don't re-spike opposite.
            // Just apply fresh to opposite (may lower if retail is smaller than arb)
            // and decay same normally
            tradeCount = tradeCount + 1;
            if (trade.isBuy) {
                // Don't override high ask from earlier arb
                // Only update if fresh > current ask (unlikely after arb)
                if (fresh > askFee) askFee = fresh;
                // Same side: just decay
                bidFee = bidFee * 8 / 9;
                if (bidFee < baseFee) bidFee = baseFee;
            } else {
                if (fresh > bidFee) bidFee = fresh;
                askFee = askFee * 8 / 9;
                if (askFee < baseFee) askFee = baseFee;
            }
        }
        bidFee = clampFee(bidFee); askFee = clampFee(askFee);
        slots[0] = bidFee; slots[1] = askFee; slots[2] = trade.timestamp; slots[3] = tradeCount;
        return (bidFee, askFee);
    }
    function getName() external pure override returns (string memory) { return "DCNR"; }
}
"""

# Approach 4: Reserve-deviation-based fee
# After arb, reserves shift from 100:10000. The deviation encodes the price move.
# fee = base + scale * deviation
# deviation = |reserveY/reserveX - initialPrice| / initialPrice
STRATEGIES["DC_reserveDev"] = """// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;
import {AMMStrategyBase} from "./AMMStrategyBase.sol";
import {IAMMStrategy, TradeInfo} from "./IAMMStrategy.sol";
contract Strategy is AMMStrategyBase {
    function afterInitialize(uint256 ix, uint256 iy) external override returns (uint256, uint256) {
        uint256 fee = 24 * BPS; slots[0] = fee; slots[1] = fee;
        slots[2] = wdiv(iy, ix); // initial price
        return (fee, fee);
    }
    function afterSwap(TradeInfo calldata trade) external override returns (uint256, uint256) {
        uint256 bidFee = slots[0]; uint256 askFee = slots[1]; uint256 baseFee = 24 * BPS;
        uint256 initPrice = slots[2];
        uint256 tr = wdiv(trade.amountY, trade.reserveY);

        // Reserve-based deviation signal
        uint256 spot = wdiv(trade.reserveY, trade.reserveX);
        uint256 dev = absDiff(spot, initPrice);
        uint256 devRatio = wdiv(dev, initPrice); // fractional deviation

        // Spike = trade-size spike + deviation bonus
        uint256 spike = tr * 5 / 4 + wmul(tr, tr) * 15;
        // Add deviation-proportional component (captures cumulative price move)
        spike = spike + devRatio * 1 / 2;

        uint256 fresh = baseFee + spike;
        uint256 dBid = bidFee * 8 / 9; uint256 dAsk = askFee * 8 / 9;
        if (dBid < baseFee) dBid = baseFee; if (dAsk < baseFee) dAsk = baseFee;
        if (trade.isBuy) { askFee = fresh > dAsk ? fresh : dAsk; bidFee = dBid; }
        else { bidFee = fresh > dBid ? fresh : dBid; askFee = dAsk; }
        bidFee = clampFee(bidFee); askFee = clampFee(askFee);
        slots[0] = bidFee; slots[1] = askFee; return (bidFee, askFee);
    }
    function getName() external pure override returns (string memory) { return "DCRD"; }
}
"""

# CRITICAL NEW IDEA: What about using DIFFERENT spike formulas for bid and ask?
# Currently: if buy → spike ask with full formula, decay bid
# What if: spike ask = strong (arb protection), but ALSO set bid = baseFee + tiny_premium
# The tiny premium on bid captures more per retail sell while keeping below vanilla's 30
STRATEGIES["DC_bidPremium"] = """// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;
import {AMMStrategyBase} from "./AMMStrategyBase.sol";
import {IAMMStrategy, TradeInfo} from "./IAMMStrategy.sol";
contract Strategy is AMMStrategyBase {
    function afterInitialize(uint256, uint256) external override returns (uint256, uint256) {
        uint256 fee = 24 * BPS; slots[0] = fee; slots[1] = fee; return (fee, fee);
    }
    function afterSwap(TradeInfo calldata trade) external override returns (uint256, uint256) {
        uint256 bidFee = slots[0]; uint256 askFee = slots[1]; uint256 baseFee = 24 * BPS;
        uint256 premium = 3 * BPS; // 3 bps premium on same side (27 total)
        uint256 tr = wdiv(trade.amountY, trade.reserveY);
        uint256 spike = tr * 5 / 4 + wmul(tr, tr) * 15;
        uint256 fresh = baseFee + spike;
        uint256 sameFresh = baseFee + premium; // Same side = base + 3 bps = 27 bps
        uint256 dBid = bidFee * 8 / 9; uint256 dAsk = askFee * 8 / 9;
        if (dBid < baseFee) dBid = baseFee; if (dAsk < baseFee) dAsk = baseFee;
        if (trade.isBuy) {
            askFee = fresh > dAsk ? fresh : dAsk;
            bidFee = sameFresh > dBid ? sameFresh : dBid;
        } else {
            bidFee = fresh > dBid ? fresh : dBid;
            askFee = sameFresh > dAsk ? sameFresh : dAsk;
        }
        bidFee = clampFee(bidFee); askFee = clampFee(askFee);
        slots[0] = bidFee; slots[1] = askFee; return (bidFee, askFee);
    }
    function getName() external pure override returns (string memory) { return "DCBP"; }
}
"""

# What if the same-side fee tracks the spike level as a floor?
# After arb buy: askFee spikes to X. Set bidFee = max(baseFee, X/10)
# This way bid stays proportional to the arb intensity
for divisor in [10, 20, 5]:
    label = f"DC_propSame{divisor}"
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
        uint256 spike = tr * 5 / 4 + wmul(tr, tr) * 15;
        uint256 fresh = baseFee + spike;
        uint256 sameProp = baseFee + spike / {divisor};
        uint256 dBid = bidFee * 8 / 9; uint256 dAsk = askFee * 8 / 9;
        if (dBid < baseFee) dBid = baseFee; if (dAsk < baseFee) dAsk = baseFee;
        if (trade.isBuy) {{
            askFee = fresh > dAsk ? fresh : dAsk;
            bidFee = sameProp > dBid ? sameProp : dBid;
        }} else {{
            bidFee = fresh > dBid ? fresh : dBid;
            askFee = sameProp > dAsk ? sameProp : dAsk;
        }}
        bidFee = clampFee(bidFee); askFee = clampFee(askFee);
        slots[0] = bidFee; slots[1] = askFee; return (bidFee, askFee);
    }}
    function getName() external pure override returns (string memory) {{ return "DCPS"; }}
}}
"""

# RADICAL: What if we use a completely different fee function?
# Instead of base + lin*tr + quad*tr², use: base * (1 + tr * scale)²
# This gives a multiplicative spike that might behave differently
STRATEGIES["DC_multSpike"] = """// SPDX-License-Identifier: MIT
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
        // Multiplicative: fee = base * (1 + 50*tr)
        // For tr=0.002 (retail ~20Y/10000Y): fee = 24 * (1 + 0.1) = 26.4 bps
        // For tr=0.01 (arb ~100Y/10000Y): fee = 24 * (1 + 0.5) = 36 bps
        // For tr=0.05 (big arb ~500Y/10000Y): fee = 24 * (1 + 2.5) = 84 bps
        uint256 multiplier = WAD + tr * 50;
        uint256 fresh = wmul(baseFee, multiplier);
        uint256 dBid = bidFee * 8 / 9; uint256 dAsk = askFee * 8 / 9;
        if (dBid < baseFee) dBid = baseFee; if (dAsk < baseFee) dAsk = baseFee;
        if (trade.isBuy) { askFee = fresh > dAsk ? fresh : dAsk; bidFee = dBid; }
        else { bidFee = fresh > dBid ? fresh : dBid; askFee = dAsk; }
        bidFee = clampFee(bidFee); askFee = clampFee(askFee);
        slots[0] = bidFee; slots[1] = askFee; return (bidFee, askFee);
    }
    function getName() external pure override returns (string memory) { return "DCM"; }
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


print("=== Experiment 037: Two-State & Novel Mechanisms (100 sims) ===\n")
results = []
order = [
    "DC_base",
    "DC_timestampDecay",
    "DC_noRespike",
    "DC_reserveDev",
    "DC_bidPremium",
    "DC_propSame10", "DC_propSame20", "DC_propSame5",
    "DC_multSpike",
]

for name in order:
    edge = run_strategy(name, STRATEGIES[name], n_sims=100)
    print(f"{name:25s} -> edge={edge}", flush=True)
    results.append((name, edge))

print("\n=== 500-sim validation ===")
promising = [(name, STRATEGIES[name]) for name, edge in results
             if edge and edge > 510 and name != "DC_base"]
for name, code in promising:
    edge = run_strategy(name, code, n_sims=500)
    print(f"{name:25s} -> edge={edge} (500 sims)", flush=True)

# Restore
with open("my_strategy.sol", "w") as f:
    f.write(STRATEGIES["DC_base"])
print("\nRestored DC baseline")
