# AMM Strategy Lab - Status Briefing
<!-- Last synced with experiment: 022 -->

## Current Best
- **Strategy**: LinQuad-Tuned (exp 013), Edge: ~482 (500 sims)
- **Mechanism**: fee = max(24bps + tradeRatio*7/8 + tradeRatio²*27, prevFee*6/7)
- **File**: my_strategy.sol
- **Target**: 525+ (known to be achievable)

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
11. Trade activity EMA adds no value on top of trade-size spike mechanism (exp 011, 018)
12. **Retail volume share is ~39.5%** — vanilla captures 60% due to our spikes raising avg fee (exp 013)
13. **Seeds are deterministic** — same N seeds always give same result, so comparisons are precise (exp 013)
14. **Cubic spike term always hurts** — over-penalizes large trades (exp 014)
15. **Spike caps hurt** — unbounded spikes are essential for arb protection (exp 016)
16. **Ratio formula doesn't matter** — Y-only, X-only, max, avg, geomean all equivalent for CPMM (exp 015)
17. **Spike stacking hurts** — max(fresh, decayed) beats additive/dampened stacking (exp 020)
18. **k-invariant growth is too slow** to provide useful intra-simulation signal (exp 021)
19. **Timestamp features add nothing** — gap decay, frequency EMA, early/late switching all neutral (exp 018)
20. **Reserve deviation signals add nothing** — as base bonus or decay modifier, zero effect (exp 022)
21. **Spike+decay paradigm is exhausted** — 22 experiments, 8+ variants on the theme, all converge to ~482 (exp 014-022)

## Critical Architecture Insights (exp 022)
- **Timing problem**: afterSwap sets fee for NEXT trade. Arb (step N) sees decayed fee from step N-1. After arb, fee spikes. Retail (same step N) sees the spike. This is structurally backwards — arb pays low, retail pays high.
- **Fee separation**: Fees go to a separate bucket, NOT reserves. Both AMMs maintain ~identical reserves throughout. Retail routing depends on fee*reserves, but reserve difference is negligible.
- **Routing sensitivity**: At 24 vs 30 bps, we capture ~57% of retail. At 500 bps spike, we capture 0% retail. Weighted average = 39.5%.
- **The fundamental tension**: Spike protects against arb (quadratic gain) but destroys retail capture (linear loss). Net positive, but the mechanism caps at ~482.

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
- Gap-aware per-step decay — worse than per-trade decay (463 vs 482, exp 018)
- Trade frequency EMA for regime detection — no value add (exp 018)
- Early/late base fee switching — no improvement (exp 018)
- Adaptive base fee (decaying floor) — never activates in practice (exp 019)
- Two-tier decay (plateau + fast drop) — no improvement (exp 019)
- Sub-base undercutting floors — unreachable, no effect (exp 019)
- Direction-dependent spike coefficients — no improvement (exp 015)
- Geometric mean / max / avg of X,Y ratios — all same as Y-only (exp 015)
- Dampened spike stacking — worse with more stacking (exp 020)
- Additive spike stacking — inflates fees, loses retail (exp 020)
- K-invariant growth tracking — too slow-moving, zero effect (exp 021)
- Reserve deviation base bonus — raises fees, loses retail (exp 022)
- Reserve deviation adaptive decay — zero effect (exp 022)
- Peak-adaptive decay — within noise (exp 022)
- Trade-size EMA as dynamic floor — catastrophic fee inflation (exp 022)
- Size-conditional decay rates — zero effect vs base clamp (exp 022)
- Linear (additive) decay — keeps fee elevated too long (exp 022)
- Shifting lin/quad balance (more quad, less lin) — worse (exp 022)

## Next Experiments — PARADIGM SHIFT NEEDED
The spike+decay paradigm is exhausted at ~482. To reach 525+, we need categorically different approaches:

1. **Exploit the timing structure**: Arb sees decayed fee, retail sees spike. Can we design a mechanism where arb pays MORE and retail pays LESS? e.g., counter-based "retail window" that drops fee for N trades after a spike.
2. **Multi-trade history**: Use slots to store last 8-16 trade sizes. Compute running variance, detect regime changes. Different from single-trade EMA because it captures distribution shape.
3. **Joint base+spike co-optimization**: The current base (24) was tuned with spike coefficients fixed. A grid search over ALL 4 params simultaneously (base, linear, quad, decay) might find a different optimum in the 4D landscape.
4. **Completely different fee curve**: fee = a + b*log(1 + c*tradeRatio) or fee = a + b*(tradeRatio/(1+c*tradeRatio)). Saturating curves that spike quickly but cap gracefully.
5. **Per-simulation sigma estimation**: Since sigma varies per sim (U[0.088%, 0.101%]), estimating it from cumulative reserve changes and adapting base fee could help.
6. **Separate bid/ask with reserve-state conditioning**: Not directional prediction, but fee ∝ exposure. If reserveX is high (we hold lots of X), charge more to buy more X.

## Key Context
- Vanilla normalizer: fixed 30 bps, scores ~250-350 edge
- Simulation: 10k steps, GBM price (σ ~ U[0.088%, 0.101%]), zero drift
- Retail: λ ~ U[0.6, 1.0], size ~ LogN(~20, 1.2), 50/50 buy/sell
- Scoring: edge = profit using fair prices at trade time (retail=positive, arb=negative)
- Retail volume share at current strategy: ~39.5% (vanilla gets ~60.5%)
- Our arb volume: ~24k Y vs vanilla's ~52k Y (spikes protect well)
- **Sim order per step**: GBM price → arb trades (both AMMs) → retail trades (routed)
- **Fee timing**: afterSwap returns fee for NEXT trade, not current
- **Fee accrual**: Separate bucket, does NOT increase reserves/k
