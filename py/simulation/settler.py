"""
Bet Settler.

After race results are generated, settle all pending bets for that day:
  - win: runner must finish 1st
  - place: runner must finish 1st, 2nd, or 3rd (depending on field size)
  - exacta: runners finish 1st and 2nd in exact order
  - trifecta: runners finish 1st, 2nd, 3rd in exact order
  - dutch: any of the selected runners finishes 1st
"""
import sqlite3
import json
from datetime import datetime


PLACE_TERMS = {
    # field_size: (place_positions, place_fraction)
    (0, 4):  (0, 0),       # no place betting
    (5, 7):  (2, 0.25),    # top 2, quarter odds
    (8, 15): (3, 0.20),    # top 3, 1/5 odds
    (16, 99): (4, 0.25),   # top 4, 1/4 odds (handicap style)
}


def get_place_terms(field_size: int) -> tuple[int, float]:
    for (lo, hi), terms in PLACE_TERMS.items():
        if lo <= field_size <= hi:
            return terms
    return (3, 0.20)


def settle_day(sim_day: int, db_path: str) -> dict:
    """
    Settle all pending bets for races on sim_day.
    Returns summary: {total_bets, wins, losses, voids, total_staked, total_returned}
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    races = conn.execute(
        "SELECT id, runner_count FROM races WHERE sim_day=?", (sim_day,)
    ).fetchall()
    race_ids = [r["id"] for r in races]
    race_field_sizes = {r["id"]: r["runner_count"] for r in races}

    if not race_ids:
        conn.close()
        return {"total_bets": 0}

    placeholders = ",".join("?" * len(race_ids))
    bets = conn.execute(
        f"""SELECT b.id, b.strategy_id, b.race_id, b.bet_type, b.runner_ids,
                   b.stake, b.odds_taken, b.potential_return
            FROM bets b
            WHERE b.race_id IN ({placeholders}) AND b.status='pending'""",
        race_ids,
    ).fetchall()

    # Build result lookup: race_id -> {runner_id: position}
    result_lookup: dict[int, dict[int, int]] = {}
    for race_id in race_ids:
        rows = conn.execute(
            "SELECT runner_id, position FROM race_results WHERE race_id=?",
            (race_id,)
        ).fetchall()
        result_lookup[race_id] = {r["runner_id"]: r["position"] for r in rows}

    # Build runner cloth → runner_id lookup per race
    cloth_lookup: dict[int, dict[int, int]] = {}
    for race_id in race_ids:
        rows = conn.execute(
            "SELECT id, cloth_number FROM runners WHERE race_id=?",
            (race_id,)
        ).fetchall()
        cloth_lookup[race_id] = {r["cloth_number"]: r["id"] for r in rows}

    total_bets = 0
    wins = 0
    losses = 0
    voids = 0
    total_staked = 0.0
    total_returned = 0.0
    now = datetime.utcnow().isoformat()

    for bet in bets:
        race_id = bet["race_id"]
        bet_type = bet["bet_type"]
        runner_cloths = json.loads(bet["runner_ids"])
        stake = bet["stake"]
        odds_taken = bet["odds_taken"]

        positions = result_lookup.get(race_id, {})
        cloth_map = cloth_lookup.get(race_id, {})
        field_size = race_field_sizes.get(race_id, 8)

        # Map cloth numbers to runner IDs → positions
        runner_positions = []
        for cloth in runner_cloths:
            runner_id = cloth_map.get(cloth)
            if runner_id:
                pos = positions.get(runner_id)
                runner_positions.append(pos)
            else:
                runner_positions.append(None)

        won, payout = _evaluate_bet(bet_type, runner_positions, stake, odds_taken, field_size)

        if payout is None:
            status = "void"
            payout = stake  # refund on void
            voids += 1
        elif won:
            status = "won"
            wins += 1
        else:
            status = "lost"
            payout = 0.0
            losses += 1

        conn.execute(
            """UPDATE bets SET status=?, payout=?, settled_at=? WHERE id=?""",
            (status, payout, now, bet["id"]),
        )

        total_bets += 1
        total_staked += stake
        total_returned += payout

    conn.commit()
    conn.close()

    return {
        "total_bets": total_bets,
        "wins": wins,
        "losses": losses,
        "voids": voids,
        "total_staked": total_staked,
        "total_returned": total_returned,
        "profit_loss": total_returned - total_staked,
    }


def _evaluate_bet(
    bet_type: str,
    runner_positions: list,
    stake: float,
    odds_taken: float,
    field_size: int,
) -> tuple[bool, float]:
    """
    Returns (won: bool, payout: float).
    Returns (False, None) for void bets.
    """
    if any(p is None for p in runner_positions):
        return False, None

    if bet_type == "win":
        won = runner_positions[0] == 1
        payout = stake * odds_taken if won else 0.0
        return won, payout

    elif bet_type == "place":
        place_positions, fraction = get_place_terms(field_size)
        if place_positions == 0:
            return False, None
        won = runner_positions[0] <= place_positions
        place_odds = 1.0 + (odds_taken - 1.0) * fraction
        payout = stake * place_odds if won else 0.0
        return won, payout

    elif bet_type == "dutch":
        # Any runner finishes 1st
        won = 1 in runner_positions
        payout = stake * odds_taken if won else 0.0
        return won, payout

    elif bet_type == "exacta":
        if len(runner_positions) < 2:
            return False, None
        won = runner_positions[0] == 1 and runner_positions[1] == 2
        payout = stake * odds_taken if won else 0.0
        return won, payout

    elif bet_type == "trifecta":
        if len(runner_positions) < 3:
            return False, None
        won = (
            runner_positions[0] == 1 and
            runner_positions[1] == 2 and
            runner_positions[2] == 3
        )
        payout = stake * odds_taken if won else 0.0
        return won, payout

    return False, None
