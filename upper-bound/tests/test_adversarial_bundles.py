"""Bounded public hostile bundles and original-wire exact witness replays."""

import json
import shutil
import subprocess
import sys
from fractions import Fraction
from pathlib import Path

import pytest
from generate_adversarial import DATA_FILES
from test_reader import records, write_records
from test_verification import assert_failure

from upper_bound_verifier.approximation import check_checked_approximation_root
from upper_bound_verifier.comparison import ComparisonStreams
from upper_bound_verifier.failures import Failure, FailureKind
from upper_bound_verifier.lottery import check_lottery_admissibility
from upper_bound_verifier.reader import BundleReader
from upper_bound_verifier.simplex import Verified
from upper_bound_verifier.sp import check_checked_sp_root
from upper_bound_verifier.verification import Accepted, verify_directory

FIXTURES = Path(__file__).parent / "fixtures"
NEGATIVES = ("single-edge-non-sp", "single-edge-false-factor")


def coordinate(point):
    """Independent unit-segment metric, without the graph-distance module."""
    if "vertex" in point:
        assert point["vertex"] in {"a", "b"}
        return Fraction(point["vertex"] == "b")
    assert point["edge"] == 0
    return Fraction(point["coordinate"])


def original_weights(directory, profile):
    """Interpolate original wire rows by a direct 2x2 Fraction calculation."""
    vertices = {
        row["id"]: tuple(map(coordinate, row["point"]))
        for row in records(directory, "vertices.jsonl")
    }
    answers = []
    for row in records(directory, "attribution.jsonl"):
        if row["type"] != "simplex":
            continue
        a, b, c = [vertices[v] for v in row["vertices"]]
        u, v = (b[0] - a[0], b[1] - a[1]), (c[0] - a[0], c[1] - a[1])
        x, y = profile[0] - a[0], profile[1] - a[1]
        det = u[0] * v[1] - u[1] * v[0]
        assert det != 0
        beta = (x * v[1] - y * v[0]) / det
        gamma = (u[0] * y - u[1] * x) / det
        barycentric = (1 - beta - gamma, beta, gamma)
        if min(barycentric) >= 0:
            answers.append(
                tuple(
                    sum(
                        (
                            lam * Fraction(weights[j])
                            for lam, weights in zip(
                                barycentric, row["weights"], strict=True
                            )
                        ),
                        Fraction(0),
                    )
                    for j in range(3)
                )
            )
    assert answers and all(a == answers[0] for a in answers)
    assert sum(answers[0]) == 1 and min(answers[0]) >= 0
    return answers[0]


def original_cost(directory, reports, true_point):
    # The stored manifest's exact selector order is separately asserted below.
    weights = original_weights(directory, reports)
    outputs = (*reports, Fraction(0))
    return sum(
        (
            w * abs(output - true_point)
            for w, output in zip(weights, outputs, strict=True)
        ),
        Fraction(0),
    )


def reconstruct_witness(directory, failure):
    """Bind the emitted witness to its original root, cell and wire vertices."""
    assert failure.location is not None and failure.witness is not None
    location, witness = failure.location, failure.witness
    name = "sp.jsonl" if failure.code == "sp_violation" else "approximation.jsonl"
    local = {}
    key = None
    cell = None
    for line, row in enumerate(records(directory, name), 1):
        if row["type"] == "root":
            key, local = row["key"], {}
        elif row["type"] == "vertex":
            local[row["id"]] = tuple(map(coordinate, row["point"]))
        elif (
            row["type"] == "simplex"
            and key == location["root"]
            and row["id"] == location["cell"]
        ):
            cell = row
            assert line == location["line"]
            break
    assert cell is not None and location["file"] == name
    barycentric = tuple(Fraction(value) for value in witness["barycentric"])
    assert sum(barycentric) == 1 and min(barycentric) >= 0
    points = [local[v] for v in cell["vertices"]]
    point = tuple(
        sum(
            (
                lam * vertex[axis]
                for lam, vertex in zip(barycentric, points, strict=True)
            ),
            Fraction(0),
        )
        for axis in range(len(points[0]))
    )
    expected = tuple(map(coordinate, witness["profile"]))
    if failure.code == "sp_violation":
        expected += (coordinate(witness["deviation"]),)
    assert point == expected
    return witness


