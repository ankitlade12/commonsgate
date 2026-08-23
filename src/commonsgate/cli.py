from __future__ import annotations

import argparse
import json

from .simulator import run_demo


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the CommonsGate fairness proof")
    parser.add_argument("--population", type=int, default=200)
    parser.add_argument("--capacity", type=int, default=20)
    parser.add_argument("--seed", default="demo-seed-v1")
    parser.add_argument("--compact", action="store_true")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    report = run_demo(
        population_size=args.population, capacity=args.capacity, seed=args.seed
    )
    print(
        json.dumps(report.as_dict(), indent=None if args.compact else 2, sort_keys=True)
    )


if __name__ == "__main__":
    main()
