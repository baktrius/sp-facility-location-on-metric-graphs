# Repository guide for agents

## Purpose and scope

This directory is the numerical-search component of the research archive for *Search and Verification for Strategyproof Facility
Location on Metric Graphs*. Read [README.md](README.md) for context and usage, and
[SCOREBOARD.md](SCOREBOARD.md) for saved results and resource estimates.

The repository preserves the numerical search implementation and experimental data
for three agents on a continuous cycle. Further feature development is not planned;
correctness fixes and bug reports through GitHub Issues are welcome. Keep changes
focused on the requested task and preserve reproducibility. Refer to the article
for the mathematical framework. Exact-verification and lower-bound components
are in the parent directory; see [the archive README](../README.md).

## Terminology and interpretation

- `lsp` in function names, CLI options, and JSON means strong strategyproofness
  (SSP), a sufficient condition for strategyproofness. Preserve existing names
  when maintaining compatibility with saved artifacts.
- The article's mesh size `q` appears as `v` in `main.py` and mechanism JSON,
  `--vertices` in the runner, and `c004`, etc. in archive folder names.
- `s` is the search sampling scale; the archived campaign and runner use `s=2`.
  It is distinct from the checker's `--min-scale` and `--max-scale` settings.
- `sampled_ratio` describes the search grid; `check.json`'s `binsearch_apx`
  contains the numerical continuous approximation interval for the saved candidate.
  Neither endpoint establishes the optimum of the unrestricted design problem.
- Floating-point checks provide numerical evidence, not exact certificates.
  Solver versions can change final digits and which optimal candidate is selected.

## Code map

`main.py` contains both the core implementation and older research experiments.
Use function names to navigate rather than treating every CLI command as part of
the published reproduction workflow.

| Area in `main.py` | Starting points |
| --- | --- |
| Three-agent cycle setup and saved mechanism loading | `m_setup`, `m_load` |
| Piecewise-linear continuous extensions | `extend_mechanism_to_continuous`, `get_anonymous_extension_of_mechanism` |
| SSP constraints and checks | `get_lsp_check`, `gen_lsp_eps_checks` |
| LP construction, solving, and candidate output | `solve_lsp_mechanism` |
| Numerical checking and approximation bisection | `check_lsp_mechanism`, `_check_lsp_mechanism` |
| Continuous approximation calculations | `get_max_of_quad`, `filter_apx_bound_chunks`, `is_apx_global_bound` |
| Provenance and solver selection | `run_metadata`, `get_cbc_path` |

- `experiments/run.py` orchestrates search/check subprocesses, logs, and metadata.
  Its `load_case` validates completion, hashes, SSP results, and approximation intervals.
- `experiments/plot.py` collects cases and generates plots, CSV, and the scoreboard.
  `scoreboard_text` rounds approximation endpoints outward; preserve that behavior.
- `experiments/s2/manifest.json` records archive selection and provenance. Each case
  has `mechanism.json` (metadata followed by coefficients), `check.json`, and `run.json`.

## Preserve the archive

- Treat `experiments/s2/` as historical evidence. Do not overwrite or reformat its
  artifacts during routine fixes: checks identify mechanisms by byte-level hashes.
  Save new experiments under `runs/`; document any necessary archival correction.
- Generate `SCOREBOARD.md` with `experiments/plot.py`; do not hand-edit generated
  values. For previewing the archive without changing the committed scoreboard,
  pass `--scoreboard figures/review/SCOREBOARD.md` explicitly, even with `--output`.
- Keep generated figures, logs, solver dumps, and new runs in ignored locations.
  Do not rewrite historical provenance to make it describe the current checkout.

## Setup and verification

Use Python 3.13+ and `uv sync --locked` from this `lsp/` directory. CBC selection is
`CBC_PATH`, then `cbc` on `PATH`, then the solver bundled with locked PuLP.

Choose verification appropriate to the change. Documentation-only edits need link
and whitespace checks; plotting changes can use the archived data without solving:

```bash
uv run experiments/plot.py --output figures/review --scoreboard figures/review/SCOREBOARD.md
```

For search/check changes, start with C4. The following creates fresh output paths;
the runner refuses existing directories, including those from failed runs:

```bash
mkdir -p runs
run_root=$(mktemp -d runs/agent-check-XXXXXX)
uv run experiments/run.py --vertices 4 --output "$run_root/c004"
uv run experiments/run.py --check-only experiments/s2/c004/mechanism.json --output "$run_root/recheck"
uv run experiments/plot.py "$run_root/c004" --output "$run_root/figures"
```

Inspect the relevant numerical results as well as command exit status. Add focused
regression coverage for correctness fixes where useful. Many `test_*` functions
in `main.py` are research experiments, and some need external reference files;
inspect a test before running it rather than assuming a fast, self-contained suite.
Use `git diff --check` before finishing and report what was actually verified.

Do not replay the full campaign for routine validation: C128 historically took
about 24.5 hours to search and 3.8 hours to check, with checker peak RSS near 29 GiB.
`--mem-limit` only controls a search cache heuristic, not total RAM or checker memory.
The runner restores archived cache settings for known sizes, including unrestricted
caching for some, and defaults to 16 GB for other sizes.
