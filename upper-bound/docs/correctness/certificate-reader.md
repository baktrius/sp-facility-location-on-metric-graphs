# Strict bundle decoding boundary (reader component)

The claim is structural decoding, never mechanism acceptance. For version one,
`reader.BundleReader(directory)` reads the fixed `manifest.json`,
`vertices.jsonl` and `attribution.jsonl` through EOF, retains their ordered
immutable records and indexes, and exposes one-shot `iter_sp_roots()` and
`iter_approximation_roots()` streams. `read_bundle(directory)` consumes both
streams fully and retains all five files' records in `DecodedBundle`.
Extra documentation files are ignored. The manifest cannot redirect a filename.

For streaming callers, **both iterators must reach `StopIteration`**. Receiving
the last expected root is insufficient: the following step reads trailing
records and checks EOF. Closing or abandoning a stream leaves
`streams_exhausted` false. That property records syntactic consumption only;
it proves prescribed SP/APX root completeness after the comparison-domain component strengthening,
but neither coverage nor admissibility. full-verification component must also
check every later
mathematical obligation before any acceptance. The reader provides no
accepted result, bound output, CLI or residual coefficients.

## Checked assumptions and why the checks suffice

The JSON decoder implements the object, array, string, literal and integer
syntax, with standard-library JSON string decoding. Every object key is
checked before insertion, so duplicates, including escaped spellings, cannot
silently override fields. Every numeric token is inspected before conversion:
floats, exponent notation and nonfinite tokens are rejected everywhere, even
in a field that would subsequently be rejected as unknown. Decimal integer
tokens go through FLINT `fmpz` then native `int`, never through a float or
Python's limited decimal string conversion. This preserves arbitrary integers
and makes JSON integer `-0` equal zero. Exact scalar slots reuse the reviewed
canonical `parse_rational`; string `"-0"` remains forbidden. Strict type
checks exclude booleans in every numeric slot. No global digit limit changes.
Runtime nesting/dimension limits return incompletion rather than success.

UTF-8 input is decoded by physical line for JSONL, and nonempty records must
be complete JSON objects on a single line. Only JSON whitespace (`space`, tab,
CR, LF) counts as blank. Other whitespace and trailing content are rejected.
The manifest is one complete JSON object. Token failures retain exact file and
physical line; decoded field errors name the record's starting line (line 1
for manifest fields). EOF errors use the next physical line. Root and cell
context is attached once available, including JSON errors fetched inside a
known root. Missing/unreadable files retain their fixed filename.

Manifest fields and nested graph/selectors use exact field sets, version and
identity checks, the reviewed graph restrictions and ordered selector parsers,
integer agent count at least two, and rational claimed factor at least one.
Global vertex IDs are nonempty strings and map injectively to canonical labeled
profiles. Equality is coordinatewise canonical graph-point equality, so a
shared endpoint in several charts cannot receive two global IDs. Every global
record is checked, even when unused. Separate regional simplex weight rows
remain separate when they refer to the same global vertex.

`attribution_root_keys(graph, agents)` generates the Cartesian product of edge
indices independently of input. Each header must equal its next lexicographic
tuple, and EOF must also exhaust that generator. Induction on headers gives
exactly one occurrence of every required attribution root in order; the final
comparison catches a missing suffix or empty stream. Extra, repeated or
reordered headers fail before they can form retained attribution. No supplied
count is trusted. comparison-domain component adds independently generated SP/APX sequences:
every header must match the next required root and EOF must exhaust the
sequence. The supplied-order check remains an additional diagnostic. See
[Comparison C1 and affine pullback](comparison-domains.md) for the current
contract and the prerequisite supersession accounting.

Within each block, the parser enforces vertex, simplex, then tree-node order,
and an exact end record. Auxiliary tables are root-local, injective and checked
against the root's edge charts; IDs may repeat in another block or overlap a
global spelling. Attribution simplices use only the global vertex table;
comparison simplices use only their local table. Each has exactly dimension+1
distinct, resolving vertex references. Weight rows match vertex/selector counts;
branch lists match `2|F|` or `n|F|+n` and contain nonnegative integer indices.
Attribution simplex IDs are globally unique; comparison simplex and tree-node
IDs are unique within their own root namespaces. Regional references resolve
only to attribution simplices, retaining truthful/deviated order.

At block end, the header resolves to a declared node, split children resolve
to nodes, and leaves resolve to local simplices. Forward children are allowed.
Split normals have the root dimension and are nonzero exact rationals. These
checks establish reference resolution only. They do not establish a genuine
rooted acyclic tree, computed memberships, routing or coverage (coverage component).

## Remaining obligations and evidence

Simplex rank/orientation/containment and interpolation remain simplex-geometry component;
coverage and tree semantics coverage component; local/global mesh conformity checks; probability normalization/sign and lottery gluing lottery component; valid
branch arity and branch inequalities distance-branch component; regional root/containment
semantics comparison-domain component;
residual signs SP and approximation stages; full composition/acceptance full-verification component.
In particular, parsing may retain negative or unnormalized weights, incorrect
geometric cells and resolving cyclic node references. Tests explicitly show
this boundary. A malformed record is refused; duplicate canonical IDs,
unresolved certificate references, chart failures and root sequence failures
are `invalid_certificate`. Bundle point records (global and local), manifest
constant points and peak selector indices also classify unresolved declared
vertex/edge/agent references this way, preserving their stable reference codes.
The bundle wrappers leave the reviewed graph parsers unchanged: malformed graph
declarations remain refused, as do malformed point/selector shapes, numeric
types and rational forms. Canonical coordinate syntax is checked before edge
resolution, so an unresolved edge with a malformed coordinate remains refused.
A negative integer branch is `invalid_certificate`/`reference_branch`, since it
cannot name any permitted branch; bool/noninteger branch slots remain malformed.
Nonnegative per-term branch arity and formula semantics are still distance-branch component.
Neither category is an SP counterexample.

Public tests cover a five-file two-agent bundle with forward tree children and
reused local IDs; a three-agent bundle; constant selectors and vertex candidate
order; independent hand-listed attribution tuples; all completeness corruptions;
separate regional weights; namespace confusion; shape/order/reference failures;
JSON failures in all five files; UTF-8 and exact source locations; 6000-digit
integer tokens and integer/string negative zero; strict blank lines; trailing
records, partial consumption and both EOF steps. The fixtures claim structural
decoding only, and need not satisfy the deferred geometric/lottery checks.
