"""
Daily simulation loop.

Orchestrates one day of racing:
  1. Generate races, runners, odds history
  2. For each race: each strategy selects bets
  3. Persist bets (debit bankrolls)
  4. Generate results
  5. Settle bets (credit bankrolls)
  6. Update Bayesian hypotheses
  7. Snapshot performance
"""
import json
import sqlite3
from datetime import date, datetime

from strategies.base import BetInstruction, Strategy
from simulation.bankroll import Bankroll
from simulation.settler import settle_day
from data.generator import SyntheticDataGenerator


def _load_race_runners(conn: sqlite3.Connection, race_id: int) -> tuple[dict, list[dict], list[dict]]:
    """Load race dict, list of runner dicts, and odds history dicts."""
    race = conn.execute("SELECT * FROM races WHERE id=?", (race_id,)).fetchone()
    if not race:
        return None, [], []

    # Enrich runners with horse name
    runners_raw = conn.execute(
        """SELECT r.*, h.name AS horse_name, h.trainer AS horse_trainer
           FROM runners r JOIN horses h ON r.horse_id = h.id
           WHERE r.race_id=?""",
        (race_id,),
    ).fetchall()

    runners = []
    for row in runners_raw:
        d = dict(row)
        if not d.get("trainer"):
            d["trainer"] = d.get("horse_trainer") or ""
        runners.append(d)

    odds_history = conn.execute(
        "SELECT * FROM odds_history WHERE race_id=?", (race_id,)
    ).fetchall()

    return dict(race), [dict(r) for r in runners], [dict(o) for o in odds_history]


def run_day(
    sim_day: int,
    race_date: date,
    generator: SyntheticDataGenerator,
    strategies: list[Strategy],
    bankrolls: dict[int, Bankroll],  # strategy_id -> Bankroll
    strategy_id_map: dict[str, int],  # variant_name -> strategy_id
    db_path: str,
    max_bet_fraction: float = 0.05,
    min_stake: float = 0.10,
) -> dict:
    """
    Run a single simulation day. Returns day summary dict.
    """
    # ── 1. Generate races ───────────────────────────────────────────────────
    race_ids = generator.generate_day(sim_day, race_date)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    # ── 2. Place bets ───────────────────────────────────────────────────────
    bets_placed = 0
    now = datetime.utcnow().isoformat()

    for race_id in race_ids:
        race, runners, odds_history = _load_race_runners(conn, race_id)
        if not race or not runners:
            continue

        for strategy in strategies:
            strategy_id = strategy_id_map.get(strategy.name)
            if not strategy_id:
                continue

            bankroll = bankrolls.get(strategy_id)
            if not bankroll or bankroll.balance < min_stake:
                continue

            try:
                instructions = strategy.select_bets(race, runners, odds_history)
            except Exception:
                continue

            for instr in instructions:
                stake = _calculate_stake(instr, bankroll, max_bet_fraction, min_stake)
                if stake < min_stake:
                    continue
                if not bankroll.place_bet(stake):
                    continue

                runner_ids = _cloth_to_ids(instr.runner_cloth_numbers, runners)
                if not runner_ids:
                    bankroll.credit(stake)  # refund
                    continue

                potential_return = stake * instr.odds_estimate

                conn.execute(
                    """INSERT INTO bets
                       (strategy_id, race_id, bet_type, runner_ids, stake,
                        odds_taken, potential_return, status, rationale, placed_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?)""",
                    (strategy_id, race_id, instr.bet_type,
                     json.dumps(instr.runner_cloth_numbers),
                     stake, instr.odds_estimate, potential_return,
                     instr.rationale[:500] if instr.rationale else None, now),
                )
                bets_placed += 1

    conn.commit()
    conn.close()

    # ── 3. Generate results ─────────────────────────────────────────────────
    generator.generate_results(sim_day)

    # ── 4. Settle bets ──────────────────────────────────────────────────────
    settlement = settle_day(sim_day, db_path)

    # ── 5. Credit bankrolls ─────────────────────────────────────────────────
    _credit_bankrolls(sim_day, db_path, bankrolls, strategy_id_map)

    return {
        "sim_day": sim_day,
        "race_date": race_date.isoformat(),
        "races_generated": len(race_ids),
        "bets_placed": bets_placed,
        **settlement,
    }


def _calculate_stake(
    instr: BetInstruction,
    bankroll: Bankroll,
    max_bet_fraction: float,
    min_stake: float,
) -> float:
    """Convert stake_fraction to £ amount, respecting bankroll limits."""
    raw_stake = bankroll.balance * instr.stake_fraction
    # For exotic bets with many combos, cap aggressively
    if instr.bet_type in ("exacta", "trifecta"):
        raw_stake = min(raw_stake, bankroll.balance * 0.002)
    capped = min(raw_stake, bankroll.max_stake())
    return round(max(min_stake, capped), 2)


def _cloth_to_ids(cloth_numbers: list, runners: list[dict]) -> list[int]:
    """Map cloth numbers to runner IDs."""
    cloth_map = {r["cloth_number"]: r["id"] for r in runners}
    ids = []
    for cloth in cloth_numbers:
        rid = cloth_map.get(cloth)
        if rid:
            ids.append(rid)
    return ids if len(ids) == len(cloth_numbers) else []


def _credit_bankrolls(
    sim_day: int,
    db_path: str,
    bankrolls: dict[int, Bankroll],
    strategy_id_map: dict[str, int],
) -> None:
    """
    For each strategy, sum all payouts on sim_day's settled bets and credit.
    Also resets day counters and writes snapshot.
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    strategy_ids = list(bankrolls.keys())
    if not strategy_ids:
        conn.close()
        return

    ph = ",".join("?" * len(strategy_ids))
    rows = conn.execute(
        f"""SELECT b.strategy_id, SUM(b.stake) AS total_staked,
                   SUM(COALESCE(b.payout, 0)) AS total_returned
            FROM bets b
            JOIN races r ON b.race_id = r.id
            WHERE r.sim_day=? AND b.strategy_id IN ({ph})
              AND b.status != 'pending'
            GROUP BY b.strategy_id""",
        [sim_day] + strategy_ids,
    ).fetchall()
    conn.close()

    for row in rows:
        sid = row["strategy_id"]
        br = bankrolls.get(sid)
        if br:
            # The stake was already debited when placed; add back the payout
            payout = row["total_returned"] or 0.0
            br.credit(payout)
            br.snapshot(sim_day, row["total_staked"] or 0, payout)
            br.reset_day_counters()
