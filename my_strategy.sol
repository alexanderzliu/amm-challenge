// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {AMMStrategyBase} from "./AMMStrategyBase.sol";
import {IAMMStrategy, TradeInfo} from "./IAMMStrategy.sol";

contract Strategy is AMMStrategyBase {
    function afterInitialize(uint256, uint256)
        external override returns (uint256, uint256)
    {
        uint256 fee = 24 * BPS;
        slots[0] = fee;
        return (fee, fee);
    }

    function afterSwap(TradeInfo calldata trade)
        external override returns (uint256, uint256)
    {
        uint256 fee = slots[0];
        uint256 baseFee = 24 * BPS;
        uint256 tradeRatio = wdiv(trade.amountY, trade.reserveY);
        uint256 linearPart = tradeRatio * 7 / 8;
        uint256 quadPart = wmul(tradeRatio, tradeRatio) * 27;
        uint256 spike = linearPart + quadPart;
        uint256 freshFee = baseFee + spike;
        uint256 decayedFee = fee * 6 / 7;
        if (decayedFee < baseFee) decayedFee = baseFee;
        fee = freshFee > decayedFee ? freshFee : decayedFee;
        fee = clampFee(fee);
        slots[0] = fee;
        return (fee, fee);
    }

    function getName() external pure override returns (string memory) {
        return "LinQuad-Tuned";
    }
}
