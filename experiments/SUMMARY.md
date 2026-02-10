# AMM Strategy Lab - Status Briefing
<!-- Last synced with experiment: 007 -->

## Current Best
- **Strategy**: SpikeOnly75-4T (exp 007), Edge: 422.12 (100 sims)
- **Mechanism**: 75 bps base, 5-tier spikes (+25 to +300 bps) based on trade size, fast decay
- **File**: my_strategy.sol

## Established Facts
1. Single vol signal (price EMA) outperforms dual signal (price + trade size) — simpler is better
2. Fee proportional to realized volatility (fee ∝ σ) is theoretically grounded but empirically suboptimal due to sitting in wrong fee region
3. Directional asymmetric fees provide no benefit against GBM random walk (zero drift, no persistent trends)
4. **Optimal fixed fee is ~75-80 bps, NOT near vanilla's 30 bps** — paradigm shift from exp 004
5. Arb protection (quadratic) far outweighs retail volume lost to vanilla at high fees
6. Retail routing is proportional (not winner-take-all) — still get retail even at 2.5x vanilla's fee
7. Arb is independent per AMM — wider no-arb band directly reduces losses
8. PropVol (exp 002) was suboptimal because it spent most time at 15-30 bps

## Dead Ends (Do NOT Revisit)
- Directional fee skew / asymmetric bid-ask from trade direction (exp 003)
- Dual EMA signals blended together (exp 001)
- Low-fee undercutting of vanilla — arb protection matters more than retail capture

## Next Experiments (Priority Order)
1. High-base spike strategy: 75-80 bps base + spike up on large trades (arb protection)
2. Continuous spike proportional to trade size vs discrete tiers
3. Spike magnitude sweep
4. Spike decay speed sweep
5. Combine high base with vol-EMA adjustment

## Key Context
- Vanilla normalizer: fixed 30 bps, scores ~250-350 edge
- Simulation: 10k steps, GBM price (σ ~ U[0.088%, 0.101%]), zero drift
- Retail: λ ~ U[0.6, 1.0], size ~ LogN(~20, 1.2), 50/50 buy/sell
- Scoring: edge = profit using fair prices at trade time (retail=positive, arb=negative)