def test_stored_non_sp_bundle_returns_a_real_mechanism_counterexample():
    directory = FIXTURES / NEGATIVES[0]
    result = assert_failure(directory, FailureKind.COUNTEREXAMPLE, "sp_violation")
    witness = reconstruct_witness(directory, result)
    profile = tuple(map(coordinate, witness["profile"]))
    deviation = coordinate(witness["deviation"])
    assert witness["agent"] == 0
    changed = (deviation, profile[1])
    truthful = original_cost(directory, profile, profile[0])
    deviated = original_cost(directory, changed, profile[0])
    assert truthful == Fraction(witness["truthful_cost"])
    assert deviated == Fraction(witness["deviated_cost"])
    assert deviated - truthful == Fraction(witness["difference"]) < 0
    # A separate fixed profitable deviation, independent of witness selection.
    assert original_cost(
        directory, (Fraction(1, 2), Fraction(1)), Fraction(0)
    ) - original_cost(directory, (Fraction(0), Fraction(1)), Fraction(0)) == Fraction(
        -1, 4
    )


def test_stored_sp_constant_false_factor_has_an_opt_zero_witness():
    directory = FIXTURES / NEGATIVES[1]
    result = assert_failure(
        directory, FailureKind.COUNTEREXAMPLE, "approximation_violation"
    )
    witness = reconstruct_witness(directory, result)
    profile = tuple(map(coordinate, witness["profile"]))
    candidate = coordinate(witness["candidate_point"])
    alpha = Fraction(
        json.loads((directory / "manifest.json").read_text())["certified_value"]
    )
    social = sum(original_cost(directory, profile, x) for x in profile)
    candidate_cost = sum(abs(x - candidate) for x in profile)
    assert social == Fraction(witness["mechanism_cost"])
    assert candidate_cost == Fraction(witness["candidate_cost"])
    assert alpha * candidate_cost - social == Fraction(witness["difference"]) < 0
    assert profile == (Fraction(1), Fraction(1)) and candidate == 1
    assert social == 2 and candidate_cost == 0  # Fails every finite factor.


@pytest.mark.parametrize("name", NEGATIVES)
def test_negative_fixture_all_roots_geometry_and_formulas_are_complete(name):
    directory = FIXTURES / name
    reader = BundleReader(directory)
    assert reader.manifest.certified_value == 1
    manifest = json.loads((directory / "manifest.json").read_text())
    assert manifest["identity"]["graph"] == {
        "vertices": ["a", "b"],
        "edges": [["a", "b"]],
    }
    assert manifest["identity"]["agents"] == 2
    assert manifest["identity"]["selectors"] == [
        {"kind": "peak", "agent": 0},
        {"kind": "peak", "agent": 1},
        {"kind": "constant", "point": {"vertex": "a"}},
    ]
    # Every original row agrees with the advertised formula, including zero
    # terms. Affinity then identifies the formula on the entire triangle.
    vertices = {row["id"]: row["point"] for row in records(directory, "vertices.jsonl")}
    for row in records(directory, "attribution.jsonl"):
        if row["type"] == "simplex":
            for v, weights in zip(row["vertices"], row["weights"], strict=True):
                x0 = coordinate(vertices[v][0])
                expected = (0, 0, 1) if name == NEGATIVES[1] else (x0, 1 - x0, 0)
                assert tuple(Fraction(value) for value in weights) == expected
    lottery = check_lottery_admissibility(
        reader.manifest.graph,
        reader.manifest.agents,
        reader.manifest.selectors,
        reader.attribution,
        reader.vertices,
    )
    streams = ComparisonStreams(lottery)
    sp = list(streams.iter_sp_roots(reader.iter_sp_roots()))
    apx = list(streams.iter_approximation_roots(reader.iter_approximation_roots()))
    assert len(reader.attribution) == 1 and len(sp) == len(apx) == 2
    assert sum(len(root.cells) for root in sp) == 12
    assert sum(len(root.cells) for root in apx) == 4
    assert reader.streams_exhausted and streams.streams_exhausted
    assert all(len(cell.distances) == 6 for root in sp for cell in root.cells.values())
    assert all(len(cell.distances) == 8 for root in apx for cell in root.cells.values())
    if name == NEGATIVES[1]:
        assert all(
            isinstance(check_checked_sp_root(lottery, root), Verified) for root in sp
        )
    else:
        assert all(
            isinstance(
                check_checked_approximation_root(
                    lottery, root, reader.manifest.certified_value
                ),
                Verified,
            )
            for root in apx
        )
    # Independent original-row interior/seam samples complement vertex checks.
    for x0 in (Fraction(0), Fraction(1, 4), Fraction(1, 2), Fraction(1)):
        for x1 in (Fraction(0), Fraction(1, 3), Fraction(1, 2), Fraction(1)):
            expected = (0, 0, 1) if name == NEGATIVES[1] else (x0, 1 - x0, 0)
            assert original_weights(directory, (x0, x1)) == expected


