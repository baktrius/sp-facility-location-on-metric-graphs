"""Public wire-reader tests; these fixtures assert no mechanism guarantee."""

import json
from pathlib import Path
from types import GeneratorType
from typing import Any

from flint import fmpq


def write_records(directory, filename, records):
    (directory / filename).write_text(
        "\n".join(json.dumps(record) for record in records) + "\n"
    )


def tiny_bundle(directory: Path):
    manifest = {
        "schema_version": 1,
        "identity": {
            "formulation": "metric_graph_upper",
            "result": "unconditional",
            "graph": {"vertices": ["a", "b"], "edges": [["b", "a"]]},
            "agents": 2,
            "selectors": [{"kind": "peak", "agent": 1}, {"kind": "peak", "agent": 0}],
        },
        "certified_value": 1,
    }
    (directory / "manifest.json").write_text(json.dumps(manifest, indent=2))
    points = [("a", "a"), ("b", "a"), ("b", "b"), ("a", "b")]
    write_records(
        directory,
        "vertices.jsonl",
        [
            {"id": f"v{i}", "point": [{"vertex": p} for p in point]}
            for i, point in enumerate(points)
        ],
    )
    attribution = [
        {"type": "root", "key": {"edges": [0, 0]}, "tree": "split"},
        {
            "type": "simplex",
            "id": "T0",
            "vertices": ["v0", "v1", "v2"],
            "weights": [[1, 0]] * 3,
        },
        {
            "type": "simplex",
            "id": "T1",
            "vertices": ["v0", "v2", "v3"],
            "weights": [[0, 1]] * 3,
        },
        {
            "type": "split",
            "id": "split",
            "normal": [1, -1],
            "offset": 0,
            "minus": "left",
            "plus": "right",
        },
        {"type": "leaf", "id": "left", "simplex": "T0"},
        {"type": "leaf", "id": "right", "simplex": "T1"},
        {"type": "end"},
    ]
    write_records(directory, "attribution.jsonl", attribution)
    for filename, dimension in [("sp.jsonl", 3), ("approximation.jsonl", 2)]:
        records: list[dict[str, Any]] = []
        for agent in range(2):
            key = {"edges": [0] * dimension}
            if dimension == 3:
                key["agent"] = agent
            else:
                key["candidate"] = {"kind": "report", "agent": agent}
            records.append({"type": "root", "key": key, "tree": "node"})
            for i in range(dimension + 1):
                point = [{"vertex": "a"}] * dimension
                if i:
                    point[i - 1] = {"vertex": "b"}
                records.append({"type": "vertex", "id": f"w{i}", "point": point})
            simplex = {
                "type": "simplex",
                "id": "cell",
                "vertices": [f"w{i}" for i in range(dimension + 1)],
                "truthful": "T0",
                "branches": [0] * (4 if dimension == 3 else 6),
            }
            if dimension == 3:
                simplex["deviated"] = "T1"
            records += [
                simplex,
                {"type": "leaf", "id": "node", "simplex": "cell"},
                {"type": "end"},
            ]
        write_records(directory, filename, records)
    return directory


def test_read_structurally_complete_bundle_retains_order_and_regional_rows(tmp_path):
    from upper_bound_verifier.reader import read_bundle

    bundle = read_bundle(tiny_bundle(tmp_path))
    assert bundle.manifest.graph.edges == (("b", "a"),)
    assert all(
        isinstance(selector, PeakSelector) for selector in bundle.manifest.selectors
    )
    assert [
        selector.agent
        for selector in bundle.manifest.selectors
        if isinstance(selector, PeakSelector)
    ] == [1, 0]
    assert tuple(bundle.vertices) == ("v0", "v1", "v2", "v3")
    first, second = bundle.attribution[0].simplices
    assert isinstance(first, AttributionSimplex)
    assert isinstance(second, AttributionSimplex)
    assert first.vertices == ("v0", "v1", "v2")
    assert first.weights[0] == (fmpq(1), fmpq(0))
    assert second.weights[0] == (fmpq(0), fmpq(1))
    assert bundle.attribution[0].tree == "split"
    node = bundle.attribution[0].nodes[0]
    assert isinstance(node, SplitNode)
    assert node.minus == "left"
    assert [root.key.to_data()["agent"] for root in bundle.sp] == [0, 1]
    assert bundle.sp[0].vertices[0].id == bundle.sp[1].vertices[0].id == "w0"
    cell = bundle.approximation[0].simplices[0]
    assert isinstance(cell, ComparisonSimplex)
    assert cell.branches == (0,) * 6


def test_json_duplicate_keys_and_float_tokens_are_refused_with_exact_line(tmp_path):
    import pytest

    from upper_bound_verifier.failures import FailureKind, VerificationError
    from upper_bound_verifier.reader import read_bundle

    tiny_bundle(tmp_path)
    path = tmp_path / "manifest.json"
    path.write_text(
        path.read_text().replace(
            '"schema_version": 1,', '"schema_version": 1,\n  "schema_version": 1,'
        )
    )
    with pytest.raises(VerificationError) as caught:
        read_bundle(tmp_path)
    assert caught.value.failure.kind is FailureKind.REFUSED
    assert caught.value.failure.location == {"file": "manifest.json", "line": 3}


def test_empty_attribution_stream_is_an_invalid_certificate(tmp_path):
    import pytest

    from upper_bound_verifier.failures import FailureKind, VerificationError
    from upper_bound_verifier.reader import read_bundle

    tiny_bundle(tmp_path)
    (tmp_path / "attribution.jsonl").write_text("\n\n")
    (tmp_path / "sp.jsonl").write_text("")
    (tmp_path / "approximation.jsonl").write_text("")
    with pytest.raises(VerificationError) as caught:
        read_bundle(tmp_path)
    assert caught.value.failure.kind is FailureKind.INVALID_CERTIFICATE
    assert caught.value.failure.code == "reference_root_sequence"
    assert caught.value.failure.location == {"file": "attribution.jsonl", "line": 3}


