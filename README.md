# Search and Verification for Strategyproof Facility Location on Metric Graphs

This repository contains the experimental artifacts accompanying the paper by
**Krzysztof Rogowski and Marcin Dziubiński**:
[Search and Verification for Strategyproof Facility Location on Metric Graphs](https://arxiv.org/abs/2611.05092)
(arXiv:2611.05092).
This work was supported by the Polish National Science Centre through grant
2021/42/E/HS4/00196.

The paper studies randomized facility location on continuous metric graphs, where
agents and the facility may lie anywhere on the graph, including edge interiors.
We search both for strategyproof mechanisms with low approximation ratios for
expected sum-distance cost and for unrestricted lower bounds that apply to all
strategyproof mechanisms. Together, these bounds delimit the best achievable
approximation ratio, independently of the mechanism classes used in our search.

The archive follows the two experiments in the paper's computational study:

1. **Upper- and lower-bound certificates and verification.** For the paper's
   LLM-based search experiment, we publish the resulting certificates and
   their verifiers. The LLM-based search code and procedures are not published.
   The [upper-bound verifier](upper-bound/README.md) checks strategyproofness and
   approximation guarantees for candidate mechanisms; the
   [lower-bound verifier](lower-bound/README.md) checks certificates of
   unrestricted lower bounds. Both use exact arithmetic. See the
   [graph-bound scoreboard](scoreboard/README.md) for results and the
   [verification guide](scripts/README.md) for replay instructions.
2. **Numerical realization of the heuristic search.** The
   [cycle experiments](lsp/README.md) implement the paper's search procedure
   under strong strategyproofness (SSP), using progressively finer meshes.
   These results provide numerical evidence; rational reconstructions of
   [four smaller cases](certificates/upper/lsp-recovered/README.md) also pass
   exact verification of strategyproofness and approximation. The name `lsp`
   in the code and data stands for *local strategyproofness*, the historical
   name of the condition now called *strong strategyproofness* in the paper.

## Install and run a small check

Install [uv](https://docs.astral.sh/uv/) and `xz` (`xz-utils` on Debian/Ubuntu),
or use the included [dev container](.devcontainer/devcontainer.json), which
provides both. With Docker and the VS Code Dev Containers extension installed,
open this repository in VS Code and select **Dev Containers: Reopen in Container**.
Run these commands from the archive root to install the components in separate
locked environments and check the verifiers:

```sh
# Exact upper verifier: pinned Python and dependencies.
uv sync --project upper-bound --locked

# Small complete checks; each prints 1 on success.
uv run --project upper-bound --locked python -m upper_bound_verifier upper-bound/tests/fixtures/single-edge-dictator
(cd lower-bound && uv run --project ../upper-bound --locked python -m sparse_verifier tests/fixtures/theta-m1-agents3.json)

# Numerical cycle experiments.
uv sync --project lsp --locked
```

The lower verifier uses only the Python standard library; the example above
reuses the upper verifier's environment.

## Reproducing the results

The [STOC 2027 submission downloads](https://students.mimuw.edu.pl/~krzysztor/stoc2027-downloads/)
provide all **33 certificate files** (about **2.09 GB**), their checksums and
packaging manifest, and a source archive of the
[`stoc2027-submission`](https://github.com/baktrius/sp-facility-location-on-metric-graphs/tree/stoc2027-submission)
snapshot.

Download the certificates and preserve these paths relative to the repository
root:

- `certificates/lower/`: 16 lower-bound `.json.xz` files.
- `certificates/upper/`: 13 graph upper-bound `.tar.xz` files.
- `certificates/upper/lsp-recovered/`: four recovered cycle `.tar.xz` files.

Keep the files compressed; the verification script handles decompression.
After downloading all 33 files, check the source and certificate bytes from the
repository root:

```sh
sha256sum -c checksums.sha256
```

The compressed downloads are excluded from Git by [`.gitignore`](.gitignore);
the packaging manifest and checksum index remain part of the source repository.

- **Verify the published upper and lower bounds.** Follow the
  [verification guide](scripts/README.md) to check the supplied certificates.
  The verification script handles decompression automatically. The LLM-based
  search that produced these certificates is not published.
- **Repeat the numerical cycle experiments.** Follow the
  [cycle experiment instructions](lsp/README.md) to rerun the heuristic search,
  recheck saved mechanisms, or regenerate plots and the scoreboard.

These guides include commands and resource requirements. See the
[validation records](validation/README.md) for recorded verification outcomes.

## Repository status

This repository is a research archive preserving the implementation and
experimental data supporting the article. Further feature development is not
planned. Correctness fixes and bug reports are welcome.

## License and citation

The code, documentation and experimental data are released under the
[MIT License](LICENSE).

If you use these materials, please consider citing the accompanying article:

> Krzysztof Rogowski and Marcin Dziubiński. *Search and Verification for
> Strategyproof Facility Location on Metric Graphs*. 2026.
> [arXiv:2611.05092](https://arxiv.org/abs/2611.05092).

Citation is appreciated but is not a condition of reuse under the MIT License.

```bibtex
@misc{rogowski2026searchverificationstrategyprooffacility,
      title={Search and Verification for Strategyproof Facility Location on Metric Graphs},
      author={Krzysztof Rogowski and Marcin Dziubiński},
      year={2026},
      eprint={2611.05092},
      archivePrefix={arXiv},
      primaryClass={cs.GT},
      url={https://arxiv.org/abs/2611.05092},
}
```
