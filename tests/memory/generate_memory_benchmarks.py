#!/usr/bin/env python3

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List


@dataclass(frozen=True)
class Case:
    filename: str
    kind: str
    scale: int


PROFILE_CASES: Dict[str, List[Case]] = {
    "quick": [
        Case("wide_globals_300.c", "wide_globals", 300),
        Case("long_declarations_500.c", "long_declarations", 500),
        Case("many_functions_20.c", "many_functions", 20),
        Case("deep_if_24.c", "deep_if", 24),
        Case("branch_chain_20.c", "branch_chain", 20),
    ],
    "full": [
        Case("wide_globals_1000.c", "wide_globals", 1000),
        Case("long_declarations_2000.c", "long_declarations", 2000),
        Case("many_functions_50.c", "many_functions", 50),
        Case("deep_if_48.c", "deep_if", 48),
        Case("branch_chain_40.c", "branch_chain", 40),
    ],
    "issue297": [
        Case("wide_globals_10000.c", "wide_globals", 10000),
        Case("deep_if_1000.c", "deep_if", 1000),
        Case("long_statements_100000.c", "long_statements", 100000),
    ],
}


def write_wide_globals(path: Path, count: int) -> None:
    lines = [
        "/* Auto-generated benchmark source: wide globals */",
        "",
    ]
    lines.extend(f"int g_{idx} = {idx % 97};" for idx in range(count))
    lines.extend(
        [
            "",
            "int main(void)",
            "{",
            "    int sum = 0;",
        ]
    )
    stride = max(1, count // 128)
    for idx in range(0, count, stride):
        lines.append(f"    sum += g_{idx};")
    lines.extend(
        [
            "    return sum & 255;",
            "}",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_long_declarations(path: Path, count: int) -> None:
    lines = [
        "/* Auto-generated benchmark source: long declarations */",
        "",
        "int main(void)",
        "{",
    ]
    for idx in range(count):
        lines.append(f"    int v_{idx} = {idx % 11};")
    lines.extend(
        [
            "    return 0;",
            "}",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_many_functions(path: Path, count: int) -> None:
    lines: List[str] = ["/* Auto-generated benchmark source: many functions */", ""]
    for idx in range(count):
        lines.append(f"int fn_{idx}(int x)")
        lines.append("{")
        lines.append(f"    return x + {(idx % 19) + 1};")
        lines.append("}")
        lines.append("")
    lines.extend(
        [
            "int main(void)",
            "{",
            "    int acc = 0;",
        ]
    )
    for idx in range(count):
        lines.append(f"    acc += fn_{idx}({idx % 7});")
    lines.extend(
        [
            "    return acc & 255;",
            "}",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_deep_if(path: Path, depth: int) -> None:
    lines = [
        "/* Auto-generated benchmark source: deep nested if */",
        "",
        "int main(void)",
        "{",
        "    int x = 0;",
        "    int y = 0;",
    ]
    for idx in range(depth):
        lines.append(("    " * (idx + 1)) + f"if (x == {idx}) {{")
        lines.append(("    " * (idx + 2)) + "x = x + 1;")
        lines.append(("    " * (idx + 2)) + "y = y + x;")
    for idx in reversed(range(depth)):
        lines.append(("    " * (idx + 1)) + "}")
    lines.extend(
        [
            "    return y & 255;",
            "}",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_branch_chain(path: Path, count: int) -> None:
    lines = [
        "/* Auto-generated benchmark source: branch chain */",
        "",
        "int main(void)",
        "{",
        "    int x = 0;",
        "    int y = 0;",
    ]
    for idx in range(count):
        lines.append(f"    if (x == {idx}) y = y + {(idx % 31) + 1};")
    lines.extend(
        [
            "    return y & 255;",
            "}",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_long_statements(path: Path, count: int) -> None:
    lines = [
        "/* Auto-generated benchmark source: long statements */",
        "",
        "int main(void)",
        "{",
        "    int x = 0;",
    ]
    for idx in range(count):
        lines.append(f"    x = x + {idx % 31};")
    lines.extend(
        [
            "    return x & 255;",
            "}",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


WRITERS = {
    "wide_globals": write_wide_globals,
    "long_declarations": write_long_declarations,
    "many_functions": write_many_functions,
    "deep_if": write_deep_if,
    "branch_chain": write_branch_chain,
    "long_statements": write_long_statements,
}


def generate_profiles(output_dir: Path, profiles: List[str]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    generated_files: List[str] = []
    for profile in profiles:
        for case in PROFILE_CASES[profile]:
            writer = WRITERS[case.kind]
            file_path = output_dir / case.filename
            writer(file_path, case.scale)
            generated_files.append(case.filename)
    for name in sorted(set(generated_files)):
        print(f"generated: {output_dir / name}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate benchmark C sources in tests/memory.")
    parser.add_argument(
        "--profile",
        choices=["quick", "full", "issue297", "all"],
        default="all",
        help="Which benchmark profile to generate.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(Path(__file__).resolve().parent),
        help="Output directory for generated C files.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.profile == "all":
        profiles = ["quick", "full", "issue297"]
    else:
        profiles = [args.profile]
    generate_profiles(Path(args.output_dir).resolve(), profiles)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
