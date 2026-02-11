# AMM Strategy Lab - Status Briefing
<!-- Last synced with experiment: 032 -->

## Current Best
- **Strategy**: DirContrarian (exp 025), Edge: ~497 (500 sims)
- **Mechanism**: Separate bid/ask fees. After trade in direction D, spike OPPOSITE direction only, decay same direction. fee_spike = 24bps + tradeRatio*5/4 + tradeRatio²*15, decay 8/9
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
9. ~~Directional asymmetric fees provide no benefit against GBM random walk (exp 003)~~ **SUPERSEDED by exp 025**: contrarian directional spike IS beneficial (+15 edge)
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
21. ~~Spike+decay paradigm is exhausted~~ **SUPERSEDED**: Directional contrarian spike breaks the ~482 ceiling → 497 (exp 025)
22. **Base=24 is globally optimal** across ALL spike/decay combos, including DirContrarian (exp 023, 025)
23. **Smooth EMA fee fails** — fee must react instantly to arbs. Any smoothing loses arb protection (exp 023)
24. **Floor above vanilla has zero effect** — fee rarely drops below 31 bps between arb events anyway (exp 023)
25. **Router uses bid_fee/ask_fee SEPARATELY** — buy orders use ask_fee, sell orders use bid_fee. This creates an exploitable asymmetry. (exp 025)
26. **Contrarian spike is strictly better than same-direction or symmetric** — spike opposite direction: 497, spike same: 302, symmetric: 482 (exp 025)
27. **DirContrarian prefers stronger linear (5/4), weaker quad (15), slower decay (8/9)** than symmetric baseline (7/8, 27, 6/7) (exp 025)
28. **Any same-direction spike component hurts** — hybrid same=10%: 496, same=25%: 495, same=50%: 491. Pure contrarian optimal. (exp 025)
29. **DirContrarian at ~497 is a robust local optimum** — 30+ enhancement variants tested (timing, asymmetric decay/base, sigma adaptation, spot tracking, reserve scaling, size switching, direction-specific coefficients), NONE beat it at 500 sims (exp 026)
30. **Spike caps hurt even in DirContrarian** — Cap50→380, Cap500→489, confirming unbounded spikes essential (exp 027)
31. **Two-level base (sameBase≠oppBase) doesn't help** — opposite side must decay to same 24 bps base for retail capture (exp 027)
32. **DC base monotonically optimal at 24** — full scan 20-40 bps shows edge declining steadily above 24 (exp 029)
33. **Fee-level routing advantage is negligible (0.015%)** — k-preservation from spike protection is what drives our ~57% retail share, not fee undercutting (exp 029)
34. **Same-side decay memory is critical** — resetting same side to base each trade → 390 edge; setting same=30 (match vanilla) → 403 edge (exp 029)
35. **All alternative fee paradigms fail** — oscillating, predictive, accumulator, delayed, high-default, reverse-decay all worse than DirContrarian. Fee must be simultaneously high for arb and low for retail; DC's bid/ask split is the best known compromise (exp 030)
36. **Optimal constant fee is ~75-80 bps** — constant fee landscape is monotonically increasing up to 75-80 range (exp 031)
37. **Revenue per order = share × fee is maximized at ~36 bps** but DC at 24 still beats DC at 36 due to routing volume advantage (exp 031)
38. **Lin+quad spike formula is well-optimized** — pure quad (410), pure linear (485), geometric mean (323) all worse. Fast/slow decay variants within noise (exp 032)

