"""Check every XZ certificate against historical content hashes, without proof replay."""
import json
from pathlib import Path
import subprocess
import sys
import time

from certificate_io import check_evidence, packaging_entries, sha256, unpack_xz

ROOT = Path(__file__).resolve().parents[1]


def check():
    entries = packaging_entries(ROOT)
    expected = {
        row[key]
        for row in json.loads((ROOT / "scoreboard/results.json").read_text())
        for key in ("upper_certificate", "lower_certificate")
        if row[key]
    }
    expected.update(
        f"certificates/upper/lsp-recovered/{receipt.parent.name}.tar.xz"
        for receipt in (ROOT / "validation/lsp-recovered").glob("*/verification.json")
    )
    paths = [entry["path"] for entry in entries]
    if len(paths) != len(set(paths)) or set(paths) != expected:
        raise ValueError("packaging manifest must cover every published certificate exactly once")
    sources = json.loads((ROOT / "validation/verifier-sources.json").read_text())
    for name, digest in sources.items():
        if sha256(ROOT / name) != digest:
            raise ValueError("mathematical verifier source differs: " + name)
    results = []
    for entry in entries:
        print("Checking " + entry["path"], file=sys.stderr, flush=True)
        start = time.monotonic()
        check_evidence(ROOT, entry)
        unpack_xz(ROOT / entry["path"], entry)
        listing = subprocess.run(
            ["xz", "--robot", "-lvv", "--", str(ROOT / entry["path"])],
            check=True, capture_output=True, text=True,
        )
        results.append(dict(path=entry["path"], archive_sha256=entry["archive_sha256"],
                            all_historical_member_hashes_match=True,
                            decoder_limit_bytes=512 * 1024**2,
                            seconds=round(time.monotonic() - start, 3),
                            xz_listing=listing.stdout))
    return dict(mathematical_verifier_sources_unchanged=True, certificates=results)


if __name__ == "__main__":
    print(json.dumps(check(), indent=2))
