# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

A competition to design dynamic fee strategies for a constant-product AMM (xy=k). Your strategy (a Solidity contract) competes against a fixed 30 bps "vanilla" normalizer. Both AMMs start with identical reserves (100 X, 10,000 Y). Score = average "edge" (profit using fair prices at trade time) across 1000 simulations of 10,000 steps each.

## Build & Run Commands

```bash
# Install Python package
pip install -e ".[dev]"

# Build the Rust simulation engine (required for running sims)
cd amm_sim_rs && pip install maturin && maturin develop --release && cd ..

# Validate a strategy (static analysis + compilation)
amm-match validate my_strategy.sol

# Run simulations (default 1000 sims)
amm-match run my_strategy.sol
amm-match run my_strategy.sol --simulations 100   # quick test

# Run tests
pytest tests/ -v
pytest tests/test_amm.py::TestAMM::test_initialization -v  # single test
```

## Architecture

**Solidity contracts** (`contracts/src/`): `IAMMStrategy.sol` defines the interface, `AMMStrategyBase.sol` provides helpers and the `slots[0..31]` storage array (32 uint256 slots, the only persistent storage allowed). `VanillaStrategy.sol` is the 30 bps normalizer you compete against.

**Python orchestration** (`amm_competition/`): `cli.py` is the entry point (`amm-match` command). `evm/validator.py` does static analysis, `evm/compiler.py` compiles with solc 0.8.24 and checks for forbidden opcodes (CALL, DELEGATECALL, CREATE, STATICCALL, SELFDESTRUCT, etc.), `evm/executor.py` deploys to pyrevm, `evm/adapter.py` bridges EVM↔Python.

**Rust simulation engine** (`amm_sim_rs/`): High-performance batch simulation. `run_batch()` is the main entry point called from Python. Handles GBM price process, arbitrageur trades, retail order generation, and optimal order routing between the two AMMs.

**Competition logic** (`amm_competition/competition/`): `match.py` runs simulations and computes results. `config.py` defines baseline settings and variance ranges (σ ∈ U[0.088%, 0.101%], retail λ ∈ U[0.6, 1.0], retail size mean ∈ U[19, 21]).

## Strategy Contract Rules

The contract must be named `Strategy`, inherit from `AMMStrategyBase`, and implement three functions:
- `afterInitialize(uint256 initialX, uint256 initialY) → (uint256 bidFee, uint256 askFee)` — called once at start
- `afterSwap(TradeInfo calldata trade) → (uint256 bidFee, uint256 askFee)` — called after every trade, returns fees for the next trade
- `getName() → string` — strategy name

Fees are in WAD precision (1e18 = 100%). Use `BPS` constant (1e14 = 1 basis point). Max fee is 10% (1e17). Only imports allowed: `./AMMStrategyBase.sol` and `./IAMMStrategy.sol`. No assembly, no external calls, no contract creation. Use `slots[0..31]` for all persistent state.

`TradeInfo` fields: `bool isBuy` (AMM bought X), `uint256 amountX/amountY` (WAD), `uint256 timestamp` (step number), `uint256 reserveX/reserveY` (post-trade).

Helper functions available: `wmul`, `wdiv`, `clampFee`, `bpsToWad`, `absDiff`, `sqrt`, `readSlot`, `writeSlot`.

## Experiment Tracking

We track strategy experiments with a two-layer system. **Read `experiments/SUMMARY.md` first** — it has the current best strategy, established facts, dead ends, and prioritized next experiments. `experiments/index.json` has structured records for every experiment with hypothesis, parameters, verdict, insights, and tags.

**Workflow for each experiment:**
1. Edit `my_strategy.sol` with the new strategy
2. Run `amm-match validate my_strategy.sol`, then `amm-match run my_strategy.sol --simulations 100`
3. Append a record to `experiments/index.json` (with hypothesis, params, results, verdict, insights)
4. Update `experiments/SUMMARY.md` if the best changed or new lessons were learned
5. Commit everything together — each experiment = one git commit, hash recorded in `index.json`

The `index.json` schema per experiment: `id`, `name`, `parent_id` (lineage), `hypothesis`, `variables_changed`, `verdict` (confirmed/rejected/inconclusive), `insights[]`, `params{}`, `results{edge, win_rate, n_simulations, retail_volume_share}`, `sim_config`, `git_hash`, `tags[]`.

## Key Domain Knowledge

The fundamental tradeoff: higher fees reduce arb losses (quadratic protection) but lose retail volume to vanilla (linear loss). Fee proportional to realized volatility (fee ≈ k × σ) is theoretically optimal and empirically confirmed. During calm markets, undercut vanilla to capture retail. During volatile markets, raise fees to limit arb losses. The price follows GBM with zero drift — there are no persistent trends to exploit, so directional strategies don't help.
