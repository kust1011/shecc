# Memory Benchmark Programs (Issue #297)

This directory contains memory stress programs aligned with issue #297:

- `wide_globals_10000.c`: wide program with 10,000 global variables.
- `deep_if_1000.c`: deep control-flow program with 1,000 nested `if` blocks.
- `long_statements_100000.c`: long program with 100,000 sequential statements.

Regeneration:

```bash
tests/memory/generate_issue297_tests.py
```
