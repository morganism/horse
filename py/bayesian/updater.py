"""
Bayesian Updater.

After each day's races are settled, update Beta distribution priors
in the hypothesis table for:
  - trainer_jockey combos
  - weight_drop patterns
  - course_specialist patterns
  - head-to-head (horse_relationships table)
  - trainer/jockey individual stats
"""
import sqlite3
from datetime import datetime


class BayesianUpdater:
    def __init__(self, db_path: str):
        self.db_path = db_path

    def update(self, sim_day: int) -> None:
        """Run all hypothesis updates for sim_day's results."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row

        races = conn.execute(
            "SELECT id, venue_id, going FROM races WHERE sim_day=?", (sim_day,)
        ).fetchall()

        for race in races:
            race_id = race["id"]
            results = conn.execute(
                """SELECT rr.runner_id, rr.position,
                          r.horse_id, r.jockey, h.trainer, r.weight_lbs,
                          r.days_since_last_run, r.course_wins,
                          h.name AS horse_name
                   FROM race_results rr
                   JOIN runners r ON rr.runner_id = r.id
                   JOIN horses h ON r.horse_id = h.id
                   WHERE rr.race_id=?
                   ORDER BY rr.position""",
                (race_id,),
            ).fetchall()

            if not results:
                continue

            self._update_trainer_jockey(conn, results)
            self._update_course_specialist(conn, results, race["venue_id"])
            self._update_h2h(conn, results)

        conn.commit()
        conn.close()

    def _upsert_hypothesis(
        self,
        conn: sqlite3.Connection,
        hypothesis_type: str,
        subject_key: str,
        won: bool,
    ) -> None:
        """Increment alpha (win) or beta_param (loss) for a Beta prior."""
        now = datetime.utcnow().isoformat()
        existing = conn.execute(
            """SELECT id, alpha, beta_param, evidence_count FROM hypothesis
               WHERE hypothesis_type=? AND subject_key=?""",
            (hypothesis_type, subject_key),
        ).fetchone()

        if existing:
            alpha = existing["alpha"] + (1.0 if won else 0.0)
            beta_param = existing["beta_param"] + (0.0 if won else 1.0)
            evidence_count = existing["evidence_count"] + 1
            confidence = alpha / (alpha + beta_param)
            conn.execute(
                """UPDATE hypothesis
                   SET alpha=?, beta_param=?, evidence_count=?, confidence=?, updated_at=?
                   WHERE id=?""",
                (alpha, beta_param, evidence_count, confidence, now, existing["id"]),
            )
        else:
            alpha = 2.0 if won else 1.0   # Bayesian +1 prior
            beta_p = 1.0 if won else 2.0
            evidence_count = 1
            confidence = alpha / (alpha + beta_p)
            conn.execute(
                """INSERT INTO hypothesis
                   (hypothesis_type, subject_key, alpha, beta_param, evidence_count, confidence, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (hypothesis_type, subject_key, alpha, beta_p, evidence_count, confidence, now),
            )

    def _update_trainer_jockey(
        self, conn: sqlite3.Connection, results: list
    ) -> None:
        for result in results:
            trainer = result["trainer"] or ""
            jockey = result["jockey"] or ""
            if not trainer or not jockey:
                continue
            subject_key = f"{trainer}::{jockey}"
            won = result["position"] == 1
            self._upsert_hypothesis(conn, "trainer_jockey", subject_key, won)

            # Also update trainer_jockey_stats table
            now = datetime.utcnow().isoformat()
            existing = conn.execute(
                "SELECT id, wins, runs FROM trainer_jockey_stats WHERE trainer=? AND jockey=?",
                (trainer, jockey),
            ).fetchone()
            if existing:
                wins = existing["wins"] + (1 if won else 0)
                runs = existing["runs"] + 1
                conn.execute(
                    "UPDATE trainer_jockey_stats SET wins=?, runs=?, win_rate=?, last_updated=? WHERE id=?",
                    (wins, runs, wins / runs, now, existing["id"]),
                )
            else:
                conn.execute(
                    "INSERT INTO trainer_jockey_stats (trainer, jockey, wins, runs, win_rate, last_updated) VALUES (?, ?, ?, 1, ?, ?)",
                    (trainer, jockey, 1 if won else 0, 1.0 if won else 0.0, now),
                )

    def _update_course_specialist(
        self, conn: sqlite3.Connection, results: list, venue_id: int
    ) -> None:
        for result in results:
            horse_id = result["horse_id"]
            subject_key = f"horse_{horse_id}::venue_{venue_id}"
            won = result["position"] == 1
            self._upsert_hypothesis(conn, "course_specialist", subject_key, won)

    def _update_h2h(self, conn: sqlite3.Connection, results: list) -> None:
        """Update head-to-head records for all pairs of runners."""
        now = datetime.utcnow().isoformat()
        # Build list of (horse_id, position) pairs
        horses = [(r["horse_id"], r["position"]) for r in results]

        for i in range(len(horses)):
            for j in range(i + 1, len(horses)):
                h_a, pos_a = horses[i]
                h_b, pos_b = horses[j]

                a_ahead = 1 if pos_a < pos_b else 0
                b_ahead = 1 - a_ahead

                # Canonical ordering: lower horse_id = horse_a
                if h_a > h_b:
                    h_a, h_b = h_b, h_a
                    a_ahead, b_ahead = b_ahead, a_ahead

                existing = conn.execute(
                    """SELECT id, meetings, horse_a_ahead, horse_b_ahead
                       FROM horse_relationships WHERE horse_a_id=? AND horse_b_id=?""",
                    (h_a, h_b),
                ).fetchone()

                if existing:
                    conn.execute(
                        """UPDATE horse_relationships
                           SET meetings=?, horse_a_ahead=?, horse_b_ahead=?, last_updated=?
                           WHERE id=?""",
                        (existing["meetings"] + 1,
                         existing["horse_a_ahead"] + a_ahead,
                         existing["horse_b_ahead"] + b_ahead,
                         now, existing["id"]),
                    )
                else:
                    conn.execute(
                        """INSERT INTO horse_relationships
                           (horse_a_id, horse_b_id, meetings, horse_a_ahead, horse_b_ahead, last_updated)
                           VALUES (?, ?, 1, ?, ?, ?)""",
                        (h_a, h_b, a_ahead, b_ahead, now),
                    )
