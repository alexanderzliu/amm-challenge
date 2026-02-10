# AMM Strategy Lab - Status Briefing
<!-- Last synced with experiment: 003 -->

## Current Best
- **Strategy**: PropVol (exp 002), Edge: 374.54 (100 sims)
- **Mechanism**: fee = 3 * emaVol, EMA alpha=0.10, floor=15bps, spike on large trades
- **File**: my_strategy.sol

## Established Facts
1. Single vol signal (price EMA) outperforms dual signal (price + trade size) — simpler is better
2. Fee proportional to realized volatility (fee ∝ σ) is theoretically grounded and empirically superior to fixed base + additive adjustment
3. Directional asymmetric fees provide no benefit against GBM random walk (zero drift, no persistent trends)
4. Wider dynamic range (15-90 bps) beats narrower (20-60 bps)
5. Faster EMA (alpha=0.10) beats slower (alpha=0.05)

## Dead Ends (Do NOT Revisit)
- Directional fee skew / asymmetric bid-ask from trade direction (exp 003)
- Dual EMA signals blended together (exp 001)

## Next Experiments (Priority Order)
1. Fixed fee sweep: 25, 28, 30, 35 bps — establish baseline to know if dynamics actually help
2. PropVol without spikes — isolate whether spikes help or hurt
3. PropVol multiplier sweep: 2.5 vs 3.0 vs 3.5
4. Faster EMA alpha=0.20 — test reaction speed
5. Squared returns EMA for better variance estimation

## Key Context
- Vanilla normalizer: fixed 30 bps, scores ~250-350 edge
- Simulation: 10k steps, GBM price (σ ~ U[0.088%, 0.101%]), zero drift
- Retail: λ ~ U[0.6, 1.0], size ~ LogN(~20, 1.2), 50/50 buy/sell
- Scoring: edge = profit using fair prices at trade time (retail=positive, arb=negative)
