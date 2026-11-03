# Recorded verification of recovered LSP certificates

This directory preserves the complete upper-verifier outcomes from November 1,
2026 for the four [recovered cycle bundles](../../certificates/upper/lsp-recovered/README.md).
All four runs exited with code 0, printed their expected exact factor and produced
empty stderr. These are historical execution records, not new runs performed
while assembling this directory.

Each of `c004/`, `c008/`, `c012/` and `c016/` contains:

- `verification.json`: status, exact factor, original command, elapsed wall/CPU
  time, bundle hashes and source fingerprints;
- `stdout.txt` and `stderr.txt`: the original verifier output;
- `provenance.json`: original numerical input and source fingerprints.

`environment.json` preserves the original interpreter/dependency information,
setup commands and negative-control result. The verifier used Python 3.14.7 and
python-flint 0.9.0. Its mathematical source files and lockfile match the included
`upper-bound/` package.

## Historical paths

The records are copied unchanged. Their commands and log paths refer to the
original workspace. Current locations are:

| Historical location | Location in this archive |
| --- | --- |
| `temp/lsp_exp/` | `lsp/` |
| `temp/sp-lower-bound-research/upper-bound-verifier/src/` | `upper-bound/src/` |
| `temp/sp-lower-bound-research/upper-bound-verifier/uv.lock` | `upper-bound/uv.lock` |
| `.scratch/s2-rational/candidates/cNNN/bundle/` | `certificates/upper/lsp-recovered/cNNN.tar.xz` |
| `.scratch/s2-rational/candidates/cNNN/verify-…/` | `validation/lsp-recovered/cNNN/` for the retained stdout/stderr |

Some provenance entries identify recovery scripts, producer helpers and
intermediate coefficient tables that are outside this release's scope. They
remain in the original records as historical identities. The full five-file
bundles contain the mechanism data needed by the included verifier; replay does
not load the omitted producer files. Use the current commands in the
[certificate guide](../../certificates/upper/lsp-recovered/README.md).

The [XZ migration checks](../README.md#xz-migration-checks) additionally record
complete acceptances of all four bundles through the current compressed wrapper.
The November 1 records here retain their original paths and input identities.
