// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {AMMStrategyBase} from "./AMMStrategyBase.sol";
import {IAMMStrategy, TradeInfo} from "./IAMMStrategy.sol";

/// @title Fixed 80 bps — optimal fixed fee from sweep
contract Strategy is AMMStrategyBase {
    function afterInitialize(uint256, uint256)
        external override returns (uint256, uint256)
    {
        uint256 fee = 80 * BPS;
        return (fee, fee);
    }

    function afterSwap(TradeInfo calldata)
        external override returns (uint256, uint256)
    {
        uint256 fee = 80 * BPS;
        return (fee, fee);
    }

    function getName() external pure override returns (string memory) {
        return "Fixed80";
    }
}
