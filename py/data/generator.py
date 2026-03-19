"""
Synthetic UK/Irish Race Data Generator.

Generates realistic race data for 30-day simulation.
All generation is seeded for reproducibility.
"""
import json
import sqlite3
from datetime import date, timedelta
from typing import Optional
import numpy as np

from .uk_constants import (
    UK_VENUES, JOCKEYS, TRAINERS, GOING_BY_SURFACE,
    FLAT_DISTANCES, HURDLE_DISTANCES, CHASE_DISTANCES,
    RACE_NAME_PREFIXES, RACE_NAME_SUFFIXES, HORSE_NAME_PARTS,
    OWNERS, SIRES,
)
from .odds_model import (
    generate_field_odds, generate_odds_history, sample_race_result
)


class SyntheticDataGenerator:
    """
    Generates and persists synthetic race data to SQLite.

    Usage:
        gen = SyntheticDataGenerator(db_path, seed=42)
        gen.seed_venues()
        gen.seed_horses(pool_size=500)
        gen.generate_day(sim_day=1, race_date=date(2024, 3, 1))
        gen.generate_results(sim_day=1)
    """

    def __init__(self, db_path: str, seed: int = 42, races_per_day: tuple = (8, 14)):
        self.db_path = db_path
        self.seed = seed
        self.rng = np.random.default_rng(seed)
        self.races_per_day_range = races_per_day
        self._horse_pool: list[int] = []  # cached horse IDs
        self._venue_ids: list[int] = []

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    # ─── Seeding ─────────────────────────────────────────────────────────────

    def seed_venues(self) -> list[int]:
        """Insert UK/Irish venues, return their IDs."""
        conn = self._conn()
        ids = []
        for v in UK_VENUES:
            cur = conn.execute(
                """INSERT OR IGNORE INTO venues (name, country, surface, race_types, straight_furlongs)
                   VALUES (?, ?, ?, ?, ?)""",
                (v["name"], v["country"], v["surface"],
                 json.dumps(v["race_types"]), v.get("straight_furlongs")),
            )
            if cur.lastrowid:
                ids.append(cur.lastrowid)
            else:
                row = conn.execute(
                    "SELECT id FROM venues WHERE name=?", (v["name"],)
                ).fetchone()
                if row:
                    ids.append(row[0])
        conn.commit()
        conn.close()
        self._venue_ids = ids
        return ids

    def seed_horses(self, pool_size: int = 500) -> list[int]:
        """Generate a pool of horses. Returns list of horse IDs."""
        conn = self._conn()
        ids = []
        names_used = set()

        for i in range(pool_size):
            name = self._generate_horse_name(names_used)
            names_used.add(name)
            age = int(self.rng.integers(2, 12))
            sex = self.rng.choice(["G", "M", "F", "C", "H"], p=[0.45, 0.15, 0.20, 0.12, 0.08])
            trainer = self.rng.choice([t[0] for t in TRAINERS])
            owner = self.rng.choice(OWNERS)
            sire = self.rng.choice(SIRES)

            cur = conn.execute(
                """INSERT OR IGNORE INTO horses (name, age, sex, trainer, owner, sire)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (name, age, sex, trainer, owner, sire),
            )
            if cur.lastrowid:
                ids.append(cur.lastrowid)

        conn.commit()
        conn.close()
        self._horse_pool = ids
        return ids

    def _generate_horse_name(self, used: set) -> str:
        for _ in range(100):
            p1 = self.rng.choice(HORSE_NAME_PARTS)
            p2 = self.rng.choice(HORSE_NAME_PARTS)
            name = f"{p1} {p2}"
            if name not in used:
                return name
        return f"Horse {len(used) + 1}"

    # ─── Daily Generation ────────────────────────────────────────────────────

    def generate_day(
        self,
        sim_day: int,
        race_date: date,
        venues_count: int = 4,
    ) -> list[int]:
        """
        Generate a full day's racing: venues, races, runners, odds history.
        Returns list of race IDs generated.
        """
        conn = self._conn()

        if not self._venue_ids:
            self._venue_ids = [
                row[0] for row in conn.execute("SELECT id FROM venues").fetchall()
            ]
        if not self._horse_pool:
            self._horse_pool = [
                row[0] for row in conn.execute("SELECT id FROM horses").fetchall()
            ]

        venues_today = [
            int(v) for v in self.rng.choice(
                self._venue_ids, size=min(venues_count, len(self._venue_ids)), replace=False
            )
        ]
        total_races = int(self.rng.integers(*self.races_per_day_range))
        races_per_venue = self._distribute_races(total_races, len(venues_today))

        race_ids = []
        for venue_id, n_races in zip(venues_today, races_per_venue):
            venue_row = conn.execute(
                "SELECT * FROM venues WHERE id=?", (venue_id,)
            ).fetchone()
            if not venue_row:
                continue

            race_types = json.loads(venue_row["race_types"])
            surface = venue_row["surface"]
            times = self._generate_race_times(n_races)

            for race_time in times:
                race_id = self._generate_race(
                    conn, venue_id, sim_day, race_date, race_time,
                    race_types, surface
                )
                if race_id:
                    race_ids.append(race_id)

        conn.commit()
        conn.close()
        return race_ids

    def _distribute_races(self, total: int, n_venues: int) -> list[int]:
        base = total // n_venues
        remainder = total % n_venues
        dist = [base] * n_venues
        for i in range(remainder):
            dist[i] += 1
        return dist

    def _generate_race_times(self, n: int) -> list[str]:
        start_hour = 12
        times = []
        current = start_hour * 60
        for _ in range(n):
            h, m = divmod(current, 60)
            times.append(f"{h:02d}:{m:02d}")
            current += int(self.rng.integers(20, 35))
        return times

    def _generate_race(
        self,
        conn: sqlite3.Connection,
        venue_id: int,
        sim_day: int,
        race_date: date,
        race_time: str,
        race_types: list,
        surface: str,
    ) -> Optional[int]:
        race_type = self.rng.choice(race_types)
        race_class = int(self.rng.integers(1, 7))
        is_handicap = int(self.rng.random() < 0.5)

        if race_type == "flat":
            distance = float(self.rng.choice(FLAT_DISTANCES))
        elif race_type == "hurdle":
            distance = float(self.rng.choice(HURDLE_DISTANCES))
        elif race_type in ("chase", "bumper"):
            distance = float(self.rng.choice(CHASE_DISTANCES))
        else:
            distance = float(self.rng.choice(FLAT_DISTANCES))

        season = self._get_season(race_date.month)
        if surface == "aw":
            going = self.rng.choice(GOING_BY_SURFACE["aw"]["any"])
        else:
            going = self.rng.choice(GOING_BY_SURFACE["turf"].get(season, ["Good"]))

        runner_count = int(self.rng.integers(5, 18))
        prize_gbp = int(self.rng.integers(3000, 250000))

        prefix = self.rng.choice(RACE_NAME_PREFIXES)
        suffix = self.rng.choice(RACE_NAME_SUFFIXES)
        race_name = f"{prefix} {suffix}"

        cur = conn.execute(
            """INSERT INTO races
               (venue_id, sim_day, race_date, race_time, race_name, race_type,
                class, distance_furlongs, going, prize_gbp, runner_count, is_handicap)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (venue_id, sim_day, race_date.isoformat(), race_time, race_name,
             race_type, race_class, distance, going, prize_gbp, runner_count, is_handicap),
        )
        race_id = cur.lastrowid
        if not race_id:
            return None

        self._generate_runners(conn, race_id, runner_count, race_date, distance)
        return race_id

    def _get_season(self, month: int) -> str:
        if month in (6, 7, 8):
            return "summer"
        elif month in (3, 4, 5):
            return "spring"
        elif month in (9, 10, 11):
            return "autumn"
        return "winter"

    def _generate_runners(
        self,
        conn: sqlite3.Connection,
        race_id: int,
        runner_count: int,
        race_date: date,
        distance_furlongs: float,
    ) -> None:
        horse_sample = [
            int(h) for h in self.rng.choice(
                self._horse_pool, size=min(runner_count, len(self._horse_pool)), replace=False
            )
        ]

        # Generate odds for the whole field
        market_mover = self.rng.random() < 0.15
        latent_abilities, morning_prices, sp_odds = generate_field_odds(
            runner_count=len(horse_sample),
            rng=self.rng,
            market_mover=market_mover,
        )

        # Sort by SP to assign favourite ranks
        fav_order = np.argsort(sp_odds)
        fav_rank = np.empty(len(horse_sample), dtype=int)
        for rank, idx in enumerate(fav_order):
            fav_rank[idx] = rank + 1

        for i, horse_id in enumerate(horse_sample):
            horse_row = conn.execute(
                "SELECT trainer FROM horses WHERE id=?", (horse_id,)
            ).fetchone()
            trainer = horse_row["trainer"] if horse_row else self.rng.choice([t[0] for t in TRAINERS])

            jockey = self.rng.choice([j[0] for j in JOCKEYS])
            cloth_number = i + 1
            weight_lbs = int(self.rng.integers(126, 168))
            official_rating = int(self.rng.integers(40, 135))
            days_since = int(self.rng.choice(
                [7, 10, 14, 21, 28, 42, 60, 90, 120, 180, 365],
                p=[0.08, 0.12, 0.18, 0.18, 0.14, 0.10, 0.08, 0.06, 0.03, 0.02, 0.01]
            ))
            career_runs = int(self.rng.integers(0, 50))
            career_wins = int(self.rng.binomial(career_runs, 0.18))
            course_wins = int(self.rng.binomial(max(0, career_runs // 3), 0.15))
            distance_wins = int(self.rng.binomial(max(0, career_runs // 4), 0.18))
            going_wins = int(self.rng.binomial(max(0, career_runs // 3), 0.18))

            cur = conn.execute(
                """INSERT INTO runners
                   (race_id, horse_id, jockey, cloth_number, weight_lbs,
                    official_rating, days_since_last_run, career_wins, career_runs,
                    course_wins, distance_wins, going_wins,
                    latent_ability, morning_price, sp, favourite_rank)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (race_id, horse_id, jockey, cloth_number, weight_lbs,
                 official_rating, days_since, career_wins, career_runs,
                 course_wins, distance_wins, going_wins,
                 float(latent_abilities[i]), float(morning_prices[i]),
                 float(sp_odds[i]), int(fav_rank[i])),
            )
            runner_id = cur.lastrowid

            # Generate odds history
            race_time = conn.execute(
                "SELECT race_time FROM races WHERE id=?", (race_id,)
            ).fetchone()
            rt = race_time["race_time"] if race_time else "14:00"

            history = generate_odds_history(
                runner_count=1,
                morning_prices=np.array([float(morning_prices[i])]),
                sp_odds=np.array([float(sp_odds[i])]),
                rng=self.rng,
                n_updates=4,
                race_time=rt,
            )
            from datetime import datetime
            for h in history:
                conn.execute(
                    """INSERT INTO odds_history (runner_id, race_id, recorded_at, hours_before, odds, movement)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (runner_id, race_id,
                     datetime.utcnow().isoformat(),
                     h.get("hours_before"),
                     h["odds"], h["movement"]),
                )

    # ─── Results Generation ──────────────────────────────────────────────────

    def generate_results(self, sim_day: int) -> None:
        """
        Generate finishing positions for all races on sim_day.
        Uses latent abilities stored in runners table.
        """
        conn = self._conn()
        races = conn.execute(
            "SELECT id FROM races WHERE sim_day=?", (sim_day,)
        ).fetchall()

        for race_row in races:
            race_id = race_row["id"]
            runners = conn.execute(
                "SELECT id, latent_ability, cloth_number FROM runners WHERE race_id=?",
                (race_id,)
            ).fetchall()

            if not runners:
                continue

            latent = np.array([r["latent_ability"] for r in runners])
            order = sample_race_result(latent, self.rng)

            for position, runner_idx in enumerate(order):
                runner = runners[int(runner_idx)]
                btn = float(position) * self.rng.uniform(0.5, 3.0) if position > 0 else 0.0
                conn.execute(
                    """INSERT OR IGNORE INTO race_results
                       (race_id, runner_id, position, btn_lengths)
                       VALUES (?, ?, ?, ?)""",
                    (race_id, runner["id"], position + 1, btn),
                )

        conn.commit()
        conn.close()
