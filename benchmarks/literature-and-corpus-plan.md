# Benchmark Literature and Corpus Plan

This note maps issue #297 stress tests to a broader, thesis-grade benchmark design.

## Why issue #297 tests are necessary but not sufficient

- `tests/memory/wide_globals_10000.c`, `deep_if_1000.c`, and `long_statements_100000.c` are excellent stressors for allocator, parser depth, and IR/SSA scaling.
- They are synthetic programs. For publication-quality claims, pair them with representative real-world C workloads.

## Common benchmark suites used in compiler/system papers

1. MiBench (Guthaus et al., WWC 2001, DOI: 10.1109/WWC.2001.990739)
- 35 embedded programs across six domains.
- Portable C source; explicitly designed as a free benchmark suite.

2. LLVM test-suite (official LLVM infrastructure)
- Includes `SingleSource`, `MultiSource`, `External`, and `CTMark`.
- Collects compile time, runtime, and code-size metrics with correctness checks.

3. SPEC CPU 2017
- 43 benchmarks, four suites; includes compile-intensive and memory-intensive workloads.
- Standard in architecture/compiler evaluation; requires a license.

4. PolyBench/C
- Polyhedral kernels with controlled instrumentation.
- Useful for stable compile-time comparisons on numeric kernels.

5. BEEBS / Embench
- BEEBS targets embedded energy/perf behavior with portable C workloads.
- Embench provides a maintained embedded benchmark process and stable releases.

## Recommended shecc benchmark tiers

1. Tier A: issue #297 stress (already implemented in `tests/memory/`)
- Goal: regression guard for pathological memory behavior.

2. Tier B: open real-world corpus (no paid license)
- Start with MiBench + Embench/BEEBS subset that parses under shecc.
- Record accepted/rejected programs explicitly for reproducibility.

3. Tier C: standard external suite (optional)
- LLVM test-suite or SPEC CPU 2017 (if license is available).
- Use for stronger external validity in thesis claims.

## Publication-ready reporting checklist

- Report exact benchmark version/tag and commit hash.
- Report fixed Docker image tag and toolchain versions.
- Always include both:
  - synthetic stress results (issue #297)
  - representative corpus results (MiBench/Embench/BEEBS/LLVM/SPEC)
- Keep raw logs (`raw.csv`, stderr logs, valgrind logs) and summary artifacts in appendices or replication package.