def records(directory, filename):
    return [
        json.loads(line)
        for line in (directory / filename).read_text().splitlines()
        if line.strip()
    ]


def two_edge_bundle(directory):
    import copy

    tiny_bundle(directory)
    manifest = json.loads((directory / "manifest.json").read_text())
    manifest["identity"]["graph"] = {
        "vertices": ["a", "b", "c"],
        "edges": [["b", "a"], ["b", "c"]],
    }
    (directory / "manifest.json").write_text(json.dumps(manifest))
    original = records(directory, "attribution.jsonl")
    blocks = []
    # Hand-listed expected order, independent of production root enumeration.
    for i, edges in enumerate([[0, 0], [0, 1], [1, 0], [1, 1]]):
        block = copy.deepcopy(original)
        block[0]["key"]["edges"] = edges
        block[1]["id"] = block[4]["simplex"] = f"T{2 * i}"
        block[2]["id"] = block[5]["simplex"] = f"T{2 * i + 1}"
        blocks.append(block)
    write_records(
        directory, "attribution.jsonl", [item for block in blocks for item in block]
    )
    complete_comparison_streams(directory)
    return blocks


def complete_comparison_streams(directory):
    """Expand syntactic templates independently into all required chart keys.

    The reader now requires completeness even in tests that claim no geometry.
    Points use the current edge's endpoints, preserving each template's 0/1
    coordinates relative to the original reversed b-a edge.
    """
    import copy
    from itertools import product

    identity = json.loads((directory / "manifest.json").read_text())["identity"]
    edges = identity["graph"]["edges"]
    agents = identity["agents"]
    vertices = identity["graph"]["vertices"]
    candidates = [{"kind": "report", "agent": i} for i in range(agents)] + [
        {"kind": "vertex", "vertex": v}
        for v in vertices
        if sum(v in edge for edge in edges) >= 3
    ]
    for filename, dimension, indices in [
        ("sp.jsonl", agents + 1, list(range(agents))),
        ("approximation.jsonl", agents, candidates),
    ]:
        rows = records(directory, filename)
        end = next(i for i, row in enumerate(rows) if row["type"] == "end") + 1
        template = rows[:end]
        expanded = []
        for index in indices:
            for chart in product(range(len(edges)), repeat=dimension):
                block = copy.deepcopy(template)
                block[0]["key"] = {"edges": list(chart)}
                block[0]["key"]["agent" if filename == "sp.jsonl" else "candidate"] = (
                    index
                )
                for row in block:
                    if row["type"] == "vertex":
                        row["point"] = [
                            {"vertex": edges[e][int(p["vertex"] == "a")]}
                            for e, p in zip(chart, row["point"], strict=True)
                        ]
                expanded.extend(block)
        write_records(directory, filename, expanded)


def assert_failure(directory, filename, code=None, kind=None, line=None):
    import pytest

    from upper_bound_verifier.failures import VerificationError
    from upper_bound_verifier.reader import read_bundle

    with pytest.raises(VerificationError) as caught:
        read_bundle(directory)
    failure = caught.value.failure
    assert failure.location is not None
    assert failure.location["file"] == filename
    assert type(failure.location["line"]) is int
    if code is not None:
        assert failure.code == code
    if kind is not None:
        assert failure.kind is kind
    if line is not None:
        assert failure.location["line"] == line
    return failure


import pytest

from upper_bound_verifier.failures import FailureKind
from upper_bound_verifier.graph import PeakSelector, VertexPoint
from upper_bound_verifier.reader import AttributionSimplex, ComparisonSimplex, SplitNode


@pytest.mark.parametrize(
    "order",
    [
        [1, 2, 3],
        [0, 2, 3],
        [0, 1, 2],
        [0, 0, 1, 2, 3],
        [0, 2, 1, 3],
        [0, 1, 2, 3, 3],
        [],
    ],
)
def test_attribution_missing_extra_duplicate_reordered_and_empty_fail(tmp_path, order):
    blocks = two_edge_bundle(tmp_path)
    write_records(
        tmp_path, "attribution.jsonl", [item for i in order for item in blocks[i]]
    )
    assert_failure(
        tmp_path,
        "attribution.jsonl",
        "reference_root_sequence",
        FailureKind.INVALID_CERTIFICATE,
    )


def test_attribution_sequence_retained_in_independently_expected_order(tmp_path):
    from upper_bound_verifier.reader import BundleReader, read_bundle

    two_edge_bundle(tmp_path)
    bundle = read_bundle(tmp_path)
    assert [root.key.edges for root in bundle.attribution] == [
        (0, 0),
        (0, 1),
        (1, 0),
        (1, 1),
    ]
    # Attribution-only construction is available, but full decoding requires
    # every comparison root and still proves no geometric or mechanism claim.
    (tmp_path / "sp.jsonl").write_text("")
    (tmp_path / "approximation.jsonl").write_text("")
    reader = BundleReader(tmp_path)
    assert len(reader.attribution) == 4
    assert_failure(tmp_path, "sp.jsonl", "reference_root_sequence")


@pytest.mark.parametrize(
    "filename",
    [
        "manifest.json",
        "vertices.jsonl",
        "attribution.jsonl",
        "sp.jsonl",
        "approximation.jsonl",
    ],
)
@pytest.mark.parametrize(
    "bad",
    [
        '{"x":0,"x":1}',
        '{"x":1.0}',
        '{"x":1e0}',
        '{"x":NaN}',
        '{"x":Infinity}',
        '{"x":-Infinity}',
        "{} garbage",
        "{} {}",
        '{"x":01}',
        '{"x":+1}',
        '{"x":1,}',
        "[0,]",
        '{"x":"\\q"}',
        "{",
    ],
)
def test_malformed_json_is_rejected_in_every_required_file(tmp_path, filename, bad):
    tiny_bundle(tmp_path)
    (tmp_path / filename).write_text("\n" + bad + "\n")
    assert_failure(
        tmp_path,
        filename,
        "schema_json",
        FailureKind.REFUSED,
        3 if bad == "{" and filename == "manifest.json" else 2,
    )


