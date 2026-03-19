"""
Performance Report.

Console report using rich tables. Also supports CSV export.
"""
import csv
import sqlite3
from io import StringIO

try:
    from rich.console import Console
    from rich.table import Table
    from rich import box
    HAS_RICH = True
except ImportError:
    HAS_RICH = False


def _load_strategy_perf(db_path: str, sim_day: int | None = None) -> list[dict]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    if sim_day:
        rows = conn.execute(
            """SELECT sp.*, s.strategy_class, s.variant_name
               FROM strategy_performance sp
               JOIN strategies s ON sp.strategy_id = s.id
               WHERE sp.sim_day=?
               ORDER BY sp.roi DESC NULLS LAST""",
            (sim_day,),
        ).fetchall()
    else:
        # Latest snapshot per strategy
        rows = conn.execute(
            """SELECT sp.*, s.strategy_class, s.variant_name
               FROM strategy_performance sp
               JOIN strategies s ON sp.strategy_id = s.id
               WHERE sp.sim_day = (
                   SELECT MAX(sim_day) FROM strategy_performance sp2
                   WHERE sp2.strategy_id = sp.strategy_id
               )
               ORDER BY sp.roi DESC NULLS LAST""",
        ).fetchall()

    conn.close()
    return [dict(r) for r in rows]


def _fmt_pct(v) -> str:
    if v is None:
        return "—"
    return f"{v*100:.1f}%"


def _fmt_float(v, decimals: int = 2) -> str:
    if v is None:
        return "—"
    return f"{v:.{decimals}f}"


def print_report(
    db_path: str,
    top_n: int = 30,
    sort_by: str = "roi",
    sim_day: int | None = None,
) -> None:
    rows = _load_strategy_perf(db_path, sim_day)

    # Sort
    rev = sort_by not in ("max_drawdown",)
    rows = sorted(
        rows,
        key=lambda r: (r.get(sort_by) or -9999 if rev else r.get(sort_by) or 9999),
        reverse=rev,
    )[:top_n]

    if HAS_RICH:
        _print_rich(rows)
    else:
        _print_plain(rows)


def _print_rich(rows: list[dict]) -> None:
    console = Console()
    table = Table(
        title="Strategy Performance Report",
        box=box.ROUNDED,
        show_header=True,
        header_style="bold cyan",
    )
    cols = [
        ("Rank",        "right"),
        ("Strategy",    "left"),
        ("Class",       "left"),
        ("Bets",        "right"),
        ("Wins",        "right"),
        ("Strike",      "right"),
        ("ROI",         "right"),
        ("P&L (£)",     "right"),
        ("Sharpe",      "right"),
        ("Drawdown",    "right"),
    ]
    for name, justify in cols:
        table.add_column(name, justify=justify)

    for i, r in enumerate(rows, 1):
        roi_str = _fmt_pct(r.get("roi"))
        roi_style = "green" if (r.get("roi") or 0) > 0 else "red"
        pl = r.get("profit_loss") or 0
        pl_str = f"{'+'if pl>0 else ''}{pl:.2f}"
        pl_style = "green" if pl > 0 else "red"

        table.add_row(
            str(i),
            (r.get("variant_name") or "")[:35],
            r.get("strategy_class") or "",
            str(r.get("total_bets") or 0),
            str(r.get("wins") or 0),
            _fmt_pct(r.get("strike_rate")),
            f"[{roi_style}]{roi_str}[/{roi_style}]",
            f"[{pl_style}]{pl_str}[/{pl_style}]",
            _fmt_float(r.get("sharpe")),
            f"£{_fmt_float(r.get('max_drawdown'))}",
        )

    console.print(table)


def _print_plain(rows: list[dict]) -> None:
    header = f"{'#':>3} {'Strategy':<36} {'Class':<22} {'Bets':>6} {'Wins':>5} {'Strike':>7} {'ROI':>8} {'P&L':>9} {'Sharpe':>7}"
    print(header)
    print("-" * len(header))
    for i, r in enumerate(rows, 1):
        pl = r.get("profit_loss") or 0
        print(
            f"{i:>3} {(r.get('variant_name') or ''):<36} "
            f"{(r.get('strategy_class') or ''):<22} "
            f"{(r.get('total_bets') or 0):>6} "
            f"{(r.get('wins') or 0):>5} "
            f"{_fmt_pct(r.get('strike_rate')):>7} "
            f"{_fmt_pct(r.get('roi')):>8} "
            f"{'+'if pl>0 else ''}{pl:>8.2f} "
            f"{_fmt_float(r.get('sharpe')):>7}"
        )


def export_csv(db_path: str, output_path: str, sim_day: int | None = None) -> None:
    rows = _load_strategy_perf(db_path, sim_day)
    if not rows:
        print("No data to export.")
        return
    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    print(f"Exported {len(rows)} rows to {output_path}")


def summary_by_class(db_path: str) -> None:
    """Print aggregated performance by strategy class."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    rows = conn.execute(
        """SELECT s.strategy_class,
                  COUNT(*) AS variants,
                  SUM(sp.total_bets) AS total_bets,
                  SUM(sp.wins) AS total_wins,
                  AVG(sp.roi) AS avg_roi,
                  SUM(sp.profit_loss) AS total_pl,
                  MAX(sp.roi) AS best_roi
           FROM strategy_performance sp
           JOIN strategies s ON sp.strategy_id = s.id
           WHERE sp.sim_day = (
               SELECT MAX(sim_day) FROM strategy_performance sp2
               WHERE sp2.strategy_id = sp.strategy_id
           )
           GROUP BY s.strategy_class
           ORDER BY avg_roi DESC""",
    ).fetchall()
    conn.close()

    print(f"\n{'Class':<25} {'Variants':>8} {'Bets':>8} {'Wins':>6} {'Avg ROI':>9} {'Total P&L':>12} {'Best ROI':>9}")
    print("-" * 82)
    for r in rows:
        avg_roi = r["avg_roi"]
        best_roi = r["best_roi"]
        pl = r["total_pl"] or 0
        print(
            f"{r['strategy_class']:<25} {r['variants']:>8} {r['total_bets']:>8} "
            f"{r['total_wins']:>6} {_fmt_pct(avg_roi):>9} "
            f"{'+'if pl>0 else ''}£{pl:>10.2f} {_fmt_pct(best_roi):>9}"
        )
