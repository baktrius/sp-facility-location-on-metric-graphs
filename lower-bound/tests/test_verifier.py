"""Tests of the sparse verifier, through its entry point and its command."""

from __future__ import annotations

import ast
import copy
import json
import subprocess
import sys
from fractions import Fraction
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from sparse_verifier import verify
from sparse_verifier.cli import main

if TYPE_CHECKING:
    from collections.abc import Callable

REPOSITORY = Path(__file__).resolve().parents[1]
THETA_1 = REPOSITORY / "tests" / "fixtures" / "theta-m1-agents3.json"


@pytest.fixture
def theta() -> dict:
    """Return the committed trivial theta certificate at subdivision 1."""
    return json.loads(THETA_1.read_text())


def write(path: Path, document: object) -> Path:
    """Write a document as JSON and return its path."""
    path.write_text(json.dumps(document), encoding="utf-8")
    return path


def test_committed_trivial_certificate_is_accepted(theta: dict) -> None:
    """The committed certificate verifies at bound 1."""
    verdict = verify(theta)
    assert verdict.accepted
    assert verdict.bound == 1


def test_wrong_claimed_bound_is_rejected_by_the_objective_check(theta: dict) -> None:
    """A claimed bound other than 1 is rejected, not refused."""
    theta["certified_value"] = "11/10"
    verdict = verify(theta)
    assert not verdict.accepted
    assert not verdict.refused
    assert verdict.failing == "objective"


@pytest.mark.parametrize(
    ("edit", "message"),
    [
        (lambda i: i["graph"].update(symmetries=[{"u": "v"}]), "lift"),
        (lambda i: i.update(subdivision=2), "flatten"),
        (lambda i: i.update(formulation="cycle"), "formulation"),
        (lambda i: i.update(result="conditional"), "unconditional"),
        (lambda i: i.update(support="peaks"), "support"),
        (lambda i: i.update(agents=1), "minimum"),
    ],
)
def test_out_of_scope_cases_are_refused_each_with_its_message(
    theta: dict, edit: Callable[[dict], object], message: str
) -> None:
    """Each out-of-scope certificate is refused with its own message."""
    edit(theta["identity"])
    verdict = verify(theta)
    assert verdict.refused
    assert verdict.failing == "scope"
    assert message in verdict.reason


def test_empty_symmetries_are_in_scope(theta: dict) -> None:
    """An empty symmetries list is the trivial group."""
    theta["identity"]["graph"]["symmetries"] = []
    assert verify(theta).accepted


@pytest.mark.parametrize(
    "edit",
    [
        lambda g: g["edges"].__delitem__(slice(4, 6)),  # cuts c off
        lambda g: g["edges"].append(["u", "v"]),  # odd cycle
        lambda g: g["edges"].append(["a", "a"]),  # self-loop
        lambda g: g["edges"].append(["v", "a"]),  # repeated edge
        lambda g: g["edges"].append(["a", "z"]),  # unknown vertex
    ],
)
def test_invalid_graphs_are_rejected_by_the_graph_check(
    theta: dict, edit: Callable[[dict], object]
) -> None:
    """Each graph outside the problem is rejected by the graph check."""
    edit(theta["identity"]["graph"])
    verdict = verify(theta)
    assert not verdict.accepted
    assert not verdict.refused
    assert verdict.failing == "graph"


def test_model_hash_is_never_read(theta: dict) -> None:
    """Absent, present and wrong hashes give one verdict."""
    verdicts = []
    for mutate in (
        dict,
        lambda i: i.pop("model_hash"),
        lambda i: i.update(model_hash="wrong"),
    ):
        document = copy.deepcopy(theta)
        mutate(document["identity"])
        verdicts.append(verify(document))
    assert verdicts[0] == verdicts[1] == verdicts[2]
    assert verdicts[0].accepted


def test_non_certificate_documents_are_refused() -> None:
    """Documents that are not certificates are refused."""
    for document in ([], {"identity": 3}, {"identity": {}}):
        assert verify(document).refused


def test_command_exit_codes(
    tmp_path: Path, theta: dict, capsys: pytest.CaptureFixture[str]
) -> None:
    """The command's exit codes and streams follow the judge's contract."""
    assert main([str(THETA_1)]) == 0
    captured = capsys.readouterr()
    assert captured.out == "1\n"

    theta["certified_value"] = "2"
    assert main([str(write(tmp_path / "bad.json", theta))]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "objective" in captured.err

    assert main([str(tmp_path / "missing.json")]) == 2
    (tmp_path / "junk.json").write_text("{not json")
    assert main([str(tmp_path / "junk.json")]) == 2
    assert main([]) == 2


def test_module_runs_as_a_command() -> None:
    """The package runs as a module on a path."""
    result = subprocess.run(
        [sys.executable, "-m", "sparse_verifier", str(THETA_1)],
        capture_output=True,
        text=True,
        check=False,
        cwd=REPOSITORY,
    )
    assert (result.returncode, result.stdout) == (0, "1\n")


def test_package_imports_only_the_standard_library_and_itself() -> None:
    """No module imports outside the standard library and the package."""
    allowed = set(sys.stdlib_module_names) | {"sparse_verifier"}
    for path in (REPOSITORY / "sparse_verifier").glob("*.py"):
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.Import):
                roots = {a.name.split(".")[0] for a in node.names}
            elif isinstance(node, ast.ImportFrom) and node.level == 0:
                roots = {(node.module or "").split(".")[0]}
            else:
                continue
            assert roots <= allowed, (path.name, roots - allowed)


def test_bound_is_a_fraction(theta: dict) -> None:
    """The bound is exact."""
    assert verify(theta).bound == Fraction(1)
