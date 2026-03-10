#!/usr/bin/env python3

from pathlib import Path


def write_wide_globals(path: Path, count: int = 10000) -> None:
    lines = [
        "/* Auto-generated for issue #297 memory benchmark: wide globals */",
        "",
    ]
    lines.extend(f"int g_{i} = {i % 97};" for i in range(count))
    lines.extend([
        "",
        "int main(void)",
        "{",
        "    int sum = 0;",
    ])

    # Sample usage to prevent all globals from being trivially dead.
    step = max(1, count // 128)
    for i in range(0, count, step):
        lines.append(f"    sum += g_{i};")

    lines.extend([
        "    return sum & 255;",
        "}",
    ])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_deep_if(path: Path, depth: int = 1000) -> None:
    lines = [
        "/* Auto-generated for issue #297 memory benchmark: deep nested if */",
        "",
        "int main(void)",
        "{",
        "    int x = 0;",
        "    int y = 0;",
    ]

    for i in range(depth):
        lines.append(f"if (x == {i}) {{")
        lines.append("x = x + 1;")
        lines.append("y = y + x;")

    for i in reversed(range(depth)):
        lines.append("}")

    lines.extend([
        "    return y & 255;",
        "}",
    ])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_long_statements(path: Path, count: int = 100000) -> None:
    lines = [
        "/* Auto-generated for issue #297 memory benchmark: long statement stream */",
        "",
        "int main(void)",
        "{",
        "    int x = 0;",
    ]

    for i in range(count):
        lines.append(f"    x = x + {i % 31};")

    lines.extend([
        "    return x & 255;",
        "}",
    ])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    root = Path(__file__).resolve().parent
    write_wide_globals(root / "wide_globals_10000.c")
    write_deep_if(root / "deep_if_1000.c")
    write_long_statements(root / "long_statements_100000.c")


if __name__ == "__main__":
    main()
