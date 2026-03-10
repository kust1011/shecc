# Memory Benchmark Programs

This directory contains all benchmark source programs used by `scripts/benchmark.py`.

Profiles:

- `quick`: `wide_globals_300.c`, `long_declarations_500.c`, `many_functions_20.c`, `deep_if_24.c`, `branch_chain_20.c`
- `full`: `wide_globals_1000.c`, `long_declarations_2000.c`, `many_functions_50.c`, `deep_if_48.c`, `branch_chain_40.c`
- `issue297`: `wide_globals_10000.c`, `deep_if_1000.c`, `long_statements_100000.c`

Regenerate all benchmark sources:

```bash
tests/memory/generate_memory_benchmarks.py --profile all
```

Regenerate only issue #297 sources:

```bash
tests/memory/generate_issue297_tests.py
```
