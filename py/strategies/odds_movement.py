"""
Odds Movement Strategies.

Exploit price movements in the betting market:
  - "Follow the money": back horses that shorten significantly (market support)
  - "Drift fader": horses drifting more than N% often face problems (lay signal,
    but we can't lay in this sim so we avoid them instead)
  - "Non-favourite opens at X, shortens to Y": value identification
  - "Morning line vs SP arbitrage window": if opening odds differ from SP pattern
"""
from dataclasses import dataclass

from .base import Strategy, StrategyParams, BetInstruction, runners_by_sp


@dataclass(frozen=True)
class OddsMovementParams(StrategyParams):
    movement_type: str            # "shorten" | "drift_avoid" | "reversal"
    min_movement_pct: float       # minimum % price change to trigger (e.g. 15.0)
    observation_window_hours: float  # look back this many hours in odds_history
    min_sp: float                 # avoid odds-on (< 2.0 = evens+)
    max_sp: float                 # don't bet beyond this SP
    stake_fraction: float
    race_type_filter: str         # "any" | "flat" | "nh"
    min_field_size: int
    # For reversal strategy: horse drifted then came back in
    reversal_drift_pct: float     # initial drift % before reversal counts


class OddsMovement(Strategy):
    """
    Three flavours:

    shorten:     Horse's odds shortened >= min_movement_pct from opening.
                 Signals professional money and inside knowledge.

    drift_avoid: Skip races where the candidate runner drifted >= min_movement_pct.
                 Instead, back the horse that shortens most in the field.

    reversal:    Horse drifted >= reversal_drift_pct then came back to within
                 5% of opening price. Classic "steam then bounce" pattern.
    """

    def __init__(self, params: OddsMovementParams):
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

    def _movement_for_runner(
        self,
        runner_id: int,
        odds_history: list[dict],
    ) -> dict:
        """
        Returns {'opening': float, 'closing': float, 'max': float, 'min': float, 'pct_change': float}
        """
        relevant = [
            h for h in odds_history
            if h.get("runner_id") == runner_id
            and h.get("hours_before", 0) <= self.p.observation_window_hours
        ]
        if not relevant:
            return {}

        sorted_h = sorted(relevant, key=lambda h: h["hours_before"], reverse=True)
        opening = sorted_h[0]["odds"]
        closing = sorted_h[-1]["odds"]
        all_odds = [h["odds"] for h in sorted_h]
        pct_change = ((closing - opening) / opening) * 100  # negative = shortening

        return {
            "opening": opening,
            "closing": closing,
            "max": max(all_odds),
            "min": min(all_odds),
            "pct_change": pct_change,  # negative = shortened
        }

    def select_bets(
        self,
        race: dict,
        runners: list[dict],
        odds_history: list[dict],
    ) -> list[BetInstruction]:
        if self.should_skip_race(race):
            return []

        bets = []

        if self.p.movement_type == "shorten":
            for runner in runners:
                sp = runner.get("sp")
                if not sp or sp < self.p.min_sp or sp > self.p.max_sp:
                    continue
                mv = self._movement_for_runner(runner["id"], odds_history)
                if not mv:
                    continue
                pct = mv["pct_change"]  # negative = shorten
                if pct <= -self.p.min_movement_pct:
                    rationale = (
                        f"Shortener: opened {mv['opening']:.1f} → SP {sp:.1f} "
                        f"({pct:.1f}% move) >= -{self.p.min_movement_pct}%"
                    )
                    bets.append(BetInstruction(
                        bet_type="win",
                        runner_cloth_numbers=[runner["cloth_number"]],
                        stake_fraction=self.p.stake_fraction,
                        odds_estimate=sp,
                        rationale=rationale,
                    ))

        elif self.p.movement_type == "drift_avoid":
            # Find biggest shortener in the field after excluding drifters
            candidates = []
            for runner in runners:
                sp = runner.get("sp")
                if not sp or sp < self.p.min_sp or sp > self.p.max_sp:
                    continue
                mv = self._movement_for_runner(runner["id"], odds_history)
                if not mv:
                    continue
                if mv["pct_change"] >= self.p.min_movement_pct:
                    continue  # drifted - skip
                candidates.append((runner, mv["pct_change"]))

            if candidates:
                # Pick the one that shortened most
                candidates.sort(key=lambda x: x[1])
                runner, pct = candidates[0]
                sp = runner.get("sp")
                if sp:
                    bets.append(BetInstruction(
                        bet_type="win",
                        runner_cloth_numbers=[runner["cloth_number"]],
                        stake_fraction=self.p.stake_fraction,
                        odds_estimate=sp,
                        rationale=f"Best shortener after excluding drifters: {pct:.1f}%",
                    ))

        elif self.p.movement_type == "reversal":
            for runner in runners:
                sp = runner.get("sp")
                if not sp or sp < self.p.min_sp or sp > self.p.max_sp:
                    continue
                mv = self._movement_for_runner(runner["id"], odds_history)
                if not mv:
                    continue
                # Check: drifted >= reversal_drift_pct then came back
                drift = ((mv["max"] - mv["opening"]) / mv["opening"]) * 100
                recovery = ((mv["max"] - mv["closing"]) / mv["max"]) * 100
                if (drift >= self.p.reversal_drift_pct and recovery >= 10.0):
                    rationale = (
                        f"Reversal: drifted +{drift:.1f}% to {mv['max']:.1f} "
                        f"then recovered {recovery:.1f}% to SP {sp:.1f}"
                    )
                    bets.append(BetInstruction(
                        bet_type="win",
                        runner_cloth_numbers=[runner["cloth_number"]],
                        stake_fraction=self.p.stake_fraction,
                        odds_estimate=sp,
                        rationale=rationale,
                    ))

        return bets