def test_duplicate_escaped_key_is_also_a_duplicate(tmp_path):
    tiny_bundle(tmp_path)
    (tmp_path / "vertices.jsonl").write_text('{"id":"v", "\\u0069d":"w", "point":[]}\n')
    assert_failure(tmp_path, "vertices.jsonl", "schema_json", FailureKind.REFUSED, 1)


@pytest.mark.parametrize(
    "filename",
    [
        "manifest.json",
        "vertices.jsonl",
        "attribution.jsonl",
        "sp.jsonl",
        "approximation.jsonl",
    ],
)
def test_missing_required_file_is_refused_when_all_streams_are_read(tmp_path, filename):
    tiny_bundle(tmp_path)
    (tmp_path / filename).unlink()
    assert_failure(tmp_path, filename, "schema_read", FailureKind.REFUSED)


@pytest.mark.parametrize(
    "filename",
    ["vertices.jsonl", "attribution.jsonl", "sp.jsonl", "approximation.jsonl"],
)
def test_trailing_records_after_valid_blocks_or_vertices_are_checked(
    tmp_path, filename
):
    tiny_bundle(tmp_path)
    path = tmp_path / filename
    old = path.read_text()
    path.write_text(old + '\n{"type":"end"}\n')
    assert_failure(
        tmp_path, filename, kind=FailureKind.REFUSED, line=len(old.splitlines()) + 2
    )


@pytest.mark.parametrize(
    "filename",
    [
        "manifest.json",
        "vertices.jsonl",
        "attribution.jsonl",
        "sp.jsonl",
        "approximation.jsonl",
    ],
)
def test_unknown_fields_are_refused_in_all_files(tmp_path, filename):
    tiny_bundle(tmp_path)
    if filename == "manifest.json":
        data = json.loads((tmp_path / filename).read_text())
        data["provenance"] = {}
        (tmp_path / filename).write_text(json.dumps(data))
    else:
        data = records(tmp_path, filename)
        data[0]["asserted_valid"] = True
        write_records(tmp_path, filename, data)
    assert_failure(tmp_path, filename, "schema_fields", FailureKind.REFUSED, 1)


@pytest.mark.parametrize(
    "field,value",
    [
        ("schema_version", True),
        ("schema_version", "1"),
        ("certified_value", False),
        ("certified_value", "-0"),
        ("certified_value", "2/4"),
        ("certified_value", "1/1"),
        ("certified_value", " 1"),
        ("certified_value", "+1"),
        ("certified_value", "01"),
        ("certified_value", "0"),
        ("schema_version", 2),
    ],
)
def test_manifest_numeric_and_scope_boundary(tmp_path, field, value):
    tiny_bundle(tmp_path)
    data = json.loads((tmp_path / "manifest.json").read_text())
    data[field] = value
    (tmp_path / "manifest.json").write_text(json.dumps(data))
    assert_failure(tmp_path, "manifest.json", kind=FailureKind.REFUSED)


@pytest.mark.parametrize(
    "target",
    [
        "agent_count",
        "selector",
        "edge",
        "weight",
        "branch",
        "normal",
        "offset",
        "coordinate",
        "sp_agent",
        "candidate",
    ],
)
def test_booleans_are_refused_in_each_numeric_record_slot(tmp_path, target):
    tiny_bundle(tmp_path)
    if target in ("agent_count", "selector"):
        path = tmp_path / "manifest.json"
        data = json.loads(path.read_text())
        if target == "agent_count":
            data["identity"]["agents"] = True
        else:
            data["identity"]["selectors"][0]["agent"] = True
        path.write_text(json.dumps(data))
        filename = path.name
    else:
        filename = (
            "sp.jsonl"
            if target in ("sp_agent", "branch")
            else "approximation.jsonl"
            if target == "candidate"
            else "attribution.jsonl"
            if target in ("edge", "weight", "normal", "offset")
            else "vertices.jsonl"
        )
        data = records(tmp_path, filename)
        if target == "edge":
            data[0]["key"]["edges"][0] = True
        elif target == "weight":
            data[1]["weights"][0][0] = True
        elif target in ("normal", "offset"):
            if target == "normal":
                data[3]["normal"][0] = True
            else:
                data[3]["offset"] = True
        elif target == "coordinate":
            data[0]["point"][0] = {"edge": 0, "coordinate": True}
        elif target == "branch":
            data[5]["branches"][0] = True
        elif target == "sp_agent":
            data[0]["key"]["agent"] = True
        else:
            data[0]["key"]["candidate"]["agent"] = True
        write_records(tmp_path, filename, data)
    assert_failure(tmp_path, filename, kind=FailureKind.REFUSED)


@pytest.mark.parametrize(
    "filename,index,field,bad",
    [
        ("vertices.jsonl", 0, "point", []),
        ("attribution.jsonl", 0, "key", {"edges": [0]}),
        ("attribution.jsonl", 1, "vertices", ["v0", "v1"]),
        ("attribution.jsonl", 1, "weights", [[1, 0]]),
        ("attribution.jsonl", 1, "weights", [[1], [1, 0], [1, 0]]),
        ("attribution.jsonl", 3, "normal", [1]),
        ("attribution.jsonl", 3, "normal", [0, 0]),
        ("sp.jsonl", 0, "key", {"agent": 0, "edges": [0, 0]}),
        ("sp.jsonl", 1, "point", [{"vertex": "a"}] * 2),
        ("sp.jsonl", 5, "branches", [0] * 3),
        ("sp.jsonl", 5, "branches", [0] * 5),
        ("sp.jsonl", 5, "branches", [0, "0", 0, 0]),
        ("approximation.jsonl", 4, "branches", [0] * 5),
    ],
)
def test_wrong_array_shapes_and_noninteger_indices_are_refused(
    tmp_path, filename, index, field, bad
):
    tiny_bundle(tmp_path)
    data = records(tmp_path, filename)
    data[index][field] = bad
    write_records(tmp_path, filename, data)
    assert_failure(tmp_path, filename, kind=FailureKind.REFUSED, line=index + 1)


