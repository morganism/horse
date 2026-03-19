"""
Abstract base class for all betting strategies.

A Strategy receives enriched race + runner data and returns bet instructions.
It does NOT manage its own bankroll - the simulation runner handles that.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, asdict
from typing import Optional
import json


@dataclass(frozen=True)
class StrategyParams:
    """Base parameter class. All strategy params must subclass this."""

    def to_json(self) -> str:
        return json.dumps(asdict(self))

    def to_slug(self) -> str:
        """Short deterministic slug for variant naming."""
        parts = []
        for k, v in asdict(self).items():
            key_abbr = "".join(w[0] for w in k.split("_"))[:3]
            if isinstance(v, list):
                val_str = "_".join(str(x) for x in v)[:8] if v else "any"
            elif isinstance(v, float):
                val_str = f"{v:.2f}".rstrip("0").rstrip(".")
            else:
                val_str = str(v)
            parts.append(f"{key_abbr}{val_str}")
        return "_".join(parts)[:60]


@dataclass(frozen=True)
class BetInstruction:
    """A single bet instruction returned by a strategy."""
    bet_type: str           # "win" | "place" | "exacta" | "trifecta" | "dutch"
    runner_cloth_numbers: list  # ordered list (position matters for exacta/trifecta)
    stake_fraction: float   # fraction of per-race budget to stake
    odds_estimate: float    # expected combined odds (decimal)
    rationale: str          # human-readable reason

    def potential_return(self, stake: float) -> float:
        return stake * self.odds_estimate


class Strategy(ABC):
    """
    Abstract strategy base. Subclass and implement:
      - select_bets(race, runners, odds_history) -> list[BetInstruction]
      - should_skip_race(race) -> bool
    """
    name: str  # set by registry after instantiation

    def __init__(self, params: StrategyParams):
        self.params = params
        self.name = f"{self.__class__.__name__}_{params.to_slug()}"

    @abstractmethod
    def select_bets(
        self,
        race: dict,
        runners: list[dict],
        odds_history: list[dict],
    ) -> list[BetInstruction]:
        """
        Given race metadata, list of enriched runner dicts, and odds history,
        return bet instructions. Return empty list to skip this race.

        Runner dict keys (from DB):
          id, race_id, horse_id, horse_name, jockey, trainer, cloth_number,
          weight_lbs, official_rating, days_since_last_run, career_wins,
          career_runs, course_wins, distance_wins, going_wins,
          morning_price, sp, favourite_rank

        Odds history keys:
          runner_id, odds, movement, hours_before
        """
        ...

    @abstractmethod
    def should_skip_race(self, race: dict) -> bool:
        """Return True if this race type is outside this strategy's scope."""
        ...

    def to_registry_row(self) -> dict:
        return {
            "strategy_class": self.__class__.__name__,
            "variant_name": self.name,
            "params_json": self.params.to_json(),
        }

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.params})"


# ─── Utility helpers used across strategy classes ───────────────────────────

def runners_by_sp(runners: list[dict]) -> list[dict]:
    """Sort runners ascending by SP (favourite first)."""
    return sorted(runners, key=lambda r: r.get("sp") or 999)


def decimal_to_fractional(d: float) -> str:
    """Quick display helper: 4.0 → '3/1'."""
    n = round(d - 1, 2)
    if n == int(n):
        return f"{int(n)}/1"
    # crude fraction
    from fractions import Fraction
    f = Fraction(n).limit_denominator(20)
    return f"{f.numerator}/{f.denominator}"


def dutch_stakes(runner_odds: list[float], total_budget: float) -> list[float]:
    """
    Calculate per-runner stakes for a Dutch bet so all winners return equally.
    Returns list of stakes in same order as runner_odds.
    Only profitable when sum(1/odds) < 1.
    """
    inv = [1.0 / o for o in runner_odds]
    total_inv = sum(inv)
    return [(i / total_inv) * total_budget for i in inv]


def dutch_return(runner_odds: list[float], total_budget: float) -> float:
    """Expected return from winning any runner in a Dutch bet."""
    inv_sum = sum(1.0 / o for o in runner_odds)
    return total_budget / inv_sum


def exacta_odds(odds_1: float, odds_2: float) -> float:
    """Approximate combined odds for an exacta (p1 * p2 inverted)."""
    p1 = 1.0 / odds_1
    p2 = 1.0 / odds_2
    return 1.0 / (p1 * p2)


def trifecta_odds(odds_1: float, odds_2: float, odds_3: float) -> float:
    """Approximate combined odds for a trifecta."""
    p1 = 1.0 / odds_1
    p2 = 1.0 / odds_2
    p3 = 1.0 / odds_3
    return 1.0 / (p1 * p2 * p3)
