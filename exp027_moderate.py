#!/usr/bin/env python3
"""Experiment 027: Moderate contrarian — cap the opposite spike at a moderate level.
Instead of huge spikes on the opposite side (losing that side's retail entirely),
keep the spike moderate (30-50 bps) to retain some retail from both directions."""

import subprocess

TEMPLATE_CAPPED = """// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;
import {{AMMStrategyBase}} from "./AMMStrategyBase.sol";
import {{IAMMStrategy, TradeInfo}} from "./IAMMStrategy.sol";
contract Strategy is AMMStrategyBase {{
    function afterInitialize(uint256, uint256) external override returns (uint256, uint256) {{
        uint256 fee = {same_base} * BPS; slots[0] = fee; slots[1] = fee; return (fee, fee);
    }}
    function afterSwap(TradeInfo calldata trade) external override returns (uint256, uint256) {{
        uint256 bidFee = slots[0]; uint256 askFee = slots[1];
        uint256 baseFee = {same_base} * BPS;
        uint256 oppBase = {opp_base} * BPS;
        uint256 tr = wdiv(trade.amountY, trade.reserveY);
        uint256 spike = tr * {lin_num} / {lin_den} + wmul(tr, tr) * {quad};
        uint256 freshOpp = oppBase + spike;
        // Cap the opposite side
        if (freshOpp > {max_opp} * BPS) freshOpp = {max_opp} * BPS;
        uint256 dBid = bidFee * {dn} / {dd}; uint256 dAsk = askFee * {dn} / {dd};
        if (dBid < baseFee) dBid = baseFee; if (dAsk < baseFee) dAsk = baseFee;
        if (trade.isBuy) {{
            askFee = freshOpp > dAsk ? freshOpp : dAsk;
            bidFee = dBid;
        }} else {{
            bidFee = freshOpp > dBid ? freshOpp : dBid;
            askFee = dAsk;
        }}
        bidFee = clampFee(bidFee); askFee = clampFee(askFee);
        slots[0] = bidFee; slots[1] = askFee; return (bidFee, askFee);
    }}
    function getName() external pure override returns (string memory) {{ return "MC"; }}
}}
"""

TEMPLATE_2LEVEL = """// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;
import {{AMMStrategyBase}} from "./AMMStrategyBase.sol";
import {{IAMMStrategy, TradeInfo}} from "./IAMMStrategy.sol";
contract Strategy is AMMStrategyBase {{
    function afterInitialize(uint256, uint256) external override returns (uint256, uint256) {{
        uint256 bidFee = {same_base} * BPS; uint256 askFee = {same_base} * BPS;
        slots[0] = bidFee; slots[1] = askFee; return (bidFee, askFee);
    }}
    function afterSwap(TradeInfo calldata trade) external override returns (uint256, uint256) {{
        uint256 bidFee = slots[0]; uint256 askFee = slots[1];
        uint256 sameBase = {same_base} * BPS;
        uint256 oppBase = {opp_base} * BPS;
        uint256 tr = wdiv(trade.amountY, trade.reserveY);
        uint256 spike = tr * {lin_num} / {lin_den} + wmul(tr, tr) * {quad};
        uint256 freshOpp = oppBase + spike;
        uint256 dBid = bidFee * {dn} / {dd}; uint256 dAsk = askFee * {dn} / {dd};
        // Floors: same side decays to sameBase, opposite decays to oppBase
        if (trade.isBuy) {{
            if (dAsk < oppBase) dAsk = oppBase;
            if (dBid < sameBase) dBid = sameBase;
            askFee = freshOpp > dAsk ? freshOpp : dAsk;
            bidFee = dBid;
        }} else {{
            if (dBid < oppBase) dBid = oppBase;
            if (dAsk < sameBase) dAsk = sameBase;
            bidFee = freshOpp > dBid ? freshOpp : dBid;
            askFee = dAsk;
        }}
        bidFee = clampFee(bidFee); askFee = clampFee(askFee);
        slots[0] = bidFee; slots[1] = askFee; return (bidFee, askFee);
    }}
    function getName() external pure override returns (string memory) {{ return "TL"; }}
}}
"""

