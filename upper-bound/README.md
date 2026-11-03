# Upper bound verifier

This package checks a supplied randomized mechanism for ordinary strategyproofness
in expectation and an expected sum-distance approximation factor on a continuous
metric graph. Acceptance covers every real profile and unilateral deviation.
Graphs must be finite, simple, connected, bipartite and have unit edges; n >= 2.

From this directory:

```sh
uv sync --locked
uv run --locked python -m upper_bound_verifier tests/fixtures/single-edge-dictator
uv run --locked python -m upper_bound_verifier tests/fixtures/four-cycle-dictator
uv run --locked pytest -q
```

Both examples print `1` and execute complete checks. They are small installation
controls, not entries in the selected scoreboard.

A certificate directory supplies `manifest.json`, `vertices.jsonl`,
`attribution.jsonl`, `sp.jsonl`, and `approximation.jsonl`. The CLI takes an
uncompressed directory. Use the [archive wrapper](../scripts/README.md) to check
the published `.tar.xz` bundles. The CLI prints a single normalized exact rational
on success (exit 0).
Exit 1 means an invalid certificate or a replayed counterexample; exit 2 means
refusal, incompleteness, malformed input, or an internal/usage failure. Failure
diagnostics are JSON on stderr; a failed check supplies no bound on stdout.

See the [wire format](docs/SCHEMA.md), [mathematical specification](docs/SPEC.md),
[trust assessment](../docs/VERIFIER-TRUST.md), and
[theory comparison](../docs/THEORY-AND-IMPLEMENTATION.md).
The source entry point is `verification.verify_directory`; individual kernel
results and manually constructed `Accepted` objects are not full verification.

Runtime pins are CPython 3.14.7 and python-flint 0.9.0, with development and build
dependencies in `uv.lock`. No solver is required. The tests include complete positive
and negative examples and untrusted certificate construction helpers. The
`experiments/random-dictator/generate.py` helper supports the generic tests;
it does not establish acceptance. Four finished
[recovered LSP bundles](../certificates/upper/lsp-recovered/README.md) are included
elsewhere in the archive and use this same verifier.

Later recovered rational data must be expanded into the five-file format and
passed through the full CLI. See [adding certificates](../docs/ADDING-CERTIFICATES.md).
The verifier certifies ordinary SP, even when a producer searched a stronger class.
