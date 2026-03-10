#!/usr/bin/env python3

from pathlib import Path

from generate_memory_benchmarks import generate_profiles


def main() -> None:
    root = Path(__file__).resolve().parent
    generate_profiles(root, ["issue297"])


if __name__ == "__main__":
    main()
