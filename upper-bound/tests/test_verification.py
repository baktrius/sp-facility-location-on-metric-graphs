"""Complete directory verification through the ordinary public API and CLI."""

import io
import json
import shutil
import subprocess
import sys
from contextlib import contextmanager
from fractions import Fraction
from pathlib import Path

import pytest
from flint import fmpq
from test_comparison import real_wire_bundle
from test_reader import records, write_records

from upper_bound_verifier.failures import Failure, FailureKind
from upper_bound_verifier.verification import Accepted, verify_directory

FIXTURE = Path(__file__).parent / "fixtures" / "single-edge-dictator"


def test_stored_complete_single_edge_dictator_is_accepted():
    result = verify_directory(FIXTURE)
    assert isinstance(result, Accepted)
    assert result.certified_value == fmpq(1)


def run_cli(*arguments):
    return subprocess.run(
        [sys.executable, "-m", "upper_bound_verifier", *map(str, arguments)],
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )


def test_cli_accepts_stored_bundle_with_exact_success_output():
    result = run_cli(FIXTURE)
    assert result.returncode == 0
    assert result.stdout == "1\n"
    assert result.stderr == ""


def test_cli_cannot_report_success_before_stdout_is_flushed(monkeypatch, capsys):
    from upper_bound_verifier.__main__ import main

    class FailingBufferedOutput(io.StringIO):
        def flush(self):
            raise OSError("injected stdout flush failure")

    # This system-boundary buffer never delivers its pending bytes.
    monkeypatch.setattr(sys, "stdout", FailingBufferedOutput())
    assert main([str(FIXTURE)]) == 2
    assert json.loads(capsys.readouterr().err)["code"] == "internal_error"


def test_unwritable_stderr_is_an_internal_exit_two(bundle, monkeypatch, capsys):
    from upper_bound_verifier.__main__ import main

    class UnwritableDiagnostic(io.StringIO):
        def write(self, text):
            raise OSError("injected permanent stderr failure")

    (bundle / "manifest.json").write_text("{")
    monkeypatch.setattr(sys, "stderr", UnwritableDiagnostic())
    assert main([str(bundle)]) == 2
    assert capsys.readouterr().out == ""


@pytest.fixture
def bundle(tmp_path):
    shutil.copytree(FIXTURE, tmp_path, dirs_exist_ok=True)
    return tmp_path


def assert_failure(directory, kind, code=None):
    result = verify_directory(directory)
    assert isinstance(result, Failure)
    assert result.kind is kind
    if code is not None:
        assert result.code == code
    cli = run_cli(directory)
    assert cli.stdout == ""
    assert cli.returncode == (
        1
        if kind in {FailureKind.INVALID_CERTIFICATE, FailureKind.COUNTEREXAMPLE}
        else 2
    )
    assert json.loads(cli.stderr) == result.to_dict()
    return result


def test_cli_normalizes_exact_rational_factor(bundle):
    path = bundle / "manifest.json"
    manifest = json.loads(path.read_text())
    manifest["certified_value"] = "3/2"
    path.write_text(json.dumps(manifest))
    result = verify_directory(bundle)
    assert isinstance(result, Accepted) and result.certified_value == fmpq(3, 2)
    cli = run_cli(bundle)
    assert (cli.returncode, cli.stdout, cli.stderr) == (0, "3/2\n", "")


@pytest.mark.parametrize(
    "arguments",
    [(), ("--partial",), ("--help",), ("a", "b"), ("--partial", FIXTURE)],
)
def test_cli_usage_and_partial_options_never_emit_a_bound(arguments):
    cli = run_cli(*arguments)
    assert cli.returncode == 2 and cli.stdout == ""
    assert json.loads(cli.stderr)["code"] == "usage"


def test_malformed_syntax_is_refused(bundle):
    (bundle / "manifest.json").write_text('{"schema_version":')
    assert_failure(bundle, FailureKind.REFUSED, "schema_json")


def test_unreadable_required_file_is_refused(bundle):
    (bundle / "sp.jsonl").unlink()
    assert_failure(bundle, FailureKind.REFUSED, "schema_read")


