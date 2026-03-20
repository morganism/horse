# Horse Racing Strategy — Task Rota

**Current Iteration**: 3
**Last Updated**: 2026-03-20
**Assigned Agent**: Claude Code (Sonnet 4.6)
**Rule**: Each iteration must add ≥3 new tasks. Completed one-off tasks are closed; recurring tasks stay in RECURRING.

---

## ✅ COMPLETED

| Iter | Task | Issue | Notes |
|------|------|-------|-------|
| 1 | Build Python simulation engine | — | 215 strategies, 30-day sim, PR #9 |
| 1 | Acknowledge STATUS issue | #2 | Running Sonnet 4.6 |
| 1 | Comment on PR strategy | #7 | Strategy documented |
| 1 | Review PR #9 | #10 | 6-point review, 3 bugs found |
| 2 | Fix stake_model bug (DutchingEnvelope) | #11 ✅ | ROI: 17.8%→20.2% |
| 2 | Fix exotic odds overestimation | #12 ✅ | ROI corrected to 77% |
| 2 | Score and rank all 215 strategies | #15 | Composite formula applied |
| 2 | Create 3 new strategy classes | #16 | FavouriteCover, HandicapExploit, TrainerGoing |
| 2 | Post iteration-2 status report | #17 | 275 strategies, 87.5% race coverage |
| 2 | Build Sinatra frontend | #24–#33 | Full app: auth, dashboard, races, strategies, correlations |
| 2 | Fix NilClass#presence routing errors | #23 ✅ PR #24 | All routes live |
| 2 | Fix simulation --db arg | #27 ✅ PR #29 | PythonRunner fixed |
| 2 | Fix ROTA encoding error | #28 ✅ PR #30 | UTF-8 read |
| 2 | Sortable table columns | #25 ✅ PR #33 | SVG sort indicators |
| 2 | Strategy class modal | #26 ✅ PR #33 | Bootstrap modal, 8 classes described |
| 2 | Fix dashboard top-strategy link | #35 ✅ PR #36 | 404 resolved |

---

## 🔄 RECURRING (every iteration)

| Issue | Task | Last Run |
|-------|------|---------|
| #15 | Score and rank all strategy variants (composite leaderboard) | Iter 2 ✓ |
| #16 | Analyse missed opportunities → create ≥3 new variants | Iter 2 ✓ |
| #17 | Update ROTA.md + post status report + assign ≥3 new tasks | Iter 3 ✓ |

---

## 📋 UPCOMING (iteration 3+)

| Priority | Issue | Task | Type |
|----------|-------|------|------|
| HIGH | #37 | **Race Calendar** — past/today/future in monthly grid, strategy P&L per race | Feature |
| HIGH | #38 | **Real-race prediction tracking** — `real_race_predictions` table, settle actuals | Feature |
| HIGH | #39 | **Today's races strategy matcher** — apply registry to live card, suggest bets | Feature |
| MED | #40 | Iter-3 strategy tasks: retire OddsMovement tail, recalibrate HandicapExploit, expand PatternRecognition | Optimisation |
| MED | #22 | Implement each-way settling in settler.py | Bug fix |
| MED | #20 | Extend simulation to 90 days (Bayesian maturity) | Analysis |
| MED | #18 | Retire bottom 24 OddsMovement variants, tune survivors | Optimisation |
| MED | #19 | Recalibrate HandicapExploit weight scoring | Bug fix |
| MED | #21 | Expand PatternRecognition to 40 variants | Feature |
| LOW | #13 | Composite index strategy_performance(strategy_id, sim_day) | Perf |
| LOW | #14 | Integration tests: generator, daily_loop, bayesian updater | Tests |

---

## 📊 STRATEGY LEADERBOARD (Iteration 2 — Day 30 snapshot)

### Composite Score = ROI×0.4 + Sharpe×0.25 + StrikeRate×0.15 + (1−DrawdownPct)×0.20

