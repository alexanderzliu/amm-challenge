#!/usr/bin/env python3
"""Analyze per-step data to understand fee patterns and retail routing."""

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
        seed=42,
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

    runner = MatchRunner(
        n_simulations=3, config=config, n_workers=resolve_n_workers(), variance=variance,
    )

    result = runner.run_match(user_strategy, default_strategy, store_results=True)
    sim = result.simulation_results[0]

    # Examine step structure
    step0 = sim.steps[0]
    print("Step 0 attributes:", [a for a in dir(step0) if not a.startswith('_')])
    print()

    for attr in dir(step0):
        if attr.startswith('_'):
            continue
        try:
            val = getattr(step0, attr)
            if not callable(val):
                print(f"  step.{attr} = {val}")
        except:
            pass

    # Look at a few interesting steps (ones with arb + retail)
    print("\n=== Analyzing step-by-step patterns ===")

    arb_steps = 0
    no_arb_steps = 0
    retail_after_arb = 0
    retail_no_arb = 0
    sub_retail_buy_arb_buy = 0  # retail buys after arb buy (opposite = spiked ask)
    sub_retail_sell_arb_buy = 0  # retail sells after arb buy (same = low bid)
    sub_retail_buy_arb_sell = 0
    sub_retail_sell_arb_sell = 0
    sub_retail_noarb = 0

    # Analyze fee at time of retail trades
    sub_bid_fees_at_retail = []
    sub_ask_fees_at_retail = []

    for i, step in enumerate(sim.steps[:20]):
        attrs = dir(step)
        # Print first 20 steps in detail
        has_arb = False
        arb_dir = None

        print(f"\nStep {i}:")
        for attr in sorted(attrs):
            if attr.startswith('_'):
                continue
            try:
                val = getattr(step, attr)
                if not callable(val):
                    sval = str(val)
                    if len(sval) < 300:
                        print(f"  {attr}: {val}")
                    else:
                        print(f"  {attr}: (len={len(sval)})")
            except:
                pass


if __name__ == "__main__":
    main()
