"""
Performance Monitor.

Writes daily performance snapshots to strategy_performance table.
"""
import sqlite3
from datetime import datetime

from performance.metrics import summarise_strategy


class PerformanceMonitor:
    def __init__(self, db_path: str):
        self.db_path = db_path

    def record_day(self, sim_day: int, strategy_ids: list[int]) -> None:
        """Update cumulative strategy_performance for all strategies."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        now = datetime.utcnow().isoformat()

        for sid in strategy_ids:
            bets = conn.execute(
                """SELECT b.stake, b.payout, b.status, b.odds_taken
                   FROM bets b
                   JOIN races r ON b.race_id = r.id
                   WHERE b.strategy_id=? AND b.status != 'pending'
                     AND r.sim_day <= ?""",
                (sid, sim_day),
            ).fetchall()

            bets = [dict(b) for b in bets]
            if not bets:
                continue

            summary = summarise_strategy(bets)

            conn.execute(
                """INSERT OR REPLACE INTO strategy_performance
                   (strategy_id, sim_day, total_bets, wins, roi, strike_rate,
                    sharpe, max_drawdown, profit_loss, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (sid, sim_day,
                 summary["total_bets"],
                 summary["wins"],
                 summary["roi"],
                 summary["strike_rate"],
                 summary["sharpe"],
                 summary["max_drawdown"],
                 summary["profit_loss"],
                 now),
            )

        conn.commit()
        conn.close()

    def get_latest_performance(self, strategy_id: int) -> dict | None:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            """SELECT * FROM strategy_performance
               WHERE strategy_id=?
               ORDER BY sim_day DESC LIMIT 1""",
            (strategy_id,),
        ).fetchone()
        conn.close()
        return dict(row) if row else None
