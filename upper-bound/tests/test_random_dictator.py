"""End-to-end controls for the independent Random Dictator bundle producer."""

import importlib.util
import json
from fractions import Fraction
from pathlib import Path

import pytest
from flint import fmpq

from upper_bound_verifier.failures import Failure, FailureKind
from upper_bound_verifier.verification import Accepted, verify_directory

GENERATOR = (
    Path(__file__).parents[1] / "experiments" / "random-dictator" / "generate.py"
)
spec = importlib.util.spec_from_file_location("random_dictator_generate", GENERATOR)
assert spec is not None and spec.loader is not None
producer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(producer)


def make_bundle(tmp_path, graph="edge", agents=3, alpha=None):
    directory = tmp_path / "bundle"
    producer.generate(directory, producer.Graph(producer.preset(graph)), agents, alpha)
    return directory


def read_rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def write_rows(path, rows):
    path.write_text("".join(json.dumps(row) + "\n" for row in rows))


def coordinate(point):
    """Read a point on the unit edge without using verifier distance code."""
    if "vertex" in point:
        assert point["vertex"] in {"v0", "v1"}
        return Fraction(point["vertex"] == "v1")
    assert point["edge"] == 0
    return Fraction(point["coordinate"])


def replay_approximation_failure(result, alpha, weights):
    assert isinstance(result, Failure)
    assert result.kind is FailureKind.COUNTEREXAMPLE
    assert result.code == "approximation_violation"
    witness = result.witness
    assert witness is not None
    profile = tuple(map(coordinate, witness["profile"]))
    candidate = coordinate(witness["candidate_point"])
    mechanism_cost = sum(
        weight * sum(abs(report - outcome) for report in profile)
        for weight, outcome in zip(weights, profile, strict=True)
    )
    candidate_cost = sum(abs(report - candidate) for report in profile)
    assert mechanism_cost == Fraction(witness["mechanism_cost"])
    assert candidate_cost == Fraction(witness["candidate_cost"])
    assert (
        alpha * candidate_cost - mechanism_cost == Fraction(witness["difference"]) < 0
    )


@pytest.mark.parametrize(
    "graph,agents", [("edge", 2), ("edge", 3), ("edge", 4), ("star3", 2)]
)
def test_complete_random_dictator_certificates_are_accepted(tmp_path, graph, agents):
    bundle = make_bundle(tmp_path, graph, agents)
    if graph == "star3":
        roots = [
            row["key"]["candidate"]
            for row in read_rows(bundle / "approximation.jsonl")
            if row["type"] == "root"
        ]
        assert {"kind": "vertex", "vertex": "o"} in roots
    result = verify_directory(bundle)
    assert isinstance(result, Accepted), result
    assert result.certified_value == fmpq(2 * agents - 2, agents)


def test_too_small_factor_produces_independently_replayed_counterexample(tmp_path):
    alpha = Fraction(4, 3) - Fraction(1, 1000)
    bundle = make_bundle(tmp_path, alpha=alpha)
    replay_approximation_failure(verify_directory(bundle), alpha, [Fraction(1, 3)] * 3)


def test_non_normalized_random_dictator_weights_are_rejected(tmp_path):
    bundle = make_bundle(tmp_path, agents=2)
    path = bundle / "attribution.jsonl"
    rows = read_rows(path)
    simplex = next(row for row in rows if row["type"] == "simplex")
    simplex["weights"][0] = ["1/2", "1/3"]
    write_rows(path, rows)
    result = verify_directory(bundle)
    assert isinstance(result, Failure)
    assert result.kind is FailureKind.INVALID_CERTIFICATE
    assert result.code == "probability_normalization"


@pytest.mark.parametrize("attack", ["missing_last_sp_root", "missing_approximation"])
def test_incomplete_random_dictator_bundle_cannot_accept(tmp_path, attack):
    bundle = make_bundle(tmp_path, agents=2)
    if attack == "missing_last_sp_root":
        path = bundle / "sp.jsonl"
        rows = read_rows(path)
        last_root = max(i for i, row in enumerate(rows) if row["type"] == "root")
        write_rows(path, rows[:last_root])
    else:
        (bundle / "approximation.jsonl").unlink()
    result = verify_directory(bundle)
    assert isinstance(result, Failure)
    assert result.kind is (
        FailureKind.INVALID_CERTIFICATE
        if attack == "missing_last_sp_root"
        else FailureKind.REFUSED
    )


def test_generator_explicitly_rejects_unsupported_odd_cycle():
    with pytest.raises(ValueError, match="bipartite"):
        producer.Graph(
            {"vertices": ["a", "b", "c"], "edges": [["a", "b"], ["b", "c"], ["c", "a"]]}
        )


def test_small_bundle_generation_is_deterministic_and_refuses_overwrite(tmp_path):
    first = tmp_path / "first"
    second = tmp_path / "second"
    graph = producer.Graph(producer.preset("edge"))
    producer.generate(first, graph, 2)
    producer.generate(second, graph, 2)
    assert {path.name for path in first.iterdir()} == {
        path.name for path in second.iterdir()
    }
    for path in first.iterdir():
        assert path.read_bytes() == (second / path.name).read_bytes()
    with pytest.raises(FileExistsError):
        producer.generate(first, graph, 2)


@pytest.mark.parametrize("agents", [2, 3, 4, 7])
def test_independent_tight_profile_distinguishes_random_from_fixed_dictator(agents):
    # One outlier at 1 and all other agents at 0, with facility optimum at 0.
    profile = [Fraction(1)] + [Fraction(0)] * (agents - 1)
    costs = [sum(abs(x - outcome) for x in profile) for outcome in profile]
    optimum = min(costs)
    assert optimum == 1
    assert sum(costs) / agents / optimum == Fraction(2 * agents - 2, agents)
    assert costs[0] / optimum == agents - 1
    if agents > 2:
        assert costs[0] > sum(costs) / agents


def test_fixed_dictator_mutation_fails_random_dictator_approximation_bound(tmp_path):
    bundle = make_bundle(tmp_path)
    path = bundle / "attribution.jsonl"
    rows = read_rows(path)
    for row in rows:
        if row["type"] == "simplex":
            row["weights"] = [["1", "0", "0"] for _ in row["vertices"]]
    write_rows(path, rows)
    # Fixed dictatorship is still SP, so complete verification reaches and
    # rejects the approximation claim with an actual graph-lottery witness.
    replay_approximation_failure(
        verify_directory(bundle),
        Fraction(4, 3),
        [Fraction(1), Fraction(0), Fraction(0)],
    )
