"""
Bayesian Correlation Strategies.

Exploit statistical patterns learned from accumulated race history:
  - P(win | trainer-jockey combo) – strong partnerships
  - P(win | weight drop ≥ N lbs vs last run)
  - P(win | horse always finishes behind rival X = "beta horse" dynamic)
  - P(win | course specialist + good going)

Each strategy reads the hypothesis table (updated daily by BayesianUpdater)
and places bets only when posterior confidence exceeds threshold.
"""
from dataclasses import dataclass
import sqlite3

from .base import Strategy, StrategyParams, BetInstruction, runners_by_sp


@dataclass(frozen=True)
class BayesianParams(StrategyParams):
    hypothesis_type: str          # "trainer_jockey"|"weight_drop"|"h2h"|"course_specialist"
    min_evidence: int             # minimum data points before trusting hypothesis
    confidence_threshold: float   # posterior mean must exceed this to bet
    stake_fraction: float         # fraction of bankroll per qualifying bet
    max_odds: float               # don't bet beyond these odds (avoid lottery tickets)
    min_odds: float               # avoid odds-on
    race_type_filter: str         # "any" | "flat" | "nh"


class BayesianCorrelation(Strategy):
    """
    Reads live Bayesian hypotheses from DB and bets when posterior confidence
    meets threshold. The hypothesis table is updated after each day's racing
    by BayesianUpdater.

    This strategy needs a db_path to query the hypothesis table at selection time.
    """

    def __init__(self, params: BayesianParams, db_path: str = ""):
        super().__init__(params)
        self.p = params
        self.db_path = db_path
        self._hypothesis_cache: dict = {}

    def _get_posterior(self, subject_key: str) -> float | None:
        """
        Retrieve Beta posterior mean from hypothesis table.
        Returns None if insufficient evidence.
        """
        if subject_key in self._hypothesis_cache:
            return self._hypothesis_cache[subject_key]

        if not self.db_path:
            return None

        try:
            conn = sqlite3.connect(self.db_path)
            cur = conn.execute(
                """SELECT alpha, beta_param, evidence_count FROM hypothesis
                   WHERE hypothesis_type=? AND subject_key=?""",
                (self.p.hypothesis_type, subject_key),
            )
            row = cur.fetchone()
            conn.close()
        except Exception:
            return None

        if not row:
            return None

        alpha, beta_param, evidence_count = row
        if evidence_count < self.p.min_evidence:
            return None

        posterior_mean = alpha / (alpha + beta_param)
        self._hypothesis_cache[subject_key] = posterior_mean
        return posterior_mean

    def _make_subject_key(self, runner: dict, race: dict) -> str | None:
        """Build the hypothesis lookup key for a runner."""
        ht = self.p.hypothesis_type

        if ht == "trainer_jockey":
            trainer = runner.get("trainer") or ""
            jockey = runner.get("jockey") or ""
            if not trainer or not jockey:
                return None
            return f"{trainer}::{jockey}"

        elif ht == "weight_drop":
            # Key includes horse + going type
            horse_id = runner.get("horse_id")
            going = race.get("going", "")
            return f"horse_{horse_id}::going_{going}"

        elif ht == "h2h":
            # Uses horse_relationships — subject key is horse_id
            return f"horse_{runner.get('horse_id')}"

        elif ht == "course_specialist":
            horse_id = runner.get("horse_id")
            venue_id = race.get("venue_id")
            return f"horse_{horse_id}::venue_{venue_id}"

        return None

    def should_skip_race(self, race: dict) -> bool:
        if self.p.race_type_filter == "flat" and race.get("race_type") != "flat":
            return True
        if self.p.race_type_filter == "nh" and race.get("race_type") == "flat":
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

        # Invalidate cache each race call
        self._hypothesis_cache = {}

        bets = []
        for runner in runners:
            sp = runner.get("sp")
            if not sp or sp < self.p.min_odds or sp > self.p.max_odds:
                continue

            subject_key = self._make_subject_key(runner, race)
            if not subject_key:
                continue

            posterior = self._get_posterior(subject_key)
            if posterior is None or posterior < self.p.confidence_threshold:
                continue

            rationale = (
                f"Bayesian[{self.p.hypothesis_type}] key={subject_key} "
                f"posterior={posterior:.3f} >= threshold={self.p.confidence_threshold}"
            )
            bets.append(BetInstruction(
                bet_type="win",
                runner_cloth_numbers=[runner["cloth_number"]],
                stake_fraction=self.p.stake_fraction,
                odds_estimate=sp,
                rationale=rationale,
            ))

        return bets
