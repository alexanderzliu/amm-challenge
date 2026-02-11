// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {AMMStrategyBase} from "./AMMStrategyBase.sol";
import {IAMMStrategy, TradeInfo} from "./IAMMStrategy.sol";

contract Strategy is AMMStrategyBase {
    // slots[0] = bid fee (used when AMM buys X)
    // slots[1] = ask fee (used when AMM sells X)

    // DirContrarian: After trade in direction D, spike OPPOSITE direction only.
    // Same direction decays. This captures more retail (50% sees low fee)
    // while providing 50% arb protection (random direction under GBM).

    function afterInitialize(uint256, uint256)
        external override returns (uint256, uint256)
    {
        uint256 fee = 24 * BPS;
        slots[0] = fee;
        slots[1] = fee;
        return (fee, fee);
    }

    function afterSwap(TradeInfo calldata trade)
        external override returns (uint256, uint256)
    {
        uint256 bidFee = slots[0];
        uint256 askFee = slots[1];
        uint256 baseFee = 24 * BPS;

        uint256 tradeRatio = wdiv(trade.amountY, trade.reserveY);
        uint256 linearPart = tradeRatio * 5 / 4;
        uint256 quadPart = wmul(tradeRatio, tradeRatio) * 15;
        uint256 spike = linearPart + quadPart;
        uint256 freshFee = baseFee + spike;

        uint256 decayedBid = bidFee * 8 / 9;
        uint256 decayedAsk = askFee * 8 / 9;
        if (decayedBid < baseFee) decayedBid = baseFee;
        if (decayedAsk < baseFee) decayedAsk = baseFee;

        if (trade.isBuy) {
            // AMM bought X → spike ask (opposite), decay bid (same)
            askFee = freshFee > decayedAsk ? freshFee : decayedAsk;
            bidFee = decayedBid;
        } else {
            // AMM sold X → spike bid (opposite), decay ask (same)
            bidFee = freshFee > decayedBid ? freshFee : decayedBid;
            askFee = decayedAsk;
        }

        bidFee = clampFee(bidFee);
        askFee = clampFee(askFee);
        slots[0] = bidFee;
        slots[1] = askFee;
        return (bidFee, askFee);
    }

    function getName() external pure override returns (string memory) {
        return "DirContrarian";
    }
}
