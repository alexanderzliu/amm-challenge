# AMM Strategy Lab - Status Briefing
<!-- Last synced with experiment: 008 -->

## Current Best
- **Strategy**: ContSpike75 (exp 008), Edge: ~434 (100 sims)
- **Mechanism**: 75 bps base + continuous spike proportional to trade size (spike = tradeRatio * 1.25), fast 1/3 decay
- **File**: my_strategy.sol

## Established Facts
1. **Optimal fee region is ~75-80 bps, NOT 30 bps** — the biggest finding (exp 004)
2. Arb protection (quadratic) far outweighs retail volume lost to vanilla at high fees
3. Retail routing is proportional (not winner-take-all) — still get retail even at 2.5x vanilla's fee
4. Arb is independent per AMM — wider no-arb band directly reduces losses
5. Continuous spike proportional to trade size beats discrete tiers (exp 008 vs 007)
6. Bigger spike magnitudes help — arb trades are large, so high spikes = high protection (exp 006→007)
7. Faster spike decay is better (1/3 > 1/4 > 1/8) — protection should be short-lived (exp 008)
8. Directional asymmetric fees provide no benefit against GBM random walk (exp 003)
9. Single vol signal outperforms dual signal — simpler is better (exp 001→002)
10. PropVol was suboptimal because it spent most time at 15-30 bps (exp 004)

## Evolution of Edge
| Exp | Strategy | Edge | Key Change |
|-----|----------|------|------------|
| 001 | AdaptiveDynamic v1 | 347 | Dual-signal vol tracking |
| 002 | PropVol | 375 | Single EMA, fee ∝ σ |
| 003 | DirSkew | 374 | Directional skew (no help) |
| 004 | Fixed80 | 385 | Discovered optimal fixed fee ~80 bps |
| 006 | SpikeOnly80 | 399 | High base + 2-tier spikes |
| 007 | SpikeOnly75-4T | 422 | Multi-tier aggressive spikes |
| 008 | ContSpike75 | 434 | Continuous proportional spike |

## Dead Ends (Do NOT Revisit)
- Directional fee skew / asymmetric bid-ask from trade direction (exp 003)
- Dual EMA signals blended together (exp 001)
- Low-fee undercutting of vanilla — arb protection matters more than retail capture
- High-floor vol-EMA (HiBase-VolAdj) — miscalibrated vol baseline caused terrible results (137 edge)

## Next Experiments (Priority Order)
1. Quadratic spike: spike ∝ tradeRatio² — penalize large trades more
2. Combine continuous spike with vol-EMA for base fee adjustment
3. Asymmetric rise/decay tuning (currently 2/3 rise, 1/3 decay)
4. Use amountX instead of amountY for spike calculation on buy trades
5. Higher-confidence run of ContSpike75 at 500+ sims

## Key Context
- Vanilla normalizer: fixed 30 bps, scores ~250-350 edge
- Simulation: 10k steps, GBM price (σ ~ U[0.088%, 0.101%]), zero drift
- Retail: λ ~ U[0.6, 1.0], size ~ LogN(~20, 1.2), 50/50 buy/sell
- Scoring: edge = profit using fair prices at trade time (retail=positive, arb=negative)