def run_config(code, n_sims=500):
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

configs = [
    # Capped opposite spike: same_base, opp_base, lin_num, lin_den, quad, max_opp, dn, dd
    # Reference: uncapped DirContrarian = 24, 24, 5, 4, 15, huge, 8, 9 → 496.84
    ("Cap50", TEMPLATE_CAPPED, {"same_base": 24, "opp_base": 24, "lin_num": 5, "lin_den": 4, "quad": 15, "max_opp": 50, "dn": 8, "dd": 9}),
    ("Cap100", TEMPLATE_CAPPED, {"same_base": 24, "opp_base": 24, "lin_num": 5, "lin_den": 4, "quad": 15, "max_opp": 100, "dn": 8, "dd": 9}),
    ("Cap200", TEMPLATE_CAPPED, {"same_base": 24, "opp_base": 24, "lin_num": 5, "lin_den": 4, "quad": 15, "max_opp": 200, "dn": 8, "dd": 9}),
    ("Cap500", TEMPLATE_CAPPED, {"same_base": 24, "opp_base": 24, "lin_num": 5, "lin_den": 4, "quad": 15, "max_opp": 500, "dn": 8, "dd": 9}),

    # Two-level: different base for same vs opposite side
    # Opposite base higher = it decays to a higher floor, always providing arb protection
    ("TL20_30", TEMPLATE_2LEVEL, {"same_base": 20, "opp_base": 30, "lin_num": 5, "lin_den": 4, "quad": 15, "dn": 8, "dd": 9}),
    ("TL20_35", TEMPLATE_2LEVEL, {"same_base": 20, "opp_base": 35, "lin_num": 5, "lin_den": 4, "quad": 15, "dn": 8, "dd": 9}),
    ("TL22_30", TEMPLATE_2LEVEL, {"same_base": 22, "opp_base": 30, "lin_num": 5, "lin_den": 4, "quad": 15, "dn": 8, "dd": 9}),
    ("TL24_30", TEMPLATE_2LEVEL, {"same_base": 24, "opp_base": 30, "lin_num": 5, "lin_den": 4, "quad": 15, "dn": 8, "dd": 9}),
    ("TL24_35", TEMPLATE_2LEVEL, {"same_base": 24, "opp_base": 35, "lin_num": 5, "lin_den": 4, "quad": 15, "dn": 8, "dd": 9}),
    ("TL18_36", TEMPLATE_2LEVEL, {"same_base": 18, "opp_base": 36, "lin_num": 5, "lin_den": 4, "quad": 15, "dn": 8, "dd": 9}),
    ("TL20_40", TEMPLATE_2LEVEL, {"same_base": 20, "opp_base": 40, "lin_num": 5, "lin_den": 4, "quad": 15, "dn": 8, "dd": 9}),
    ("TL24_40", TEMPLATE_2LEVEL, {"same_base": 24, "opp_base": 40, "lin_num": 5, "lin_den": 4, "quad": 15, "dn": 8, "dd": 9}),

    # Two-level with different spike params (tuned for the two-level structure)
    ("TL20_30_l1q20", TEMPLATE_2LEVEL, {"same_base": 20, "opp_base": 30, "lin_num": 1, "lin_den": 1, "quad": 20, "dn": 8, "dd": 9}),
    ("TL22_30_l1q20", TEMPLATE_2LEVEL, {"same_base": 22, "opp_base": 30, "lin_num": 1, "lin_den": 1, "quad": 20, "dn": 8, "dd": 9}),
    ("TL20_35_d67", TEMPLATE_2LEVEL, {"same_base": 20, "opp_base": 35, "lin_num": 5, "lin_den": 4, "quad": 15, "dn": 6, "dd": 7}),
]

print("=== Experiment 027: Moderate/Two-Level Contrarian (500 sims) ===\n")
results = []
for label, template, params in configs:
    code = template.format(**params)
    edge = run_config(code, n_sims=500)
    print(f"{label:25s} → {edge}", flush=True)
    results.append((edge or 0, label))

print("\n=== SORTED ===")
for edge, label in sorted(results, reverse=True):
    print(f"{label:25s} → {edge:.2f}")

# Restore
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
