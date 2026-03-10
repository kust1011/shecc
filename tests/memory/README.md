# Memory Benchmark Programs

This directory contains stress-test sources used by memory diagnostics.

Recommended defaults for Valgrind:

- `long_declarations_500.c`: stable default for `make memcheck` / `make massif`
- `branch_chain_20.c`: smaller sanity-check input
- `wide_globals_10000.c`, `deep_if_1000.c`, `long_statements_100000.c`: issue #297 stress inputs

Regenerate stress sources:

```bash
tests/memory/generate_memory_benchmarks.py --profile all
```

Regenerate only issue #297 sources:

```bash
tests/memory/generate_issue297_tests.py
```
