# AMM Strategy Lab - Status Briefing
<!-- Last synced with experiment: 017 -->

## Current Best
- **Strategy**: LinQuad-Tuned (exp 013), Edge: ~482 (500 sims)
- **Mechanism**: fee = max(24bps + tradeRatio*7/8 + tradeRatio²*27, prevFee*6/7)
- **File**: my_strategy.sol

## Established Facts
1. **Optimal fixed fee is ~75-80 bps** — but dynamic spikes shift this (exp 004)
2. **With strong spikes, optimal base drops to 24-30 bps** — spikes handle arb, low base captures retail (exp 010, 013)
3. **Lin+quad spike > pure linear > pure quadratic > piecewise linear > sqrt** — continuous curve best (exp 009, 016)
4. **Instant rise + slow decay is optimal** — react instantly to threats, relax gradually (exp 011)
5. No smoothing at all (instant both ways) is terrible — fee must persist across trades (exp 011)
6. Arb protection (quadratic) far outweighs retail volume lost to vanilla at high fees
7. Retail routing is optimal splitting (not proportional) — share ∝ sqrt(γ·reserves) (exp 013)
8. Arb is independent per AMM — wider no-arb band directly reduces losses
9. Directional asymmetric fees provide no benefit against GBM random walk (exp 003)
10. Price-change-based spike is corrupted by fee impact — trade size is the right signal (exp 012, 017)
11. Trade activity EMA adds no value on top of trade-size spike mechanism (exp 011, 013)
12. **Retail volume share is ~39.5%** — vanilla captures 60% due to our spikes raising avg fee (exp 013)
13. **Seeds are deterministic** — same N seeds always give same result, so comparisons are precise (exp 013)
14. **Cubic spike term always hurts** — over-penalizes large trades (exp 014)
15. **Spike caps hurt** — unbounded spikes are essential for arb protection (exp 016)
16. **Ratio formula doesn't matter** — Y-only, X-only, max, avg, geomean all equivalent for CPMM (exp 015) (exp 013)

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
| 013 | LinQuad-Tuned | 482 | Fine-tuned params: base 24, quad 27, decay 6/7 |

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
- Cubic spike term — over-penalizes, always hurts (exp 014)
- Spike caps (100-1000 bps) — limiting spikes loses arb protection (exp 016)
- Piecewise linear spike — worse than continuous lin+quad (exp 016)
- Sqrt-based spike — catastrophically over-reactive (89-367 edge, exp 016)
- Realized vol from spot prices — corrupted by trade impact, catastrophic (294 edge, exp 017)
- Gap-aware per-step decay — worse than per-trade decay (463 vs 482, exp 013)
- Adaptive base fee (decaying floor) — never activates in practice (exp 013)
- Trade frequency EMA for regime detection — no value add (exp 013)
- Two-tier decay (plateau + fast drop) — no improvement (exp 013)
- Direction-dependent spike coefficients — no improvement (exp 015)
- Geometric mean / max / avg of X,Y ratios — all same as Y-only (exp 015)

## Next Experiments (Priority Order)
1. **New information sources**: The strategy currently only uses trade.amountY, trade.reserveY, and prevFee. Explore what truly novel information can be extracted from the 6 TradeInfo fields.
2. **Ensemble/switching**: Different strategies for early vs late simulation (warmup then optimize)
3. **Non-linear decay**: Exponential/polynomial decay curves instead of constant multiplicative
4. **Fee-dependent spike scaling**: Scale spike inversely with current fee (spike less when already high)

## Key Context
- Vanilla normalizer: fixed 30 bps, scores ~250-350 edge
- Simulation: 10k steps, GBM price (σ ~ U[0.088%, 0.101%]), zero drift
- Retail: λ ~ U[0.6, 1.0], size ~ LogN(~20, 1.2), 50/50 buy/sell
- Scoring: edge = profit using fair prices at trade time (retail=positive, arb=negative)
- Retail volume share at current strategy: ~39.5% (vanilla gets ~60.5%)
- Our arb volume: ~24k Y vs vanilla's ~52k Y (spikes protect well)