@pytest.mark.parametrize("name", NEGATIVES)
def test_negative_fixture_regenerates_in_a_separate_untrusted_process(tmp_path, name):
    constant = name == NEGATIVES[1]
    code = "from pathlib import Path; from generate_adversarial import generate; generate(Path(__import__('sys').argv[1]), constant=__import__('sys').argv[2] == 'True')"
    result = subprocess.run(
        [sys.executable, "-c", code, str(tmp_path), str(constant)],
        cwd=Path(__file__).parent,
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )
    assert (result.returncode, result.stdout, result.stderr) == (0, "", "")
    for filename in DATA_FILES:
        assert (tmp_path / filename).read_bytes() == (
            FIXTURES / name / filename
        ).read_bytes()
    result = verify_directory(tmp_path)
    assert isinstance(result, Failure) and result.kind is FailureKind.COUNTEREXAMPLE


@pytest.fixture
def passing_three_selector_bundle(tmp_path):
    shutil.copytree(FIXTURES / NEGATIVES[0], tmp_path, dirs_exist_ok=True)
    rows = records(tmp_path, "attribution.jsonl")
    for row in rows:
        if row["type"] == "simplex":
            row["weights"] = [["1/2", "1/2", "0"] for _ in row["vertices"]]
    write_records(tmp_path, "attribution.jsonl", rows)
    assert isinstance(verify_directory(tmp_path), Accepted)
    return tmp_path


@pytest.mark.parametrize(
    "attack,code",
    [
        ("volume_gap", "coverage_volume"),
        ("balanced_overlap", "coverage_leaf_membership"),
        ("duplicated_leaf_volume", "coverage_volume"),
        ("lottery_seam", "lottery_consistency"),
        ("zero_mass", "probability_normalization"),
        ("negative_mass", "probability_negative"),
    ],
)
def test_complete_bundle_attacks_are_invalid_without_mechanism_witness(
    passing_three_selector_bundle, attack, code
):
    directory = passing_three_selector_bundle
    rows = records(directory, "attribution.jsonl")
    cells = [row for row in rows if row["type"] == "simplex"]
    if attack in {"volume_gap", "duplicated_leaf_volume"}:
        header = dict(rows[0], tree="attack-root")
        nodes = [{"type": "leaf", "id": "attack-root", "simplex": cells[0]["id"]}]
        if attack == "duplicated_leaf_volume":
            nodes = [
                {
                    "type": "split",
                    "id": "attack-root",
                    "normal": [1, 0],
                    "offset": "1/2",
                    "minus": "m",
                    "plus": "p",
                },
                {"type": "leaf", "id": "m", "simplex": cells[0]["id"]},
                {"type": "leaf", "id": "p", "simplex": cells[0]["id"]},
            ]
        rows = [header, cells[0], *nodes, {"type": "end"}]
    elif attack == "balanced_overlap":
        cells[1]["vertices"] = list(reversed(cells[0]["vertices"]))
    elif attack == "lottery_seam":
        cells[1]["weights"] = [["0", "0", "1"] for _ in cells[1]["vertices"]]
    else:
        weights = ["0", "0", "0"] if attack == "zero_mass" else ["-1", "2", "0"]
        for cell in cells:
            cell["weights"] = [weights[:] for _ in cell["vertices"]]
    write_records(directory, "attribution.jsonl", rows)
    failure = assert_failure(directory, FailureKind.INVALID_CERTIFICATE, code)
    assert failure.witness is None


@pytest.mark.parametrize("stream", ["sp", "approximation"])
@pytest.mark.parametrize("attack", ["zero_weight_branch", "wrong_region"])
def test_unused_terms_and_existing_wrong_regions_are_checked_by_directory_api(
    passing_three_selector_bundle, stream, attack
):
    directory = passing_three_selector_bundle
    filename = stream + ".jsonl"
    rows = records(directory, filename)
    cell = next(row for row in rows if row["type"] == "simplex")
    if attack == "zero_weight_branch":
        # Valid index 1 chooses the longer endpoint route to constant a.
        # Column2 is globally zero; the formula must still be checked.
        term = 2
        cell["branches"][term] = 1
        code = "distance_branch"
    else:
        mode = "deviated" if stream == "sp" else "truthful"
        cell[mode] = "r0-root-1" if cell[mode] == "r0-root-0" else "r0-root-0"
        code = "region_containment"
    write_records(directory, filename, rows)
    failure = assert_failure(directory, FailureKind.INVALID_CERTIFICATE, code)
    assert failure.witness is None
    assert failure.location is not None and failure.location["cell"] == cell["id"]
    if attack == "zero_weight_branch":
        assert failure.location["term"] == term
