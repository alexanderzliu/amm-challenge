#!/usr/bin/env python3
"""Experiment 035: Size-Discriminating Spike.

Key insight from execution order analysis:
- Arb trades first, afterSwap spikes fee
- Retail arrives next, sees spiked fee = loses retail on opposite side
- ~28% of steps have 2+ retail orders, each triggers afterSwap sequentially
- After retail trade #1 (small), afterSwap fires and affects retail trade #2

Current problem:
- After arb buy: ask spikes high → ALL retail buys lost to vanilla
- After retail buy (small): ask gets tiny spike → still hurts retail #2

Winner captures 77.3K retail at 36 bps avg vs our 69.7K at ~40 bps.
They must charge more per-trade while losing fewer trades.

Hypothesis: If we DON'T spike after small (retail) trades, we keep fees low
for subsequent retail orders in the same step. The arb spike from the first
trade of the step still provides protection. Net effect: same arb protection,
but more retail captured on multi-order steps.

Variants:
A) Size threshold: only spike if tradeRatio > threshold (arb detection)
B) Two-tier spike: full spike for arb-sized, micro spike for retail-sized
C) Smart decay: after small trade, decay faster (or reset to base)
D) Higher base + weaker spike: base=30, smaller spike → avg fee closer to 36
E) Reverse approach: base=30 + size-conditional contrarian (only spike on arb)
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

# A: Only spike if tradeRatio > threshold (arb threshold ~ 0.1% of reserves)
# Retail trades are typically 20Y out of 10000Y = 0.2%, arb can be much bigger
# But we need to be careful: arb size depends on price move and fee level
# With 24 bps fee, typical arb for 0.1% price move: ~0.05% of reserves
# Let's test multiple thresholds
for thresh_num, thresh_den, label in [
    (1, 1000, "DC_thresh01"),   # 0.1% threshold
    (2, 1000, "DC_thresh02"),   # 0.2% threshold
    (5, 1000, "DC_thresh05"),   # 0.5% threshold
    (1, 100, "DC_thresh1"),     # 1% threshold
]:
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
        uint256 dBid = bidFee * 8 / 9; uint256 dAsk = askFee * 8 / 9;
        if (dBid < baseFee) dBid = baseFee; if (dAsk < baseFee) dAsk = baseFee;
        // Only spike if trade is large enough (arb detection)
        if (tr > {thresh_num} * WAD / {thresh_den}) {{
            uint256 spike = tr * 5 / 4 + wmul(tr, tr) * 15;
            uint256 fresh = baseFee + spike;
            if (trade.isBuy) {{ askFee = fresh > dAsk ? fresh : dAsk; bidFee = dBid; }}
            else {{ bidFee = fresh > dBid ? fresh : dBid; askFee = dAsk; }}
        }} else {{
            // Small trade: just decay both sides, no spike
            bidFee = dBid; askFee = dAsk;
        }}
        bidFee = clampFee(bidFee); askFee = clampFee(askFee);
        slots[0] = bidFee; slots[1] = askFee; return (bidFee, askFee);
    }}
    function getName() external pure override returns (string memory) {{ return "DCT"; }}
}}
"""