def test_geometry_failure_is_invalid_certificate(bundle):
    rows = records(bundle, "attribution.jsonl")
    rows[1]["vertices"][-1] = "v3"
    write_records(bundle, "attribution.jsonl", rows)
    failure = assert_failure(bundle, FailureKind.INVALID_CERTIFICATE)
    assert failure.code == "coverage_leaf_membership"


def point_coordinate(point):
    """Independent unit-segment coordinate for witness replay."""
    return (
        Fraction(point["vertex"] == "b")
        if "vertex" in point
        else Fraction(point["coordinate"])
    )


def test_genuine_sp_violation_is_replayed_from_actual_graph_lottery(tmp_path):
    # The untrusted wire helper supplies M(x)=x0*peak0+(1-x0)*peak1.
    real_wire_bundle(tmp_path)
    failure = assert_failure(tmp_path, FailureKind.COUNTEREXAMPLE, "sp_violation")
    witness = failure.witness
    assert witness is not None
    assert witness["agent"] == 0
    x0, x1 = map(point_coordinate, witness["profile"])
    z = point_coordinate(witness["deviation"])
    truthful = (1 - x0) * abs(x1 - x0)
    deviated = z * abs(z - x0) + (1 - z) * abs(x1 - x0)
    assert truthful == Fraction(witness["truthful_cost"])
    assert deviated == Fraction(witness["deviated_cost"])
    assert deviated - truthful == Fraction(witness["difference"]) < 0


def test_sp_constant_false_factor_returns_actual_approximation_violation(tmp_path):
    real_wire_bundle(tmp_path)
    rows = records(tmp_path, "attribution.jsonl")
    for row in rows:
        if row["type"] == "simplex":
            row["weights"] = [["0", "0", "1"] for _ in row["vertices"]]
    write_records(tmp_path, "attribution.jsonl", rows)
    failure = assert_failure(
        tmp_path, FailureKind.COUNTEREXAMPLE, "approximation_violation"
    )
    witness = failure.witness
    assert witness is not None
    x0, x1 = map(point_coordinate, witness["profile"])
    candidate = point_coordinate(witness["candidate_point"])
    mechanism = x0 + x1  # deterministic constant at a=0
    candidate_cost = abs(x0 - candidate) + abs(x1 - candidate)
    assert mechanism == Fraction(witness["mechanism_cost"])
    assert candidate_cost == Fraction(witness["candidate_cost"])
    assert candidate_cost - mechanism == Fraction(witness["difference"]) < 0


def test_genuine_counterexample_needs_only_its_checked_root_after_global_attribution(
    tmp_path,
):
    real_wire_bundle(tmp_path)
    rows = records(tmp_path, "sp.jsonl")
    end = next(i for i, row in enumerate(rows) if row["type"] == "end") + 1
    write_records(tmp_path, "sp.jsonl", rows[:end])
    (tmp_path / "approximation.jsonl").unlink()
    assert_failure(tmp_path, FailureKind.COUNTEREXAMPLE, "sp_violation")


@pytest.mark.parametrize("stream", ["sp", "approximation"])
@pytest.mark.parametrize("attack", ["branch", "region"])
def test_bad_formula_is_certificate_failure_even_after_negative_cell(
    tmp_path, stream, attack
):
    real_wire_bundle(tmp_path)
    if stream == "approximation":
        rows = records(tmp_path, "attribution.jsonl")
        for row in rows:
            if row["type"] == "simplex":
                row["weights"] = [["0", "0", "1"] for _ in row["vertices"]]
        write_records(tmp_path, "attribution.jsonl", rows)
    filename = stream + ".jsonl"
    rows = records(tmp_path, filename)
    end = next(i for i, row in enumerate(rows) if row["type"] == "end")
    cell = next(row for row in reversed(rows[:end]) if row["type"] == "simplex")
    if attack == "branch":
        cell["branches"][-1] = 99
    else:
        # Existing opposite region, not an unresolved parser reference.
        cell["truthful"] = (
            "r0-root-1" if cell["truthful"] == "r0-root-0" else "r0-root-0"
        )
    write_records(tmp_path, filename, rows)
    failure = assert_failure(tmp_path, FailureKind.INVALID_CERTIFICATE)
    assert failure.code in {"distance_branch", "region_containment"}


