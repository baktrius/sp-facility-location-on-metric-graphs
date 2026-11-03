# Verification evidence

This directory distinguishes recorded complete acceptances from checks performed
while preparing the original verifier export. An integrity check or a test-suite pass is
not a fresh complete verification of every benchmark certificate.

## Recorded endpoint evidence

`recorded-upper-acceptances.json` contains the complete recorded results for the
13 selected upper bundles, including exact bound, exit/output, archive and member
hashes, code/dependency fingerprints, and historical resource measurements. The original
ZIP identities remain recorded there; current XZ identities are listed separately
in `certificates/packaging.json`, with the same member hashes. The copied upper
code and lockfiles still match their historical fingerprints.
The complete 13-bundle benchmark was not rerun during handoff preparation.

`recorded-lower-acceptances.json` identifies the original accepted lower input hashes
and the included copies' hashes. Each copy has exactly the same decoded `identity`,
`certified_value` and `multipliers` as its accepted input. Only optional top-level
metadata was removed. This comparison is evidence of unchanged mathematical content;
it is not presented as a historical CLI run on the newly serialized bytes.
The copied lower code matches its accepted source fingerprints.

`verifier-sources.json` hashes every copied mathematical verifier module.
`inventory-check.json` records actual graph correspondences for all 16 configurations.
For each upper endpoint it also confirms the archive hash and code/pin fingerprints.
Graphs are read from certificates, and agent counts are checked separately. The
inventory script does not evaluate the dual constraints or continuous inequalities.

## Original verifier-export preparation checks

- `upper-tests.txt`: 964 tests passed in the copied upper package's newly installed
  locked environment. The suite uses only included code, helpers and fixtures.
- `lower-tests.txt`: 20 focused lower tests passed using the copied checker.
- `metric-tests.txt`: five matching controls passed, including changed metric ratios
  and search-resource refusal.
- `upper-smoke.json`: complete ordinary CLI runs on four generic fixtures. The
  single-edge and four-cycle dictators return factor 1; the non-SP and false-factor
  examples return exact counterexamples with exit 1 and no bound on stdout.
- `lower-recheck.json`: complete CLI attempts on every selected lower copy, each with
  a 60-second wall cap. Exit 0 with the exact expected stdout is acceptance. A null
  exit code and timeout message is an incomplete replay, not an invalid certificate.
- The small `lower-bound/tests/fixtures/four-cycle-n2.json` also returned 1. Its graph
  and two-agent count exactly equal the upper four-cycle dictator fixture's inputs.
- `environment.json`: commands, runtime versions and check scope.

The readable per-case replay summary is in [lower-status.md](lower-status.md).
The November 1 recovered LSP certificate acceptances are documented separately
in [lsp-recovered/](lsp-recovered/README.md); they are not included in these original
preparation-test totals.
The source-based trust assessment is a review aid, not a new independent audit.

## XZ migration checks

The November 2 migration checks every decompressed file against its established
hash, using a single-thread XZ decoder with a 512 MiB memory limit. The packaging
manifest records settings, sizes and compression timings. Original acceptance
records were not rewritten to claim runs on different archive bytes.

`xz-replays/` contains fresh complete-verifier attempts through the XZ wrapper.
Each report distinguishes acceptance, failure and incomplete execution. These runs
cover the selected cases explicitly listed in the reports; byte-identity checks
on the remaining archives are not presented as new mathematical verifications.
All 16 lower and all four recovered upper certificates passed fresh complete
replays. The 13 graph-bound upper proofs were not rerun; every decompressed input
file matches its historical acceptance hash. All 16 graph-inventory cases passed,
and all 28 mathematical verifier source files remain unchanged.
See [the migration summary](xz-migration.json), [full integrity audit](xz-integrity.json)
and [current inventory audit](xz-inventory.json).

## Completing longer replays

From the archive root:

```sh
python scripts/verify.py --direction lower --report /tmp/lower-complete.json
python scripts/verify.py --direction upper --report /tmp/upper-complete.json
```

These commands use a 12-hour limit per certificate by default. Use `--case ID` to
repeat one configuration, and `--timeout` to change that limit. Upper verification
extracts one archive at a time; its historical combined runtime was about 87 hours.
All timeouts, interruptions and internal failures leave the particular replay
incomplete or failed and establish no new bound. Retain both process results and
input/code identities when adding future execution evidence.
