"""Run or check one s=2 experiment; save a folder that plot.py can read."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]


def read_json(path):
    return json.loads(path.read_text())


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def model_size(log):
    # The first CBC model is the primary LP; the second minimizes average cost.
    match = re.search(
        r"Problem MODEL has (\d+) rows, (\d+) columns and (\d+) elements", log
    )
    return (
        dict(
            zip(("rows", "columns", "elements"), map(int, match.groups()), strict=False)
        )
        if match
        else None
    )


def load_case(directory):
    mechanism_path = directory / "mechanism.json"
    mechanism = read_json(mechanism_path)[0]
    check = read_json(directory / "check.json")
    run = read_json(directory / "run.json")
    if mechanism.get("status") != "complete" or check.get("status") != "complete":
        raise ValueError(f"Incomplete experiment: {directory}")
    if mechanism["provenance"]["settings"]["s"] != 2:
        raise ValueError(f"Expected s=2: {directory}")
    if check["mechanism"]["sha256"] != sha256(mechanism_path):
        raise ValueError(f"Mechanism/check hash mismatch: {directory}")
    if check.get("lsp_counterexample") is not None:
        raise ValueError(f"LSP counterexample found: {directory}")
    for name, expected in run.get("artifact_sha256", {}).items():
        if sha256(directory / name) != expected:
            raise ValueError(f"Artifact hash mismatch: {directory / name}")
    interval = check["binsearch_apx"]
    if not 1 <= interval["low"] <= interval["high"]:
        raise ValueError(f"Invalid approximation interval: {directory}")
    return mechanism, check, run


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--vertices", type=int, help="Solve and then check this cycle size"
    )
    mode.add_argument("--check-only", type=Path, help="Check an existing mechanism")
    parser.add_argument(
        "--output", type=Path, required=True, help="New output directory"
    )
    parser.add_argument(
        "--mem-limit",
        type=float,
        help="Search cache heuristic in GB; not a process RAM limit",
    )
    args = parser.parse_args()
    if args.vertices is not None and args.vertices < 2:
        parser.error("--vertices must be at least 2")
    if args.mem_limit is not None and args.mem_limit <= 0.15:
        parser.error("--mem-limit must exceed 0.15")
    if args.check_only and args.mem_limit is not None:
        parser.error("--mem-limit applies only to search")
    source = args.check_only.resolve() if args.check_only else None
    if source:
        meta = read_json(source)[0]
        if meta.get("status") != "complete" or meta["provenance"]["settings"]["s"] != 2:
            parser.error("--check-only requires a completed s=2 mechanism")
    out = args.output.resolve()
    # Never overwrite published results or a previous run, including partial runs.
    out.mkdir(parents=True, exist_ok=False)
    env = dict(os.environ, PYTHONHASHSEED="0", PYTHONUNBUFFERED="1")
    for name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
        env[name] = "1"
    recorded = {
        "schema_version": 1,
        "origin": "reproduction",
        "timing_note": "Wall-clock estimates; other processes may affect measurements.",
        "machine": {
            "platform": platform.platform(),
            "logical_cpus": os.cpu_count(),
            "processor": platform.processor(),
        },
        "phases": {},
    }
    cpuinfo = Path("/proc/cpuinfo")
    if cpuinfo.exists():
        match = re.search(r"model name\s*:\s*(.+)", cpuinfo.read_text())
        if match:
            recorded["machine"]["processor"] = match[1]

    def phase(name, command):
        print(f"{name}: {' '.join(command)}", flush=True)
        start = time.monotonic()
        with (
            (out / f"{name}.stdout.log").open("w") as stdout,
            (out / f"{name}.stderr.log").open("w") as stderr,
        ):
            result = subprocess.run(
                command, cwd=out, env=env, stdout=stdout, stderr=stderr
            )
        recorded["phases"][name] = {
            "wall_seconds": time.monotonic() - start,
            "exit_code": result.returncode,
            "command": command,
        }
        write_json(out / "run.json", recorded)
        if result.returncode:
            raise SystemExit(
                f"{name} failed (exit {result.returncode}); see {out / (name + '.stderr.log')}"
            )

    if source:
        shutil.copyfile(source, out / "mechanism.json")
        recorded["source_mechanism"] = str(source)
    else:
        archived = (
            ROOT / "experiments" / "s2" / f"c{args.vertices:03}" / "mechanism.json"
        )
        cache = (
            read_json(archived)[0]["provenance"]["settings"].get("mem_limit")
            if archived.exists()
            else 16
        )
        if args.mem_limit is not None:
            cache = args.mem_limit
        command = [
            sys.executable,
            str(ROOT / "main.py"),
            "solve-lsp-mechanism",
            str(args.vertices),
            "--s",
            "2",
            "--enforce-lsp",
            "--no-enforce-sp",
            "--warm-start",
            "--no-local-lsp-apx-constraints",
            "--minimize-avg-cost",
            "--no-minimize-dis-from-pcd",
            "--no-keep-files",
            "--save-path",
            "mechanism.json",
        ]
        if cache is not None:
            command += ["--mem-limit", str(cache)]
        phase("search", command)
        recorded["primary_model"] = model_size((out / "search.stdout.log").read_text())
    phase(
        "check",
        [
            sys.executable,
            str(ROOT / "main.py"),
            "check-lsp-mechanism",
            "mechanism.json",
            "--check-lsp",
            "--no-check-sp",
            "--no-check-anonymity",
            "--calc-apx",
            "--min-scale",
            "7",
            "--max-scale",
            "8",
            "--binsearch-apx",
            "0.00001",
            "--track-time",
            "--save-results",
            "check.json",
        ],
    )
    recorded["artifact_sha256"] = {
        name: sha256(out / name) for name in ("mechanism.json", "check.json")
    }
    write_json(out / "run.json", recorded)
    mechanism, check, _ = load_case(out)
    print(f"C{mechanism['v']}: {check['binsearch_apx']}; saved to {out}")


if __name__ == "__main__":
    main()
