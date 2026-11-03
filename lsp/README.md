# Numerical LSP experiments on cycles

Part of the [experimental archive accompanying the paper](../README.md).

The code implements the article's numerical search method for **three agents on a
cycle**. It represents mechanisms using piecewise-linear attributions, constructs
candidates through a linear program with strong strategyproofness (SSP)
constraints and sampled approximation comparisons, and numerically checks their
continuous extensions. Increasing the cycle mesh size refines the representation.
**See the article for the mathematical background and method**; this repository
provides the implementation and saved data needed to reproduce the numerical
experiments.

The [scoreboard](SCOREBOARD.md) summarizes 17 saved experiments at search sampling
scale `s=2`, with cycle mesh sizes from `q=4` to `q=128`. The `q=128` candidate
achieves a numerical approximation upper endpoint of about **1.07229**, and all
saved cases completed the SSP check without a reported counterexample.

These floating-point results are **numerical evidence, not exact certificates**.
The [upper](../upper-bound/README.md) and [lower](../lower-bound/README.md)
verifiers accompany the numerical experiments. Exact certificates for rational
reconstructions of four saved candidates are available in
[the recovered-certificate collection](../certificates/upper/lsp-recovered/README.md).
The historical name `lsp` in command-line options and JSON fields
refers to **SSP**, a sufficient condition for strategyproofness.

## Contents

- [main.py](main.py): mechanism construction and numerical checker.
- [experiments/run.py](experiments/run.py): solve and check a case, or recheck a
  saved mechanism.
- [experiments/plot.py](experiments/plot.py): validate saved results and generate
  plots, CSV, and [SCOREBOARD.md](SCOREBOARD.md).
- [experiments/s2/](experiments/s2/): one archived run per mesh size (`c128` means
  `q=128`), each containing `mechanism.json`, `check.json`, and resource/model-size
  measurements in `run.json`. The [manifest](experiments/s2/manifest.json) records
  their source runs and selection.

## Reproducing the experiments

### Install

Use Python 3.13+ and [uv](https://docs.astral.sh/uv/). Run the commands below from
this `lsp/` directory:

```bash
uv sync --locked
```

Alternatively, with Docker and the VS Code Dev Containers extension installed,
open this `lsp/` folder in VS Code and select **Dev Containers: Reopen in Container**
to use the included [devcontainer](.devcontainer/devcontainer.json), then run
`uv sync --locked` there.

CBC is bundled with the locked PuLP dependency. Solver selection is `CBC_PATH`,
then `cbc` on `PATH`, then the bundled solver. Solver versions can affect final
digits and which optimal mechanism is selected.

### Generate plots and the scoreboard

```bash
uv run experiments/plot.py
```

This takes seconds, validates the saved artifacts and their hashes, and regenerates
`SCOREBOARD.md` without solving or rechecking. Approximation, runtime, and LP
model-size plots (PNG/PDF), plus `summary.csv`, go under Git-ignored `figures/`.

### Solve and check a new mechanism

Start with a small experiment:

```bash
uv run experiments/run.py --vertices 4 --output runs/c004
```

This uses the published `s=2` workflow and writes the three JSON files listed
above, plus logs. **Output directories must be new**, including for rechecks.

To repeat all 17 published cycle sizes sequentially:

```bash
for q in 4 8 12 16 20 24 28 32 36 40 44 48 64 80 96 112 128; do
  uv run experiments/run.py --vertices "$q" --output "runs/replay/c$q" || break
done
```

For larger runs, see [time and memory](#time-and-memory) before starting.

### Recheck an existing mechanism

Only a completed `s=2` mechanism is needed:

```bash
uv run experiments/run.py \
  --check-only experiments/s2/c004/mechanism.json \
  --output runs/c004-recheck
```

### Plot new runs

```bash
uv run experiments/plot.py runs/replay --output figures/replay
```

Pass a single run folder or a collection with one completed run per cycle size.
For custom inputs, the scoreboard is saved beside the plots. Incomplete runs,
reported SSP counterexamples, and hash mismatches are rejected.

### Time and memory

Recorded runs used an **AMD Ryzen 9 9950X (16 cores, 32 logical CPUs)** in a Linux
x86-64 devcontainer, with CBC 2.10.3 and PuLP 3.0.2. Times are
**order-of-magnitude estimates**, affected by other processes and runtime settings.

C4 takes seconds. C128 took about **24 h 28 min to construct** and **3 h 48 min to
check**, with peak RSS of **19.5 GiB** and **29.2 GiB**, respectively. See the
[scoreboard](SCOREBOARD.md) for per-run estimates.

`--mem-limit` is a search cache-size heuristic in GB, **not a total RAM cap**.
A smaller cache trades memory for recomputation without changing the optimization
problem; it does not reduce checker memory. The runner defaults to the archived
cache setting for known mesh sizes (including unrestricted caching for some), or
16 for other sizes. To override it:

```bash
uv run experiments/run.py --vertices 128 --mem-limit 8 --output runs/c128-cache8
```

Repository status, licensing and citation information are in the
[root README](../README.md#license-and-citation).
