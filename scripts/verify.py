"""Run complete verifiers on selected artifacts; never infer acceptance from a hash."""

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
import tarfile
import time
import zipfile
from pathlib import Path

from certificate_io import materialize, packaging_entries

ROOT = Path(__file__).resolve().parents[1]
FILES = {
    "manifest.json",
    "vertices.jsonl",
    "attribution.jsonl",
    "sp.jsonl",
    "approximation.jsonl",
}
# -I excludes cwd and PYTHONPATH imports; the copied package is prepended.
BOOT = 'import sys,runpy;sys.path.insert(0,sys.argv.pop(1));sys.argv[0]=sys.argv.pop(1);runpy.run_module(sys.argv[0],run_name="__main__")'


def sha256(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def invoke(python, direction, path, timeout):
    package = "sparse_verifier" if direction == "lower" else "upper_bound_verifier"
    source = ROOT / ("lower-bound" if direction == "lower" else "upper-bound/src")
    start = time.monotonic()
    try:
        proc = subprocess.run(
            [python, "-I", "-B", "-c", BOOT, str(source), package, str(path)],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=ROOT,
            check=False,
        )
        return {
            "exit_code": proc.returncode,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
            "seconds": time.monotonic() - start,
        }
    except subprocess.TimeoutExpired:
        return {
            "exit_code": None,
            "stdout": "",
            "stderr": "verification timed out",
            "seconds": time.monotonic() - start,
        }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--direction", choices=["lower", "upper", "all"], default="lower")
    ap.add_argument(
        "--case", action="append", help="configuration ID; repeat to select several"
    )
    ap.add_argument("--lower-python", default=sys.executable)
    ap.add_argument(
        "--upper-python", default=str(ROOT / "upper-bound/.venv/bin/python")
    )
    ap.add_argument(
        "--timeout", type=float, default=43200, help="seconds per complete verifier"
    )
    ap.add_argument("--report", type=Path, help="write a fresh JSON result file")
    ap.add_argument("--certificate", help="XZ certificate path from certificates/packaging.json; includes recovered bundles")
    args = ap.parse_args()
    rows = json.loads((ROOT / "scoreboard/results.json").read_text())
    receipts = {
        r["configuration"]: r
        for r in json.loads(
            (ROOT / "validation/recorded-upper-acceptances.json").read_text()
        )
    }
    packages = {e["path"]: e for e in packaging_entries(ROOT)} if (ROOT / "certificates/packaging.json").exists() else {}
    if args.certificate:
        if args.case:
            ap.error("--certificate and --case are mutually exclusive")
        candidate = Path(args.certificate)
        try:
            rel = str(candidate.resolve().relative_to(ROOT)) if candidate.is_absolute() else str(candidate)
        except ValueError:
            ap.error("certificate is outside the archive root")
        if rel not in packages:
            ap.error("certificate is not in the packaging manifest")
        entry = packages[rel]
        args.direction = entry["direction"]
        rows = [{"id": entry["configuration"], "lower_certificate": None, "upper_certificate": None,
                 entry["direction"] + "_certificate": rel, entry["direction"]: entry["bound"]}]
    if args.case and set(args.case) - {r["id"] for r in rows}:
        ap.error("unknown configuration ID")
    reports = []
    for row in rows:
        if args.case and row["id"] not in args.case:
            continue
        for direction in ["lower", "upper"]:
            if args.direction not in [direction, "all"]:
                continue
            rel = row[direction + "_certificate"]
            if rel is None:
                continue
            path = ROOT / rel
            print(f"Checking {row['id']} {direction}", file=sys.stderr, flush=True)
            result = {
                "configuration": row["id"],
                "direction": direction,
                "certificate": rel,
                "expected_bound": row[direction],
            }
            try:
                result["sha256"] = sha256(path)
                if path.suffix == ".xz":
                    entry = packages[rel]
                    if entry["direction"] != direction or entry["bound"] != row[direction]:
                        raise ValueError("scoreboard and packaging metadata disagree")
                    with materialize(ROOT, entry) as expanded:
                        result.update(invoke(args.lower_python if direction == "lower" else args.upper_python,
                                             direction, expanded, args.timeout))
                    result["members"] = entry["members"]
                elif direction == "lower":
                    result.update(
                        invoke(args.lower_python, direction, path, args.timeout)
                    )
                else:
                    receipt = receipts[row["id"]]
                    if result["sha256"] != receipt["archive_sha256"]:
                        raise ValueError("archive hash differs from recorded evidence")
                    with tempfile.TemporaryDirectory(prefix="sp-upper-") as temp:
                        dest = Path(temp)
                        with zipfile.ZipFile(path) as archive:
                            if (
                                len(archive.namelist()) != 5
                                or set(archive.namelist()) != FILES
                            ):
                                raise ValueError(
                                    "expected exactly the five canonical root files"
                                )
                            for name in sorted(FILES):
                                member = receipt["members"][name]
                                if archive.getinfo(name).file_size != member["bytes"]:
                                    raise ValueError(
                                        "expanded size differs from manifest"
                                    )
                                archive.extract(name, dest)
                                if sha256(dest / name) != member["sha256"]:
                                    raise ValueError(
                                        "member hash differs from recorded evidence"
                                    )
                        result.update(
                            invoke(args.upper_python, direction, dest, args.timeout)
                        )
                result["accepted"] = (
                    result["exit_code"] == 0
                    and result["stdout"] == row[direction] + "\n"
                    and not result["stderr"]
                )
            except (OSError, ValueError, KeyError, EOFError, tarfile.TarError, zipfile.BadZipFile) as error:
                result.update(accepted=False, error=str(error))
            result["status"] = (
                "accepted"
                if result["accepted"]
                else "incomplete"
                if result.get("exit_code") is None and "error" not in result
                else "failed"
            )
            reports.append(result)
            if args.report:
                args.report.parent.mkdir(parents=True, exist_ok=True)
                args.report.write_text(json.dumps(reports, indent=2) + "\n")
    if not reports:
        ap.error("selection contains no certificates for this direction")
    if not args.report:
        print(json.dumps(reports, indent=2))
    return 0 if all(r["accepted"] for r in reports) else 1


if __name__ == "__main__":
    raise SystemExit(main())