@pytest.mark.parametrize(
    "filename,index,field,value,code",
    [
        (
            "attribution.jsonl",
            1,
            "vertices",
            ["v0", "v0", "v2"],
            "reference_simplex_vertex",
        ),
        (
            "attribution.jsonl",
            1,
            "vertices",
            ["v0", "w0", "v2"],
            "reference_simplex_vertex",
        ),
        (
            "sp.jsonl",
            5,
            "vertices",
            ["v0", "w1", "w2", "w3"],
            "reference_simplex_vertex",
        ),
        ("sp.jsonl", 5, "truthful", "cell", "reference_region"),
        ("sp.jsonl", 5, "deviated", "missing", "reference_region"),
        ("attribution.jsonl", 0, "tree", "T0", "reference_tree"),
        ("attribution.jsonl", 3, "minus", "T0", "reference_tree"),
        ("attribution.jsonl", 4, "simplex", "v0", "reference_tree"),
        ("sp.jsonl", 6, "simplex", "T0", "reference_tree"),
        ("attribution.jsonl", 2, "id", "T0", "reference_duplicate_simplex"),
        ("attribution.jsonl", 5, "id", "left", "reference_duplicate_node"),
    ],
)
def test_unresolved_references_and_duplicate_ids_are_certificate_failures(
    tmp_path, filename, index, field, value, code
):
    tiny_bundle(tmp_path)
    data = records(tmp_path, filename)
    data[index][field] = value
    write_records(tmp_path, filename, data)
    failure = assert_failure(
        tmp_path, filename, code, FailureKind.INVALID_CERTIFICATE, index + 1
    )
    assert "root" in failure.location
    if field in ("vertices", "truthful", "deviated"):
        assert failure.location["cell"] in ("T0", "cell")


def test_global_id_cannot_rescue_same_spelling_missing_local_vertex(tmp_path):
    tiny_bundle(tmp_path)
    data = records(tmp_path, "sp.jsonl")
    data[5]["vertices"][0] = "v0"
    write_records(tmp_path, "sp.jsonl", data)
    assert_failure(
        tmp_path,
        "sp.jsonl",
        "reference_simplex_vertex",
        FailureKind.INVALID_CERTIFICATE,
    )


@pytest.mark.parametrize("duplicate_id", [False, True])
def test_global_vertex_injectivity_across_charts_including_unused_records(
    tmp_path, duplicate_id
):
    two_edge_bundle(tmp_path)
    data = records(tmp_path, "vertices.jsonl")
    shared = {"id": "shared", "point": [{"vertex": "b"}, {"vertex": "a"}]}
    if duplicate_id:
        shared = {"id": "v0", "point": [{"vertex": "c"}, {"vertex": "c"}]}
    data.append(shared)
    write_records(tmp_path, "vertices.jsonl", data)
    assert_failure(
        tmp_path,
        "vertices.jsonl",
        "reference_duplicate_vertex",
        FailureKind.INVALID_CERTIFICATE,
        5,
    )


@pytest.mark.parametrize("mode", ["id", "point", "chart"])
def test_auxiliary_vertices_have_injective_local_tables_and_chart_membership(
    tmp_path, mode
):
    two_edge_bundle(tmp_path)
    data = records(tmp_path, "sp.jsonl")
    if mode == "id":
        data[2]["id"] = "w0"
    elif mode == "point":
        data[2]["point"] = data[1]["point"]
    else:
        data[2]["point"][0] = {"vertex": "c"}
    write_records(tmp_path, "sp.jsonl", data)
    code = "reference_chart" if mode == "chart" else "reference_duplicate_vertex"
    assert_failure(tmp_path, "sp.jsonl", code, FailureKind.INVALID_CERTIFICATE, 3)


@pytest.mark.parametrize(
    "filename", ["attribution.jsonl", "sp.jsonl", "approximation.jsonl"]
)
def test_missing_end_record_is_truncation_with_eof_location(tmp_path, filename):
    tiny_bundle(tmp_path)
    data = records(tmp_path, filename)
    data.pop()
    write_records(tmp_path, filename, data)
    assert_failure(
        tmp_path, filename, "schema_truncated", FailureKind.REFUSED, len(data) + 1
    )


@pytest.mark.parametrize(
    "filename,first,second",
    [("sp.jsonl", 2, 6), ("attribution.jsonl", 2, 4), ("attribution.jsonl", 0, 1)],
)
def test_wrong_record_order_is_refused(tmp_path, filename, first, second):
    tiny_bundle(tmp_path)
    data = records(tmp_path, filename)
    data[first], data[second] = data[second], data[first]
    write_records(tmp_path, filename, data)
    assert_failure(tmp_path, filename, kind=FailureKind.REFUSED)


def test_auxiliary_vertex_record_in_attribution_is_refused(tmp_path):
    tiny_bundle(tmp_path)
    data = records(tmp_path, "attribution.jsonl")
    data.insert(1, {"type": "vertex", "id": "local", "point": [{"vertex": "a"}] * 2})
    write_records(tmp_path, "attribution.jsonl", data)
    assert_failure(
        tmp_path, "attribution.jsonl", "schema_order", FailureKind.REFUSED, 2
    )


@pytest.mark.parametrize("filename", ["sp.jsonl", "approximation.jsonl"])
def test_comparison_roots_must_be_strictly_in_supplied_canonical_order(
    tmp_path, filename
):
    tiny_bundle(tmp_path)
    data = records(tmp_path, filename)
    split = 8 if filename == "sp.jsonl" else 7
    write_records(tmp_path, filename, data[split:] + data[:split])
    assert_failure(
        tmp_path,
        filename,
        "reference_root_sequence",
        FailureKind.INVALID_CERTIFICATE,
        1,
    )