# B: Two-tier spike: full contrarian for arb-sized, small symmetric for retail
# On retail: both sides get a tiny bump (proportional to retail size)
# This raises avg fee slightly while keeping retail
for thresh_num, thresh_den, small_mult, label in [
    (2, 1000, 0, "DC_2tier_none"),     # No spike at all below threshold
    (2, 1000, 2, "DC_2tier_sym2"),     # Below thresh: symmetric spike * 1/2
    (5, 1000, 2, "DC_2tier5_sym2"),    # Higher threshold
]:
    small_code = ""
    if small_mult == 0:
        small_code = "bidFee = dBid; askFee = dAsk;"
    else:
        small_code = f"""uint256 spike = tr * 5 / 4 + wmul(tr, tr) * 15;
            uint256 symFee = baseFee + spike / {small_mult};
            bidFee = symFee > dBid ? symFee : dBid;
            askFee = symFee > dAsk ? symFee : dAsk;"""

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
        uint256 dBid = bidFee * 8 / 9; uint256 dAsk = askFee * 8 / 9;
        if (dBid < baseFee) dBid = baseFee; if (dAsk < baseFee) dAsk = baseFee;
        if (tr > {thresh_num} * WAD / {thresh_den}) {{
            uint256 spike = tr * 5 / 4 + wmul(tr, tr) * 15;
            uint256 fresh = baseFee + spike;
            if (trade.isBuy) {{ askFee = fresh > dAsk ? fresh : dAsk; bidFee = dBid; }}
            else {{ bidFee = fresh > dBid ? fresh : dBid; askFee = dAsk; }}
        }} else {{
            {small_code}
        }}
        bidFee = clampFee(bidFee); askFee = clampFee(askFee);
        slots[0] = bidFee; slots[1] = askFee; return (bidFee, askFee);
    }}
    function getName() external pure override returns (string memory) {{ return "D2T"; }}
}}
"""

# C: Higher base + size-conditional contrarian
# The idea: base=30 to match vanilla. Only contrarian spike on arb-sized trades.
# On retail trades, fee stays at 30 both sides → 50/50 retail split
# On arb: contrarian spike provides protection
# Net: 50% retail at 30 bps = more retail income, with arb protection from spikes
for base, thresh_n, thresh_d, label in [
    (30, 2, 1000, "DC30_arb"),
    (28, 2, 1000, "DC28_arb"),
    (30, 5, 1000, "DC30_arb5"),
]:
    STRATEGIES[label] = f"""// SPDX-License-Identifier: MIT
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
        uint256 dBid = bidFee * 8 / 9; uint256 dAsk = askFee * 8 / 9;
        if (dBid < baseFee) dBid = baseFee; if (dAsk < baseFee) dAsk = baseFee;
        if (tr > {thresh_n} * WAD / {thresh_d}) {{
            // Arb-sized trade: full contrarian spike
            uint256 spike = tr * 5 / 4 + wmul(tr, tr) * 15;
            uint256 fresh = baseFee + spike;
            if (trade.isBuy) {{ askFee = fresh > dAsk ? fresh : dAsk; bidFee = dBid; }}
            else {{ bidFee = fresh > dBid ? fresh : dBid; askFee = dAsk; }}
        }} else {{
            // Retail: just decay, no spike, stay near base
            bidFee = dBid; askFee = dAsk;
        }}
        bidFee = clampFee(bidFee); askFee = clampFee(askFee);
        slots[0] = bidFee; slots[1] = askFee; return (bidFee, askFee);
    }}
    function getName() external pure override returns (string memory) {{ return "DCA"; }}
}}
"""

# D: DC with faster post-retail decay
# After small trade: decay at 2/3 instead of 8/9 (faster return to base)
# After big trade: still use 8/9 slow decay
# This means the arb spike persists for the arb, but drops quickly after retail
for fast_n, fast_d, thresh_n, thresh_d, label in [
    (2, 3, 2, 1000, "DC_fastRetail23"),
    (3, 4, 2, 1000, "DC_fastRetail34"),
    (1, 2, 2, 1000, "DC_fastRetail12"),
]:
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
        // Size-dependent decay: faster after small trades
        uint256 dN; uint256 dD;
        if (tr > {thresh_n} * WAD / {thresh_d}) {{
            dN = 8; dD = 9; // Normal slow decay after arb
        }} else {{
            dN = {fast_n}; dD = {fast_d}; // Fast decay after retail
        }}
        uint256 dBid = bidFee * dN / dD; uint256 dAsk = askFee * dN / dD;
        if (dBid < baseFee) dBid = baseFee; if (dAsk < baseFee) dAsk = baseFee;
        if (trade.isBuy) {{ askFee = fresh > dAsk ? fresh : dAsk; bidFee = dBid; }}
        else {{ bidFee = fresh > dBid ? fresh : dBid; askFee = dAsk; }}
        bidFee = clampFee(bidFee); askFee = clampFee(askFee);
        slots[0] = bidFee; slots[1] = askFee; return (bidFee, askFee);
    }}
    function getName() external pure override returns (string memory) {{ return "DCFR"; }}
}}
"""

