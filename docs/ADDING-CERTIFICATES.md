# Adding later certificates

Recovered rational cycle data can be integrated without including the search that
produced it. A rational probability table is input to certificate construction;
it becomes evidence for a continuous upper bound only after a full verifier run.
The [recovered LSP collection](../certificates/upper/lsp-recovered/README.md)
already supplies four complete five-file bundles. Its recovery software is outside
the release scope. The steps below describe requirements for any further additions.

For each new mechanism:

1. State the exact unit graph, agent count, candidate rational factor, selectors
   and piecewise-affine interpolation rule. Recovery from a sampled LP does not
   establish continuous SP or approximation, even if every sampled row is exact.
2. Produce the five files in the [upper schema](../upper-bound/docs/SCHEMA.md).
   Include every required attribution, SP and approximation root, with coverage
   trees and all gluing data. Symmetry may guide generation, but the verifier still
   requires the complete root enumeration.
3. Run `python -m upper_bound_verifier <directory>` in the locked upper environment.
   Retain exit code, exact stdout, stderr, runtime and hashes of the actual input
   files and verifier code. Only exit 0 with the expected exact factor is acceptance.
4. Keep small complete bundles uncompressed for installation examples. Large bundles
   use a `.tar.xz` archive containing exactly the five canonical regular files at
   its root. Lower JSON certificates use `.json.xz`. The
   included orchestration script checks each member and verifies after extraction.
5. Match the actual graph and agent count against `scoreboard/configurations.json`
   with the metric helper. A cycle's number of subdivision vertices is not by itself
   a distinct continuous configuration: uniform scaling preserves SP and the factor.
6. If the new bound improves an existing endpoint, update `scoreboard/results.json`,
   retain the new complete acceptance record and file hashes, and regenerate the
   readable table with `scripts/render_scoreboard.py`. The existing upper archive
   workflow reads `validation/recorded-upper-acceptances.json`; new compressed entries
   need the same member-hash, byte-count and code-fingerprint fields. Add the
   archive identity and historical member identities to `certificates/packaging.json`.
   Preserve historical receipts when only the packaging changes. A different
   verifier version requires a deliberate update to that version check.

For a lower certificate, use the [lower format](../lower-bound/FORMAT.md), run the
complete lower CLI and match the explicit graph metric. Lower-only rows can retain
null upper and gap fields. Multiple representatives attaining the same endpoint need
not all be retained; prefer a smaller or faster certificate when the verified value
and configuration coincide.

Remove optional search narratives and numerical solver statuses from publication
copies. Preserve required mathematical scope fields and reverify after any change
to certificate bytes. A copied historical receipt describes its original hashed
inputs; it is not a receipt for a newly modified artifact. Update checksums after
all intended changes. Small examples test installation; they do not replace
complete checks of the larger certificates.
