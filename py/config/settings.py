from dataclasses import dataclass, field
from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DB = BASE_DIR / "data" / "horse_racing.db"


@dataclass
class Config:
    db_path: str = str(DEFAULT_DB)
    initial_bankroll: float = 1000.0
    sim_days: int = 30
    random_seed: int = 42
    # Per-strategy bankroll allocation fraction (equal split across strategies)
    per_strategy_fraction: float = 1.0   # each strategy manages its own £1000
    # Kelly fraction for Kelly stake sizing
    kelly_fraction: float = 0.25         # quarter-Kelly to limit variance
    # Minimum stake (£)
    min_stake: float = 0.10
    # Maximum single bet as fraction of strategy bankroll
    max_bet_fraction: float = 0.05
    # Race generation params
    races_per_day_min: int = 8
    races_per_day_max: int = 14
    venues_per_day: int = 4
    # Odds model
    overround_min: float = 1.10
    overround_max: float = 1.18
    # Bayesian update min evidence before using hypothesis
    min_bayesian_evidence: int = 5


DEFAULT_CONFIG = Config()