# E: Same-side fee = base + small fraction of spike (charge retail more)
# Currently: same side pure decay. What if same = baseFee + spike/8?
# This raises same-side fee from 24 to ~27 bps (closer to 30)
# We lose some routing advantage but gain more per-trade income
for frac_n, frac_d, label in [
    (1, 8, "DC_sameSmall8"),   # ~27 bps on same side
    (1, 4, "DC_sameSmall4"),   # ~30 bps on same side
]:
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
        uint256 oppFresh = baseFee + spike;
        uint256 sameFresh = baseFee + spike * {frac_n} / {frac_d};
        uint256 dBid = bidFee * 8 / 9; uint256 dAsk = askFee * 8 / 9;
        if (dBid < baseFee) dBid = baseFee; if (dAsk < baseFee) dAsk = baseFee;
        if (trade.isBuy) {{
            askFee = oppFresh > dAsk ? oppFresh : dAsk;
            bidFee = sameFresh > dBid ? sameFresh : dBid;
        }} else {{
            bidFee = oppFresh > dBid ? oppFresh : dBid;
            askFee = sameFresh > dAsk ? sameFresh : dAsk;
        }}
        bidFee = clampFee(bidFee); askFee = clampFee(askFee);
        slots[0] = bidFee; slots[1] = askFee; return (bidFee, askFee);
    }}
    function getName() external pure override returns (string memory) {{ return "DCSS"; }}
}}
"""

# F: RADICAL: What if the winner uses amountX instead of amountY?
# Our formula: tr = amountY / reserveY. But amountX / reserveX might behave differently
# because reserveX = 100 (much smaller than reserveY = 10000)
# This means trX = amountX/100 ≈ 100x larger than trY = amountY/10000
# The spike coefficients would need to be MUCH smaller
# Let's try: spike = trX * small_lin + trX^2 * small_quad
STRATEGIES["DC_tradeX"] = """// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;
import {AMMStrategyBase} from "./AMMStrategyBase.sol";
import {IAMMStrategy, TradeInfo} from "./IAMMStrategy.sol";
contract Strategy is AMMStrategyBase {
    function afterInitialize(uint256, uint256) external override returns (uint256, uint256) {
        uint256 fee = 24 * BPS; slots[0] = fee; slots[1] = fee; return (fee, fee);
    }
    function afterSwap(TradeInfo calldata trade) external override returns (uint256, uint256) {
        uint256 bidFee = slots[0]; uint256 askFee = slots[1]; uint256 baseFee = 24 * BPS;
        // Use amountX / reserveX instead of amountY / reserveY
        uint256 tr = wdiv(trade.amountX, trade.reserveX);
        uint256 spike = tr * 5 / 4 + wmul(tr, tr) * 15;
        uint256 fresh = baseFee + spike;
        uint256 dBid = bidFee * 8 / 9; uint256 dAsk = askFee * 8 / 9;
        if (dBid < baseFee) dBid = baseFee; if (dAsk < baseFee) dAsk = baseFee;
        if (trade.isBuy) { askFee = fresh > dAsk ? fresh : dAsk; bidFee = dBid; }
        else { bidFee = fresh > dBid ? fresh : dBid; askFee = dAsk; }
        bidFee = clampFee(bidFee); askFee = clampFee(askFee);
        slots[0] = bidFee; slots[1] = askFee; return (bidFee, askFee);
    }
    function getName() external pure override returns (string memory) { return "DCX"; }
}
"""

# G: OPPOSITE LOGIC — what about NOT spiking after arb, and instead
# keeping fee permanently higher? Base=36, NO spike at all (constant 36)
# was tested and got 362 edge. But what about base=36 + moderate contrarian?
# Already tested base>24 with spikes, always worse...
# BUT we haven't tested base=30 with SIZE-CONDITIONAL spike where the
# size threshold is perfectly calibrated.

# H: Multi-slot tracking — track the LAST N trade sizes to identify regime
# If last 3+ trades were all large → we're in an arb cluster → keep spike
# If last 3+ trades were small → we're in retail flow → drop to base
STRATEGIES["DC_regime3"] = """// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;
import {AMMStrategyBase} from "./AMMStrategyBase.sol";
import {IAMMStrategy, TradeInfo} from "./IAMMStrategy.sol";
contract Strategy is AMMStrategyBase {
    // slots: 0=bid, 1=ask, 2=largeTrades (count of recent large trades)
    function afterInitialize(uint256, uint256) external override returns (uint256, uint256) {
        uint256 fee = 24 * BPS; slots[0] = fee; slots[1] = fee; return (fee, fee);
    }
    function afterSwap(TradeInfo calldata trade) external override returns (uint256, uint256) {
        uint256 bidFee = slots[0]; uint256 askFee = slots[1]; uint256 baseFee = 24 * BPS;
        uint256 largeCount = slots[2];
        uint256 tr = wdiv(trade.amountY, trade.reserveY);

        // Track arb regime: increment on large trades, decrement on small
        if (tr > 2 * WAD / 1000) {
            largeCount = largeCount + 3; // Big jump up on arb
            if (largeCount > 10) largeCount = 10;
        } else {
            largeCount = largeCount > 1 ? largeCount - 1 : 0; // Slow decay
        }

        uint256 spike = tr * 5 / 4 + wmul(tr, tr) * 15;
        uint256 fresh = baseFee + spike;

        // If we're in arb regime, use full contrarian spike
        // If in retail regime, use weaker spike (less aggressive)
        uint256 dBid; uint256 dAsk;
        if (largeCount > 3) {
            // Arb regime: slow decay
            dBid = bidFee * 8 / 9; dAsk = askFee * 8 / 9;
        } else {
            // Retail regime: fast decay
            dBid = bidFee * 3 / 4; dAsk = askFee * 3 / 4;
        }
        if (dBid < baseFee) dBid = baseFee; if (dAsk < baseFee) dAsk = baseFee;
        if (trade.isBuy) { askFee = fresh > dAsk ? fresh : dAsk; bidFee = dBid; }
        else { bidFee = fresh > dBid ? fresh : dBid; askFee = dAsk; }
        bidFee = clampFee(bidFee); askFee = clampFee(askFee);
        slots[0] = bidFee; slots[1] = askFee; slots[2] = largeCount;
        return (bidFee, askFee);
    }
    function getName() external pure override returns (string memory) { return "DCR3"; }
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


print("=== Experiment 035: Size-Discriminating Spike (100 sims) ===\n")
results = []

# Run all variants
order = [
    "DC_base",
    # Threshold variants
    "DC_thresh01", "DC_thresh02", "DC_thresh05", "DC_thresh1",
    # Two-tier variants
    "DC_2tier_none", "DC_2tier_sym2", "DC_2tier5_sym2",
    # Higher base + arb-only
    "DC30_arb", "DC28_arb", "DC30_arb5",
    # Fast post-retail decay
    "DC_fastRetail23", "DC_fastRetail34", "DC_fastRetail12",
    # Same-side small spike
    "DC_sameSmall8", "DC_sameSmall4",
    # X-based trade ratio
    "DC_tradeX",
    # Regime detection
    "DC_regime3",
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

# Restore baseline
with open("my_strategy.sol", "w") as f:
    f.write(STRATEGIES["DC_base"])
print("\nRestored DC baseline")