| Rank | Class | Variants | Avg ROI | Best ROI | Avg Sharpe | Status |
|------|-------|----------|---------|----------|------------|--------|
| 1 | DutchingEnvelope | 60 | +20.2% | +32.3% | 16.4 | ⬆️ PROMOTE |
| 2 | FavouriteCover *(new)* | 20 | +78.0% | +84.6% | ~4.2 | ⬆️ PROMOTE |
| 3 | ExoticPermutation | 60 | +77.1%† | +80.6%† | 2.97 | ✅ MONITOR |
| 4 | PatternRecognition | 5 | -8.1% | -3.7% | 0.1 | ⚠️ MONITOR |
| 5 | OddsMovement | 40 | -16.9% | +29.8% | -0.9 | 🔻 REVIEW |
| 6 | HandicapExploit *(new)* | 20 | -49.4% | -10.1% | -1.8 | ⚠️ MONITOR |
| 7 | BayesianCorrelation | 50 | -57.0% | -22.0% | -0.6 | 🔻 REVIEW |
| 8 | TrainerGoing *(new)* | 20 | n/a | n/a | n/a | 🆕 OBSERVE |

†Corrected with market_efficiency=0.70 (#12 fixed)

---

## 🗓️ ITERATION 3 — NEW TASKS

### Task #37: Race Calendar
Monthly calendar view at `/calendar`. Each day cell:
- **Past days with races**: badge showing race count; click → day detail with races + strategies ranked by P&L/unit
- **Today**: highlighted in gold; shows race card + strategy matcher with suggested bets
- **Future days**: greyed; click → placeholder (date/time only)

### Task #38: Real-race prediction tracking
New table `real_race_predictions`. When strategy matcher fires on today's races:
- Record: date, venue, time, horse, strategy, bet_type, stake_pct, predicted_position
- After results known: settle with actual_position + profit_loss
- Source flag `'real'` distinguishes from simulation bets
- Accuracy metrics feed back to strategy scoring

### Task #39: Today's races strategy matcher
`lib/strategy_matcher.rb` — Ruby implementation of top-4 strategies applied to a live race card:
- **FavouriteCover**: SP ≤ 3.0, check form figures
- **DutchingEnvelope**: compute dutch sum, flag if < 1.0
- **PatternRecognition**: parse form string for improving sequence
- **BayesianCorrelation**: look up trainer×going priors in hypothesis table
Returns ranked bet suggestions with stake % and confidence score.

---

## 🧬 STRATEGY LINEAGE (Iteration 2)

```
BaseStrategy
├── DutchingEnvelope (v1→v2) ── 60 variants
│   └── v2: stake_model bug fixed (#11) — level/proportional/kelly
├── ExoticPermutation (v1→v2) ── 60 variants
│   └── v2: market_efficiency param added (#12)
├── BayesianCorrelation (v1) ── 50 variants [REVIEW]
├── OddsMovement (v1) ── 40 variants [24 retirement candidates]
├── PatternRecognition (v1) ── 5 variants [under-sampled]
│   └── v2 planned: full 40-variant grid (#21)
├── FavouriteCover (v1) ── 20 variants [NEW — PROMOTE] ← iter-2
│   └── Parent: PatternRecognition(composite) × DutchingEnvelope
├── HandicapExploit (v1) ── 20 variants [NEW — MONITOR] ← iter-2
│   └── Parent: PatternRecognition(class_drop)
└── TrainerGoing (v1) ── 20 variants [NEW — OBSERVE] ← iter-2
    └── Parent: BayesianCorrelation(trainer_jockey)
```

---

## 📈 MISSED OPPORTUNITIES ANALYSIS (Iteration 2)

Post-fix coverage: **87.5%** of races had at least one winning bet (562/642)

Remaining 80 missed races breakdown:
- Short-price winners (SP ≤3): now partially covered by FavouriteCover ✓
- Handicap winners: HandicapExploit underperforming — recalibration needed (#19)
- Each-way opportunities uncaptured — settler doesn't handle correctly (#22)
- Trainer::going signal weak in first 30 days — needs 90-day run (#20)

---

## 🔁 ITERATION HISTORY

| Iter | Date | Strategies | Race Coverage | Key Change | Status |
|------|------|-----------|---------------|------------|--------|
| 1 | 2026-03-19 | 215 | 82.7% | Initial build | ✅ |
| 2 | 2026-03-19 | 275 | 87.5% | 3 new classes, 2 bug fixes, full Sinatra frontend | ✅ |
| 3 | 2026-03-20 | 275 | 87.5% | Calendar, real-race predictions, strategy matcher | 🔄 |

---

*Maintained by Claude Code. Auto-updated end of each iteration.*