def test_large_json_integer_tokens_and_negative_zero_are_exact(tmp_path):
    import sys

    from upper_bound_verifier.exact import format_rational
    from upper_bound_verifier.reader import read_bundle

    tiny_bundle(tmp_path)
    limit = sys.get_int_max_str_digits()
    huge = "9" * 6000
    path = tmp_path / "manifest.json"
    path.write_text(
        path.read_text().replace('"certified_value": 1', '"certified_value": ' + huge)
    )
    path = tmp_path / "attribution.jsonl"
    path.write_text(path.read_text().replace("[[1, 0]", "[[" + huge + ", -0]"))
    bundle = read_bundle(tmp_path)
    assert format_rational(bundle.manifest.certified_value) == huge
    cell = bundle.attribution[0].simplices[0]
    assert isinstance(cell, AttributionSimplex)
    assert format_rational(cell.weights[0][0]) == huge
    assert cell.weights[0][1] == 0
    assert sys.get_int_max_str_digits() == limit
    path.write_text(path.read_text().replace(", -0]", ', "-0"]'))
    assert_failure(
        tmp_path, "attribution.jsonl", "schema_rational_syntax", FailureKind.REFUSED, 2
    )


def test_streams_exhausted_requires_both_iterators_and_their_eof_steps(tmp_path):
    from upper_bound_verifier.reader import BundleReader

    tiny_bundle(tmp_path)
    reader = BundleReader(tmp_path)
    assert not reader.streams_exhausted
    sp = reader.iter_sp_roots()
    assert next(sp).key.to_data()["agent"] == 0
    assert next(sp).key.to_data()["agent"] == 1
    assert not reader.streams_exhausted
    assert list(reader.iter_approximation_roots())
    assert not reader.streams_exhausted
    with pytest.raises(StopIteration):
        next(sp)
    assert reader.streams_exhausted
    with pytest.raises(ValueError, match="one-shot"):
        reader.iter_sp_roots()


def test_trailing_record_cannot_hide_behind_last_streamed_root(tmp_path):
    from upper_bound_verifier.failures import VerificationError
    from upper_bound_verifier.reader import BundleReader

    tiny_bundle(tmp_path)
    path = tmp_path / "sp.jsonl"
    with path.open("a") as stream:
        stream.write('{"type":"end"}\n')
    reader = BundleReader(tmp_path)
    list(reader.iter_approximation_roots())
    sp = reader.iter_sp_roots()
    next(sp)
    next(sp)
    assert not reader.streams_exhausted
    with pytest.raises(VerificationError) as caught:
        next(sp)
    assert caught.value.failure.location is not None
    assert caught.value.failure.location["line"] == 17
    assert not reader.streams_exhausted


def test_documentation_files_are_ignored_and_cannot_redirect_inputs(tmp_path):
    from upper_bound_verifier.reader import read_bundle

    tiny_bundle(tmp_path)
    (tmp_path / "notes.json").write_text('{"certified_value":NaN}')
    assert read_bundle(tmp_path).manifest.certified_value == 1
    data = json.loads((tmp_path / "manifest.json").read_text())
    data["paths"] = {"sp": "notes.json"}
    (tmp_path / "manifest.json").write_text(json.dumps(data))
    assert_failure(tmp_path, "manifest.json", "schema_fields", FailureKind.REFUSED)


def test_syntax_decoding_does_not_check_admissibility_or_tree_routing(tmp_path):
    from upper_bound_verifier.reader import BundleReader

    tiny_bundle(tmp_path)
    data = records(tmp_path, "attribution.jsonl")
    data[1]["weights"][0] = [-1, 7]
    # Declared child references resolve, but a self-loop is not a genuine tree.
    data[3]["minus"] = "split"
    write_records(tmp_path, "attribution.jsonl", data)
    reader = BundleReader(tmp_path)
    cell = reader.attribution[0].simplices[0]
    node = reader.attribution[0].nodes[0]
    assert isinstance(cell, AttributionSimplex)
    assert isinstance(node, SplitNode)
    assert cell.weights[0] == (fmpq(-1), fmpq(7))
    assert node.minus == "split"
    assert not reader.streams_exhausted
    list(reader.iter_sp_roots())
    list(reader.iter_approximation_roots())
    assert reader.streams_exhausted
    assert not hasattr(reader, "accepted")


@pytest.mark.parametrize("trailing", ["\v", "\f", "\u00a0", "\u2003"])
@pytest.mark.parametrize(
    "filename",
    ["vertices.jsonl", "attribution.jsonl", "sp.jsonl", "approximation.jsonl"],
)
def test_non_json_whitespace_cannot_disappear_as_a_blank_record(
    tmp_path, filename, trailing
):
    tiny_bundle(tmp_path)
    path = tmp_path / filename
    original = path.read_text()
    path.write_text(original + trailing + "\n")
    assert_failure(
        tmp_path,
        filename,
        "schema_json",
        FailureKind.REFUSED,
        len(original.splitlines()) + 1,
    )


def test_json_blank_lines_preserve_physical_source_locations(tmp_path):
    from upper_bound_verifier.reader import read_bundle

    tiny_bundle(tmp_path)
    for filename in [
        "vertices.jsonl",
        "attribution.jsonl",
        "sp.jsonl",
        "approximation.jsonl",
    ]:
        path = tmp_path / filename
        path.write_text("\n \t\r\n" + path.read_text() + " \t\n\n")
    bundle = read_bundle(tmp_path)
    assert bundle.attribution[0].location.line == 3
    assert bundle.attribution[0].simplices[0].location.to_dict() == {
        "file": "attribution.jsonl",
        "line": 4,
        "root": {"edges": [0, 0]},
        "cell": "T0",
    }
    assert bundle.vertices["v0"].location.line == 3


@pytest.mark.parametrize(
    "filename", ["attribution.jsonl", "sp.jsonl", "approximation.jsonl"]
)
def test_json_error_inside_block_keeps_available_root_context(tmp_path, filename):
    tiny_bundle(tmp_path)
    path = tmp_path / filename
    lines = path.read_text().splitlines()
    key = json.loads(lines[0])["key"]
    lines[1] = '{"id":1.0}'
    path.write_text("\n".join(lines) + "\n")
    failure = assert_failure(tmp_path, filename, "schema_json", FailureKind.REFUSED, 2)
    assert failure.location["root"] == key


