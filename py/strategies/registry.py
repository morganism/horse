"""
Strategy Registry.

Generates 200+ strategy variants via cartesian product of parameter grids.
Each variant is a unique, named Strategy instance.

Usage:
    from strategies.registry import build_registry, save_registry
    strategies = build_registry()   # list[Strategy]
    save_registry(strategies, db_path)
"""
from itertools import product
from typing import Iterator

from .base import Strategy
from .dutching import DutchingEnvelope, DutchingParams
from .exotic import ExoticPermutation, ExoticParams
from .bayesian_correlation import BayesianCorrelation, BayesianParams
from .odds_movement import OddsMovement, OddsMovementParams
from .pattern_recognition import PatternRecognition, PatternParams
# Iteration-2 new classes
from .favourite_cover import FavouriteCover, FavCoverParams
from .handicap_exploit import HandicapExploit, HandicapParams
from .trainer_going import TrainerGoing, TrainerGoingParams


# ─── Parameter Grids ────────────────────────────────────────────────────────
# Each grid generates variants via cartesian product, filtered for validity.

DUTCHING_GRID = {
    "max_odds_include":      [20.0, 33.0, 50.0],
    "target_profit_margin":  [0.03, 0.05, 0.08, 0.12],
    "min_runners_dutch":     [3, 4, 5],
    "max_runners_dutch":     [5, 6, 8, 10],
    "stake_model":           ["level", "proportional"],
    "race_type_filter":      ["any", "flat", "nh"],
    "min_field_size":        [6, 8],
}
# After validity filter (min < max runners), ~3*4*3*3*2*3*2 / ~30% valid = ~130 → cap 60

EXOTIC_GRID = {
    "bet_type":              ["exacta", "trifecta", "both"],
    "selection_method":      ["top_n_odds", "sweet_spot_odds", "non_fav_focus"],
    "max_runners_in_combo":  [3, 4, 5],
    "min_field_size":        [8, 10, 12],
    "race_type_filter":      ["any", "flat", "nh"],
    "min_odds_include":      [2.0, 3.0],
    "max_odds_include":      [10.0, 20.0, 33.0],
    "stake_per_combo":       [0.001, 0.002, 0.005],  # fraction of bankroll
    "class_max":             [0, 4, 6],  # 0=no filter
}
# Cap 60

BAYESIAN_GRID = {
    "hypothesis_type":       ["trainer_jockey", "weight_drop", "course_specialist"],
    "min_evidence":          [5, 10, 20],
    "confidence_threshold":  [0.40, 0.50, 0.55, 0.60],
    "stake_fraction":        [0.01, 0.02, 0.03],
    "max_odds":              [10.0, 20.0, 33.0],
    "min_odds":              [2.0, 3.0],
    "race_type_filter":      ["any", "flat", "nh"],
}
# Cap 50

ODDS_MOVEMENT_GRID = {
    "movement_type":               ["shorten", "drift_avoid", "reversal"],
    "min_movement_pct":            [10.0, 15.0, 25.0],
    "observation_window_hours":    [1.0, 2.0, 4.0],
    "min_sp":                      [2.0, 3.0],
    "max_sp":                      [10.0, 20.0, 33.0],
    "stake_fraction":              [0.01, 0.02],
    "race_type_filter":            ["any", "flat", "nh"],
    "min_field_size":              [6, 8],
    "reversal_drift_pct":          [10.0, 20.0],
}
# Cap 40

PATTERN_GRID = {
    "pattern_type":          ["course_specialist", "distance_specialist",
                              "going_preference", "class_drop", "fresh_horse", "composite"],
    "min_score":             [0.40, 0.55, 0.70],
    "stake_fraction":        [0.01, 0.02, 0.03],
    "min_odds":              [2.0, 3.0, 4.0],
    "max_odds":              [10.0, 20.0],
    "race_type_filter":      ["any", "flat", "nh"],
    "min_field_size":        [6, 8],
    "min_course_wins":       [1, 2],
    "min_distance_wins":     [1, 2],
    "min_going_wins":        [1, 2],
    "days_since_run_min":    [0, 7],
    "days_since_run_max":    [14, 28, 60],
    "class_drop_required":   [True, False],
}
# Cap 40


