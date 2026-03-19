#!/usr/bin/env python3
"""
Horse Racing Strategy Simulation CLI.

Usage:
    python cli.py init [--db PATH]
    python cli.py simulate [--days N] [--bankroll AMOUNT] [--seed N] [--db PATH]
    python cli.py report [--top N] [--sort FIELD] [--day N] [--db PATH]
    python cli.py report-class [--db PATH]
    python cli.py export [--out FILE] [--db PATH]
    python cli.py strategies [--db PATH]
    python cli.py correlations [--db PATH]
    python cli.py reset --confirm [--db PATH]
"""
import argparse
import sys
from pathlib import Path

# Make sure py/ is on the path when run directly
sys.path.insert(0, str(Path(__file__).parent))

from config.settings import Config, DEFAULT_DB
from db.connection import apply_schema


def cmd_init(args) -> None:
    print(f"Initialising database at {args.db}")
    apply_schema(args.db)
    print("Schema applied.")

    from data.generator import SyntheticDataGenerator
    gen = SyntheticDataGenerator(args.db)
    gen.seed_venues()
    print(f"Seeded {len(gen._venue_ids)} venues.")
    gen.seed_horses(pool_size=500)
    print(f"Seeded {len(gen._horse_pool)} horses.")

    from strategies.registry import build_registry, save_registry
    strategies = build_registry(db_path=args.db)
    id_map = save_registry(strategies, args.db)
    print(f"Registered {len(id_map)} strategy variants.")


def cmd_simulate(args) -> None:
    cfg = Config(
        db_path=args.db,
        initial_bankroll=args.bankroll,
        sim_days=args.days,
        random_seed=args.seed,
    )
    from simulation.runner import SimulationRunner
    runner = SimulationRunner(cfg)
    runner.run(verbose=not args.quiet)


def cmd_report(args) -> None:
    from performance.report import print_report
    print_report(
        db_path=args.db,
        top_n=args.top,
        sort_by=args.sort,
        sim_day=args.day,
    )


def cmd_report_class(args) -> None:
    from performance.report import summary_by_class
    summary_by_class(args.db)


def cmd_export(args) -> None:
    from performance.report import export_csv
    export_csv(args.db, args.out)
    print(f"Exported to {args.out}")


def cmd_strategies(args) -> None:
    import sqlite3
    conn = sqlite3.connect(args.db)
    rows = conn.execute(
        "SELECT strategy_class, COUNT(*) AS n FROM strategies GROUP BY strategy_class ORDER BY n DESC"
    ).fetchall()
    conn.close()
    total = 0
    print(f"\n{'Strategy Class':<30} {'Variants':>10}")
    print("-" * 42)
    for r in rows:
        print(f"{r[0]:<30} {r[1]:>10}")
        total += r[1]
    print("-" * 42)
    print(f"{'TOTAL':<30} {total:>10}")


def cmd_correlations(args) -> None:
    from bayesian.correlations import CorrelationAnalyser
    analyser = CorrelationAnalyser(args.db)
    result = analyser.analyse_all()

    print("\n=== Beta Horses (consistent dominance patterns) ===")
    for pair in result["beta_horses"][:10]:
        print(f"  {pair['dominant']} dominates {pair['beta']}: "
              f"{pair['dominance_pct']}% over {pair['meetings']} meetings")

    print("\n=== Top Trainer-Jockey Combos ===")
    for combo in result["top_trainer_jockey"][:10]:
        print(f"  {combo['trainer']} / {combo['jockey']}: "
              f"{combo['win_rate']:.1%} ({combo['wins']}/{combo['runs']})")

    print("\n=== Going Preference Highlights ===")
    for pref in result["going_preference"][:10]:
        print(f"  {pref['horse']} on {pref['going']}: "
              f"{pref['win_rate']:.1%} ({pref['wins']}/{pref['runs']})")


def cmd_reset(args) -> None:
    if not args.confirm:
        print("Requires --confirm flag. This will DROP all data.")
        sys.exit(1)
    import sqlite3, os
    if Path(args.db).exists():
        os.remove(args.db)
        print(f"Deleted {args.db}")
    apply_schema(args.db)
    print("Fresh schema applied.")


def main():
    parser = argparse.ArgumentParser(
        description="Horse Racing Strategy Simulation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--db", default=str(DEFAULT_DB), help="SQLite database path")

    sub = parser.add_subparsers(dest="command", required=True)

    # init
    sub.add_parser("init", help="Initialise DB, seed venues/horses, register strategies")

    # simulate
    p_sim = sub.add_parser("simulate", help="Run N-day simulation")
    p_sim.add_argument("--days",     type=int,   default=30,     help="Number of simulation days")
    p_sim.add_argument("--bankroll", type=float, default=1000.0, help="Starting bankroll per strategy (£)")
    p_sim.add_argument("--seed",     type=int,   default=42,     help="Random seed")
    p_sim.add_argument("--quiet",    action="store_true",         help="Suppress verbose output")

    # report
    p_rep = sub.add_parser("report", help="Print strategy performance table")
    p_rep.add_argument("--top",  type=int,   default=30,   help="Top N strategies to show")
    p_rep.add_argument("--sort", default="roi",             help="Sort column: roi|profit_loss|sharpe|total_bets")
    p_rep.add_argument("--day",  type=int,   default=None, help="Show performance for specific sim day")

    # report-class
    sub.add_parser("report-class", help="Aggregated performance by strategy class")

    # export
    p_exp = sub.add_parser("export", help="Export performance to CSV")
    p_exp.add_argument("--out", default="strategy_performance.csv", help="Output CSV path")

    # strategies
    sub.add_parser("strategies", help="List registered strategy variants")

    # correlations
    sub.add_parser("correlations", help="Show Bayesian correlation findings")

    # reset
    p_reset = sub.add_parser("reset", help="Delete and recreate database (destructive!)")
    p_reset.add_argument("--confirm", action="store_true")

    args = parser.parse_args()

    commands = {
        "init":         cmd_init,
        "simulate":     cmd_simulate,
        "report":       cmd_report,
        "report-class": cmd_report_class,
        "export":       cmd_export,
        "strategies":   cmd_strategies,
        "correlations": cmd_correlations,
        "reset":        cmd_reset,
    }
    commands[args.command](args)


if __name__ == "__main__":
    main()
