// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {AMMStrategyBase} from "./AMMStrategyBase.sol";
import {IAMMStrategy, TradeInfo} from "./IAMMStrategy.sol";

/// @title Continuous Spike Strategy
/// @notice 75 bps base with continuous spike proportional to trade size.
///         spike = tradeRatio * 1.25 (so 1% trade → 125 bps spike, 2% → 250 bps).
///         Fast decay (1/3 of gap per trade) keeps fees responsive.
contract Strategy is AMMStrategyBase {
    // slots[0] = current fee (WAD)

    function afterInitialize(uint256, uint256)
        external override returns (uint256, uint256)
    {
        uint256 fee = 75 * BPS;
        slots[0] = fee;
        return (fee, fee);
    }

    function afterSwap(TradeInfo calldata trade)
        external override returns (uint256, uint256)
    {
        uint256 fee = slots[0];
        uint256 baseFee = 75 * BPS;

        // Continuous spike proportional to trade size
        // tradeRatio in WAD: 1% = 1e16, we want 1% → ~125 bps = 125e14
        // spike = tradeRatio * 5/4
        uint256 tradeRatio = wdiv(trade.amountY, trade.reserveY);
        uint256 spike = tradeRatio * 5 / 4;

        uint256 targetFee = baseFee + spike;

        if (targetFee > fee) {
            fee = fee + (targetFee - fee) * 2 / 3;
        } else {
            fee = fee - (fee - targetFee) / 3;
        }

        fee = clampFee(fee);
        if (fee < baseFee) fee = baseFee;

        slots[0] = fee;
        return (fee, fee);
    }

    function getName() external pure override returns (string memory) {
        return "ContSpike75";
    }
}
