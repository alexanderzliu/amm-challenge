// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {AMMStrategyBase} from "./AMMStrategyBase.sol";
import {IAMMStrategy, TradeInfo} from "./IAMMStrategy.sol";

/// @title Spike-Only Strategy — 75 bps base, 4-tier aggressive spikes
/// @notice More granular spike tiers with larger magnitudes.
///         0.5%→+25, 1%→+75, 2%→+150, 3%→+200, 5%→+300 bps above base.
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

        uint256 tradeRatio = wdiv(trade.amountY, trade.reserveY);
        uint256 targetFee = baseFee;

        if (tradeRatio > WAD / 20) {           // > 5% of reserves
            targetFee = baseFee + 300 * BPS;   // spike to 375 bps
        } else if (tradeRatio > WAD / 33) {    // > 3% of reserves
            targetFee = baseFee + 200 * BPS;   // spike to 275 bps
        } else if (tradeRatio > WAD / 50) {    // > 2% of reserves
            targetFee = baseFee + 150 * BPS;   // spike to 225 bps
        } else if (tradeRatio > WAD / 100) {   // > 1% of reserves
            targetFee = baseFee + 75 * BPS;    // spike to 150 bps
        } else if (tradeRatio > WAD / 200) {   // > 0.5% of reserves
            targetFee = baseFee + 25 * BPS;    // spike to 100 bps
        }

        if (targetFee > fee) {
            fee = fee + (targetFee - fee) * 2 / 3;
        } else {
            // Faster decay: 1/4 of gap
            fee = fee - (fee - targetFee) / 4;
        }

        fee = clampFee(fee);
        if (fee < baseFee) fee = baseFee;

        slots[0] = fee;
        return (fee, fee);
    }

    function getName() external pure override returns (string memory) {
        return "SpikeOnly75-4T";
    }
}
