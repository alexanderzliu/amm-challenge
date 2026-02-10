# AMM Strategy Lab - Status Briefing
<!-- Last synced with experiment: 012 -->

## Current Best
- **Strategy**: LinQuad-MultDecay (exp 012), Edge: ~478 (500 sims)
- **Mechanism**: fee = max(30bps + tradeRatio*0.75 + tradeRatio²*25, prevFee*7/8)
- **File**: my_strategy.sol

## Established Facts
1. **Optimal fixed fee is ~75-80 bps** — but dynamic spikes shift this (exp 004)
2. **With strong spikes, optimal base drops to 30-40 bps** — spikes handle arb, low base captures retail (exp 010)
3. **Lin+quad spike > pure linear > pure quadratic** — hybrid penalizes large trades more while still reacting to small ones (exp 009)
4. **Instant rise + slow decay is optimal** — react instantly to threats, relax gradually (exp 011)
5. No smoothing at all (instant both ways) is terrible — fee must persist across trades (exp 011)
6. Arb protection (quadratic) far outweighs retail volume lost to vanilla at high fees
7. Retail routing is proportional (not winner-take-all) — still get retail even at 2.5x vanilla's fee
8. Arb is independent per AMM — wider no-arb band directly reduces losses
9. Directional asymmetric fees provide no benefit against GBM random walk (exp 003)
10. Price-change-based spike (450) is worse than trade-size-based spike (479) — size is a better signal
11. Trade activity EMA adds no value on top of the smoothed spike mechanism (exp ~011)

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
| 009 | LinQuadSpike | 445 | Hybrid lin+quad spike formula |
| 010 | LinQuad-LowBase | 464 | Base drops to 30 bps with strong spikes |
| 011 | LinQuad-InstantRise | 479 | Instant rise + 1/5 decay |
| 012 | LinQuad-MultDecay | 478 | Multiplicative decay (fee*7/8), 500-sim validated |

## Dead Ends (Do NOT Revisit)
- Directional fee skew / asymmetric bid-ask from trade direction (exp 003)
- Dual EMA signals blended together (exp 001)
- Low-fee undercutting of vanilla without spikes — arb protection matters more
- High-floor vol-EMA (HiBase-VolAdj) — miscalibrated vol baseline (137 edge)
- Pure quadratic spike — underreacts to small trades (427 vs 445 lin+quad)
- Price-change spike — trade size is a better reactive signal (450 vs 479)
- Trade activity EMA on top of smoothed spike — no improvement
- No smoothing (instant fee) — terrible without memory (396)
- Asymmetric bid/ask fees — hurts significantly (405 vs 474) under GBM
- Vol-regime-aware base fee — corrupted signal from trade price changes (456 vs 474)
- Arb cluster detection (adaptive decay) — no improvement (474)
- Max X/Y ratio — no difference from Y-only (474)
- Multiplicative spike on current fee — runaway fee inflation (155)

## Next Experiments (Priority Order)
1. Explore fundamentally different spike shapes (piecewise, capped, etc.)
2. Time-based features (use timestamp to detect regime changes)
3. Reserve-ratio-based signals (track xy=k invariant changes)
4. Ensemble: blend multiple simple strategies

## Key Context
- Vanilla normalizer: fixed 30 bps, scores ~250-350 edge
- Simulation: 10k steps, GBM price (σ ~ U[0.088%, 0.101%]), zero drift
- Retail: λ ~ U[0.6, 1.0], size ~ LogN(~20, 1.2), 50/50 buy/sell
- Scoring: edge = profit using fair prices at trade time (retail=positive, arb=negative)
