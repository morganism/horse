"""
Favourite Cover Strategy  (v1 — Iteration 2)
Lineage: new class, addresses missed opportunity analysis iteration-1

43 of 56 missed winning races (77%) had winners at SP ≤3.0.
This strategy captures those short-priced winners with disciplined
each-way and win betting, using strict bankroll management to stay
profitable despite low odds.

Key insight: favourites win ~30% of flat races and ~25% of NH races.
At SP 2.0 the break-even strike rate is 50% — so flat-win on all favs
loses. BUT:
  a) Each-way at 1/4 odds on a 2.0 fav gives place odds of 1.25 —
     break-even strike for a place is ~80%, achievable in large fields
  b) Selective favourites (course+distance+going record) have
     materially higher strike rates than the field average

Variant parent: PatternRecognition (composite scoring) × DutchingEnvelope
"""
from dataclasses import dataclass
from .base import Strategy, StrategyParams, BetInstruction, runners_by_sp


@dataclass(frozen=True)
class FavCoverParams(StrategyParams):
    bet_type: str           # "win" | "each_way" | "dutch_top2"
    max_sp: float           # only back horses up to this SP (e.g. 3.0)
    min_sp: float           # avoid odds-on below this (e.g. 1.4)
    min_course_wins: int    # course specialist filter
    min_field_size: int     # only in races with enough runners for place terms
    race_type_filter: str   # "any" | "flat" | "nh"
    stake_fraction: float
    require_course_win: bool  # True = only bet course specialists


class FavouriteCover(Strategy):
    """
    Targets short-priced (≤3.0 SP) runners with course/distance credentials.
    Plugs the biggest gap in the iteration-1 strategy coverage.
    """

    def __init__(self, params: FavCoverParams):
        super().__init__(params)
        self.p = params

    def should_skip_race(self, race: dict) -> bool:
        if self.p.race_type_filter == "flat" and race.get("race_type") != "flat":
            return True
        if self.p.race_type_filter == "nh" and race.get("race_type") == "flat":
            return True
        if race.get("runner_count", 0) < self.p.min_field_size:
            return True
        return False

    def select_bets(
        self,
        race: dict,
        runners: list[dict],
        odds_history: list[dict],
    ) -> list[BetInstruction]:
        if self.should_skip_race(race):
            return []

        candidates = [
            r for r in runners
            if r.get("sp") and self.p.min_sp <= r["sp"] <= self.p.max_sp
        ]

        if self.p.require_course_win:
            candidates = [r for r in candidates if r.get("course_wins", 0) >= self.p.min_course_wins]

        if not candidates:
            return []

        bets = []

        if self.p.bet_type == "dutch_top2":
            # Dutch the top 2 fancies (1st and 2nd favourite in the SP band)
            top2 = sorted(candidates, key=lambda r: r["sp"])[:2]
            if len(top2) < 2:
                return []
            from .base import dutch_stakes, dutch_return
            odds_list = [r["sp"] for r in top2]
            total_inv = sum(1.0 / o for o in odds_list)
            if total_inv >= 1.0:
                return []  # overround — not profitable
            combined = dutch_return(odds_list, self.p.stake_fraction) / self.p.stake_fraction
            bets.append(BetInstruction(
                bet_type="dutch",
                runner_cloth_numbers=[r["cloth_number"] for r in top2],
                stake_fraction=self.p.stake_fraction,
                odds_estimate=combined,
                rationale=f"FavCover dutch_top2 SP={[r['sp'] for r in top2]}",
            ))
        else:
            for runner in sorted(candidates, key=lambda r: r["sp"])[:1]:
                sp = runner["sp"]
                if self.p.bet_type == "each_way":
                    # Place portion at 1/4 odds (standard UK terms for 8+ runner races)
                    place_odds = 1.0 + (sp - 1.0) * 0.25
                    bets.append(BetInstruction(
                        bet_type="place",
                        runner_cloth_numbers=[runner["cloth_number"]],
                        stake_fraction=self.p.stake_fraction,
                        odds_estimate=place_odds,
                        rationale=f"FavCover each_way place SP={sp:.1f} course_wins={runner.get('course_wins',0)}",
                    ))
                bets.append(BetInstruction(
                    bet_type="win",
                    runner_cloth_numbers=[runner["cloth_number"]],
                    stake_fraction=self.p.stake_fraction,
                    odds_estimate=sp,
                    rationale=f"FavCover win SP={sp:.1f} course_wins={runner.get('course_wins',0)}",
                ))

        return bets
