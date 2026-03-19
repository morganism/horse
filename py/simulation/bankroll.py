"""
Bankroll manager per strategy.

Each strategy starts with its own £1000 allocation.
The bankroll tracks running balance and enforces bet limits.
"""
import sqlite3
from datetime import datetime


class Bankroll:
    """
    Manages a single strategy's bankroll.

    Balances are persisted to bankroll_snapshots after each day.
    """

    def __init__(
        self,
        strategy_id: int,
        db_path: str,
        initial_balance: float = 1000.0,
        max_bet_fraction: float = 0.05,
        min_stake: float = 0.10,
    ):
        self.strategy_id = strategy_id
        self.db_path = db_path
        self.initial_balance = initial_balance
        self.max_bet_fraction = max_bet_fraction
        self.min_stake = min_stake

        self._balance = initial_balance
        self._day_staked = 0.0
        self._day_returned = 0.0

    @property
    def balance(self) -> float:
        return self._balance

    def max_stake(self) -> float:
        """Maximum allowed single stake."""
        return max(self.min_stake, self._balance * self.max_bet_fraction)

    def can_afford(self, stake: float) -> bool:
        return stake >= self.min_stake and stake <= self._balance

    def place_bet(self, stake: float) -> bool:
        """Deduct stake. Returns False if insufficient funds."""
        if not self.can_afford(stake):
            return False
        self._balance -= stake
        self._day_staked += stake
        return True

    def credit(self, amount: float) -> None:
        """Credit payout (can be 0 for losses)."""
        self._balance += amount
        self._day_returned += amount

    def settle_bets_from_db(self, sim_day: int) -> None:
        """
        Read all settled bets for this strategy/day from DB and
        update balance accordingly (used when reloading state).
        """
        conn = sqlite3.connect(self.db_path)
        rows = conn.execute(
            """SELECT b.stake, b.payout, b.status
               FROM bets b
               JOIN races r ON b.race_id = r.id
               WHERE b.strategy_id=? AND r.sim_day=? AND b.status != 'pending'""",
            (self.strategy_id, sim_day),
        ).fetchall()
        conn.close()

        for row in rows:
            stake, payout, status = row
            if status in ("won", "lost", "void"):
                payout = payout or 0.0
                self._balance += payout - stake  # net effect

    def reset_day_counters(self) -> None:
        self._day_staked = 0.0
        self._day_returned = 0.0

    def snapshot(self, sim_day: int, total_staked: float, total_returned: float) -> None:
        """Write balance snapshot to DB."""
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            """INSERT INTO bankroll_snapshots
               (sim_day, strategy_id, balance, total_staked, total_returned, snapshot_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (sim_day, self.strategy_id, self._balance, total_staked, total_returned,
             datetime.utcnow().isoformat()),
        )
        conn.commit()
        conn.close()

    def day_pl(self) -> float:
        return self._day_returned - self._day_staked
