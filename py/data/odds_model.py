"""
Odds generation model for synthetic UK/Irish racing.

Key principle: latent ability → win probability → decimal odds + overround noise.
Results are drawn from latent ability (not odds), keeping the simulation honest.
"""
import numpy as np
from numpy.random import Generator as NpRng


def softmax(x: np.ndarray, temperature: float = 1.0) -> np.ndarray:
    """Convert ability scores to win probabilities."""
    x = np.array(x) / temperature
    x -= x.max()  # numerical stability
    e = np.exp(x)
    return e / e.sum()


def probs_to_odds(probs: np.ndarray, overround: float) -> np.ndarray:
    """Convert true probabilities to bookmaker decimal odds with overround."""
    # Inflate probabilities by overround, then invert
    inflated = probs * overround
    return 1.0 / inflated


def add_odds_noise(odds: np.ndarray, rng: NpRng, sigma: float = 0.15) -> np.ndarray:
    """Add log-normal noise to morning prices (market noise)."""
    noise = rng.standard_normal(len(odds))
    return odds * np.exp(sigma * noise)


def round_to_uk_odds(decimal_odds: float) -> float:
    """
    Round decimal odds to realistic UK bookmaker increments.
    e.g. 1.5, 1.75, 2.0, 2.25, 2.5, 3.0, 3.5, 4.0, 5.0, 6.0, 7.0, 8.0,
         10.0, 12.0, 14.0, 16.0, 20.0, 25.0, 33.0, 40.0, 50.0, 66.0, 100.0
    """
    grid = [
        1.25, 1.33, 1.40, 1.50, 1.57, 1.67, 1.80, 2.00, 2.10, 2.20, 2.25,
        2.38, 2.50, 2.63, 2.75, 3.00, 3.25, 3.50, 4.00, 4.50, 5.00, 5.50,
        6.00, 6.50, 7.00, 8.00, 9.00, 10.0, 11.0, 12.0, 13.0, 14.0, 16.0,
        18.0, 20.0, 25.0, 33.0, 40.0, 50.0, 66.0, 80.0, 100.0,
    ]
    arr = np.array(grid)
    idx = np.argmin(np.abs(arr - decimal_odds))
    return float(arr[idx])


def generate_field_odds(
    runner_count: int,
    rng: NpRng,
    temperature: float = 1.2,
    overround_range: tuple[float, float] = (1.10, 1.18),
    sigma: float = 0.15,
    market_mover: bool = False,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Generate morning price and SP for a field of runners.

    Returns:
        latent_abilities: shape (runner_count,) - used for result sampling
        sp_odds: shape (runner_count,) - starting price decimal odds
    """
    # Latent ability scores
    abilities = rng.standard_normal(runner_count)

    # Win probabilities
    probs = softmax(abilities, temperature=temperature)

    # Overround
    overround = rng.uniform(*overround_range)

    # Morning prices (early odds before market)
    morning_raw = probs_to_odds(probs, overround)
    morning_noisy = add_odds_noise(morning_raw, rng, sigma=sigma * 1.5)
    morning_prices = np.array([round_to_uk_odds(o) for o in morning_noisy])

    # SP: drift or shorten from morning price
    if market_mover:
        # One horse shortens significantly (market support)
        mover_idx = rng.integers(0, runner_count)
        sp_raw = morning_noisy.copy()
        sp_raw[mover_idx] *= rng.uniform(0.55, 0.75)  # shortens 25-45%
    else:
        sp_raw = add_odds_noise(morning_noisy, rng, sigma=sigma)

    sp_odds = np.array([round_to_uk_odds(o) for o in sp_raw])

    return abilities, morning_prices, sp_odds


def generate_odds_history(
    runner_count: int,
    morning_prices: np.ndarray,
    sp_odds: np.ndarray,
    rng: NpRng,
    n_updates: int = 4,
    race_time: str = "14:30",
) -> list[dict]:
    """
    Generate n_updates intermediate price points between morning and SP.
    Returns list of {runner_cloth, hours_before, odds, movement} dicts.
    """
    from datetime import datetime, timedelta

    # Parse race time
    h, m = map(int, race_time.split(":"))
    race_dt = datetime(2000, 1, 1, h, m, 0)  # dummy date, relative times

    records = []
    hours_offsets = sorted(rng.uniform(0.5, 4.0, n_updates), reverse=True)

    for runner_idx in range(runner_count):
        start = morning_prices[runner_idx]
        end = sp_odds[runner_idx]
        # Interpolate with noise
        prices_interp = np.linspace(start, end, n_updates + 2)
        prices_interp += rng.standard_normal(n_updates + 2) * 0.05 * start
        prices_interp = np.clip(prices_interp, 1.1, 200.0)

        prev_odds = start
        for i, hours in enumerate(hours_offsets):
            odds = float(round_to_uk_odds(prices_interp[i + 1]))
            if odds < prev_odds - 0.1:
                movement = "shorten"
            elif odds > prev_odds + 0.1:
                movement = "drift"
            else:
                movement = "stable"
            records.append({
                "runner_cloth_idx": runner_idx,
                "hours_before": hours,
                "odds": odds,
                "movement": movement,
            })
            prev_odds = odds

    return records


def sample_race_result(latent_abilities: np.ndarray, rng: NpRng) -> list[int]:
    """
    Sample finishing positions from latent abilities.
    Returns list of runner indices ordered 1st, 2nd, 3rd, ...
    """
    # Race day noise
    race_day = rng.standard_normal(len(latent_abilities)) * 0.4
    final_scores = latent_abilities + race_day
    # Higher score = better finishing position
    return list(np.argsort(-final_scores))
