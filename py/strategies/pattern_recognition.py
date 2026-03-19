"""
Pattern Recognition Strategies.

Exploit observable patterns in runner form data:
  - Course specialists (multiple wins at this track)
  - Distance specialists (optimum trip)
  - Going preferences (wins on similar ground)
  - Jockey-trainer combo with strong strike rate
  - Class drop (horse dropping down from higher class)
  - Fresh horses (optimal days since last run)
  - Weight-to-carry advantage (official rating vs weight carried)
"""
from dataclasses import dataclass

from .base import Strategy, StrategyParams, BetInstruction, runners_by_sp


@dataclass(frozen=True)
class PatternParams(StrategyParams):
    pattern_type: str             # see PATTERN_TYPES below
    min_score: float              # minimum scoring threshold to place bet
    stake_fraction: float
    min_odds: float
    max_odds: float
    race_type_filter: str         # "any" | "flat" | "nh"
    min_field_size: int
    # Pattern-specific params
    min_course_wins: int          # for course_specialist
    min_distance_wins: int        # for distance_specialist
    min_going_wins: int           # for going_preference
    days_since_run_min: int       # for freshness (0=any)
    days_since_run_max: int       # for freshness (999=any)
    class_drop_required: bool     # for class_drop


# Pattern type constants
PATTERN_TYPES = [
    "course_specialist",
    "distance_specialist",
    "going_preference",
    "class_drop",
    "fresh_horse",
    "composite",   # weighted sum of all factors
]


class PatternRecognition(Strategy):
    """
    Score runners using observable form patterns and bet on those exceeding
    min_score threshold. Composite mode weights all factors together.
    """

    # Composite weights (tunable via params in future)
    WEIGHTS = {
        "course":    0.25,
        "distance":  0.20,
        "going":     0.15,
        "freshness": 0.15,
        "class_drop": 0.15,
        "career_form": 0.10,
    }

    def __init__(self, params: PatternParams):
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

    def _score_runner(self, runner: dict, race: dict) -> float:
        """
        Score a runner 0.0–1.0 based on pattern type.
        """
        pt = self.p.pattern_type

        if pt == "course_specialist":
            wins = runner.get("course_wins", 0)
            return min(1.0, wins / max(1, self.p.min_course_wins))

        elif pt == "distance_specialist":
            wins = runner.get("distance_wins", 0)
            return min(1.0, wins / max(1, self.p.min_distance_wins))

        elif pt == "going_preference":
            wins = runner.get("going_wins", 0)
            return min(1.0, wins / max(1, self.p.min_going_wins))

        elif pt == "class_drop":
            if not self.p.class_drop_required:
                return 0.5
            race_class = race.get("class") or 5
            runner_or = runner.get("official_rating") or 80
            # Simple proxy: higher OR than race class implies dropping in class
            class_ceiling = {1: 110, 2: 100, 3: 90, 4: 80, 5: 70, 6: 60}
            ceiling = class_ceiling.get(race_class, 70)
            score = min(1.0, max(0.0, (runner_or - ceiling + 10) / 20))
            return score

        elif pt == "fresh_horse":
            days = runner.get("days_since_last_run")
            if days is None:
                return 0.3
            in_range = self.p.days_since_run_min <= days <= self.p.days_since_run_max
            return 1.0 if in_range else 0.0

        elif pt == "composite":
            return self._composite_score(runner, race)

        return 0.0

    def _composite_score(self, runner: dict, race: dict) -> float:
        """Weighted composite of all factors."""
        race_class = race.get("class") or 5
        class_ceiling = {1: 110, 2: 100, 3: 90, 4: 80, 5: 70, 6: 60}
        ceiling = class_ceiling.get(race_class, 70)
        or_val = runner.get("official_rating") or 70
        class_drop_score = min(1.0, max(0.0, (or_val - ceiling + 10) / 20))

        course = min(1.0, runner.get("course_wins", 0) / 2)
        distance = min(1.0, runner.get("distance_wins", 0) / 2)
        going = min(1.0, runner.get("going_wins", 0) / 2)

        days = runner.get("days_since_last_run") or 30
        freshness = 1.0 if 7 <= days <= 21 else (0.7 if 22 <= days <= 42 else 0.3)

        runs = max(1, runner.get("career_runs", 1))
        wins = runner.get("career_wins", 0)
        career_form = min(1.0, wins / runs * 3)

        return (
            self.WEIGHTS["course"] * course +
            self.WEIGHTS["distance"] * distance +
            self.WEIGHTS["going"] * going +
            self.WEIGHTS["freshness"] * freshness +
            self.WEIGHTS["class_drop"] * class_drop_score +
            self.WEIGHTS["career_form"] * career_form
        )

    def select_bets(
        self,
        race: dict,
        runners: list[dict],
        odds_history: list[dict],
    ) -> list[BetInstruction]:
        if self.should_skip_race(race):
            return []

        bets = []
        for runner in runners:
            sp = runner.get("sp")
            if not sp or sp < self.p.min_odds or sp > self.p.max_odds:
                continue

            score = self._score_runner(runner, race)
            if score < self.p.min_score:
                continue

            rationale = (
                f"Pattern[{self.p.pattern_type}] score={score:.3f} "
                f">= min={self.p.min_score} horse={runner.get('horse_name', '?')} "
                f"SP={sp}"
            )
            bets.append(BetInstruction(
                bet_type="win",
                runner_cloth_numbers=[runner["cloth_number"]],
                stake_fraction=self.p.stake_fraction,
                odds_estimate=sp,
                rationale=rationale,
            ))

        return bets