@pytest.mark.parametrize("attack", ["syntax", "probability", "geometry"])
def test_late_invalid_attribution_precedes_profitable_deviation(tmp_path, attack):
    real_wire_bundle(tmp_path)
    rows = records(tmp_path, "attribution.jsonl")
    cell = [row for row in rows if row["type"] == "simplex"][-1]
    if attack == "syntax":
        with (tmp_path / "attribution.jsonl").open("a") as stream:
            stream.write('{"type":\n')
        assert_failure(tmp_path, FailureKind.REFUSED, "schema_json")
        return
    if attack == "probability":
        cell["weights"][-1] = ["0", "0", "0"]
    else:
        cell["vertices"][-1] = cell["vertices"][0]
    write_records(tmp_path, "attribution.jsonl", rows)
    failure = assert_failure(tmp_path, FailureKind.INVALID_CERTIFICATE)
    assert failure.code in {"probability_normalization", "reference_simplex_vertex"}


@pytest.mark.parametrize("stream", ["sp", "approximation"])
@pytest.mark.parametrize(
    "attack", ["missing_final", "truncated", "extra_root", "trailing"]
)
def test_incomplete_or_trailing_comparison_stream_cannot_accept(bundle, stream, attack):
    filename = stream + ".jsonl"
    rows = records(bundle, filename)
    split = next(i for i, row in enumerate(rows) if row["type"] == "end") + 1
    if attack == "missing_final":
        rows = rows[:split]
    elif attack == "truncated":
        rows = rows[:-1]
    elif attack == "extra_root":
        rows += rows[split:]
    else:
        rows += [{"type": "end"}]
    write_records(bundle, filename, rows)
    kind = (
        FailureKind.REFUSED
        if attack in {"trailing", "truncated"}
        else FailureKind.INVALID_CERTIFICATE
    )
    assert_failure(bundle, kind)


@pytest.mark.parametrize(
    "filename", ["manifest.json", "vertices.jsonl", "attribution.jsonl"]
)
def test_trailing_data_in_global_input_cannot_accept(bundle, filename):
    with (bundle / filename).open("a") as stream:
        stream.write("null\n")
    assert_failure(bundle, FailureKind.REFUSED)


@pytest.mark.parametrize("entry", ["api", "cli"])
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
    "error,kind,code",
    [
        (RuntimeError, FailureKind.REFUSED, "internal_error"),
        (MemoryError, FailureKind.INCOMPLETE, "resource_exhausted"),
        (RecursionError, FailureKind.INCOMPLETE, "resource_exhausted"),
        (KeyboardInterrupt, FailureKind.INCOMPLETE, "interrupted"),
        (OSError, FailureKind.REFUSED, "schema_read"),
    ],
)
def test_bounded_io_failures_are_structured_and_never_accept(
    bundle, monkeypatch, capsys, entry, filename, error, kind, code
):
    from upper_bound_verifier.__main__ import main

    original_open = Path.open
    injected = False

    def faulty_open(path, *args, **kwargs):
        nonlocal injected
        if path == bundle / filename and not injected:
            injected = True
            raise error("injected at file I/O boundary")
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", faulty_open)
    if entry == "api":
        result = verify_directory(bundle)
        assert (
            isinstance(result, Failure) and result.kind is kind and result.code == code
        )
    else:
        assert main([str(bundle)]) == 2
        output = capsys.readouterr()
        assert output.out == ""
        failure = json.loads(output.err)
        assert failure["kind"] == kind.value and failure["code"] == code
    assert injected


@pytest.mark.parametrize("stream", ["sp", "approximation"])
@pytest.mark.parametrize("error", [RuntimeError, MemoryError, KeyboardInterrupt])
def test_failure_reading_eof_after_final_root_never_accepts(
    bundle, monkeypatch, capsys, stream, error
):
    from upper_bound_verifier.__main__ import main

    original_open = Path.open

    @contextmanager
    def faulty_open(path, *args, **kwargs):
        with original_open(path, *args, **kwargs) as file:
            if path == bundle / (stream + ".jsonl"):

                def lines():
                    yield from file
                    raise error("injected while reading actual EOF")

                yield lines()
            else:
                yield file

    monkeypatch.setattr(Path, "open", faulty_open)
    assert main([str(bundle)]) == 2
    output = capsys.readouterr()
    assert output.out == ""
    assert json.loads(output.err)["kind"] in {"refused", "incomplete"}
