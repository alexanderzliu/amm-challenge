// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {AMMStrategyBase} from "./AMMStrategyBase.sol";
import {IAMMStrategy, TradeInfo} from "./IAMMStrategy.sol";

/// @title Proportional Volatility Fee Strategy
/// @notice Fee scales linearly with realized volatility (fee ≈ 3 * σ).
///         Market-making theory: optimal spread ∝ volatility.
///         In calm markets, drops to 15 bps (aggressive undercut of vanilla 30 bps).
///         In volatile markets, rises to 60-90 bps (strong arb protection).
///         Spikes temporarily after large trades for immediate reaction.
contract Strategy is AMMStrategyBase {
    // Storage layout:
    // slots[0] = current fee (WAD)
    // slots[1] = EMA of |price change| — realized volatility proxy (WAD)
    // slots[2] = previous implied price reserveY/reserveX (WAD)

    function afterInitialize(uint256 initialX, uint256 initialY)
        external override returns (uint256, uint256)
    {
        uint256 fee = 25 * BPS;
        slots[0] = fee;
        slots[1] = 1e15;  // seed vol estimate ~0.1% (→ 30 bps initial fee)
        slots[2] = wdiv(initialY, initialX);
        return (fee, fee);
    }

    function afterSwap(TradeInfo calldata trade)
        external override returns (uint256, uint256)
    {
        // --- 1. Price-change volatility signal ---
        uint256 curPrice = wdiv(trade.reserveY, trade.reserveX);
        uint256 prevPrice = slots[2];
        slots[2] = curPrice;

        uint256 pctChange = 0;
        if (prevPrice > 0) {
            pctChange = wdiv(absDiff(curPrice, prevPrice), prevPrice);
        }

        // EMA of |price change| (alpha = 0.1, half-life ≈ 7 trades)
        uint256 emaVol = slots[1];
        emaVol = (emaVol * 9 + pctChange) / 10;
        slots[1] = emaVol;

        // --- 2. Proportional fee: fee = 3 × realized vol ---
        // emaVol ~5e14 (calm)  → 15 bps (floor)
        // emaVol ~1e15 (normal) → 30 bps
        // emaVol ~2e15 (volatile) → 60 bps
        // emaVol ~3e15 (very volatile) → 90 bps
        uint256 targetFee = emaVol * 3;

        // --- 3. Spike for large individual trades (immediate arb reaction) ---
        uint256 tradeRatio = wdiv(trade.amountY, trade.reserveY);
        if (tradeRatio > WAD / 50) {          // > 2% of reserves
            targetFee = targetFee + 20 * BPS;
        } else if (tradeRatio > WAD / 100) {  // > 1% of reserves
            targetFee = targetFee + 10 * BPS;
        }

        // Floor at 15 bps
        if (targetFee < 15 * BPS) targetFee = 15 * BPS;

        // --- 4. Smooth transitions ---
        uint256 fee = slots[0];
        if (targetFee > fee) {
            // Fast rise: close 2/3 of gap per trade
            fee = fee + (targetFee - fee) * 2 / 3;
        } else {
            // Moderate decay: close 1/4 of gap per trade
            fee = fee - (fee - targetFee) / 4;
        }

        fee = clampFee(fee);
        if (fee < 15 * BPS) fee = 15 * BPS;

        slots[0] = fee;
        return (fee, fee);
    }

    function getName() external pure override returns (string memory) {
        return "PropVol";
    }
}