## Critical Architecture Insights (exp 022, 025)
- **Timing problem**: afterSwap sets fee for NEXT trade. Arb (step N) sees decayed fee from step N-1. After arb, fee spikes. Retail (same step N) sees the spike. This is structurally backwards — arb pays low, retail pays high.
- **Directional exploit**: Router evaluates bid_fee and ask_fee independently for buy/sell orders. By spiking only the OPPOSITE direction's fee after a trade, half of retail sees the low (decayed) fee while the spiked direction provides arb protection with 50% probability.
- **Fee separation**: Fees go to a separate bucket, NOT reserves. k = x*y is preserved exactly. Both AMMs maintain identical k throughout. Retail routing depends on fee alone (A_i = sqrt(k * gamma_i)).
- **Routing sensitivity**: At 24 vs 30 bps, we capture ~57% of retail. At 500 bps spike, we capture 0% retail. Weighted average = 39.5%.
- **The fundamental tension**: Spike protects against arb (quadratic gain) but destroys retail capture (linear loss). DirContrarian partially resolves this by splitting the spike across directions.

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
| 025 | DirContrarian | 497 | **Contrarian directional bid/ask spike** |

## Dead Ends (Do NOT Revisit)
- ~~Directional fee skew / asymmetric bid-ask from trade direction (exp 003)~~ — NOTE: exp 003 tested SAME-direction skew which failed. CONTRARIAN direction works! (exp 025)
- Dual EMA signals blended together (exp 001)
- Low-fee undercutting of vanilla without spikes — arb protection matters more
- High-floor vol-EMA (HiBase-VolAdj) — miscalibrated vol baseline (137 edge)
- Pure quadratic spike — underreacts to small trades (427 vs 445 lin+quad)
- Price-change spike — trade size is a better reactive signal (450 vs 479)
- Trade activity EMA on top of smoothed spike — no improvement
- No smoothing (instant fee) — terrible without memory (396)
- **Same-direction spike** — spikes the fee retail uses, catastrophic (302 edge, exp 025)
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
- Higher base (28-40 bps) with any spike combination — always worse at 500 sims (exp 023)
- Smooth EMA fee (α=1/4) — too slow for arb protection, 421 edge (exp 023)
- Vol-proportional fee from trade variance EMA — corrupted signal, 413 edge (exp 023)
- Floor above vanilla (31 bps min) — zero effect, fee rarely that low anyway (exp 023)
- 4D grid search exhausted: base 24 is globally optimal across all spike/decay combos (exp 023)
- Reserve-state bid/ask asymmetry — neutral to harmful under GBM (exp 024)
- Saturating spike (Hill function) — same problem as hard caps (exp 024)
- Hybrid saturating bonus on lin+quad — inflates retail fee (exp 024)
- Price-change spike — catastrophic, corrupted by fee (exp 024)
- Partial spike stacking (1/4 decayed excess) — within noise (exp 024)
- TimingSwitch binary arb/retail detection — too noisy, 324-400 edge (exp 025)
- Sigma-adaptive base fee — adds noise, 480 edge (exp 025)
- Two-phase temporal strategy — no improvement (exp 025)
- Reserve-ratio fee scaling — catastrophic (80 edge, exp 025)
- Hybrid contrarian+same spike — any same-direction component hurts (exp 025)
- DirContrarian + timing detection — dropping both fees after arb loses contrarian protection (407-449, exp 026)
- DirContrarian + stronger/weaker spikes — 2x spikes (381), 0.5x (463), pure linear (495) all worse (exp 026)
- DirContrarian + same-side reset to base — continuity matters, catastrophic (390, exp 026)
- DirContrarian + sticky hold (no same-side decay) — fee gets stuck high (389, exp 026)
- DirContrarian + spot-price change bonus — corrupted signal (133, exp 026)
- DirContrarian + reserve-ratio scaling — catastrophic (194, exp 026)
- DirContrarian + cumulative per-step trade ratio — no improvement (496.3, exp 026)
- DirContrarian + consecutive arb direction tracking — no improvement (494, exp 026)
- DirContrarian + direction-specific spike coefficients — no improvement (495.5, exp 026)
- DirContrarian + asymmetric base (bid≠ask base) — within noise (exp 026)
- DirContrarian + asymmetric decay rates — within noise (497.04, exp 026)
- DirContrarian + ultra-low same-side base (18 or 0 bps) — no improvement (exp 026)
- DirContrarian + size-based contrarian/symmetric switching — worse (exp 026)
- Spike caps on DirContrarian: Cap50→380, Cap100→426, Cap200→462, Cap500→489 — unbounded spikes essential (exp 027)
- Two-level base floors (sameBase≠oppBase): TL20_30→494, TL24_35→491, TL24_40→488 — all worse than single base=24 (exp 027)
- Higher opposite-side base floor (30-40 bps) — opposite must decay to 24 to attract retail (exp 027)
- Constant 36 bps (winner's avg fee) — 362 edge, no spike protection (exp 028)
- DC at higher bases (30-40): monotonically worse than 24 (exp 028)
- Size-dependent decay (fast after arb, slow after retail) — breaks arb protection, 472 edge (exp 028)
- Step-aware switching (spike on first trade, moderate after) — 409 edge (exp 028)
- Same-side floor at 30-36 bps — within noise or worse (exp 028)
- Same-side always 30 bps (match vanilla) — catastrophic (403), our advantage IS lower fee (exp 029)
- Reset same-side to base each trade (no memory) — catastrophic (390) (exp 029)
- Oscillating fee (toggle spike/no-spike) — 430 edge, loses arb protection half the time (exp 030)
- Inverse prediction (low after arb) — 346 edge, no protection for next arb (exp 030)
- EMA threat accumulator — 301 edge, inflates fees (exp 030)
- Delayed contrarian (buffer spike by 1 trade) — 345 edge, arb unprotected (exp 030)
- High default fee + drop after arb — 342 edge, loses retail between arbs (exp 030)
- Reverse decay (fee increases between arbs) — 343 edge, same problem (exp 030)
- Constant 28-75 bps: best is ~75-80 bps at 392 edge, NO dynamic mechanism (exp 031)
- Symmetric spike at base 30-36 with tuned params: 448-481, all worse than DC (exp 031)
- Same-side constant bump (2-4 bps above base) — within noise (exp 031)
- Proportional same-side spike (1/8 to 1/2 of opposite) — worse with higher fraction (exp 031)
- Pure quadratic spike in DC — 410, needs linear term (exp 032)
- Pure linear spike in DC — 485, needs quadratic (exp 032)
- Fast decay (2/3) in DC — 477, spike doesn't persist (exp 032)
- Geometric mean of X/Y trade ratios — 323, Y-only is correct (exp 032)
- Spike persistence via max(current, prev) — 493, too persistent (exp 032)

## Winner Analysis (Target: 525+)
- **Avg Fee**: 36.1 bps (vs our ~40+ weighted avg)
- **Avg Arb Volume**: 23.8K (similar to our ~24K)
- **Avg Retail Volume**: 77.3K (vs our ~63K, 22% more)
- Winner earns MORE per retail trade (36 vs 24 bps) while capturing MORE retail volume
- Higher consistent fee preserves reserves (k) better → routing advantage
- Simple base raise doesn't work — must achieve this through different mechanism

## Next Experiments
DirContrarian at 497 is robust. All single-variable enhancements exhausted. To reach 525+:

1. **Multi-contrarian**: What if we spike BOTH opposite AND keep a small delayed same-side spike (not immediate, but via a pending buffer that activates 2+ trades later)?
2. **Phase-adaptive contrarian**: Different contrarian behavior in early vs late simulation stages as reserves/price evolve.
3. **Retail-focused undercutting**: During "calm" periods (no arb for N steps), switch to ultra-aggressive retail capture mode (both fees at 20 bps). Switch back to contrarian on arb detection.
4. **Exploit order-within-step**: Router recalculates per retail order. After first retail trade sets contrarian, second retail trade sees updated fees. Can we exploit the per-order fee update within a step?
5. **Completely different mechanism**: Maybe the winner doesn't use spike/decay at all. Try: fee = constant * (1 + accumulated_state_variable).
6. **Study the edge decomposition**: Instrument the simulation to understand WHERE our edge comes from (per-trade breakdown: arb loss, retail income by direction).

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
- **Router**: Uses bid_fee for sell orders, ask_fee for buy orders (independently)
