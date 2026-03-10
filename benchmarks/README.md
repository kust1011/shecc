# Benchmark Workspace

This directory stores versioned benchmark metadata for optimization studies.

- `baselines/*.json` keeps saved benchmark summaries from `make bench-save-baseline`.
- Benchmark run outputs are generated under `out/bench/` and are intentionally not committed.

Suggested baseline naming:

- `baseline-YYYY-MM-DD` for daily snapshots
- `baseline-<git-short-sha>` for commit-specific snapshots
