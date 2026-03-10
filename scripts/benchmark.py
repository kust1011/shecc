#!/usr/bin/env python3

"""Benchmark harness for reproducible shecc performance and memory experiments."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import platform
import shlex
import statistics
import subprocess
import sys
import time
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Sequence

try:
    import resource
except ImportError:
    resource = None


@dataclass(frozen=True)
class CaseSpec:
    name: str
    source: str
    generated: bool = False
    generator: Optional[str] = None
    scale: int = 0


PROFILE_CASES: Dict[str, List[CaseSpec]] = {
    "quick": [
        CaseSpec(
            name="wide_globals_300",
            source="wide_globals_300.c",
            generated=True,
            generator="wide_globals",
            scale=300,
        ),
        CaseSpec(
            name="long_declarations_500",
            source="long_declarations_500.c",
            generated=True,
            generator="long_declarations",
            scale=500,
        ),
        CaseSpec(
            name="many_functions_20",
            source="many_functions_20.c",
            generated=True,
            generator="many_functions",
            scale=20,
        ),
        CaseSpec(
            name="deep_if_24",
            source="deep_if_24.c",
            generated=True,
            generator="deep_if",
            scale=24,
        ),
        CaseSpec(
            name="branch_chain_20",
            source="branch_chain_20.c",
            generated=True,
            generator="branch_chain",
            scale=20,
        ),
    ],
    "full": [
        CaseSpec(
            name="wide_globals_1000",
            source="wide_globals_1000.c",
            generated=True,
            generator="wide_globals",
            scale=1000,
        ),
        CaseSpec(
            name="long_declarations_2000",
            source="long_declarations_2000.c",
            generated=True,
            generator="long_declarations",
            scale=2000,
        ),
        CaseSpec(
            name="many_functions_50",
            source="many_functions_50.c",
            generated=True,
            generator="many_functions",
            scale=50,
        ),
        CaseSpec(
            name="deep_if_48",
            source="deep_if_48.c",
            generated=True,
            generator="deep_if",
            scale=48,
        ),
        CaseSpec(
            name="branch_chain_40",
            source="branch_chain_40.c",
            generated=True,
            generator="branch_chain",
            scale=40,
        ),
    ],
    "issue297": [
        CaseSpec(
            name="wide_globals_10000",
            source="tests/memory/wide_globals_10000.c",
        ),
        CaseSpec(
            name="deep_if_1000",
            source="tests/memory/deep_if_1000.c",
        ),
        CaseSpec(
            name="long_statements_100000",
            source="tests/memory/long_statements_100000.c",
        ),
    ],
}


def generate_wide_globals(path: Path, count: int) -> None:
    lines: List[str] = []
    for idx in range(count):
        lines.append("int g_%d = %d;" % (idx, idx % 97))
    lines.append("")
    lines.append("int main(void)")
    lines.append("{")
    lines.append("    int acc = 0;")
    stride = max(1, count // 32)
    for idx in range(0, count, stride):
        lines.append("    acc += g_%d;" % idx)
    lines.append("    return acc & 255;")
    lines.append("}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def generate_long_statements(path: Path, count: int) -> None:
    lines = [
        "int main(void)",
        "{",
        "    int a = 1;",
        "    int b = 3;",
        "    int c = 7;",
    ]
    for idx in range(count):
        lines.append("    a = a + b + %d;" % (idx % 17))
        lines.append("    b = b ^ (a + %d);" % (idx % 11))
        lines.append("    c = c + (b & 31);")
    lines.extend(
        [
            "    return (a + b + c) & 255;",
            "}",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def generate_long_declarations(path: Path, count: int) -> None:
    lines = [
        "int main(void)",
        "{",
    ]
    for idx in range(count):
        lines.append("    int v_%d = %d;" % (idx, idx % 11))
    lines.extend(
        [
            "    return 0;",
            "}",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def generate_many_functions(path: Path, count: int) -> None:
    lines: List[str] = []
    for idx in range(count):
        lines.append(
            "int fn_%d(int x)\n{\n    return x + %d;\n}\n" % (idx, (idx % 19) + 1)
        )
    lines.append("int main(void)")
    lines.append("{")
    lines.append("    int acc = 0;")
    for idx in range(count):
        lines.append("    acc += fn_%d(%d);" % (idx, idx % 7))
    lines.append("    return acc & 255;")
    lines.append("}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def generate_deep_if(path: Path, depth: int) -> None:
    lines = [
        "int main(void)",
        "{",
        "    int x = 0;",
        "    int y = 0;",
    ]
    for idx in range(depth):
        lines.append(("    " * (idx + 1)) + "if (x == %d) {" % idx)
        lines.append(("    " * (idx + 2)) + "x = x + 1;")
        lines.append(("    " * (idx + 2)) + "y = y + x;")
    for idx in reversed(range(depth)):
        lines.append(("    " * (idx + 1)) + "}")
    lines.append("    return y & 255;")
    lines.append("}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def generate_branch_chain(path: Path, count: int) -> None:
    lines = [
        "int main(void)",
        "{",
        "    int x = 0;",
        "    int y = 0;",
    ]
    for idx in range(count):
        lines.append("    if (x == %d) y = y + %d;" % (idx, (idx % 31) + 1))
    lines.extend(
        [
            "    return y & 255;",
            "}",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


GENERATOR_MAP = {
    "wide_globals": generate_wide_globals,
    "long_statements": generate_long_statements,
    "long_declarations": generate_long_declarations,
    "many_functions": generate_many_functions,
    "deep_if": generate_deep_if,
    "branch_chain": generate_branch_chain,
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file_obj:
        while True:
            chunk = file_obj.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def normalize_ru_maxrss(raw_value: Optional[int]) -> float:
    if raw_value is None:
        return -1.0
    # ru_maxrss is bytes on Darwin and kilobytes on most Linux systems.
    if platform.system() == "Darwin":
        return float(raw_value) / 1024.0
    return float(raw_value)


def run_with_metrics(
    command: Sequence[str], stderr_log: Path, memory_limit_mb: Optional[int]
) -> Dict[str, object]:
    start = time.perf_counter()
    preexec_fn = None
    if memory_limit_mb is not None:
        if resource is None:
            return {
                "exit_code": 126,
                "elapsed_s": 0.0,
                "max_rss_kb": -1.0,
                "spawn_error": "Python resource module is unavailable for memory limits.",
            }
        limit_bytes = int(memory_limit_mb) * 1024 * 1024

        def apply_limit() -> None:
            resource.setrlimit(resource.RLIMIT_AS, (limit_bytes, limit_bytes))

        preexec_fn = apply_limit

    with stderr_log.open("wb") as stderr_file:
        try:
            proc = subprocess.Popen(
                command,
                stdout=subprocess.DEVNULL,
                stderr=stderr_file,
                preexec_fn=preexec_fn,
            )
        except OSError as error:
            return {
                "exit_code": 126,
                "elapsed_s": 0.0,
                "max_rss_kb": -1.0,
                "spawn_error": str(error),
            }
        if hasattr(os, "wait4"):
            _, status, usage = os.wait4(proc.pid, 0)
            exit_code = os.waitstatus_to_exitcode(status)
            rss_kb = normalize_ru_maxrss(getattr(usage, "ru_maxrss", None))
        else:
            exit_code = proc.wait()
            rss_kb = -1.0
    elapsed = time.perf_counter() - start
    return {
        "exit_code": exit_code,
        "elapsed_s": elapsed,
        "max_rss_kb": rss_kb,
        "spawn_error": None,
    }


def median_or_none(values: List[float]) -> Optional[float]:
    if not values:
        return None
    return float(statistics.median(values))


def mean_or_none(values: List[float]) -> Optional[float]:
    if not values:
        return None
    return float(statistics.fmean(values))


def create_sources(repo_root: Path, source_root: Path, cases: List[CaseSpec]) -> None:
    source_root.mkdir(parents=True, exist_ok=True)
    for case in cases:
        if not case.generated:
            continue
        target = source_root / case.source
        target.parent.mkdir(parents=True, exist_ok=True)
        generator = GENERATOR_MAP.get(case.generator or "")
        if generator is None:
            raise ValueError("Unknown generator: %s" % case.generator)
        generator(target, case.scale)


def resolve_source(repo_root: Path, source_root: Path, case: CaseSpec) -> Path:
    if case.generated:
        return source_root / case.source
    return repo_root / case.source


def build_case_rows(
    repo_root: Path,
    shecc_path: Path,
    runner_prefix: Sequence[str],
    out_dir: Path,
    cases: List[CaseSpec],
    repeat: int,
    include_libc: bool,
    memory_limit_mb: Optional[int],
) -> List[Dict[str, object]]:
    rows: List[Dict[str, object]] = []
    bin_dir = out_dir / "bin"
    log_dir = out_dir / "logs"
    src_dir = out_dir / "generated_sources"
    bin_dir.mkdir(parents=True, exist_ok=True)
    log_dir.mkdir(parents=True, exist_ok=True)

    create_sources(repo_root, src_dir, cases)

    shecc_cmd_base = list(runner_prefix) + [str(shecc_path)]
    if not include_libc:
        shecc_cmd_base.append("--no-libc")

    for case in cases:
        src_path = resolve_source(repo_root, src_dir, case)
        for run_id in range(1, repeat + 1):
            out_bin = bin_dir / ("%s.elf" % case.name)
            stderr_log = log_dir / ("%s.run%d.stderr.log" % (case.name, run_id))
            command = shecc_cmd_base + ["-o", str(out_bin), str(src_path)]
            metrics = run_with_metrics(command, stderr_log, memory_limit_mb)

            output_size = None
            output_sha256 = None
            if metrics["exit_code"] == 0 and out_bin.exists():
                output_size = out_bin.stat().st_size
                output_sha256 = sha256_file(out_bin)

            rows.append(
                {
                    "case": case.name,
                    "run": run_id,
                    "source": str(src_path.relative_to(repo_root)),
                    "generated": case.generated,
                    "exit_code": metrics["exit_code"],
                    "elapsed_s": metrics["elapsed_s"],
                    "max_rss_kb": metrics["max_rss_kb"],
                    "output_size_bytes": output_size,
                    "output_sha256": output_sha256,
                    "stderr_log": str(stderr_log.relative_to(repo_root)),
                    "spawn_error": metrics["spawn_error"],
                    "memory_limit_mb": memory_limit_mb,
                }
            )
    return rows


def summarize_rows(
    rows: List[Dict[str, object]],
    profile: str,
    repeat: int,
    include_libc: bool,
    memory_limit_mb: Optional[int],
    shecc_path: Path,
    runner_prefix: str,
    repo_root: Path,
) -> Dict[str, object]:
    grouped: Dict[str, List[Dict[str, object]]] = defaultdict(list)
    for row in rows:
        grouped[str(row["case"])].append(row)

    case_summaries: Dict[str, Dict[str, object]] = {}
    total_runs = 0
    total_failures = 0
    for case_name, case_rows in grouped.items():
        total_runs += len(case_rows)
        success_rows = [row for row in case_rows if row["exit_code"] == 0]
        failure_rows = [row for row in case_rows if row["exit_code"] != 0]
        total_failures += len(failure_rows)

        elapsed_values = [float(row["elapsed_s"]) for row in success_rows]
        rss_values = [float(row["max_rss_kb"]) for row in success_rows]
        size_values = [
            int(row["output_size_bytes"])
            for row in success_rows
            if row["output_size_bytes"] is not None
        ]
        hashes = {
            str(row["output_sha256"])
            for row in success_rows
            if row["output_sha256"] is not None
        }

        case_summaries[case_name] = {
            "runs": len(case_rows),
            "successful_runs": len(success_rows),
            "failed_runs": len(failure_rows),
            "success_rate": len(success_rows) / float(len(case_rows)),
            "elapsed_median_s": median_or_none(elapsed_values),
            "elapsed_mean_s": mean_or_none(elapsed_values),
            "max_rss_median_kb": median_or_none(rss_values),
            "max_rss_mean_kb": mean_or_none(rss_values),
            "output_size_median_bytes": median_or_none([float(v) for v in size_values]),
            "output_hash_stable": len(hashes) <= 1,
            "output_hashes": sorted(hashes),
            "spawn_errors": sorted(
                {
                    str(row["spawn_error"])
                    for row in case_rows
                    if row.get("spawn_error") is not None
                }
            ),
        }

    summary = {
        "metadata": {
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "host_platform": platform.platform(),
            "python_version": sys.version.split()[0],
            "profile": profile,
            "repeat": repeat,
            "include_libc": include_libc,
            "memory_limit_mb": memory_limit_mb,
            "shecc_path": str(shecc_path.relative_to(repo_root)),
            "runner_prefix": runner_prefix,
        },
        "cases": case_summaries,
        "overall": {
            "total_runs": total_runs,
            "total_failures": total_failures,
            "all_successful": total_failures == 0,
        },
    }
    return summary


def format_float(value: Optional[float], digits: int = 3) -> str:
    if value is None:
        return "n/a"
    return ("%0." + str(digits) + "f") % value


def write_summary_markdown(summary: Dict[str, object], out_path: Path) -> None:
    cases = summary["cases"]
    lines = [
        "# shecc Benchmark Summary",
        "",
        "| Case | Success | Median Time (s) | Median RSS (MB) | Median Output (bytes) | Hash Stable |",
        "|---|---:|---:|---:|---:|---|",
    ]
    for case_name in sorted(cases.keys()):
        case = cases[case_name]
        rss_mb = None
        if case["max_rss_median_kb"] is not None:
            rss_mb = float(case["max_rss_median_kb"]) / 1024.0
        lines.append(
            "| %s | %d/%d | %s | %s | %s | %s |"
            % (
                case_name,
                case["successful_runs"],
                case["runs"],
                format_float(case["elapsed_median_s"], 4),
                format_float(rss_mb, 2),
                format_float(case["output_size_median_bytes"], 1),
                "yes" if case["output_hash_stable"] else "no",
            )
        )
    lines.append("")
    lines.append(
        "All Successful: %s"
        % ("yes" if summary["overall"]["all_successful"] else "no")
    )
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_benchmarks(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve()
    shecc_path = Path(args.shecc).resolve()
    out_dir = Path(args.output_dir).resolve()
    runner_prefix = shlex.split(args.runner.strip()) if args.runner.strip() else []

    if not shecc_path.exists():
        print("error: shecc binary not found: %s" % shecc_path, file=sys.stderr)
        return 2
    if args.profile not in PROFILE_CASES:
        print("error: unsupported profile: %s" % args.profile, file=sys.stderr)
        return 2
    if args.memory_limit_mb is not None and args.memory_limit_mb <= 0:
        print("error: --memory-limit-mb must be a positive integer.", file=sys.stderr)
        return 2

    out_dir.mkdir(parents=True, exist_ok=True)
    rows = build_case_rows(
        repo_root=repo_root,
        shecc_path=shecc_path,
        runner_prefix=runner_prefix,
        out_dir=out_dir,
        cases=PROFILE_CASES[args.profile],
        repeat=args.repeat,
        include_libc=args.with_libc,
        memory_limit_mb=args.memory_limit_mb,
    )

    raw_csv_path = out_dir / "raw.csv"
    with raw_csv_path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(
            csv_file,
            fieldnames=[
                "case",
                "run",
                "source",
                "generated",
                "exit_code",
                "elapsed_s",
                "max_rss_kb",
                "output_size_bytes",
                "output_sha256",
                "stderr_log",
                "spawn_error",
                "memory_limit_mb",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)

    summary = summarize_rows(
        rows=rows,
        profile=args.profile,
        repeat=args.repeat,
        include_libc=args.with_libc,
        memory_limit_mb=args.memory_limit_mb,
        shecc_path=shecc_path,
        runner_prefix=args.runner,
        repo_root=repo_root,
    )

    summary_path = out_dir / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")

    markdown_path = out_dir / "summary.md"
    write_summary_markdown(summary, markdown_path)

    print("Benchmark raw data: %s" % raw_csv_path)
    print("Benchmark summary : %s" % summary_path)
    print("Benchmark report  : %s" % markdown_path)

    if args.fail_on_error and not summary["overall"]["all_successful"]:
        return 1
    return 0


def prepare_benchmarks(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve()
    out_dir = Path(args.output_dir).resolve()

    if args.profile not in PROFILE_CASES:
        print("error: unsupported profile: %s" % args.profile, file=sys.stderr)
        return 2

    out_dir.mkdir(parents=True, exist_ok=True)
    src_dir = out_dir / "generated_sources"
    create_sources(repo_root, src_dir, PROFILE_CASES[args.profile])

    manifest = {
        "profile": args.profile,
        "generated_sources": [],
    }
    for case in PROFILE_CASES[args.profile]:
        source_path = resolve_source(repo_root, src_dir, case)
        manifest["generated_sources"].append(
            {
                "case": case.name,
                "path": str(source_path),
                "generated": case.generated,
            }
        )

    manifest_path = out_dir / "generated_sources_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print("Generated benchmark sources at: %s" % src_dir)
    print("Generated source manifest   : %s" % manifest_path)
    return 0


def percent_delta(current: Optional[float], baseline: Optional[float]) -> Optional[float]:
    if current is None or baseline is None:
        return None
    if baseline == 0:
        return None
    return (current - baseline) / baseline * 100.0


def geometric_mean(values: List[float]) -> Optional[float]:
    if not values:
        return None
    product = 1.0
    for value in values:
        product *= value
    return product ** (1.0 / len(values))


def compare_summaries(args: argparse.Namespace) -> int:
    baseline_path = Path(args.baseline).resolve()
    current_path = Path(args.current).resolve()
    output_path = Path(args.output).resolve() if args.output else None

    if not baseline_path.exists():
        print("error: baseline summary does not exist: %s" % baseline_path, file=sys.stderr)
        return 2
    if not current_path.exists():
        print("error: current summary does not exist: %s" % current_path, file=sys.stderr)
        return 2

    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    current = json.loads(current_path.read_text(encoding="utf-8"))

    base_cases = baseline.get("cases", {})
    curr_cases = current.get("cases", {})
    case_names = sorted(set(base_cases.keys()) & set(curr_cases.keys()))

    lines = [
        "# shecc Benchmark Comparison",
        "",
        "| Case | Time Δ% (median) | RSS Δ% (median) |",
        "|---|---:|---:|",
    ]
    time_ratios: List[float] = []
    rss_ratios: List[float] = []
    for case_name in case_names:
        base_case = base_cases[case_name]
        curr_case = curr_cases[case_name]
        time_delta = percent_delta(
            curr_case.get("elapsed_median_s"), base_case.get("elapsed_median_s")
        )
        rss_delta = percent_delta(
            curr_case.get("max_rss_median_kb"), base_case.get("max_rss_median_kb")
        )
        if (
            curr_case.get("elapsed_median_s") is not None
            and base_case.get("elapsed_median_s") not in (None, 0)
        ):
            time_ratios.append(
                curr_case.get("elapsed_median_s") / base_case.get("elapsed_median_s")
            )
        if (
            curr_case.get("max_rss_median_kb") is not None
            and base_case.get("max_rss_median_kb") not in (None, 0)
        ):
            rss_ratios.append(
                curr_case.get("max_rss_median_kb")
                / base_case.get("max_rss_median_kb")
            )
        lines.append(
            "| %s | %s | %s |"
            % (
                case_name,
                format_float(time_delta, 2),
                format_float(rss_delta, 2),
            )
        )

    time_geomean = geometric_mean(time_ratios)
    rss_geomean = geometric_mean(rss_ratios)
    lines.append("")
    lines.append(
        "Geomean Time Ratio (current/baseline): %s"
        % format_float(time_geomean, 4)
    )
    lines.append(
        "Geomean RSS Ratio (current/baseline): %s"
        % format_float(rss_geomean, 4)
    )
    lines.append("")

    report = "\n".join(lines) + "\n"
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(report, encoding="utf-8")
        print("Comparison report : %s" % output_path)
    print(report, end="")
    return 0


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run reproducible shecc benchmark workloads and compare results."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Generate workloads and run benchmark")
    run_parser.add_argument(
        "--repo-root",
        default=".",
        help="Path to shecc repository root (default: current directory).",
    )
    run_parser.add_argument(
        "--shecc", default="out/shecc", help="Path to shecc binary (default: out/shecc)."
    )
    run_parser.add_argument(
        "--runner",
        default=os.environ.get("TARGET_EXEC", ""),
        help=(
            "Optional runner command prefix for shecc "
            "(for example 'qemu-aarch64')."
        ),
    )
    run_parser.add_argument(
        "--output-dir",
        default="out/bench/latest",
        help="Directory for raw and summarized benchmark output.",
    )
    run_parser.add_argument(
        "--profile",
        default="full",
        choices=sorted(PROFILE_CASES.keys()),
        help="Benchmark profile to run.",
    )
    run_parser.add_argument(
        "--repeat",
        type=int,
        default=5,
        help="Repeat each benchmark case N times (default: 5).",
    )
    run_parser.add_argument(
        "--with-libc",
        action="store_true",
        help="Include embedded libc during benchmark compilation.",
    )
    run_parser.add_argument(
        "--memory-limit-mb",
        type=int,
        default=None,
        help="Optional per-run address-space limit in MiB (Linux RLIMIT_AS).",
    )
    run_parser.add_argument(
        "--no-fail-on-error",
        action="store_true",
        help="Do not fail command when one or more benchmark runs fail.",
    )

    prepare_parser = subparsers.add_parser(
        "prepare", help="Generate benchmark source files without compiling."
    )
    prepare_parser.add_argument(
        "--repo-root",
        default=".",
        help="Path to shecc repository root (default: current directory).",
    )
    prepare_parser.add_argument(
        "--output-dir",
        default="out/bench/latest",
        help="Directory where generated benchmark sources are written.",
    )
    prepare_parser.add_argument(
        "--profile",
        default="issue297",
        choices=sorted(PROFILE_CASES.keys()),
        help="Benchmark profile to generate.",
    )

    compare_parser = subparsers.add_parser(
        "compare", help="Compare two benchmark summary.json files."
    )
    compare_parser.add_argument("--baseline", required=True, help="Baseline summary.json path.")
    compare_parser.add_argument("--current", required=True, help="Current summary.json path.")
    compare_parser.add_argument(
        "--output", help="Optional markdown output path for the comparison report."
    )

    args = parser.parse_args(argv)
    if args.command == "run":
        args.fail_on_error = not args.no_fail_on_error
        if args.repeat <= 0:
            parser.error("--repeat must be a positive integer.")
    return args


def main(argv: Sequence[str]) -> int:
    args = parse_args(argv)
    if args.command == "run":
        return run_benchmarks(args)
    if args.command == "prepare":
        return prepare_benchmarks(args)
    if args.command == "compare":
        return compare_summaries(args)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
