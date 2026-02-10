// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {AMMStrategyBase} from "./AMMStrategyBase.sol";
import {IAMMStrategy, TradeInfo} from "./IAMMStrategy.sol";

/// @title Spike-Only Strategy — 80 bps base, spike up on large trades
/// @notice Stays at 80 bps normally, spikes to 100-120 bps after large trades,
///         then decays back. Never goes below 80 bps.
contract Strategy is AMMStrategyBase {
    // slots[0] = current fee (WAD)

    function afterInitialize(uint256, uint256)
        external override returns (uint256, uint256)
    {
        uint256 fee = 80 * BPS;
        slots[0] = fee;
        return (fee, fee);
    }

    function afterSwap(TradeInfo calldata trade)
        external override returns (uint256, uint256)
    {
        uint256 fee = slots[0];
        uint256 baseFee = 80 * BPS;

        // Spike for large trades
        uint256 tradeRatio = wdiv(trade.amountY, trade.reserveY);
        uint256 targetFee = baseFee;
        if (tradeRatio > WAD / 50) {          // > 2% of reserves
            targetFee = baseFee + 40 * BPS;   // spike to 120 bps
        } else if (tradeRatio > WAD / 100) {  // > 1% of reserves
            targetFee = baseFee + 20 * BPS;   // spike to 100 bps
        }

        // Fast rise, moderate decay back to base
        if (targetFee > fee) {
            fee = fee + (targetFee - fee) * 2 / 3;
        } else {
            // Decay 1/6 of gap per trade
            fee = fee - (fee - targetFee) / 6;
        }

        fee = clampFee(fee);
        if (fee < baseFee) fee = baseFee;

        slots[0] = fee;
        return (fee, fee);
    }

    function getName() external pure override returns (string memory) {
        return "SpikeOnly80";
    }
}
