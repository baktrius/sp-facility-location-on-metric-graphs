"""Checked transport for certificates; mathematical verifier code stays unchanged."""

import contextlib
import hashlib
import json
import subprocess
import tarfile
import tempfile
from pathlib import Path

FILES = {"manifest.json", "vertices.jsonl", "attribution.jsonl", "sp.jsonl", "approximation.jsonl"}


def sha256(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def copy_checked(source, target, expected):
    digest = hashlib.sha256()
    count = 0
    while chunk := source.read(1024 * 1024):
        count += len(chunk)
        if count > expected["bytes"]:
            raise ValueError("expanded size exceeds recorded size")
        digest.update(chunk)
        if target is not None:
            target.write(chunk)
    if count != expected["bytes"] or digest.hexdigest() != expected["sha256"]:
        raise ValueError("certificate member differs from recorded evidence")


def unpack_xz(path, entry, destination=None):
    """Stream-check every member, optionally extracting into an empty directory.

    The external decoder enforces a 512 MiB limit and one thread. Only canonical
    regular files are accepted; no archive-supplied paths or links are extracted.
    """
    if sha256(path) != entry["archive_sha256"]:
        raise ValueError("archive hash differs from packaging manifest")
    members = entry["members"]
    if entry["direction"] == "upper" and set(members) != FILES:
        raise ValueError("expected exactly the five canonical files")
    if entry["direction"] == "lower" and len(members) != 1:
        raise ValueError("expected one lower JSON file")
    with tempfile.TemporaryFile() as errors:
        proc = subprocess.Popen(
            ["xz", "-T1", "--memlimit-decompress=512MiB", "-dc", "--", str(path)],
            stdout=subprocess.PIPE, stderr=errors,
        )
        try:
            if entry["direction"] == "upper":
                seen = set()
                with tarfile.open(fileobj=proc.stdout, mode="r|") as archive:
                    for member in archive:
                        name = member.name
                        if name not in FILES or name in seen or not member.isfile() or member.issparse():
                            raise ValueError("unexpected, duplicate or non-regular tar member")
                        if member.size != members[name]["bytes"]:
                            raise ValueError("tar member size differs from recorded evidence")
                        seen.add(name)
                        with archive.extractfile(member) as source:
                            with contextlib.ExitStack() as stack:
                                target = stack.enter_context((destination / name).open("xb")) if destination else None
                                copy_checked(source, target, members[name])
                    if seen != FILES:
                        raise ValueError("missing canonical tar member")
            else:
                name, expected = next(iter(members.items()))
                if Path(name).name != name or name in (".", ".."):
                    raise ValueError("invalid lower filename")
                with contextlib.ExitStack() as stack:
                    target = stack.enter_context((destination / name).open("xb")) if destination else None
                    copy_checked(proc.stdout, target, expected)
            # Drain through the XZ footer so truncation/checksum errors cannot pass.
            while proc.stdout.read(1024 * 1024):
                pass
            if proc.wait() != 0:
                errors.seek(0)
                raise ValueError("XZ decoding failed: " + errors.read().decode(errors="replace"))
        finally:
            proc.stdout.close()
            if proc.poll() is None:
                proc.kill()
            proc.wait()


def packaging_entries(root):
    return json.loads((root / "certificates/packaging.json").read_text())["entries"]


def check_evidence(root, entry):
    """Bind the new transport manifest to unchanged historical input hashes."""
    if entry["collection"] == "graph-upper":
        receipts = json.loads((root / "validation/recorded-upper-acceptances.json").read_text())
        receipt = next(r for r in receipts if r["configuration"] == entry["configuration"])
        if entry["members"] != receipt["members"] or entry["source_archive_sha256"] != receipt["archive_sha256"] or entry["bound"] != receipt["bound"]:
            raise ValueError("packaging metadata differs from historical upper evidence")
    elif entry["collection"] == "recovered-upper":
        receipt = json.loads((root / "validation/lsp-recovered" / entry["configuration"] / "verification.json").read_text())
        if {n: m["sha256"] for n, m in entry["members"].items()} != receipt["bundle_sha256"] or entry["bound"] != receipt["factor"]:
            raise ValueError("packaging metadata differs from recovered evidence")
    elif entry["collection"] == "graph-lower":
        receipts = json.loads((root / "validation/recorded-lower-acceptances.json").read_text())
        receipt = next(r for r in receipts if r["configuration"] == entry["configuration"])
        if next(iter(entry["members"].values()))["sha256"] != receipt["included_input_sha256"] or entry["bound"] != receipt["bound"]:
            raise ValueError("packaging metadata differs from lower evidence")
    else:
        raise ValueError("unknown certificate collection")


@contextlib.contextmanager
def materialize(root, entry):
    check_evidence(root, entry)
    with tempfile.TemporaryDirectory(prefix="sp-xz-") as temp:
        dest = Path(temp)
        unpack_xz(root / entry["path"], entry, dest)
        yield dest if entry["direction"] == "upper" else dest / next(iter(entry["members"]))
