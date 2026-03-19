"""
Trainer-Going Correlation Strategy  (v1 — Iteration 2)
Lineage: BayesianCorrelation parent, new hypothesis_type

Observation: BayesianCorrelation uses trainer::jockey combos but misses
trainer::going correlations. Some trainers (esp. NH trainers) have
dramatically different strike rates on different going types.
Example: a jumps trainer who prepares horses specifically for soft/heavy
ground will have meaningfully higher win rates when those conditions occur.

This strategy reads the hypothesis table for trainer::going combos
(populated by an extended BayesianUpdater) AND trainer::jockey combos
simultaneously, betting when BOTH signals align.
"""
from dataclasses import dataclass
import sqlite3
from .base import Strategy, StrategyParams, BetInstruction


@dataclass(frozen=True)
class TrainerGoingParams(StrategyParams):
    min_evidence: int              # minimum observations for hypothesis
    trainer_going_threshold: float # min posterior for trainer::going combo
    trainer_jockey_threshold: float # min posterior for trainer::jockey (0=ignore)
    require_both: bool             # True = both signals needed, False = either
    min_sp: float
    max_sp: float
    stake_fraction: float
    race_type_filter: str


class TrainerGoing(Strategy):
    """
    Dual-signal Bayesian: trainer::going AND optionally trainer::jockey.
    Addresses the gap identified in iteration-1 missed opportunity analysis.
    """

    def __init__(self, params: TrainerGoingParams, db_path: str = ""):
        super().__init__(params)
        self.p = params
        self.db_path = db_path
        self._cache: dict = {}

    def _get_posterior(self, hypothesis_type: str, subject_key: str) -> float:
        cache_key = f"{hypothesis_type}::{subject_key}"
        if cache_key in self._cache:
            return self._cache[cache_key]
        if not self.db_path:
            return 0.0
        try:
            conn = sqlite3.connect(self.db_path)
            row = conn.execute(
                """SELECT alpha, beta_param, evidence_count FROM hypothesis
                   WHERE hypothesis_type=? AND subject_key=?""",
                (hypothesis_type, subject_key),
            ).fetchone()
            conn.close()
        except Exception:
            return 0.0
        if not row or row[2] < self.p.min_evidence:
            self._cache[cache_key] = 0.0
            return 0.0
        posterior = row[0] / (row[0] + row[1])
        self._cache[cache_key] = posterior
        return posterior

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

        self._cache = {}  # reset per race
        going = race.get("going", "")
        bets = []

        for runner in runners:
            sp = runner.get("sp")
            if not sp or sp < self.p.min_sp or sp > self.p.max_sp:
                continue

            trainer = runner.get("trainer") or ""
            jockey = runner.get("jockey") or ""
            if not trainer:
                continue

            # Signal 1: trainer::going
            tg_key = f"{trainer}::{going}"
            tg_post = self._get_posterior("trainer_jockey", tg_key)  # reuse table
            tg_signal = tg_post >= self.p.trainer_going_threshold

            # Signal 2: trainer::jockey (optional)
            tj_signal = True
            if self.p.trainer_jockey_threshold > 0 and jockey:
                tj_key = f"{trainer}::{jockey}"
                tj_post = self._get_posterior("trainer_jockey", tj_key)
                tj_signal = tj_post >= self.p.trainer_jockey_threshold

            if self.p.require_both:
                fires = tg_signal and tj_signal
            else:
                fires = tg_signal or tj_signal

            if not fires:
                continue

            bets.append(BetInstruction(
                bet_type="win",
                runner_cloth_numbers=[runner["cloth_number"]],
                stake_fraction=self.p.stake_fraction,
                odds_estimate=sp,
                rationale=(
                    f"TrainerGoing trainer={trainer} going={going} "
                    f"tg_post={tg_post:.3f} tj_post={self._get_posterior('trainer_jockey', f'{trainer}::{jockey}'):.3f}"
                ),
            ))

        return bets
