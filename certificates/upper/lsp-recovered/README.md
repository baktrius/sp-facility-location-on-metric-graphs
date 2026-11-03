# Recovered LSP cycle certificates

These four complete upper certificates encode rational reconstructions of the
saved `s=2` LSP candidates for three agents on a continuous cycle. The mesh size
`q` identifies the source numerical experiment. Each bundle contains
`manifest.json`, `vertices.jsonl`, `attribution.jsonl`, `sp.jsonl`, and
`approximation.jsonl`, including the exact mechanism and its checking data.

All four have recorded complete upper-verifier acceptances from November 1, 2026.
Acceptance establishes ordinary SP in expectation and the stated approximation
factor for the encoded rational mechanism. It does not establish SSP or certify
the original floating-point coefficients or other mesh sizes.

| Mesh `q` | Source numerical case | Certificate | Exact factor | Decimal factor | Recorded verification time |
| ---: | --- | --- | --- | ---: | ---: |
| 4 | [c004](../../../lsp/experiments/s2/c004/) | [c004](c004.tar.xz) | `5/4` | 1.25 | 14 s |
| 8 | [c008](../../../lsp/experiments/s2/c008/) | [c008](c008.tar.xz) | `120738663/100000000` | 1.20738663 | 3.8 min |
| 12 | [c012](../../../lsp/experiments/s2/c012/) | [c012](c012.tar.xz) | `118617969/100000000` | 1.18617969 | 18.7 min |
| 16 | [c016](../../../lsp/experiments/s2/c016/) | [c016](c016.tar.xz) | `116861459/100000000` | 1.16861459 | 57.4 min |

Timings describe the recorded runs and depend on the machine. The uncompressed
bundles occupy approximately 6.6 MB, 102 MB, 510 MB and 1.61 GB, respectively.
These are the November 1 reconstructions of the archived `s=2` candidates;
older cycle recovery experiments used different inputs and settings.

## Verification

From the repository root, install the upper environment and check a bundle:

```sh
uv sync --project upper-bound --locked
python scripts/verify.py --certificate certificates/upper/lsp-recovered/c004.tar.xz
python scripts/verify.py --certificate certificates/upper/lsp-recovered/c008.tar.xz
python scripts/verify.py --certificate certificates/upper/lsp-recovered/c012.tar.xz
python scripts/verify.py --certificate certificates/upper/lsp-recovered/c016.tar.xz
```

Each successful command exits with code 0 and reports the exact factor in the table.
The wrapper verifies the compressed archive and original member hashes, extracts
to temporary storage and invokes the unchanged upper verifier. Its JSON report
records the exact stdout and exit code; acceptance requires the expected factor.

The [original verification records](../../../validation/lsp-recovered/README.md)
identify the bundle bytes and verifier sources. File hashes also appear in the
root `checksums.sha256`. The numerical archive is preserved independently; its
floating-point data have not been replaced by rational coefficients. The recovery
script and producer workspace are not required to check these finished bundles.
