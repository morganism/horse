"""
Smoke tests — fast checks that core modules import and basic logic works.
No DB required for most tests.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
import numpy as np


# ── Odds model ──────────────────────────────────────────────────────────────

def test_softmax_sums_to_one():
    from data.odds_model import softmax
    probs = softmax(np.array([1.0, 0.5, -0.3, 0.8, 1.2]))
    assert abs(probs.sum() - 1.0) < 1e-9


def test_round_to_uk_odds_clips():
    from data.odds_model import round_to_uk_odds
    assert round_to_uk_odds(3.14) in (3.0, 3.25, 3.5)
    assert round_to_uk_odds(0.5) == 1.25  # clips to minimum


def test_generate_field_odds_shapes():
    from data.odds_model import generate_field_odds
    rng = np.random.default_rng(42)
    abilities, morning, sp = generate_field_odds(8, rng)
    assert len(abilities) == 8
    assert len(morning) == 8
    assert len(sp) == 8
    assert all(o >= 1.1 for o in sp)


def test_sample_result_returns_all_runners():
    from data.odds_model import sample_race_result
    rng = np.random.default_rng(0)
    abilities = np.array([1.0, 0.5, -0.3, 0.8])
    order = sample_race_result(abilities, rng)
    assert sorted(order) == [0, 1, 2, 3]


# ── Strategy base ────────────────────────────────────────────────────────────

def test_dutch_stakes_equal_return():
    from strategies.base import dutch_stakes, dutch_return
    odds = [2.0, 3.0, 5.0]
    budget = 100.0
    stakes = dutch_stakes(odds, budget)
    returns = [s * o for s, o in zip(stakes, odds)]
    assert all(abs(r - returns[0]) < 0.01 for r in returns)


def test_dutch_return_positive_when_below_one():
    from strategies.base import dutch_return
    # When sum(1/odds) < 1, return > budget
    odds = [3.5, 4.0, 6.0]  # sum(1/o) ≈ 0.28+0.25+0.17 = 0.70 < 1
    budget = 100.0
    ret = dutch_return(odds, budget)
    assert ret > budget


def test_exacta_odds_calculation():
    from strategies.base import exacta_odds
    # 2.0 * 3.0 = 6.0 (probabilities 0.5 and 0.333...)
    result = exacta_odds(2.0, 3.0)
    assert abs(result - 6.0) < 0.01


# ── Strategy params slugs ────────────────────────────────────────────────────

def test_params_slug_is_deterministic():
    from strategies.dutching import DutchingParams
    p = DutchingParams(
        max_odds_include=33.0, target_profit_margin=0.05,
        min_runners_dutch=4, max_runners_dutch=8,
        stake_model="level", race_type_filter="any", min_field_size=6,
    )
    assert p.to_slug() == p.to_slug()


def test_params_json_roundtrip():
    import json
    from dataclasses import asdict
    from strategies.dutching import DutchingParams
    p = DutchingParams(
        max_odds_include=20.0, target_profit_margin=0.08,
        min_runners_dutch=3, max_runners_dutch=6,
        stake_model="proportional", race_type_filter="flat", min_field_size=8,
    )
    j = p.to_json()
    d = json.loads(j)
    assert d["max_odds_include"] == 20.0


# ── Registry ────────────────────────────────────────────────────────────────

def test_registry_builds_minimum_strategies():
    from strategies.registry import build_dutching_variants, build_exotic_variants
    dutching = build_dutching_variants(max_total=10)
    assert len(dutching) == 10
    exotic = build_exotic_variants(max_total=10)
    assert len(exotic) == 10


def test_registry_names_are_unique():
    from strategies.registry import build_registry
    strategies = build_registry()
    names = [s.name for s in strategies]
    assert len(names) == len(set(names)), "Duplicate strategy names found"


def test_registry_total_count():
    from strategies.registry import build_registry
    strategies = build_registry()
    assert len(strategies) >= 200, f"Expected >=200 strategies, got {len(strategies)}"


# ── Metrics ──────────────────────────────────────────────────────────────────

def test_roi_positive():
    from performance.metrics import roi
    assert roi(100.0, 110.0) == pytest.approx(0.10)


def test_roi_none_on_zero_stake():
    from performance.metrics import roi
    assert roi(0.0, 50.0) is None


def test_max_drawdown_flat():
    from performance.metrics import max_drawdown
    assert max_drawdown([100, 100, 100]) == 0.0


def test_max_drawdown_calculated():
    from performance.metrics import max_drawdown
    series = [100, 120, 90, 110, 80]
    # peak=120, trough=80, drawdown=40
    assert max_drawdown(series) == pytest.approx(40.0)


def test_kelly_fraction_positive_edge():
    from performance.metrics import kelly_fraction
    # 50% chance, 3.0 decimal odds → f* = (2*0.5 - 0.5) / 2 = 0.25
    k = kelly_fraction(0.5, 3.0)
    assert k == pytest.approx(0.25)


def test_kelly_fraction_negative_edge():
    from performance.metrics import kelly_fraction
    # 20% chance, 2.0 decimal odds (negative EV)
    k = kelly_fraction(0.2, 2.0)
    assert k == 0.0


# ── Settler ─────────────────────────────────────────────────────────────────

def test_settle_win_bet():
    from simulation.settler import _evaluate_bet
    won, payout = _evaluate_bet("win", [1], stake=10.0, odds_taken=4.0, field_size=8)
    assert won
    assert payout == pytest.approx(40.0)


def test_settle_win_bet_lost():
    from simulation.settler import _evaluate_bet
    won, payout = _evaluate_bet("win", [2], stake=10.0, odds_taken=4.0, field_size=8)
    assert not won
    assert payout == 0.0


def test_settle_exacta_correct_order():
    from simulation.settler import _evaluate_bet
    won, payout = _evaluate_bet("exacta", [1, 2], stake=5.0, odds_taken=10.0, field_size=10)
    assert won
    assert payout == pytest.approx(50.0)


def test_settle_exacta_wrong_order():
    from simulation.settler import _evaluate_bet
    won, payout = _evaluate_bet("exacta", [2, 1], stake=5.0, odds_taken=10.0, field_size=10)
    assert not won


def test_settle_trifecta():
    from simulation.settler import _evaluate_bet
    won, payout = _evaluate_bet("trifecta", [1, 2, 3], stake=2.0, odds_taken=50.0, field_size=12)
    assert won
    assert payout == pytest.approx(100.0)


def test_settle_dutch_any_winner():
    from simulation.settler import _evaluate_bet
    won, payout = _evaluate_bet("dutch", [1, 3, 5], stake=10.0, odds_taken=2.5, field_size=10)
    # position[0]=1 means first runner won
    assert won
