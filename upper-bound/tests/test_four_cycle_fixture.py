"""Stored C4 data must pass the ordinary complete verifier."""

import json
import shutil
import subprocess
import sys
from itertools import product
from pathlib import Path

import pytest
from flint import fmpq

from upper_bound_verifier import affine
from upper_bound_verifier.approximation import approximation_residual
from upper_bound_verifier.comparison import check_comparison_root
from upper_bound_verifier.failures import Failure, FailureKind
from upper_bound_verifier.graph import PeakSelector, point_from_chart
from upper_bound_verifier.lottery import check_lottery_admissibility
from upper_bound_verifier.reader import (
    ApproximationKey,
    AttributionSimplex,
    BundleReader,
    ReportCandidate,
    SPKey,
)
from upper_bound_verifier.sp import sp_residual
from upper_bound_verifier.verification import Accepted, verify_directory

FIXTURE = Path(__file__).parent / "fixtures" / "four-cycle-dictator"
DATA_FILES = (
    "manifest.json",
    "vertices.jsonl",
    "attribution.jsonl",
    "sp.jsonl",
    "approximation.jsonl",
)


def test_stored_complete_four_cycle_dictator_is_accepted():
    result = verify_directory(FIXTURE)
    assert isinstance(result, Accepted), result
    assert result.certified_value == fmpq(1)


def test_four_cycle_generator_reproduces_all_five_stored_files(tmp_path):
    # Separate process: the producer has no verifier imports or test fixtures.
    generated = subprocess.run(
        [
            sys.executable,
            str(Path(__file__).with_name("generate_four_cycle.py")),
            str(tmp_path),
        ],
        capture_output=True,
        check=False,
        timeout=30,
    )
    assert (generated.returncode, generated.stdout, generated.stderr) == (0, b"", b"")
    assert {p.name for p in tmp_path.iterdir()} == set(DATA_FILES)
    for filename in DATA_FILES:
        assert (tmp_path / filename).read_bytes() == (FIXTURE / filename).read_bytes()
    assert isinstance(verify_directory(tmp_path), Accepted)


def test_four_cycle_cli_accepts_actual_stored_bundle():
    # The measured ~3s C4 check needs more room than the earlier tiny-edge helper.
    result = subprocess.run(
        [sys.executable, "-m", "upper_bound_verifier", str(FIXTURE)],
        capture_output=True,
        check=False,
        timeout=60,
    )
    assert (result.returncode, result.stdout, result.stderr) == (0, b"1\n", b"")


def test_four_cycle_inventory_includes_every_chart_agent_candidate_and_tree():
    reader = BundleReader(FIXTURE)
    manifest = reader.manifest
    assert manifest.agents == 2 and manifest.selectors == (PeakSelector(0),)
    assert len(reader.vertices) == 64
    assert len({v.point for v in reader.vertices.values()}) == 64
    assert [root.key.edges for root in reader.attribution] == list(
        product(range(4), repeat=2)
    )
    assert len(reader.attribution) == 16
    assert all(
        len(root.simplices) == 8 and len(root.nodes) == 15
        for root in reader.attribution
    )
    assert all(
        isinstance(cell, AttributionSimplex) and cell.weights == ((fmpq(1),),) * 3
        for root in reader.attribution
        for cell in root.simplices
    )
    sp = tuple(reader.iter_sp_roots())
    apx = tuple(reader.iter_approximation_roots())
    assert [root.key for root in sp] == [
        SPKey(i, e) for i in (0, 1) for e in product(range(4), repeat=3)
    ]
    assert [root.key for root in apx] == [
        ApproximationKey(ReportCandidate(i), e)
        for i in (0, 1)
        for e in product(range(4), repeat=2)
    ]
    assert len(sp) == 128 and len(apx) == 32 and reader.streams_exhausted
    assert all(
        len(root.vertices) == 27 and len(root.simplices) == 48 and len(root.nodes) == 95
        for root in sp
    )
    assert all(
        len(root.vertices) == 9 and len(root.simplices) == 8 and len(root.nodes) == 15
        for root in apx
    )


@pytest.fixture(scope="module")
def checked_fixture():
    reader = BundleReader(FIXTURE)
    lottery = check_lottery_admissibility(
        reader.manifest.graph,
        reader.manifest.agents,
        reader.manifest.selectors,
        reader.attribution,
        reader.vertices,
    )
    return (
        lottery,
        tuple(reader.iter_sp_roots()),
        tuple(reader.iter_approximation_roots()),
    )


def test_opposite_edge_routes_meet_on_a_nontrivial_closed_tie(checked_fixture):
    lottery, sp, _ = checked_fixture
    root = next(r for r in sp if r.key == SPKey(0, (0, 1, 2)))
    checked = check_comparison_root(lottery, root)
    location = (fmpq(1, 4),) * 3
    incident = [
        cell for cell in checked.cells.values() if cell.geometry.contains(location)
    ]
    assert len(incident) >= 2
    # On e0/e2, the 01 and 10 routes are 2+s-t and 2-s+t. At s=t=1/4
    # both are 2, while routes 00 and 11 are 5/2 and 7/2 respectively.
    assert {cell.record.branches[1] for cell in incident} == {1, 2}
    for cell in incident:
        assert tuple(d.evaluate(location) for d in cell.distances) == (0, 2)
        assert affine.evaluate(sp_residual(cell), location) == 2
        assert tuple(w.evaluate(location) for w in cell.truthful_weights) == (1,)


@pytest.mark.parametrize(
    "edges,coordinates", [((0, 0), (fmpq(1, 4),) * 2), ((0, 3), (fmpq(0), fmpq(1)))]
)
def test_collocated_interior_and_cross_chart_endpoint_have_zero_optimum(
    checked_fixture, edges, coordinates
):
    lottery, _, apx = checked_fixture
    points = tuple(
        point_from_chart(lottery.graph, e, t)
        for e, t in zip(edges, coordinates, strict=True)
    )
    assert points[0] == points[1]
    for candidate in (0, 1):
        root = next(
            r
            for r in apx
            if r.key == ApproximationKey(ReportCandidate(candidate), edges)
        )
        checked = check_comparison_root(lottery, root)
        incident = [
            c for c in checked.cells.values() if c.geometry.contains(coordinates)
        ]
        assert incident
        for cell in incident:
            assert tuple(d.evaluate(coordinates) for d in cell.distances) == (
                0,
                0,
                0,
                0,
            )
            assert affine.evaluate(approximation_residual(cell, 1), coordinates) == 0


def test_corrupt_opposite_edge_route_is_rejected_by_ordinary_verification(tmp_path):
    shutil.copytree(FIXTURE, tmp_path, dirs_exist_ok=True)
    path = tmp_path / "sp.jsonl"
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    in_root = False
    for row in rows:
        if row["type"] == "root":
            in_root = row["key"] == {"agent": 0, "edges": [0, 1, 2]}
        elif in_root and row["type"] == "simplex":
            row["branches"][1] = 0  # Route 00 is longer than 01/10 in this cell.
            break
    path.write_text("".join(json.dumps(row) + "\n" for row in rows))
    result = verify_directory(tmp_path)
    assert isinstance(result, Failure)
    assert (
        result.kind is FailureKind.INVALID_CERTIFICATE
        and result.code == "distance_branch"
    )