@pytest.mark.parametrize("filename", ["manifest.json", "vertices.jsonl", "sp.jsonl"])
def test_invalid_utf8_has_a_physical_file_and_line(tmp_path, filename):
    tiny_bundle(tmp_path)
    path = tmp_path / filename
    if filename == "manifest.json":
        path.write_bytes(b'{\n"bad": "\xff"}\n')
    else:
        path.write_bytes(b'\n{"bad": "\xff"}\n')
    assert_failure(tmp_path, filename, "schema_encoding", FailureKind.REFUSED, 2)


@pytest.mark.parametrize(
    "filename,index,field",
    [
        ("vertices.jsonl", 0, "id"),
        ("attribution.jsonl", 0, "tree"),
        ("attribution.jsonl", 1, "id"),
        ("attribution.jsonl", 4, "id"),
        ("attribution.jsonl", 4, "simplex"),
        ("sp.jsonl", 1, "id"),
        ("sp.jsonl", 5, "truthful"),
        ("sp.jsonl", 5, "deviated"),
    ],
)
def test_record_ids_must_be_nonempty_strings(tmp_path, filename, index, field):
    tiny_bundle(tmp_path)
    data = records(tmp_path, filename)
    data[index][field] = ""
    write_records(tmp_path, filename, data)
    assert_failure(tmp_path, filename, "schema_id", FailureKind.REFUSED, index + 1)


def test_empty_graph_vertex_label_remains_valid_through_bundle_reader(tmp_path):
    from upper_bound_verifier.reader import read_bundle

    tiny_bundle(tmp_path)
    for path in tmp_path.iterdir():
        path.write_text(path.read_text().replace('"a"', '""'))
    bundle = read_bundle(tmp_path)
    assert bundle.manifest.graph.vertices == ("", "b")
    point = bundle.vertices["v0"].point[0]
    assert isinstance(point, VertexPoint)
    assert point.vertex == ""


def test_attribution_simplex_ids_are_global_but_tree_leaves_are_root_local(tmp_path):
    two_edge_bundle(tmp_path)
    data = records(tmp_path, "attribution.jsonl")
    data[8]["id"] = "T0"
    write_records(tmp_path, "attribution.jsonl", data)
    assert_failure(
        tmp_path,
        "attribution.jsonl",
        "reference_duplicate_simplex",
        FailureKind.INVALID_CERTIFICATE,
        9,
    )
    two_edge_bundle(tmp_path)
    data = records(tmp_path, "attribution.jsonl")
    data[11]["simplex"] = "T0"
    write_records(tmp_path, "attribution.jsonl", data)
    assert_failure(
        tmp_path,
        "attribution.jsonl",
        "reference_tree",
        FailureKind.INVALID_CERTIFICATE,
        12,
    )


def test_local_namespace_is_selected_even_when_global_spelling_also_exists(tmp_path):
    from upper_bound_verifier.reader import read_bundle

    tiny_bundle(tmp_path)
    data = records(tmp_path, "sp.jsonl")
    data[1]["id"] = data[5]["vertices"][0] = "v0"
    write_records(tmp_path, "sp.jsonl", data)
    bundle = read_bundle(tmp_path)
    assert bundle.sp[0].vertices[0].id == "v0"
    assert len(bundle.sp[0].vertices[0].point) == 3
    assert len(bundle.vertices["v0"].point) == 2


def test_closing_partial_stream_never_sets_exhaustion_state(tmp_path):
    from upper_bound_verifier.reader import BundleReader

    tiny_bundle(tmp_path)
    reader = BundleReader(tmp_path)
    iterator = reader.iter_sp_roots()
    next(iterator)
    assert isinstance(iterator, GeneratorType)
    iterator.close()
    list(reader.iter_approximation_roots())
    assert not reader.streams_exhausted


@pytest.mark.parametrize("token", ["-01", "0x10", "1e", "1.", "--1", "true false"])
def test_integer_token_boundaries_cannot_be_partially_decoded(tmp_path, token):
    tiny_bundle(tmp_path)
    path = tmp_path / "vertices.jsonl"
    path.write_text('{"id":"v", "point":[], "bad":' + token + "}\n")
    assert_failure(tmp_path, "vertices.jsonl", "schema_json", FailureKind.REFUSED, 1)


@pytest.mark.parametrize(
    "filename,index",
    [
        ("attribution.jsonl", 1),
        ("attribution.jsonl", 3),
        ("attribution.jsonl", 4),
        ("attribution.jsonl", 6),
        ("sp.jsonl", 1),
        ("sp.jsonl", 5),
        ("sp.jsonl", 6),
        ("approximation.jsonl", 4),
    ],
)
def test_unknown_fields_inside_root_records_are_refused(tmp_path, filename, index):
    tiny_bundle(tmp_path)
    data = records(tmp_path, filename)
    data[index]["solver_coefficients"] = []
    write_records(tmp_path, filename, data)
    assert_failure(tmp_path, filename, "schema_fields", FailureKind.REFUSED, index + 1)


