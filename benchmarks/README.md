# Benchmark Workspace

This directory stores versioned benchmark metadata for optimization studies.

- `baselines/*.json` keeps saved benchmark summaries from `make bench-save-baseline`.
- Benchmark run outputs are generated under `out/bench/` and are intentionally not committed.
- Issue #297 runs should use `BENCH_PROFILE=issue297`.
- Issue #297 source programs are versioned under `tests/memory/`.
- Validate run integrity with `make bench-validate BENCH_OUTPUT_DIR=out/bench/<run-name>`.
- Literature and corpus guidance is in `literature-and-corpus-plan.md`.

Suggested baseline naming:

- `baseline-YYYY-MM-DD` for daily snapshots
- `baseline-<git-short-sha>` for commit-specific snapshots
