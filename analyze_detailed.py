#!/usr/bin/env python3
"""Detailed per-step analysis to understand fee dynamics and routing."""

import numpy as np
import amm_sim_rs
from amm_competition.competition.match import MatchRunner, HyperparameterVariance
from amm_competition.evm.adapter import EVMStrategyAdapter
from amm_competition.evm.baseline import load_vanilla_strategy
from amm_competition.evm.compiler import SolidityCompiler
from amm_competition.competition.config import (
    BASELINE_SETTINGS, BASELINE_VARIANCE,
    baseline_nominal_retail_rate, baseline_nominal_retail_size,
    baseline_nominal_sigma, resolve_n_workers,
)
from pathlib import Path


def main():
    source = Path("my_strategy.sol").read_text()
    compiler = SolidityCompiler()
    comp = compiler.compile(source)
    if not comp.success:
        print("Compilation failed"); return

    user_strategy = EVMStrategyAdapter(bytecode=comp.bytecode, abi=comp.abi)
    default_strategy = load_vanilla_strategy()

    config = amm_sim_rs.SimulationConfig(
        n_steps=BASELINE_SETTINGS.n_steps,
        initial_price=BASELINE_SETTINGS.initial_price,
        initial_x=BASELINE_SETTINGS.initial_x,
        initial_y=BASELINE_SETTINGS.initial_y,
        gbm_mu=BASELINE_SETTINGS.gbm_mu,
        gbm_sigma=baseline_nominal_sigma(),
        gbm_dt=BASELINE_SETTINGS.gbm_dt,
        retail_arrival_rate=baseline_nominal_retail_rate(),
        retail_mean_size=baseline_nominal_retail_size(),
        retail_size_sigma=BASELINE_SETTINGS.retail_size_sigma,
        retail_buy_prob=BASELINE_SETTINGS.retail_buy_prob,
        seed=42,  # Fixed seed for reproducibility
    )

    variance = HyperparameterVariance(
        retail_mean_size_min=BASELINE_VARIANCE.retail_mean_size_min,
        retail_mean_size_max=BASELINE_VARIANCE.retail_mean_size_max,
        vary_retail_mean_size=BASELINE_VARIANCE.vary_retail_mean_size,
        retail_arrival_rate_min=BASELINE_VARIANCE.retail_arrival_rate_min,
        retail_arrival_rate_max=BASELINE_VARIANCE.retail_arrival_rate_max,
        vary_retail_arrival_rate=BASELINE_VARIANCE.vary_retail_arrival_rate,
        gbm_sigma_min=BASELINE_VARIANCE.gbm_sigma_min,
        gbm_sigma_max=BASELINE_VARIANCE.gbm_sigma_max,
        vary_gbm_sigma=BASELINE_VARIANCE.vary_gbm_sigma,
    )

    # Run just 10 sims to examine detailed structure
    runner = MatchRunner(
        n_simulations=10, config=config, n_workers=resolve_n_workers(), variance=variance,
    )

    print("Running 10 sims with store_results=True...")
    result = runner.run_match(user_strategy, default_strategy, store_results=True)

    # Look at what's available in simulation results
    for i, sim in enumerate(result.simulation_results[:3]):
        print(f"\n=== Sim {i} ===")
        print(f"Edge: sub={sim.edges.get('submission', 0):.2f}, norm={sim.edges.get('normalizer', 0):.2f}")
        print(f"Arb vol Y: sub={sim.arb_volume_y.get('submission', 0):.0f}, norm={sim.arb_volume_y.get('normalizer', 0):.0f}")
        print(f"Retail vol Y: sub={sim.retail_volume_y.get('submission', 0):.0f}, norm={sim.retail_volume_y.get('normalizer', 0):.0f}")
        print(f"Avg fees: {sim.average_fees}")

        # Check what attributes are available
        attrs = [a for a in dir(sim) if not a.startswith('_')]
        print(f"Available attrs: {attrs}")

        # Check for per-trade data
        if hasattr(sim, 'trades'):
            print(f"Trades available: {len(sim.trades)}")
        if hasattr(sim, 'trade_results'):
            print(f"Trade results: {len(sim.trade_results)}")
        if hasattr(sim, 'per_step_data'):
            print(f"Per-step data: {len(sim.per_step_data)}")
        if hasattr(sim, 'fee_history'):
            print(f"Fee history: {len(sim.fee_history)}")

        # Try to access all attributes
        for attr in attrs:
            try:
                val = getattr(sim, attr)
                if not callable(val) and val is not None:
                    if isinstance(val, (dict, list)):
                        if len(str(val)) < 200:
                            print(f"  {attr}: {val}")
                        else:
                            print(f"  {attr}: len={len(val)}")
                    elif isinstance(val, (int, float, str, bool)):
                        print(f"  {attr}: {val}")
            except:
                pass

    # Overall stats
    print("\n=== Overall ===")
    print(f"Wins: {result.wins_a}/{10}")
    print(f"Draws: {result.draws}/{10}")

    # Print match result attributes
    attrs = [a for a in dir(result) if not a.startswith('_')]
    print(f"Result attrs: {attrs}")


if __name__ == "__main__":
    main()
