// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {AMMStrategyBase} from "./AMMStrategyBase.sol";
import {IAMMStrategy, TradeInfo} from "./IAMMStrategy.sol";

/// @title LinQuad Spike — Low Base
/// @notice Base 30 bps + hybrid linear+quadratic spike from trade size.
///         spike = tradeRatio * 0.75 + tradeRatio² * 25
///         Rise 2/3, decay 1/3. Low base captures retail, spikes handle arb.
contract Strategy is AMMStrategyBase {
    // slots[0] = current fee (WAD)

    function afterInitialize(uint256, uint256)
        external override returns (uint256, uint256)
    {
        uint256 fee = 30 * BPS;
        slots[0] = fee;
        return (fee, fee);
    }

    function afterSwap(TradeInfo calldata trade)
        external override returns (uint256, uint256)
    {
        uint256 fee = slots[0];
        uint256 baseFee = 30 * BPS;

        uint256 tradeRatio = wdiv(trade.amountY, trade.reserveY);
        uint256 linearPart = tradeRatio * 3 / 4;
        uint256 quadPart = wmul(tradeRatio, tradeRatio) * 25;
        uint256 spike = linearPart + quadPart;

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
        return "LinQuad-LowBase";
    }
}
