"""
Performance metrics for strategy evaluation.

All functions operate on sequences of plain Python numbers or dicts
fetched from the DB — no external dependencies beyond math/statistics.
"""
import math
import statistics
from typing import Optional


def roi(total_staked: float, total_returned: float) -> Optional[float]:
    """Return on Investment as a fraction. 0.05 = 5% profit."""
    if total_staked <= 0:
        return None
    return (total_returned - total_staked) / total_staked


def strike_rate(n_bets: int, n_wins: int) -> Optional[float]:
    """Fraction of bets that won."""
    if n_bets <= 0:
        return None
    return n_wins / n_bets


def avg_winning_odds(bets: list[dict]) -> Optional[float]:
    """Average decimal odds of winning bets."""
    winning_odds = [b["odds_taken"] for b in bets if b.get("status") == "won"]
    return statistics.mean(winning_odds) if winning_odds else None


def profit_loss_series(bets: list[dict]) -> list[float]:
    """
    Per-bet profit/loss series.
    Won: payout - stake. Lost: -stake. Void: 0.
    """
    series = []
    for b in bets:
        stake = b.get("stake", 0)
        if b.get("status") == "won":
            series.append((b.get("payout") or 0) - stake)
        elif b.get("status") == "lost":
            series.append(-stake)
        # void and pending contribute 0
    return series


def cumulative_balance(initial: float, pl_series: list[float]) -> list[float]:
    """Running balance starting from initial."""
    balance = initial
    result = [balance]
    for pl in pl_series:
        balance += pl
        result.append(balance)
    return result


def max_drawdown(balance_series: list[float]) -> float:
    """
    Maximum peak-to-trough drawdown in absolute terms.
    O(n) implementation.
    """
    if not balance_series:
        return 0.0
    peak = balance_series[0]
    max_dd = 0.0
    for val in balance_series[1:]:
        if val > peak:
            peak = val
        dd = peak - val
        if dd > max_dd:
            max_dd = dd
    return max_dd


def max_drawdown_pct(balance_series: list[float]) -> float:
    """Maximum drawdown as a percentage of peak balance."""
    if not balance_series or balance_series[0] <= 0:
        return 0.0
    peak = balance_series[0]
    max_dd_pct = 0.0
    for val in balance_series[1:]:
        if val > peak:
            peak = val
        if peak > 0:
            dd_pct = (peak - val) / peak
            if dd_pct > max_dd_pct:
                max_dd_pct = dd_pct
    return max_dd_pct


def sharpe_ratio(daily_pl: list[float], periods_per_year: float = 252) -> Optional[float]:
    """
    Simplified Sharpe ratio (no risk-free rate).
    Uses daily P&L series; annualises using periods_per_year.
    """
    if len(daily_pl) < 2:
        return None
    try:
        mean = statistics.mean(daily_pl)
        std = statistics.stdev(daily_pl)
    except statistics.StatisticsError:
        return None
    if std == 0:
        return None
    return (mean / std) * math.sqrt(periods_per_year)


def expected_value(odds: float, win_prob: float, stake: float = 1.0) -> float:
    """
    EV = (win_prob * (odds - 1) * stake) - ((1 - win_prob) * stake)
       = stake * (win_prob * odds - 1)
    """
    return stake * (win_prob * odds - 1.0)


def kelly_fraction(win_prob: float, decimal_odds: float) -> float:
    """
    Full Kelly fraction: f* = (bp - q) / b
    where b = decimal_odds - 1, p = win_prob, q = 1 - win_prob.
    Returns 0 if bet has negative edge.
    """
    b = decimal_odds - 1.0
    if b <= 0:
        return 0.0
    p = win_prob
    q = 1.0 - p
    k = (b * p - q) / b
    return max(0.0, k)


def summarise_strategy(bets: list[dict], initial_balance: float = 1000.0) -> dict:
    """
    Full performance summary for a strategy given its bet history.
    """
    total_bets = len([b for b in bets if b.get("status") != "pending"])
    n_wins = sum(1 for b in bets if b.get("status") == "won")
    total_staked = sum(b.get("stake", 0) for b in bets if b.get("status") != "pending")
    total_returned = sum(
        b.get("payout") or 0 for b in bets if b.get("status") in ("won", "void")
    )

    pl_seq = profit_loss_series(bets)
    balance_seq = cumulative_balance(initial_balance, pl_seq)

    return {
        "total_bets":      total_bets,
        "wins":            n_wins,
        "strike_rate":     strike_rate(total_bets, n_wins),
        "total_staked":    round(total_staked, 2),
        "total_returned":  round(total_returned, 2),
        "profit_loss":     round(total_returned - total_staked, 2),
        "roi":             roi(total_staked, total_returned),
        "avg_win_odds":    avg_winning_odds(bets),
        "max_drawdown":    round(max_drawdown(balance_seq), 2),
        "max_drawdown_pct": round(max_drawdown_pct(balance_seq) * 100, 2),
        "sharpe":          sharpe_ratio(pl_seq),
        "final_balance":   round(balance_seq[-1], 2) if balance_seq else initial_balance,
    }
