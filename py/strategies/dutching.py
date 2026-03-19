"""
Dutching Envelope Strategy.

Distributes stake across multiple runners so any winner returns the same profit.
The "envelope" excludes outlier horses (very long odds) to tighten the market.
"""
from dataclasses import dataclass
from itertools import combinations
from typing import Optional

from .base import Strategy, StrategyParams, BetInstruction, dutch_stakes, dutch_return


@dataclass(frozen=True)
class DutchingParams(StrategyParams):
    max_odds_include: float       # exclude horses above this SP (e.g. 33.0)
    target_profit_margin: float   # 0.05 = aim for 5% above breakeven
    min_runners_dutch: int        # minimum horses to include in Dutch
    max_runners_dutch: int        # maximum horses to include
    stake_model: str              # "level" | "proportional" | "kelly"
    race_type_filter: str         # "any" | "flat" | "nh" (non-flat)
    min_field_size: int           # don't enter races with fewer than this


class DutchingEnvelope(Strategy):
    """
    Find races where the sum of inverse odds (excluding outliers) approaches 1.0,
    then Dutch the field with stakes designed to return target_profit_margin.

    Variants with race_type_filter="nh" exploit the observation that non-flat
    races have higher upset rates, so the Dutch envelope captures more value.
    """

    def __init__(self, params: DutchingParams):
        super().__init__(params)
        self.p = params

    def should_skip_race(self, race: dict) -> bool:
        if self.p.race_type_filter == "flat" and race["race_type"] != "flat":
            return True
        if self.p.race_type_filter == "nh" and race["race_type"] == "flat":
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

        # Filter to runners within odds envelope
        eligible = [
            r for r in runners
            if r.get("sp") and r["sp"] <= self.p.max_odds_include
        ]
        if len(eligible) < self.p.min_runners_dutch:
            return []

        # Cap at max_runners_dutch (take shortest odds)
        eligible = sorted(eligible, key=lambda r: r["sp"])[:self.p.max_runners_dutch]

        odds_list = [r["sp"] for r in eligible]
        total_inv = sum(1.0 / o for o in odds_list)

        # Dutch is only +EV when total_inv < 1 / (1 + target_profit_margin)
        threshold = 1.0 / (1.0 + self.p.target_profit_margin)
        if total_inv >= threshold:
            # Still place if close (within 5% of threshold) – optimistic variant
            if total_inv >= threshold * 1.05:
                return []

        # Calculate a unit budget (stake_fraction * bankroll applied by runner)
        # Return stake fractions; actual £ calculated by simulation runner
        budget_fraction = 0.03  # 3% of strategy bankroll per Dutch bet
        stakes = dutch_stakes(odds_list, budget_fraction)
        expected_return = dutch_return(odds_list, budget_fraction)
        combined_expected_odds = expected_return / budget_fraction

        cloth_numbers = [r["cloth_number"] for r in eligible]
        rationale = (
            f"Dutch {len(eligible)} runners: {[f'{c}@{o}' for c,o in zip(cloth_numbers, odds_list)]} "
            f"total_inv={total_inv:.3f} threshold={threshold:.3f}"
        )

        return [
            BetInstruction(
                bet_type="dutch",
                runner_cloth_numbers=cloth_numbers,
                stake_fraction=budget_fraction,
                odds_estimate=combined_expected_odds,
                rationale=rationale,
            )
        ]
