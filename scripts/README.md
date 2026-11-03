# Verification and inventory helpers

Run these scripts from any working directory; their data root is the containing
archive folder, derived from the script location.

- `verify.py`: complete CLI checks of selected certificate copies. Defaults to all
  lower certificates. Use `--direction upper`, `--case ID`, `--timeout SECONDS`, and
  `--report FILE` to select work. Use `--certificate PATH` for any published XZ
  artifact, including a recovered upper bundle. Upper archives are extracted one at a time. Every
  result records exact output, exit code and elapsed time; timeouts never pass.
- `check_inventory.py`: verifies the selected artifact hashes against recorded upper
  acceptances, verifies the upper code/pins match those receipts, and checks graph
  correspondence and agent counts. This is not mathematical certificate verification.
- `check_packaging.py`: streams every XZ certificate through the bounded decoder,
  checks every original member hash and confirms unchanged verifier sources.
  This includes the four recovered bundles; it does not replay the proofs.
- `metric.py`: validates unit graphs, suppresses degree-two paths, divides path lengths
  by their greatest common divisor, and searches for a length/incidence-preserving
  junction bijection. A connected graph of degree two is a circle. It independently
  rechecks the resulting bijection. Search exhaustion raises an error, never a match.
- `render_scoreboard.py`: renders exact endpoint data into the readable table and
  checks rational gap arithmetic. It does not discover or verify certificates.

The correspondence ignores vertex labels and uniform metric scale, while preserving
relative path lengths and multiplicities. It preserves graph structure beyond metric
equivalence rather than asserting equivalence from a graph family name. The caller
checks agent counts separately. The helper bounds graph size and search effort;
unsupported inputs require a separate correspondence argument.

The `tests/` controls distinguish uniform subdivision from changed theta ratios,
exercise graph relabeling and pure circles, and ensure invalid graphs and exhausted
searches do not produce matches.

## Check the selected graph bounds

Run from the archive root after installing the upper environment as described in
the [main README](../README.md):

```sh
# Integrity and graph matching; these do not verify mathematical inequalities.
sha256sum -c checksums.sha256
python scripts/check_packaging.py
python scripts/check_inventory.py

# All 16 lower certificates, or select a configuration with --case.
python scripts/verify.py --direction lower --report /tmp/lower-results.json

# One upper certificate; omit --case for all 13 graph-bound upper bundles.
python scripts/verify.py --direction upper --case cycle-n3 --report /tmp/upper-results.json

# Regenerate the readable graph-bound table from its exact values.
python scripts/render_scoreboard.py
```

These scripts use `scoreboard/results.json` and the original graph-bound records.
The [recovered LSP bundles](../certificates/upper/lsp-recovered/README.md) use
`--certificate certificates/upper/lsp-recovered/c004.tar.xz` (and similarly for
`c008`, `c012`, `c016`). The wrapper calls the same upper-verifier CLI. The
LSP numerical archive uses its existing `lsp/experiments/` scripts.

Use `--lower-python` or `--upper-python` to choose an interpreter and `--timeout`
for the wall-time limit per verification. The default is 43,200 seconds. A timeout
is an incomplete check. The upper wrapper checks archive and member hashes and
extracts one bundle at a time into a temporary directory, removed after the run.
Set `TMPDIR` to choose scratch storage. Upper-only selection skips lower-only rows.

The 13 graph-bound upper archives expand to about 64.09 GB in total.
Exact compressed sizes and settings are recorded in `certificates/packaging.json`. Sequential verification needs approximately 14 GB of extraction
space for the largest bundle, in addition to the stored XZ archives. Recorded complete
upper verification took about 87 hours overall; this is a historical measurement.
See [validation](../validation/README.md) for the scope of the recorded checks.

## XZ transport and evidence

`certificate_io.py` handles the packaging layer. Upper `.tar.xz` files contain
exactly five regular files at the archive root; paths, links, duplicate members,
wrong lengths and wrong member hashes are rejected. Lower `.json.xz` files decode
to the original JSON bytes. Both formats require the expected compressed hash,
complete XZ decoding, and the historical input hashes before verifier invocation.

`certificates/packaging.json` records current archive identities and original
member identities. Historical acceptance JSON files retain their original ZIP
hashes, input hashes and timings. Those historical ZIP paths describe prior inputs;
they are not the current download paths. The mathematical verifier modules and
lockfiles have not changed. Legacy ZIP handling remains available in the wrapper.

The `xz` executable is required. Decoding uses `-T1 --memlimit-decompress=512MiB`;
this limit applies to the decoder, not the mathematical verifier or disk usage.
Set `TMPDIR` for extraction space. The archive's 8 MiB dictionaries need roughly
9 MiB of decoder working memory, plus process overhead. Parallel compression at
preset `6e` changes packaging bytes, not the certificate contents.

## Tests

From the archive root:

```sh
uv run --project upper-bound --locked pytest -q upper-bound/tests
(cd lower-bound && ../upper-bound/.venv/bin/python -m pytest -q tests)
python -m unittest discover -s scripts/tests
```