def test_vertex_candidates_and_constant_selector_columns_retain_document_order(
    tmp_path,
):
    import copy

    from upper_bound_verifier.reader import read_bundle

    tiny_bundle(tmp_path)
    path = tmp_path / "manifest.json"
    data = json.loads(path.read_text())
    data["identity"]["graph"] = {
        "vertices": ["a", "d", "b", "c"],
        "edges": [["b", "a"], ["b", "c"], ["d", "b"]],
    }
    data["identity"]["selectors"].append({"kind": "constant", "point": {"vertex": "b"}})
    path.write_text(json.dumps(data))
    # Use the one-edge chart only and complete its attribution sequence below.
    original = records(tmp_path, "attribution.jsonl")
    blocks = []
    for i, edges in enumerate(
        [(0, 0), (0, 1), (0, 2), (1, 0), (1, 1), (1, 2), (2, 0), (2, 1), (2, 2)]
    ):
        block = copy.deepcopy(original)
        block[0]["key"]["edges"] = list(edges)
        block[1]["id"] = block[4]["simplex"] = f"T{2 * i}"
        block[2]["id"] = block[5]["simplex"] = f"T{2 * i + 1}"
        for record in block[1:3]:
            for row in record["weights"]:
                row.append("1/3")
        blocks.extend(block)
    write_records(tmp_path, "attribution.jsonl", blocks)
    sp = records(tmp_path, "sp.jsonl")
    for record in sp:
        if record["type"] == "simplex":
            record["branches"] = [0] * 6
    write_records(tmp_path, "sp.jsonl", sp)
    approximation = records(tmp_path, "approximation.jsonl")
    vertex_block = copy.deepcopy(approximation[7:])
    vertex_block[0]["key"]["candidate"] = {"kind": "vertex", "vertex": "b"}
    approximation.extend(vertex_block)
    for record in approximation:
        if record["type"] == "simplex":
            record["branches"] = [0] * 8
    write_records(tmp_path, "approximation.jsonl", approximation)
    complete_comparison_streams(tmp_path)
    bundle = read_bundle(tmp_path)
    assert bundle.manifest.graph.vertices == ("a", "d", "b", "c")
    assert [root.key.to_data()["candidate"] for root in bundle.approximation[::9]] == [
        {"kind": "report", "agent": 0},
        {"kind": "report", "agent": 1},
        {"kind": "vertex", "vertex": "b"},
    ]
    assert bundle.manifest.graph.degree("b") == 3


def test_three_agent_record_dimensions_and_branch_counts(tmp_path):
    from upper_bound_verifier.reader import read_bundle

    tiny_bundle(tmp_path)
    path = tmp_path / "manifest.json"
    manifest = json.loads(path.read_text())
    manifest["identity"]["agents"] = 3
    path.write_text(json.dumps(manifest))
    global_points = [("a", "a", "a"), ("b", "a", "a"), ("a", "b", "a"), ("a", "a", "b")]
    write_records(
        tmp_path,
        "vertices.jsonl",
        [
            {"id": f"v{i}", "point": [{"vertex": v} for v in point]}
            for i, point in enumerate(global_points)
        ],
    )
    write_records(
        tmp_path,
        "attribution.jsonl",
        [
            {"type": "root", "key": {"edges": [0, 0, 0]}, "tree": "node"},
            {
                "type": "simplex",
                "id": "T",
                "vertices": ["v0", "v1", "v2", "v3"],
                "weights": [[1, 0]] * 4,
            },
            {"type": "leaf", "id": "node", "simplex": "T"},
            {"type": "end"},
        ],
    )
    for filename, dimension, branch_count in [
        ("sp.jsonl", 4, 4),
        ("approximation.jsonl", 3, 9),
    ]:
        data: list[dict[str, Any]] = []
        for agent in range(3):
            key: dict[str, Any] = {"edges": [0] * dimension}
            key["agent" if filename == "sp.jsonl" else "candidate"] = (
                agent if filename == "sp.jsonl" else {"kind": "report", "agent": agent}
            )
            data.append({"type": "root", "key": key, "tree": "node"})
            for i in range(dimension + 1):
                point = [{"vertex": "a"}] * dimension
                if i:
                    point[i - 1] = {"vertex": "b"}
                data.append({"type": "vertex", "id": f"w{i}", "point": point})
            cell: dict[str, Any] = {
                "type": "simplex",
                "id": "cell",
                "vertices": [f"w{i}" for i in range(dimension + 1)],
                "truthful": "T",
                "branches": [0] * branch_count,
            }
            if filename == "sp.jsonl":
                cell["deviated"] = "T"
            data += [
                cell,
                {"type": "leaf", "id": "node", "simplex": "cell"},
                {"type": "end"},
            ]
        write_records(tmp_path, filename, data)
    bundle = read_bundle(tmp_path)
    assert bundle.attribution[0].key.edges == (0, 0, 0)
    assert [root.key.to_data()["agent"] for root in bundle.sp] == [0, 1, 2]
    decoded_cell = bundle.approximation[0].simplices[0]
    assert isinstance(decoded_cell, ComparisonSimplex)
    assert decoded_cell.branches == (0,) * 9


def test_runtime_json_depth_limit_is_incompletion(tmp_path):
    tiny_bundle(tmp_path)
    (tmp_path / "vertices.jsonl").write_text("[" * 2000 + "0" + "]" * 2000)
    assert_failure(
        tmp_path,
        "vertices.jsonl",
        "resource_limit_json_depth",
        FailureKind.INCOMPLETE,
        1,
    )


def test_arbitrary_integer_agent_token_exceeding_runtime_dimension_is_incompletion(
    tmp_path,
):
    tiny_bundle(tmp_path)
    path = tmp_path / "manifest.json"
    path.write_text(path.read_text().replace('"agents": 2', '"agents": ' + "9" * 6000))
    (tmp_path / "vertices.jsonl").write_text("")
    assert_failure(
        tmp_path,
        "attribution.jsonl",
        "resource_limit_dimensions",
        FailureKind.INCOMPLETE,
        1,
    )


@pytest.mark.parametrize(
    "filename,key,code",
    [
        ("attribution.jsonl", {"edges": [0, 1]}, "reference_index"),
        ("sp.jsonl", {"agent": 2, "edges": [0, 0, 0]}, "reference_index"),
        (
            "approximation.jsonl",
            {"candidate": {"kind": "report", "agent": -1}, "edges": [0, 0]},
            "reference_index",
        ),
        (
            "approximation.jsonl",
            {"candidate": {"kind": "vertex", "vertex": "unknown"}, "edges": [0, 0]},
            "reference_candidate",
        ),
    ],
)
def test_unresolved_root_key_indices_and_candidates_are_certificate_failures(
    tmp_path, filename, key, code
):
    tiny_bundle(tmp_path)
    data = records(tmp_path, filename)
    data[0]["key"] = key
    write_records(tmp_path, filename, data)
    assert_failure(tmp_path, filename, code, FailureKind.INVALID_CERTIFICATE, 1)