def _grid_variants(grid: dict, max_variants: int) -> Iterator[dict]:
    """Yield up to max_variants param combinations from the cartesian product."""
    keys = list(grid.keys())
    count = 0
    for values in product(*grid.values()):
        if count >= max_variants:
            break
        yield dict(zip(keys, values))
        count += 1


def _is_valid_dutch(p: dict) -> bool:
    return p["min_runners_dutch"] < p["max_runners_dutch"]


def _is_valid_exotic(p: dict) -> bool:
    return p["min_odds_include"] < p["max_odds_include"]


def _is_valid_bayesian(p: dict) -> bool:
    return p["min_odds"] < p["max_odds"]


def _is_valid_odds_movement(p: dict) -> bool:
    return p["min_sp"] < p["max_sp"]


def _is_valid_pattern(p: dict) -> bool:
    return (
        p["min_odds"] < p["max_odds"] and
        p["days_since_run_min"] < p["days_since_run_max"]
    )


def build_dutching_variants(max_total: int = 60) -> list[Strategy]:
    strategies = []
    seen_names = set()
    for p in _grid_variants(DUTCHING_GRID, max_total * 4):
        if len(strategies) >= max_total:
            break
        if not _is_valid_dutch(p):
            continue
        params = DutchingParams(**p)
        s = DutchingEnvelope(params)
        if s.name not in seen_names:
            seen_names.add(s.name)
            strategies.append(s)
    return strategies


def build_exotic_variants(max_total: int = 60) -> list[Strategy]:
    strategies = []
    seen_names = set()
    for p in _grid_variants(EXOTIC_GRID, max_total * 4):
        if len(strategies) >= max_total:
            break
        if not _is_valid_exotic(p):
            continue
        params = ExoticParams(**p)
        s = ExoticPermutation(params)
        if s.name not in seen_names:
            seen_names.add(s.name)
            strategies.append(s)
    return strategies


def build_bayesian_variants(max_total: int = 50, db_path: str = "") -> list[Strategy]:
    strategies = []
    seen_names = set()
    for p in _grid_variants(BAYESIAN_GRID, max_total * 4):
        if len(strategies) >= max_total:
            break
        if not _is_valid_bayesian(p):
            continue
        params = BayesianParams(**p)
        s = BayesianCorrelation(params, db_path=db_path)
        if s.name not in seen_names:
            seen_names.add(s.name)
            strategies.append(s)
    return strategies


def build_odds_movement_variants(max_total: int = 40) -> list[Strategy]:
    strategies = []
    seen_names = set()
    for p in _grid_variants(ODDS_MOVEMENT_GRID, max_total * 4):
        if len(strategies) >= max_total:
            break
        if not _is_valid_odds_movement(p):
            continue
        params = OddsMovementParams(**p)
        s = OddsMovement(params)
        if s.name not in seen_names:
            seen_names.add(s.name)
            strategies.append(s)
    return strategies


def build_pattern_variants(max_total: int = 40) -> list[Strategy]:
    strategies = []
    seen_names = set()
    for p in _grid_variants(PATTERN_GRID, max_total * 6):
        if len(strategies) >= max_total:
            break
        if not _is_valid_pattern(p):
            continue
        params = PatternParams(**p)
        s = PatternRecognition(params)
        if s.name not in seen_names:
            seen_names.add(s.name)
            strategies.append(s)
    return strategies


FAV_COVER_GRID = {
    "bet_type":            ["win", "each_way", "dutch_top2"],
    "max_sp":              [2.5, 3.0, 4.0],
    "min_sp":              [1.4, 1.6, 2.0],
    "min_course_wins":     [1, 2],
    "min_field_size":      [6, 8],
    "race_type_filter":    ["any", "flat", "nh"],
    "stake_fraction":      [0.02, 0.03],
    "require_course_win":  [True, False],
}

HANDICAP_GRID = {
    "min_field_size":         [8, 10, 12],
    "max_field_size":         [16, 20],
    "weight_below_top":       [10, 15],
    "weight_above_bottom":    [5, 10],
    "min_sp":                 [2.0, 3.0],
    "max_sp":                 [8.0, 12.0],
    "min_official_rating":    [70, 80, 90],
    "race_type_filter":       ["any", "flat", "nh"],
    "stake_fraction":         [0.02, 0.03],
    "bet_type":               ["win", "each_way"],
}

