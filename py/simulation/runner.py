"""
Simulation Runner.

Orchestrates the 30-day simulation:
  1. Init DB schema
  2. Seed venues and horse pool
  3. Build strategy registry
  4. Initialise bankrolls
  5. For each day: run_day()
  6. Final performance report
"""
from datetime import date, timedelta

from db.connection import apply_schema
from data.generator import SyntheticDataGenerator
from strategies.registry import build_registry, save_registry, load_strategy_ids
from simulation.bankroll import Bankroll
from simulation.daily_loop import run_day
from bayesian.updater import BayesianUpdater
from performance.monitor import PerformanceMonitor
from config.settings import Config, DEFAULT_CONFIG


class SimulationRunner:
    def __init__(self, config: Config = DEFAULT_CONFIG):
        self.config = config
        self.db_path = config.db_path

    def run(self, verbose: bool = True) -> None:
        cfg = self.config

        if verbose:
            print(f"[init] Applying schema to {self.db_path}")
        apply_schema(self.db_path)

        generator = SyntheticDataGenerator(
            db_path=self.db_path,
            seed=cfg.random_seed,
            races_per_day=(cfg.races_per_day_min, cfg.races_per_day_max),
        )

        if verbose:
            print("[init] Seeding venues...")
        generator.seed_venues()

        if verbose:
            print("[init] Seeding horse pool (500 horses)...")
        generator.seed_horses(pool_size=500)

        if verbose:
            print("[init] Building strategy registry (~250 variants)...")
        strategies = build_registry(db_path=self.db_path)
        strategy_id_map = save_registry(strategies, self.db_path)

        if verbose:
            print(f"[init] {len(strategies)} strategies registered")

        # Initialise bankrolls for each strategy
        bankrolls: dict[int, Bankroll] = {}
        for name, sid in strategy_id_map.items():
            bankrolls[sid] = Bankroll(
                strategy_id=sid,
                db_path=self.db_path,
                initial_balance=cfg.initial_bankroll,
                max_bet_fraction=cfg.max_bet_fraction,
                min_stake=cfg.min_stake,
            )

        bayesian_updater = BayesianUpdater(self.db_path)
        monitor = PerformanceMonitor(self.db_path)

        start_date = date(2024, 3, 1)

        for day in range(1, cfg.sim_days + 1):
            race_date = start_date + timedelta(days=day - 1)

            if verbose:
                print(f"\n[day {day:02d}] {race_date} ──────────────────────")

            day_result = run_day(
                sim_day=day,
                race_date=race_date,
                generator=generator,
                strategies=strategies,
                bankrolls=bankrolls,
                strategy_id_map=strategy_id_map,
                db_path=self.db_path,
                max_bet_fraction=cfg.max_bet_fraction,
                min_stake=cfg.min_stake,
            )

            # Update Bayesian priors from today's results
            bayesian_updater.update(sim_day=day)

            # Record performance metrics
            monitor.record_day(sim_day=day, strategy_ids=list(strategy_id_map.values()))

            if verbose:
                print(
                    f"         races={day_result['races_generated']} "
                    f"bets={day_result['bets_placed']} "
                    f"wins={day_result.get('wins', 0)} "
                    f"P&L=£{day_result.get('profit_loss', 0):.2f}"
                )

        if verbose:
            print("\n[done] Simulation complete. Run `python cli.py report` for results.")