def test_unknown_global_point_reference_is_invalid_certificate(tmp_path):
    tiny_bundle(tmp_path)
    data = records(tmp_path, "vertices.jsonl")
    data[0]["point"][0] = {"vertex": "ghost"}
    write_records(tmp_path, "vertices.jsonl", data)
    assert_failure(
        tmp_path,
        "vertices.jsonl",
        "reference_vertex",
        FailureKind.INVALID_CERTIFICATE,
        1,
    )


@pytest.mark.parametrize(
    "filename,index", [("sp.jsonl", 5), ("approximation.jsonl", 4)]
)
def test_negative_integer_branch_reference_is_invalid_certificate(
    tmp_path, filename, index
):
    tiny_bundle(tmp_path)
    data = records(tmp_path, filename)
    data[index]["branches"][0] = -1
    write_records(tmp_path, filename, data)
    assert_failure(
        tmp_path,
        filename,
        "reference_branch",
        FailureKind.INVALID_CERTIFICATE,
        index + 1,
    )


@pytest.mark.parametrize(
    "filename,index",
    [("vertices.jsonl", 0), ("sp.jsonl", 1), ("approximation.jsonl", 1)],
)
@pytest.mark.parametrize(
    "point,code",
    [
        ({"vertex": "ghost"}, "reference_vertex"),
        ({"edge": 7, "coordinate": "1/2"}, "reference_index"),
        ({"edge": -1, "coordinate": "1/2"}, "reference_index"),
    ],
)
def test_global_and_auxiliary_point_references_are_certificate_failures(
    tmp_path, filename, index, point, code
):
    tiny_bundle(tmp_path)
    data = records(tmp_path, filename)
    data[index]["point"][0] = point
    write_records(tmp_path, filename, data)
    failure = assert_failure(
        tmp_path, filename, code, FailureKind.INVALID_CERTIFICATE, index + 1
    )
    if filename != "vertices.jsonl":
        assert failure.location["root"] == data[0]["key"]


@pytest.mark.parametrize(
    "filename,index",
    [("vertices.jsonl", 0), ("sp.jsonl", 1), ("approximation.jsonl", 1)],
)
@pytest.mark.parametrize(
    "point",
    [
        {"vertex": False},
        {"vertex": "ghost", "extra": 1},
        {"edge": True, "coordinate": "1/2"},
        {"edge": 7, "coordinate": "2/4"},
        {"edge": 7, "coordinate": "-0"},
        {"edge": 7, "coordinate": 0},
        {"edge": 7, "coordinate": True},
    ],
)
def test_malformed_points_remain_refused_even_with_unresolved_edge(
    tmp_path, filename, index, point
):
    tiny_bundle(tmp_path)
    data = records(tmp_path, filename)
    data[index]["point"][0] = point
    write_records(tmp_path, filename, data)
    assert_failure(tmp_path, filename, kind=FailureKind.REFUSED, line=index + 1)


@pytest.mark.parametrize(
    "selector,code",
    [
        ({"kind": "peak", "agent": 2}, "reference_index"),
        ({"kind": "peak", "agent": -1}, "reference_index"),
        ({"kind": "constant", "point": {"vertex": "ghost"}}, "reference_vertex"),
        (
            {"kind": "constant", "point": {"edge": 7, "coordinate": "1/2"}},
            "reference_index",
        ),
    ],
)
def test_manifest_selector_references_are_certificate_failures(
    tmp_path, selector, code
):
    tiny_bundle(tmp_path)
    path = tmp_path / "manifest.json"
    data = json.loads(path.read_text())
    data["identity"]["selectors"][0] = selector
    path.write_text(json.dumps(data))
    assert_failure(tmp_path, "manifest.json", code, FailureKind.INVALID_CERTIFICATE, 1)


@pytest.mark.parametrize(
    "selector",
    [
        {"kind": "peak", "agent": True},
        {"kind": "peak", "agent": "7"},
        {"kind": "peak", "agent": 7, "extra": 0},
        {"kind": "constant", "point": {"vertex": False}},
        {"kind": "constant", "point": {"edge": 7, "coordinate": "2/4"}},
        {"kind": "constant", "point": {"edge": 7, "coordinate": 1}},
    ],
)
def test_malformed_manifest_selectors_remain_refused(tmp_path, selector):
    tiny_bundle(tmp_path)
    path = tmp_path / "manifest.json"
    data = json.loads(path.read_text())
    data["identity"]["selectors"][0] = selector
    path.write_text(json.dumps(data))
    assert_failure(tmp_path, "manifest.json", kind=FailureKind.REFUSED, line=1)


def test_malformed_graph_remains_refused_at_bundle_boundary(tmp_path):
    tiny_bundle(tmp_path)
    path = tmp_path / "manifest.json"
    data = json.loads(path.read_text())
    data["identity"]["graph"]["edges"][0][0] = "ghost"
    path.write_text(json.dumps(data))
    assert_failure(tmp_path, "manifest.json", "graph_endpoint", FailureKind.REFUSED, 1)


@pytest.mark.parametrize(
    "filename,index", [("sp.jsonl", 5), ("approximation.jsonl", 4)]
)
@pytest.mark.parametrize("value", [True, "-1", None])
def test_malformed_branch_types_remain_refused(tmp_path, filename, index, value):
    tiny_bundle(tmp_path)
    data = records(tmp_path, filename)
    data[index]["branches"][0] = value
    write_records(tmp_path, filename, data)
    assert_failure(tmp_path, filename, "schema_branch", FailureKind.REFUSED, index + 1)


def test_nonnegative_branch_arity_is_deferred_to_distance_checks(tmp_path):
    from upper_bound_verifier.reader import read_bundle

    tiny_bundle(tmp_path)
    data = records(tmp_path, "sp.jsonl")
    data[5]["branches"][0] = 7
    write_records(tmp_path, "sp.jsonl", data)
    bundle = read_bundle(tmp_path)
    cell = bundle.sp[0].simplices[0]
    assert isinstance(cell, ComparisonSimplex)
    assert cell.branches[0] == 7
