#!/usr/bin/env python3

"""Validate consistency between benchmark raw.csv and summary.json."""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List


def parse_int(value: str) -> int:
    return int(str(value).strip())


def check_summary(bench_dir: Path, repo_root: Path) -> int:
    raw_path = bench_dir / "raw.csv"
    summary_path = bench_dir / "summary.json"

    if not raw_path.exists():
        print(f"error: missing benchmark raw file: {raw_path}", file=sys.stderr)
        return 2
    if not summary_path.exists():
        print(f"error: missing benchmark summary file: {summary_path}", file=sys.stderr)
        return 2

    with raw_path.open("r", encoding="utf-8", newline="") as raw_file:
        rows = list(csv.DictReader(raw_file))
    summary = json.loads(summary_path.read_text(encoding="utf-8"))

    errors: List[str] = []
    grouped: Dict[str, List[dict]] = defaultdict(list)
    failures = 0

    for row in rows:
        case = str(row.get("case", "")).strip()
        if not case:
            errors.append("raw.csv has a row with empty case name")
            continue
        grouped[case].append(row)
        if parse_int(row["exit_code"]) != 0:
            failures += 1

        stderr_rel = str(row.get("stderr_log", "")).strip()
        if stderr_rel and not (repo_root / stderr_rel).exists():
            errors.append(f"missing stderr log: {stderr_rel}")

    summary_cases = summary.get("cases", {})
    if not isinstance(summary_cases, dict):
        errors.append("summary.json: cases must be an object")
        summary_cases = {}

    overall = summary.get("overall", {})
    if not isinstance(overall, dict):
        errors.append("summary.json: overall must be an object")
        overall = {}

    if parse_int(overall.get("total_runs", -1)) != len(rows):
        errors.append(
            f"overall.total_runs mismatch: summary={overall.get('total_runs')} raw={len(rows)}"
        )
    if parse_int(overall.get("total_failures", -1)) != failures:
        errors.append(
            f"overall.total_failures mismatch: summary={overall.get('total_failures')} raw={failures}"
        )

    raw_case_names = set(grouped.keys())
    summary_case_names = set(summary_cases.keys())
    if raw_case_names != summary_case_names:
        missing_in_summary = sorted(raw_case_names - summary_case_names)
        missing_in_raw = sorted(summary_case_names - raw_case_names)
        if missing_in_summary:
            errors.append(f"cases missing in summary: {', '.join(missing_in_summary)}")
        if missing_in_raw:
            errors.append(f"cases missing in raw: {', '.join(missing_in_raw)}")

    for case in sorted(raw_case_names & summary_case_names):
        case_rows = grouped[case]
        case_summary = summary_cases[case]

        runs = len(case_rows)
        success = sum(1 for row in case_rows if parse_int(row["exit_code"]) == 0)
        failed = runs - success
        success_rate = success / float(runs)
        hashes = {
            str(row["output_sha256"])
            for row in case_rows
            if parse_int(row["exit_code"]) == 0 and str(row.get("output_sha256", "")).strip()
        }
        hash_stable = len(hashes) <= 1

        if parse_int(case_summary.get("runs", -1)) != runs:
            errors.append(
                f"{case}: runs mismatch: summary={case_summary.get('runs')} raw={runs}"
            )
        if parse_int(case_summary.get("successful_runs", -1)) != success:
            errors.append(
                f"{case}: successful_runs mismatch: summary={case_summary.get('successful_runs')} raw={success}"
            )
        if parse_int(case_summary.get("failed_runs", -1)) != failed:
            errors.append(
                f"{case}: failed_runs mismatch: summary={case_summary.get('failed_runs')} raw={failed}"
            )

        summary_rate = float(case_summary.get("success_rate", -1.0))
        if not math.isclose(summary_rate, success_rate, rel_tol=1e-9, abs_tol=1e-9):
            errors.append(
                f"{case}: success_rate mismatch: summary={summary_rate} raw={success_rate}"
            )

        summary_hash_stable = bool(case_summary.get("output_hash_stable", False))
        if summary_hash_stable != hash_stable:
            errors.append(
                f"{case}: output_hash_stable mismatch: summary={summary_hash_stable} raw={hash_stable}"
            )

    if errors:
        print("Benchmark validation: FAILED")
        for item in errors:
            print(f"- {item}")
        return 1

    print("Benchmark validation: PASSED")
    print(f"- benchmark_dir: {bench_dir}")
    print(f"- rows: {len(rows)}")
    print(f"- cases: {len(raw_case_names)}")
    print(f"- failures: {failures}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate benchmark output consistency."
    )
    parser.add_argument(
        "--bench-dir",
        default="out/bench/latest",
        help="Directory containing raw.csv and summary.json",
    )
    parser.add_argument(
        "--repo-root",
        default=".",
        help="Repository root used to resolve relative log paths",
    )
    args = parser.parse_args()
    return check_summary(
        bench_dir=Path(args.bench_dir).resolve(),
        repo_root=Path(args.repo_root).resolve(),
    )


if __name__ == "__main__":
    raise SystemExit(main())
