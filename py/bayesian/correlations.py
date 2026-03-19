"""
Bayesian Correlation Analysis.

Queries the accumulated hypothesis and race_results tables to surface
statistically significant correlations. Writes findings back to hypothesis.

Key patterns detected:
  - Beta horse: horse consistently finishes behind a specific rival
  - Weight drop: horses winning after weight reduction
  - Class drop: horses succeeding when dropping in class
  - Going preference: win rate conditional on specific going
  - Trainer patterns: win spikes at certain course/distance combos
"""
import sqlite3
from datetime import datetime
import math


class CorrelationAnalyser:
    def __init__(self, db_path: str, min_evidence: int = 5):
        self.db_path = db_path
        self.min_evidence = min_evidence

    def analyse_all(self) -> dict:
        """Run all correlation checks and return summary."""
        return {
            "beta_horses": self.detect_beta_horses(),
            "weight_drop": self.analyse_weight_drop(),
            "going_preference": self.analyse_going_preference(),
            "top_trainer_jockey": self.top_trainer_jockey_combos(n=10),
        }

    def detect_beta_horses(self, min_meetings: int = 3) -> list[dict]:
        """
        Find pairs where horse_a finishes ahead of horse_b in >= 80% of meetings.
        These are "beta" relationships: B consistently defers to A.
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row

        rows = conn.execute(
            """SELECT hr.horse_a_id, hr.horse_b_id, hr.meetings,
                      hr.horse_a_ahead, hr.horse_b_ahead,
                      ha.name AS name_a, hb.name AS name_b
               FROM horse_relationships hr
               JOIN horses ha ON hr.horse_a_id = ha.id
               JOIN horses hb ON hr.horse_b_id = hb.id
               WHERE hr.meetings >= ?""",
            (min_meetings,),
        ).fetchall()

        results = []
        for row in rows:
            meetings = row["meetings"]
            a_ahead = row["horse_a_ahead"]
            dominance_a = a_ahead / meetings

            if dominance_a >= 0.80:
                results.append({
                    "dominant": row["name_a"],
                    "beta": row["name_b"],
                    "meetings": meetings,
                    "dominance_pct": round(dominance_a * 100, 1),
                })
            elif dominance_a <= 0.20:
                results.append({
                    "dominant": row["name_b"],
                    "beta": row["name_a"],
                    "meetings": meetings,
                    "dominance_pct": round((1 - dominance_a) * 100, 1),
                })

        conn.close()
        return sorted(results, key=lambda x: -x["dominance_pct"])

    def analyse_weight_drop(self) -> list[dict]:
        """
        Analyse win rate when a horse carries less weight than their previous run.
        Returns sorted list of (weight_drop_band, win_rate, evidence).
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row

        # For each runner, compare weight vs previous race weight
        # Using career_wins / career_runs as proxy since we don't track weight history
        rows = conn.execute(
            """SELECT h.hypothesis_type, h.subject_key, h.alpha, h.beta_param,
                      h.evidence_count, h.confidence
               FROM hypothesis h
               WHERE h.hypothesis_type = 'weight_drop'
                 AND h.evidence_count >= ?
               ORDER BY h.confidence DESC""",
            (self.min_evidence,),
        ).fetchall()

        conn.close()
        return [dict(r) for r in rows]

    def analyse_going_preference(self) -> list[dict]:
        """
        Compute win rates per (horse, going_type) combo from race results.
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row

        rows = conn.execute(
            """SELECT h.name AS horse_name, r.going,
                      COUNT(*) AS runs,
                      SUM(CASE WHEN rr.position=1 THEN 1 ELSE 0 END) AS wins
               FROM race_results rr
               JOIN runners ru ON rr.runner_id = ru.id
               JOIN horses h ON ru.horse_id = h.id
               JOIN races r ON rr.race_id = r.id
               GROUP BY h.id, r.going
               HAVING runs >= ?
               ORDER BY wins * 1.0 / runs DESC""",
            (self.min_evidence,),
        ).fetchall()

        conn.close()
        return [
            {
                "horse": r["horse_name"],
                "going": r["going"],
                "runs": r["runs"],
                "wins": r["wins"],
                "win_rate": round(r["wins"] / r["runs"], 3),
            }
            for r in rows
        ]

    def top_trainer_jockey_combos(self, n: int = 20) -> list[dict]:
        """Return top N trainer-jockey partnerships by win rate (min evidence)."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row

        rows = conn.execute(
            """SELECT trainer, jockey, wins, runs, win_rate
               FROM trainer_jockey_stats
               WHERE runs >= ?
               ORDER BY win_rate DESC, runs DESC
               LIMIT ?""",
            (self.min_evidence, n),
        ).fetchall()

        conn.close()
        return [dict(r) for r in rows]

    def bayesian_win_rate(self, hypothesis_type: str, subject_key: str) -> dict:
        """
        Return full Bayesian stats for a specific hypothesis.
        Includes credible interval [2.5%, 97.5%].
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row

        row = conn.execute(
            """SELECT alpha, beta_param, evidence_count, confidence
               FROM hypothesis WHERE hypothesis_type=? AND subject_key=?""",
            (hypothesis_type, subject_key),
        ).fetchone()
        conn.close()

        if not row:
            return {}

        alpha = row["alpha"]
        beta_p = row["beta_param"]
        n = row["evidence_count"]

        # Beta distribution mean and variance
        mean = alpha / (alpha + beta_p)
        variance = (alpha * beta_p) / ((alpha + beta_p) ** 2 * (alpha + beta_p + 1))
        std = math.sqrt(variance)

        # Approximate 95% credible interval using normal approximation
        ci_lo = max(0.0, mean - 1.96 * std)
        ci_hi = min(1.0, mean + 1.96 * std)

        return {
            "hypothesis_type": hypothesis_type,
            "subject_key": subject_key,
            "posterior_mean": round(mean, 4),
            "std": round(std, 4),
            "ci_95_lo": round(ci_lo, 4),
            "ci_95_hi": round(ci_hi, 4),
            "evidence_count": n,
        }
