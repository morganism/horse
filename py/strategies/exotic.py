"""
Exotic Permutation Strategies.

Exacta: pick 1st and 2nd in correct order.
Trifecta: pick 1st, 2nd, 3rd in correct order.
Box: cover all permutations of selected horses.

Strategies here focus on identified situations where exotics offer value:
  - Non-flat races with large fields (favourites less dominant)
  - Races where 3rd+ favourite has value (odds 3/1 to 8/1 sweet spot)
  - Pure combinatorial: top-N box bets
"""
from dataclasses import dataclass, field
from itertools import permutations

from .base import (
    Strategy, StrategyParams, BetInstruction,
    runners_by_sp, exacta_odds, trifecta_odds,
)


@dataclass(frozen=True)
class ExoticParams(StrategyParams):
    bet_type: str               # "exacta" | "trifecta" | "both"
    selection_method: str       # "top_n_odds" | "sweet_spot_odds" | "non_fav_focus"
    max_runners_in_combo: int   # how many horses to box (e.g. 4 = C(4,2)=6 exactas)
    min_field_size: int         # minimum runners in race
    race_type_filter: str       # "any" | "flat" | "nh"
    min_odds_include: float     # only include runners with odds >= this
    max_odds_include: float     # only include runners with odds <= this
    stake_per_combo: float      # fixed stake per combination (fraction of bankroll)
    class_max: int              # only enter races of this class or lower (higher = lower quality)
    market_efficiency: float = 0.70  # bookmaker payout as fraction of theoretical — fixes #12


class ExoticPermutation(Strategy):
    """
    Places exacta/trifecta box bets on selected combinations of runners.

    selection_method:
      top_n_odds:       Take the N shortest-priced runners
      sweet_spot_odds:  Take runners in a specific odds band (min_odds to max_odds)
      non_fav_focus:    Take the 2nd-5th favourites (exclude market leader)
    """

    def __init__(self, params: ExoticParams):
        super().__init__(params)
        self.p = params

    def should_skip_race(self, race: dict) -> bool:
        if self.p.race_type_filter == "flat" and race["race_type"] != "flat":
            return True
        if self.p.race_type_filter == "nh" and race["race_type"] == "flat":
            return True
        if race.get("runner_count", 0) < self.p.min_field_size:
            return True
        if self.p.class_max > 0 and (race.get("class") or 99) > self.p.class_max:
            return True
        return False

    def _select_runners(self, runners: list[dict]) -> list[dict]:
        by_odds = runners_by_sp(runners)
        valid = [r for r in by_odds if r.get("sp") and
                 self.p.min_odds_include <= r["sp"] <= self.p.max_odds_include]

        if self.p.selection_method == "top_n_odds":
            # Top-N by shortest SP (ignoring the odds filter for this one)
            by_odds_all = runners_by_sp(runners)
            return by_odds_all[:self.p.max_runners_in_combo]

        elif self.p.selection_method == "sweet_spot_odds":
            return valid[:self.p.max_runners_in_combo]

        elif self.p.selection_method == "non_fav_focus":
            # Skip the market leader (rank 1), take next N
            non_favs = [r for r in by_odds if r.get("favourite_rank", 99) > 1]
            sweet = [r for r in non_favs if r.get("sp") and
                     self.p.min_odds_include <= r["sp"] <= self.p.max_odds_include]
            return sweet[:self.p.max_runners_in_combo]

        return valid[:self.p.max_runners_in_combo]

    def select_bets(
        self,
        race: dict,
        runners: list[dict],
        odds_history: list[dict],
    ) -> list[BetInstruction]:
        if self.should_skip_race(race):
            return []

        selected = self._select_runners(runners)

        bet_instructions = []

        if self.p.bet_type in ("exacta", "both"):
            if len(selected) >= 2:
                for r1, r2 in permutations(selected, 2):
                    odds = exacta_odds(r1["sp"], r2["sp"])
                    rationale = (
                        f"Exacta {r1['cloth_number']}@{r1['sp']:.1f} → "
                        f"{r2['cloth_number']}@{r2['sp']:.1f} "
                        f"[{self.p.selection_method}]"
                    )
                    bet_instructions.append(BetInstruction(
                        bet_type="exacta",
                        runner_cloth_numbers=[r1["cloth_number"], r2["cloth_number"]],
                        stake_fraction=self.p.stake_per_combo,
                        odds_estimate=odds * self.p.market_efficiency,
                        rationale=rationale,
                    ))

        if self.p.bet_type in ("trifecta", "both"):
            if len(selected) >= 3:
                for r1, r2, r3 in permutations(selected, 3):
                    odds = trifecta_odds(r1["sp"], r2["sp"], r3["sp"])
                    rationale = (
                        f"Trifecta {r1['cloth_number']}@{r1['sp']:.1f} → "
                        f"{r2['cloth_number']}@{r2['sp']:.1f} → "
                        f"{r3['cloth_number']}@{r3['sp']:.1f} "
                        f"[{self.p.selection_method}]"
                    )
                    bet_instructions.append(BetInstruction(
                        bet_type="trifecta",
                        runner_cloth_numbers=[
                            r1["cloth_number"], r2["cloth_number"], r3["cloth_number"]
                        ],
                        stake_fraction=self.p.stake_per_combo,
                        odds_estimate=odds * self.p.market_efficiency,
                        rationale=rationale,
                    ))

        return bet_instructions