TRAINER_GOING_GRID = {
    "min_evidence":                [3, 5, 10],
    "trainer_going_threshold":     [0.35, 0.45, 0.55],
    "trainer_jockey_threshold":    [0.0, 0.40, 0.50],
    "require_both":                [True, False],
    "min_sp":                      [2.0, 3.0],
    "max_sp":                      [10.0, 20.0],
    "stake_fraction":              [0.01, 0.02],
    "race_type_filter":            ["any", "flat", "nh"],
}


def build_fav_cover_variants(max_total: int = 20) -> list[Strategy]:
    strategies = []
    seen_names = set()
    for p in _grid_variants(FAV_COVER_GRID, max_total * 4):
        if len(strategies) >= max_total:
            break
        if p["min_sp"] >= p["max_sp"]:
            continue
        params = FavCoverParams(**p)
        s = FavouriteCover(params)
        if s.name not in seen_names:
            seen_names.add(s.name)
            strategies.append(s)
    return strategies


def build_handicap_variants(max_total: int = 20) -> list[Strategy]:
    strategies = []
    seen_names = set()
    for p in _grid_variants(HANDICAP_GRID, max_total * 4):
        if len(strategies) >= max_total:
            break
        if p["min_sp"] >= p["max_sp"] or p["min_field_size"] >= p["max_field_size"]:
            continue
        params = HandicapParams(**p)
        s = HandicapExploit(params)
        if s.name not in seen_names:
            seen_names.add(s.name)
            strategies.append(s)
    return strategies


def build_trainer_going_variants(max_total: int = 20, db_path: str = "") -> list[Strategy]:
    strategies = []
    seen_names = set()
    for p in _grid_variants(TRAINER_GOING_GRID, max_total * 4):
        if len(strategies) >= max_total:
            break
        if p["min_sp"] >= p["max_sp"]:
            continue
        params = TrainerGoingParams(**p)
        s = TrainerGoing(params, db_path=db_path)
        if s.name not in seen_names:
            seen_names.add(s.name)
            strategies.append(s)
    return strategies


def build_registry(db_path: str = "") -> list[Strategy]:
    """
    Build the full strategy registry (~275 variants across 8 classes).
    Returns a list of named Strategy instances.
    """
    all_strategies = []
    all_strategies.extend(build_dutching_variants(60))
    all_strategies.extend(build_exotic_variants(60))
    all_strategies.extend(build_bayesian_variants(50, db_path=db_path))
    all_strategies.extend(build_odds_movement_variants(40))
    all_strategies.extend(build_pattern_variants(40))
    # Iteration-2 new classes
    all_strategies.extend(build_fav_cover_variants(20))
    all_strategies.extend(build_handicap_variants(20))
    all_strategies.extend(build_trainer_going_variants(20, db_path=db_path))
    return all_strategies


def save_registry(strategies: list[Strategy], db_path: str) -> dict[str, int]:
    """
    Persist all strategies to the strategies table.
    Returns mapping of variant_name -> strategy_id.
    """
    import sqlite3
    from datetime import datetime

    conn = sqlite3.connect(db_path)
    name_to_id = {}
    now = datetime.utcnow().isoformat()

    for s in strategies:
        row = s.to_registry_row()
        cur = conn.execute(
            """INSERT OR IGNORE INTO strategies (strategy_class, variant_name, params_json, created_at)
               VALUES (?, ?, ?, ?)""",
            (row["strategy_class"], row["variant_name"], row["params_json"], now),
        )
        if cur.lastrowid:
            name_to_id[row["variant_name"]] = cur.lastrowid
        else:
            existing = conn.execute(
                "SELECT id FROM strategies WHERE variant_name=?",
                (row["variant_name"],)
            ).fetchone()
            if existing:
                name_to_id[row["variant_name"]] = existing[0]

    conn.commit()
    conn.close()
    return name_to_id


def load_strategy_ids(db_path: str) -> dict[str, int]:
    """Load variant_name -> id mapping from DB."""
    import sqlite3
    conn = sqlite3.connect(db_path)
    rows = conn.execute("SELECT id, variant_name FROM strategies").fetchall()
    conn.close()
    return {row[1]: row[0] for row in rows}
