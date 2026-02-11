#!/usr/bin/env python3
"""Detailed edge decomposition analysis.
Run with: python3 analyze_edge.py
This analyzes per-step data to decompose edge into arb loss and retail gain."""

import sys
from pathlib import Path
import numpy as np

import amm_sim_rs
from amm_competition.competition.match import MatchRunner, HyperparameterVariance
from amm_competition.evm.adapter import EVMStrategyAdapter
from amm_competition.evm.baseline import load_vanilla_strategy
from amm_competition.evm.compiler import SolidityCompiler
from amm_competition.competition.config import (
    BASELINE_SETTINGS,
    BASELINE_VARIANCE,
    baseline_nominal_retail_rate,
    baseline_nominal_retail_size,
    baseline_nominal_sigma,
    resolve_n_workers,
)


def main():
    strategy_path = Path("my_strategy.sol")
    source_code = strategy_path.read_text()

    compiler = SolidityCompiler()
    compilation = compiler.compile(source_code)
    if not compilation.success:
        print("Compilation failed")
        return

    user_strategy = EVMStrategyAdapter(bytecode=compilation.bytecode, abi=compilation.abi)
    default_strategy = load_vanilla_strategy()

    n_sims = 100

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
        seed=None,
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
        n_simulations=n_sims,
        config=config,
        n_workers=resolve_n_workers(),
        variance=variance,
    )

    print(f"Running {n_sims} simulations with detailed analysis...\n")
    result = runner.run_match(user_strategy, default_strategy, store_results=True)

    # Collect per-sim data
    sub_edges = []
    norm_edges = []
    sub_arb_vols = []
    sub_retail_vols = []
    norm_arb_vols = []
    norm_retail_vols = []
    sub_avg_fees_bid = []
    sub_avg_fees_ask = []
    retail_shares = []

    for sim in result.simulation_results:
        sub_edges.append(float(sim.edges.get("submission", 0)))
        norm_edges.append(float(sim.edges.get("normalizer", 0)))
        sub_arb_vols.append(sim.arb_volume_y.get("submission", 0))
        sub_retail_vols.append(sim.retail_volume_y.get("submission", 0))
        norm_arb_vols.append(sim.arb_volume_y.get("normalizer", 0))
        norm_retail_vols.append(sim.retail_volume_y.get("normalizer", 0))

        sub_fee = sim.average_fees.get("submission", (0, 0))
        if isinstance(sub_fee, tuple):
            sub_avg_fees_bid.append(sub_fee[0])
            sub_avg_fees_ask.append(sub_fee[1])
        else:
            sub_avg_fees_bid.append(sub_fee)
            sub_avg_fees_ask.append(sub_fee)

        total_retail = sim.retail_volume_y.get("submission", 0) + sim.retail_volume_y.get("normalizer", 0)
        if total_retail > 0:
            retail_shares.append(sim.retail_volume_y.get("submission", 0) / total_retail)

    # Compute derived metrics
    sub_edges = np.array(sub_edges)
    norm_edges = np.array(norm_edges)
    sub_arb_vols = np.array(sub_arb_vols)
    sub_retail_vols = np.array(sub_retail_vols)
    norm_arb_vols = np.array(norm_arb_vols)
    norm_retail_vols = np.array(norm_retail_vols)

    # Estimate arb and retail edge contributions
    # Total edge = arb_edge (negative) + retail_edge (positive)
    # arb_edge ≈ -arb_volume * effective_arb_spread (unknown exact value)
    # retail_edge ≈ retail_volume * avg_fee (approximately)

    # We can estimate retail_edge = retail_vol * avg_fee (weighted)
    # Then arb_edge = total_edge - retail_edge
    avg_bid_fee = np.mean(sub_avg_fees_bid) / 1e18  # convert from WAD
    avg_ask_fee = np.mean(sub_avg_fees_ask) / 1e18
    avg_fee = (avg_bid_fee + avg_ask_fee) / 2

    est_retail_edge = sub_retail_vols * avg_fee
    est_arb_edge = sub_edges - est_retail_edge

    print(f"=== EDGE DECOMPOSITION ({n_sims} sims) ===")
    print(f"Total submission edge (avg): {sub_edges.mean():.2f}")
    print(f"Total normalizer edge (avg): {norm_edges.mean():.2f}")
    print(f"Submission std:              {sub_edges.std():.2f}")
    print()
    print(f"Est. retail income (avg):    {est_retail_edge.mean():.2f}")
    print(f"Est. arb loss (avg):         {est_arb_edge.mean():.2f}")
    print(f"  (retail - arb = total)")
    print()

    print(f"=== VOLUME ===")
    print(f"Sub arb vol:     {sub_arb_vols.mean():.0f} (±{sub_arb_vols.std():.0f})")
    print(f"Sub retail vol:  {sub_retail_vols.mean():.0f} (±{sub_retail_vols.std():.0f})")
    print(f"Norm arb vol:    {norm_arb_vols.mean():.0f}")
    print(f"Norm retail vol: {norm_retail_vols.mean():.0f}")
    print(f"Total retail:    {(sub_retail_vols + norm_retail_vols).mean():.0f}")
    print(f"Retail share:    {np.mean(retail_shares)*100:.1f}%")
    print()

    print(f"=== FEES (bps) ===")
    print(f"Sub avg bid fee: {avg_bid_fee*10000:.1f}")
    print(f"Sub avg ask fee: {avg_ask_fee*10000:.1f}")
    print(f"Sub avg fee:     {avg_fee*10000:.1f}")
    print()

    print(f"=== WIN RATE ===")
    print(f"Wins: {result.wins_a}/{n_sims} ({100*result.wins_a/n_sims:.0f}%)")
    print()

    # Per-sim distribution
    print(f"=== EDGE DISTRIBUTION ===")
    percentiles = [5, 25, 50, 75, 95]
    for p in percentiles:
        print(f"  P{p}: {np.percentile(sub_edges, p):.2f}")

    # Correlation analysis
    print(f"\n=== CORRELATIONS ===")
    print(f"edge vs arb_vol:    r={np.corrcoef(sub_edges, sub_arb_vols)[0,1]:.3f}")
    print(f"edge vs retail_vol: r={np.corrcoef(sub_edges, sub_retail_vols)[0,1]:.3f}")
    print(f"arb_vol vs retail_vol: r={np.corrcoef(sub_arb_vols, sub_retail_vols)[0,1]:.3f}")


if __name__ == "__main__":
    main()
